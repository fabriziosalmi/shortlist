import os
import json
import subprocess
import uuid
import logging
from datetime import datetime
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from github import Github
import tempfile
import shutil

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
MAINTAINER_API_TOKEN = os.getenv("MAINTAINER_API_TOKEN")
CONTRIBUTOR_API_TOKEN = os.getenv("CONTRIBUTOR_API_TOKEN")
GIT_AUTH_TOKEN = os.getenv("GIT_AUTH_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO", "owner/repo")  # Format: "owner/repo"

app = FastAPI(title="Shortlist Governance API", version="1.0.0")

# Request models
class ShortlistUpdate(BaseModel):
    items: list[str]

class ShortlistProposal(BaseModel):
    items: list[str]
    description: str = "Proposed shortlist update"

# Authentication dependencies
def verify_maintainer_token(authorization: str = Header(...)):
    if not MAINTAINER_API_TOKEN:
        raise HTTPException(status_code=503, detail="Maintainer authentication not configured")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header format")

    token = authorization.replace("Bearer ", "")
    if token != MAINTAINER_API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid maintainer token")

    return token

def verify_contributor_token(authorization: str = Header(...)):
    if not CONTRIBUTOR_API_TOKEN:
        raise HTTPException(status_code=503, detail="Contributor authentication not configured")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header format")

    token = authorization.replace("Bearer ", "")
    if token != CONTRIBUTOR_API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid contributor token")

    return token

# Git operations helper
class GitManager:
    def __init__(self):
        if not GIT_AUTH_TOKEN:
            raise ValueError("GIT_AUTH_TOKEN environment variable is required")
        if not GITHUB_REPO:
            raise ValueError("GITHUB_REPO environment variable is required")

        self.github = Github(GIT_AUTH_TOKEN)
        self.repo = self.github.get_repo(GITHUB_REPO)
        self.repo_url = f"https://{GIT_AUTH_TOKEN}@github.com/{GITHUB_REPO}.git"

    def clone_repo(self, temp_dir: str) -> str:
        """Clone the repository to a temporary directory"""
        repo_path = os.path.join(temp_dir, "repo")

        try:
            subprocess.run([
                "git", "clone", self.repo_url, repo_path
            ], check=True, capture_output=True, text=True)

            # Configure git user
            subprocess.run([
                "git", "config", "user.email", "bot@shortlist.io"
            ], cwd=repo_path, check=True)

            subprocess.run([
                "git", "config", "user.name", "Shortlist Bot"
            ], cwd=repo_path, check=True)

            return repo_path
        except subprocess.CalledProcessError as e:
            logger.error(f"Git clone failed: {e.stderr}")
            raise HTTPException(status_code=500, detail=f"Failed to clone repository: {e.stderr}")

    def create_branch_and_commit(self, repo_path: str, branch_name: str,
                                shortlist_content: Dict[str, Any], commit_message: str):
        """Create a new branch, update shortlist.json, and commit"""
        try:
            # Create and checkout new branch
            subprocess.run([
                "git", "checkout", "-b", branch_name
            ], cwd=repo_path, check=True)

            # Update shortlist.json
            shortlist_path = os.path.join(repo_path, "shortlist.json")
            with open(shortlist_path, 'w') as f:
                json.dump(shortlist_content, f, indent=2)

            # Add and commit changes
            subprocess.run([
                "git", "add", "shortlist.json"
            ], cwd=repo_path, check=True)

            subprocess.run([
                "git", "commit", "-m", commit_message
            ], cwd=repo_path, check=True)

            # Push branch
            subprocess.run([
                "git", "push", "origin", branch_name
            ], cwd=repo_path, check=True)

        except subprocess.CalledProcessError as e:
            logger.error(f"Git operations failed: {e.stderr}")
            raise HTTPException(status_code=500, detail=f"Git operations failed: {e.stderr}")

    def create_pull_request(self, branch_name: str, title: str, body: str):
        """Create a pull request from the branch to main"""
        try:
            pr = self.repo.create_pull(
                title=title,
                body=body,
                head=branch_name,
                base="main"
            )
            return pr
        except Exception as e:
            logger.error(f"Failed to create PR: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to create pull request: {str(e)}")

    def approve_and_merge_pr(self, pr):
        """Approve and merge the pull request"""
        try:
            # Create a review with approval
            pr.create_review(event="APPROVE", body="Auto-approved by maintainer API")

            # Merge the PR
            merge_result = pr.merge(
                commit_title=f"Merge PR #{pr.number}: {pr.title}",
                commit_message="Merged via Shortlist Governance API",
                merge_method="squash"
            )

            return merge_result
        except Exception as e:
            logger.error(f"Failed to approve/merge PR: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to approve/merge PR: {str(e)}")

