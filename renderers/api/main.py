import os
import json
import subprocess
import uuid
from datetime import datetime
import uuid
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional, Literal
from fastapi.responses import FileResponse
from fastapi import FastAPI, HTTPException, Header, Depends, Request
from fastapi.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel
from typing import List
from github import Github
import tempfile
import shutil

from utils.logging_config import configure_logging
from utils.logging_utils import (
    ComponentLogger,
    RENDERER_CONTEXT,
    log_operation,
    log_execution_time
)

# Configure logging
configure_logging('api_renderer', log_level="INFO", log_file='/app/data/api.log')
logger = ComponentLogger('api_renderer')
logger.logger.add_context(**RENDERER_CONTEXT, renderer_type='api')

# Custom middleware for request logging
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        with log_operation(logger.logger, "http_request",
                          path=request.url.path,
                          method=request.method,
                          remote_addr=request.client.host if request.client else None):
            response = await call_next(request)
            logger.logger.info("Request completed",
                              status_code=response.status_code)
            return response

# Environment variables
MAINTAINER_API_TOKEN = os.getenv("MAINTAINER_API_TOKEN")
CONTRIBUTOR_API_TOKEN = os.getenv("CONTRIBUTOR_API_TOKEN")
GIT_AUTH_TOKEN = os.getenv("GIT_AUTH_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO", "owner/repo")  # Format: "owner/repo"

app = FastAPI(title="Shortlist Governance API", version="1.0.0")

# Secrets storage configuration
SECRETS_DIR = "/app/data/secrets"
SECRETS_FILE = os.path.join(SECRETS_DIR, "secrets.json")

os.makedirs(SECRETS_DIR, exist_ok=True)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Request models
class ShortlistUpdate(BaseModel):
    items: list[str]

class ShortlistProposal(BaseModel):
    items: list[str]
    description: str = "Proposed shortlist update"

class HistoryEntry(BaseModel):
    hash: str
    author: str
    date: str
    subject: str

class PreviewRequest(BaseModel):
    renderer_type: Literal["audio", "video"]
    content: Dict[str, Any]

class RevertRequest(BaseModel):
    commit_hash: str

class SecretUpsert(BaseModel):
    key: str
    value: str

class SecretDelete(BaseModel):
    key: str

# Authentication dependencies
@log_execution_time(logger.logger)
def verify_maintainer_token(authorization: str = Header(...)) -> str:
    """Verify maintainer authentication token.
    
    Args:
        authorization: Authorization header value
        
    Returns:
        Verified token
        
    Raises:
        HTTPException: If token is invalid or authentication is not configured
    """
    with log_operation(logger.logger, "verify_maintainer_token"):
        if not MAINTAINER_API_TOKEN:
            logger.logger.error("Maintainer authentication not configured")
            raise HTTPException(status_code=503, detail="Maintainer authentication not configured")

        if not authorization.startswith("Bearer "):
            logger.logger.warning("Invalid auth header format", auth_header=authorization)
            raise HTTPException(status_code=401, detail="Invalid authorization header format")

        token = authorization.replace("Bearer ", "")
        if token != MAINTAINER_API_TOKEN:
            logger.logger.warning("Invalid maintainer token")
            raise HTTPException(status_code=401, detail="Invalid maintainer token")

        return token

@log_execution_time(logger.logger)
def verify_contributor_token(authorization: str = Header(...)) -> str:
    """Verify contributor authentication token.
    
    Args:
        authorization: Authorization header value
        
    Returns:
        Verified token
        
    Raises:
        HTTPException: If token is invalid or authentication is not configured
    """
    with log_operation(logger.logger, "verify_contributor_token"):
        if not CONTRIBUTOR_API_TOKEN:
            logger.logger.error("Contributor authentication not configured")
            raise HTTPException(status_code=503, detail="Contributor authentication not configured")

        if not authorization.startswith("Bearer "):
            logger.logger.warning("Invalid auth header format", auth_header=authorization)
            raise HTTPException(status_code=401, detail="Invalid authorization header format")

        token = authorization.replace("Bearer ", "")
        if token != CONTRIBUTOR_API_TOKEN:
            logger.logger.warning("Invalid contributor token")
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
            logger.logger.error("Git clone failed",
                              error=e.stderr,
                              repo_url=self.repo_url.replace(GIT_AUTH_TOKEN, '***'))
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
            logger.logger.error("Git operations failed",
                              error=e.stderr,
                              branch_name=branch_name)
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
            logger.logger.error("Failed to create PR",
                              error=str(e),
                              branch_name=branch_name)
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
            logger.logger.error("Failed to approve/merge PR",
                              error=str(e),
                              pr_number=pr.number)
            raise HTTPException(status_code=500, detail=f"Failed to approve/merge PR: {str(e)}")

# Initialize Git manager
git_manager = None
try:
    git_manager = GitManager()
    logger.logger.info("GitHub integration initialized successfully",
                        repo=GITHUB_REPO)
