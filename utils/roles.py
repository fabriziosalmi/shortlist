"""
Role management for Shortlist nodes.

This module handles role-based task assignment and validation.
"""

from typing import List, Set, Dict, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

# Default role for backward compatibility
# Complete set of available roles
AVAILABLE_ROLES = {
    "system",   # Core system tasks (governor, healer)
    "media",    # Audio/video processing
    "web",      # Web interfaces
    "broadcaster" # Social media integration
}

# Default roles for backward compatibility
DEFAULT_ROLES = AVAILABLE_ROLES.copy()

def validate_roles(roles: Set[str]) -> Set[str]:
    """Validate a set of roles against available roles.
    
    Args:
        roles: Set of roles to validate
    
    Returns:
        Validated set of roles
    
    Raises:
        ValueError: If any role is invalid
    """
    invalid_roles = roles - AVAILABLE_ROLES
    if invalid_roles:
        raise ValueError(f"Invalid roles: {invalid_roles}")
    return roles

@dataclass
class NodeRoles:
    """Manages node roles and role-based task assignment."""
    
    roles: Set[str]
    
    @classmethod
    def from_string(cls, roles_str: Optional[str] = None) -> 'NodeRoles':
        """Create NodeRoles from a comma-separated string.
        
        Args:
            roles_str: Optional comma-separated list of roles
                      (e.g., "system,media,web")
        
        Returns:
            NodeRoles instance with parsed roles
        """
        if not roles_str:
            # Default to all roles for backward compatibility
            return cls(DEFAULT_ROLES)
        
        roles = {
            role.strip().lower()
            for role in roles_str.split(',')
            if role.strip()
        }
        
        return cls(roles)
    
    def can_handle_task(self, task: Dict[str, Any]) -> bool:
        """Check if this node can handle a given task based on roles.
        
        Args:
            task: Task definition from schedule.json
        
        Returns:
            True if the node can handle this task
        """
        required_role = task.get('required_role')
        
        # If no role is required, any node can handle it
        if not required_role:
            return True
        
        # Check if we have the required role
        has_role = required_role.lower() in self.roles
        
        if not has_role:
            logger.debug("Task requires role %s, node has roles %s",
                       required_role, self.roles)
        
        return has_role
    
    def __str__(self) -> str:
        """String representation of roles."""
        return f"NodeRoles({','.join(sorted(self.roles))})"