# Initialize Git manager
git_manager = None
try:
    git_manager = GitManager()
    logger.info("GitHub integration initialized successfully")
except Exception as e:
    logger.warning(f"GitHub integration not available: {e}")
    logger.info("API will run in limited mode - status endpoints available")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "shortlist-governance-api"
    }

@app.post("/v1/admin/shortlist")
async def update_shortlist_admin(
    update: ShortlistUpdate,
    token: str = Depends(verify_maintainer_token)
):
    """
    Maintainer endpoint: Update shortlist with immediate merge
    Requires MAINTAINER_API_TOKEN
    """
    logger.info(f"Admin shortlist update requested with {len(update.items)} items")

    # Create temporary directory for git operations
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Clone repository
            repo_path = git_manager.clone_repo(temp_dir)

            # Create branch name with timestamp
            timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
            branch_name = f"update-from-api-{timestamp}"

            # Prepare shortlist content
            shortlist_content = {"items": update.items}
            commit_message = f"feat: Update shortlist via admin API\n\n🤖 Generated with Shortlist Governance API\nTimestamp: {datetime.utcnow().isoformat()}"

            # Create branch and commit
            git_manager.create_branch_and_commit(
                repo_path, branch_name, shortlist_content, commit_message
            )

            # Create pull request
            pr_title = f"Admin Update: Shortlist ({timestamp})"
            pr_body = f"""## Admin Shortlist Update

**Items:** {len(update.items)}
**Timestamp:** {datetime.utcnow().isoformat()}
**Updated via:** Shortlist Governance API (Admin)

### New Content:
{chr(10).join([f'- {item}' for item in update.items])}

🤖 This PR was automatically created and will be auto-merged by the Shortlist Governance API.
"""

            pr = git_manager.create_pull_request(branch_name, pr_title, pr_body)

            # Approve and merge immediately
            merge_result = git_manager.approve_and_merge_pr(pr)

            return {
                "status": "merged",
                "pull_request_url": pr.html_url,
                "merge_sha": merge_result.sha,
                "branch_name": branch_name,
                "items_count": len(update.items)
            }

        except Exception as e:
            logger.error(f"Admin update failed: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/proposals/shortlist")
async def propose_shortlist_update(
    proposal: ShortlistProposal,
    token: str = Depends(verify_contributor_token)
):
    """
    Contributor endpoint: Propose shortlist changes via Pull Request
    Requires CONTRIBUTOR_API_TOKEN
    """
    logger.info(f"Shortlist proposal requested with {len(proposal.items)} items")

    # Create temporary directory for git operations
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Clone repository
            repo_path = git_manager.clone_repo(temp_dir)

            # Create branch name with UUID
            proposal_id = str(uuid.uuid4())[:8]
            branch_name = f"proposal-{proposal_id}"

            # Prepare shortlist content
            shortlist_content = {"items": proposal.items}
            commit_message = f"feat: Propose shortlist update\n\n{proposal.description}\n\n🤖 Generated with Shortlist Governance API\nProposal ID: {proposal_id}"

            # Create branch and commit
            git_manager.create_branch_and_commit(
                repo_path, branch_name, shortlist_content, commit_message
            )

            # Create pull request (but don't merge)
            pr_title = f"Proposal: {proposal.description} ({proposal_id})"
            pr_body = f"""## Shortlist Update Proposal

**Description:** {proposal.description}
**Items:** {len(proposal.items)}
**Proposal ID:** {proposal_id}
**Timestamp:** {datetime.utcnow().isoformat()}
**Submitted via:** Shortlist Governance API (Contributor)

### Proposed Content:
{chr(10).join([f'- {item}' for item in proposal.items])}

### Review Required
This proposal requires review and approval by a maintainer before merging.

🤖 This PR was automatically created by the Shortlist Governance API.
"""

            pr = git_manager.create_pull_request(branch_name, pr_title, pr_body)

            return {
                "status": "proposal_created",
                "pull_request_url": pr.html_url,
                "proposal_id": proposal_id,
                "branch_name": branch_name,
                "items_count": len(proposal.items)
            }

        except Exception as e:
            logger.error(f"Proposal creation failed: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

@app.get("/v1/status")
async def get_system_status():
    """Get current system configuration status"""
    return {
        "maintainer_auth_configured": bool(MAINTAINER_API_TOKEN),
        "contributor_auth_configured": bool(CONTRIBUTOR_API_TOKEN),
        "git_auth_configured": bool(GIT_AUTH_TOKEN),
        "github_repo": GITHUB_REPO,
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)