except Exception as e:
    logger.logger.warning("GitHub integration not available",
                           error=str(e))
    logger.logger.info("API running in limited mode - status endpoints only")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    with log_operation(logger.logger, "health_check"):
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
    logger.logger.info("Admin shortlist update requested",
                       items_count=len(update.items))

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
            logger.logger.error("Admin update failed",
                              error=str(e),
                              error_type=type(e).__name__)
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
    logger.logger.info("Shortlist proposal requested",
                       items_count=len(proposal.items),
                       description=proposal.description)

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
            logger.logger.error("Proposal creation failed",
                              error=str(e),
                              error_type=type(e).__name__,
                              proposal_id=proposal_id)
            raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/admin/preview")
async def generate_preview(
    request: PreviewRequest,
    token: str = Depends(verify_maintainer_token)
):
    """Generate a preview of content using an isolated renderer instance."""
    allowed_renderers = {
        "audio": {
            "image": "shortlist-audio",
            "output_file": "shortlist_loop.mp3",
            "content_type": "audio/mpeg"
        },
        "video": {
            "image": "shortlist-video",
            "output_file": "shortlist_video.mp4",
            "content_type": "video/mp4"
        }
    }
    
    if request.renderer_type not in allowed_renderers:
        raise HTTPException(status_code=400, detail="Invalid renderer type")
        
    renderer_config = allowed_renderers[request.renderer_type]
    
    with log_operation(logger.logger, "generate_preview",
                     renderer_type=request.renderer_type):
        # Create temporary directories for input and output
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                temp_path = Path(temp_dir)
                input_dir = temp_path / "input"
                output_dir = temp_path / "output"
                input_dir.mkdir()
                output_dir.mkdir()
                
                # Write preview content to shortlist.json
                shortlist_path = input_dir / "shortlist.json"
                with shortlist_path.open('w') as f:
                    json.dump(request.content, f, indent=2)
                
                logger.logger.info("Starting preview generation",
                               input_file=str(shortlist_path),
                               renderer=renderer_config["image"])
                
                # Run renderer container
                container_cmd = [
                    "docker", "run", "--rm",
                    "-v", f"{input_dir}:/app/data:ro",
                    "-v", f"{output_dir}:/app/output",
                    renderer_config["image"]
                ]
                
                result = subprocess.run(
                    container_cmd,
                    check=True,
                    capture_output=True,
                    text=True
                )
                
                output_file = output_dir / renderer_config["output_file"]
                if not output_file.exists():
                    logger.logger.error("Renderer did not generate output file",
                                    output_path=str(output_file))
                    raise HTTPException(
                        status_code=500,
                        detail="Failed to generate preview"
                    )
                
                logger.logger.info("Preview generated successfully",
                               output_file=str(output_file))
                
                return FileResponse(
                    path=str(output_file),
                    media_type=renderer_config["content_type"],
                    filename=f"preview.{output_file.suffix[1:]}"
                )
                
            except subprocess.CalledProcessError as e:
                logger.logger.error("Preview generation failed",
                               error=e.stderr,
                               command=" ".join(e.cmd))
                raise HTTPException(
                    status_code=500,
                    detail=f"Preview generation failed: {e.stderr}"
                )
            except Exception as e:
                logger.logger.error("Preview generation failed",
                               error=str(e),
                               error_type=type(e).__name__)
                raise HTTPException(
                    status_code=500,
                    detail=str(e)
                )

@app.get("/v1/admin/history")
async def get_history(token: str = Depends(verify_maintainer_token)) -> List[HistoryEntry]:
    """Get git history for shortlist.json file."""
    with log_operation(logger.logger, "get_history"):
        try:
            # Use git log to get history of shortlist.json
            result = subprocess.run([
                "git", "log",
                "--pretty=format:{\"hash\": \"%H\", \"author\": \"%an\", \"date\": \"%ai\", \"subject\": \"%s\"}",
                "--no-merges",  # Exclude merge commits
                "-n", "30",    # Limit to 30 entries
                "--", "shortlist.json"
            ], check=True, capture_output=True, text=True)
            
            # Parse JSON lines into list
            history_lines = [line for line in result.stdout.split('\n') if line.strip()]
            history = []
            
            for line in history_lines:
                try:
                    entry = json.loads(line)
                    history.append(HistoryEntry(**entry))
                except Exception as e:
                    logger.logger.warning("Failed to parse history entry",
                                       error=str(e),
                                       line=line)
                    continue
            
            logger.logger.info("History retrieved successfully",
                             entries_count=len(history))
            return history
            
        except subprocess.CalledProcessError as e:
            logger.logger.error("Git history failed",
                             error=e.stderr,
                             command=" ".join(e.cmd))
            raise HTTPException(status_code=500, detail=f"Failed to get history: {e.stderr}")
        except Exception as e:
            logger.logger.error("History retrieval failed",
                             error=str(e),
                             error_type=type(e).__name__)
            raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/admin/revert")
async def revert_commit(request: RevertRequest, token: str = Depends(verify_maintainer_token)):
    """Revert a specific commit from the shortlist history."""
    with log_operation(logger.logger, "revert_commit",
                     commit_hash=request.commit_hash):
        try:
            # Validate commit exists and affects shortlist.json
            result = subprocess.run([
                "git", "log",
                "--format=%H",
                "--no-merges",
                "--", "shortlist.json"
            ], check=True, capture_output=True, text=True)
            
            valid_hashes = set(result.stdout.strip().split('\n'))
            if request.commit_hash not in valid_hashes:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid commit hash or commit does not affect shortlist.json"
                )
            
            # Create a new branch for the revert
            timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
            branch_name = f"revert-{timestamp}"
            
            # Create new branch
            subprocess.run(["git", "checkout", "-b", branch_name], check=True)
            
            try:
                # Revert the commit
                revert_result = subprocess.run(
                    ["git", "revert", "--no-edit", request.commit_hash],
                    check=True,
                    capture_output=True,
                    text=True
                )
                
                # Push branch
                subprocess.run(["git", "push", "origin", branch_name], check=True)
                
                # Create PR
                pr_title = f"Revert: {request.commit_hash[:8]} (via Control Room)"
                pr_body = f"""## Automatic Revert

This PR reverts commit {request.commit_hash} through the Control Room.

🔄 Generated by: Shortlist Governance API
⏰ Timestamp: {datetime.utcnow().isoformat()}
                """
                
                pr = git_manager.create_pull_request(branch_name, pr_title, pr_body)
                
                # Approve and merge immediately
                merge_result = git_manager.approve_and_merge_pr(pr)
                
                logger.logger.info("Revert successful",
                                commit_hash=request.commit_hash,
                                branch=branch_name,
                                pr_number=pr.number)
                
                return {
                    "status": "reverted",
                    "reverted_commit": request.commit_hash,
                    "revert_commit": merge_result.sha,
                    "pull_request_url": pr.html_url
                }
                
            finally:
                # Clean up: switch back to main branch
                subprocess.run(["git", "checkout", "main"], check=True)
            
        except subprocess.CalledProcessError as e:
            logger.logger.error("Git revert failed",
                             error=e.stderr,
                             command=" ".join(e.cmd))
            raise HTTPException(
                status_code=500,
                detail=f"Revert operation failed: {e.stderr}"
            )
            
        except Exception as e:
            logger.logger.error("Revert failed",
                             error=str(e),
                             error_type=type(e).__name__)
            raise HTTPException(status_code=500, detail=str(e))

def _read_secrets() -> Dict[str, str]:
    try:
        if not os.path.exists(SECRETS_FILE):
            return {}
        with open(SECRETS_FILE, 'r') as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            return {}
    except Exception as e:
        logger.logger.error("Failed to read secrets.json", error=str(e), error_type=type(e).__name__)
        return {}


def _write_secrets(data: Dict[str, str]) -> bool:
    try:
        os.makedirs(SECRETS_DIR, exist_ok=True)
        temp_path = SECRETS_FILE + ".tmp"
        with open(temp_path, 'w') as f:
            json.dump(data, f, indent=2)
        os.replace(temp_path, SECRETS_FILE)
        return True
    except Exception as e:
        logger.logger.error("Failed to write secrets.json", error=str(e), error_type=type(e).__name__)
        return False


@app.get("/v1/admin/secrets")
async def list_secrets(token: str = Depends(verify_maintainer_token)):
    """Return only the list of secret keys (no values)."""
    with log_operation(logger.logger, "list_secrets"):
        secrets = _read_secrets()
        return {"secrets": sorted(list(secrets.keys()))}


@app.post("/v1/admin/secrets")
async def upsert_secret(secret: SecretUpsert, token: str = Depends(verify_maintainer_token)):
    """Create or update a secret value by key."""
    with log_operation(logger.logger, "upsert_secret", key=secret.key):
        if not secret.key or secret.value is None:
            raise HTTPException(status_code=400, detail="key and value are required")
        secrets = _read_secrets()
        secrets[secret.key] = secret.value
        if not _write_secrets(secrets):
            raise HTTPException(status_code=500, detail="Failed to persist secret")
        return {"status": "ok", "message": f"Secret {secret.key} stored"}


@app.delete("/v1/admin/secrets")
async def delete_secret(payload: SecretDelete, token: str = Depends(verify_maintainer_token)):
    """Delete a secret by key."""
    with log_operation(logger.logger, "delete_secret", key=payload.key):
        secrets = _read_secrets()
        if payload.key in secrets:
            del secrets[payload.key]
            if not _write_secrets(secrets):
                raise HTTPException(status_code=500, detail="Failed to persist secrets after delete")
        return {"status": "ok", "message": f"Secret {payload.key} deleted (if existed)"}


@app.get("/v1/status")
async def get_system_status():
    """Get current system configuration status"""
    with log_operation(logger.logger, "get_system_status"):
        return {
        "maintainer_auth_configured": bool(MAINTAINER_API_TOKEN),
        "contributor_auth_configured": bool(CONTRIBUTOR_API_TOKEN),
        "git_auth_configured": bool(GIT_AUTH_TOKEN),
        "github_repo": GITHUB_REPO,
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    logger.log_startup(
        service="Shortlist Governance API",
        host="0.0.0.0",
        port=8000
    )
    uvicorn.run(app, host="0.0.0.0", port=8000)
    logger.log_shutdown()
