"""
Regional coordination system for geographic task distribution.
Handles cross-region task assignment, coordination, and failover.
"""

import json
import os
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, asdict

from .logging_utils import ComponentLogger
from .geographic import GeographicManager, get_geographic_manager, OperationMetadata, ConsistencyLevel
from .conflict_resolver import ConflictResolver, ConflictedVersion
from .git_manager import GitManager


@dataclass
class RegionalTaskAssignment:
    """Enhanced task assignment with regional context."""
    task_id: str
    node_id: str
    region: str
    assigned_at: str
    lease_expires_at: str
    cross_region_priority: int = 5
    regional_metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.regional_metadata is None:
            self.regional_metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RegionalTaskAssignment':
        """Create from dictionary."""
        return cls(**data)

    def is_expired(self) -> bool:
        """Check if the task assignment lease has expired."""
        try:
            expiry = datetime.fromisoformat(self.lease_expires_at.replace('Z', '+00:00'))
            return datetime.now(timezone.utc) > expiry
        except (ValueError, AttributeError):
            return True

    def is_cross_region_conflict(self, other: 'RegionalTaskAssignment') -> bool:
        """Check if this assignment conflicts with another from a different region."""
        return (self.task_id == other.task_id and
                self.region != other.region and
                not self.is_expired() and
                not other.is_expired())


class RegionalCoordinator:
    """Coordinates task assignment and execution across multiple regions."""

    def __init__(self, git_manager: GitManager):
        from .logging_config import get_logger
        self.logger = get_logger("regional_coordinator")
        self.git_manager = git_manager
        self.geo_manager = get_geographic_manager()
        self.conflict_resolver = ConflictResolver()

        self.logger.info("Regional coordinator initialized",
            current_region=self.geo_manager.current_region,
            sharding_enabled=self.geo_manager.is_sharding_enabled()
        )

    def get_regional_assignments(self) -> Dict[str, RegionalTaskAssignment]:
        """Get current task assignments with regional context."""
        try:
            assignments_data = self.git_manager.read_json_file("assignments.json")
            regional_assignments = {}

            for task_id, assignment_data in assignments_data.get('assignments', {}).items():
                if isinstance(assignment_data, dict):
                    # Convert legacy assignments to regional format
                    if 'region' not in assignment_data:
                        assignment_data['region'] = self.geo_manager.current_region

                    # Ensure all required fields are present
                    assignment_data.setdefault('cross_region_priority', 5)
                    assignment_data.setdefault('regional_metadata', {})

                    regional_assignment = RegionalTaskAssignment(
                        task_id=task_id,
                        node_id=assignment_data.get('node_id', ''),
                        region=assignment_data.get('region', self.geo_manager.current_region),
                        assigned_at=assignment_data.get('assigned_at', ''),
                        lease_expires_at=assignment_data.get('lease_expires_at', ''),
                        cross_region_priority=assignment_data.get('cross_region_priority', 5),
                        regional_metadata=assignment_data.get('regional_metadata', {})
                    )
                    regional_assignments[task_id] = regional_assignment

            return regional_assignments

        except Exception as e:
            self.logger.error("Failed to get regional assignments", {'error': str(e)})
            return {}

    def can_claim_task(self, task_config: Dict[str, Any], node_id: str) -> Tuple[bool, str]:
        """
        Check if current node can claim a task, considering regional constraints.

        Returns:
            (can_claim, reason)
        """
        task_id = task_config.get('id', '')

        # Check basic regional eligibility
        if not self.geo_manager.can_execute_task(task_config):
            return False, f"Task {task_id} not eligible for region {self.geo_manager.current_region}"

        # Check current assignments
        assignments = self.get_regional_assignments()
        current_assignment = assignments.get(task_id)

        if current_assignment:
            # Task is currently assigned
            if not current_assignment.is_expired():
                if current_assignment.region == self.geo_manager.current_region:
                    return False, f"Task {task_id} already assigned to node {current_assignment.node_id} in same region"
                else:
                    # Cross-region conflict detection
                    if self.geo_manager.should_coordinate_globally('schedule_changes'):
                        return False, f"Task {task_id} assigned in different region {current_assignment.region}, global coordination required"

        # Check role requirements (if roles system is available)
        try:
            from .roles import get_role_manager
            role_manager = get_role_manager()
            if not role_manager.can_execute_task(task_config):
                return False, f"Node role insufficient for task {task_id}"
        except ImportError:
            # Roles system not available, continue
            pass

        return True, "Task can be claimed"

    def claim_task(self, task_config: Dict[str, Any], node_id: str, lease_duration: timedelta) -> bool:
        """
        Claim a task with regional coordination.

        Returns:
            True if task was successfully claimed
        """
        task_id = task_config.get('id', '')

        # Pre-check eligibility
        can_claim, reason = self.can_claim_task(task_config, node_id)
        if not can_claim:
            self.logger.debug("Cannot claim task", {
                'task_id': task_id,
                'reason': reason
            })
            return False

        try:
            # Create regional assignment
            now = datetime.now(timezone.utc)
            lease_expires = now + lease_duration

            regional_assignment = RegionalTaskAssignment(
                task_id=task_id,
                node_id=node_id,
                region=self.geo_manager.current_region,
                assigned_at=now.isoformat(),
                lease_expires_at=lease_expires.isoformat(),
                cross_region_priority=task_config.get('priority', 5),
                regional_metadata={
                    'node_hostname': os.getenv('HOSTNAME', 'unknown'),
                    'assignment_method': 'regional_coordinator',
                    'geo_version': '1.0'
                }
            )

            # Atomic assignment with conflict detection
            success = self._atomic_task_assignment(regional_assignment)

            if success:
                self.logger.info("Task claimed successfully", {
                    'task_id': task_id,
                    'node_id': node_id,
                    'region': self.geo_manager.current_region,
                    'lease_expires': lease_expires.isoformat()
                })
            else:
                self.logger.warning("Failed to claim task atomically", {
                    'task_id': task_id,
                    'node_id': node_id
                })

            return success

        except Exception as e:
            self.logger.error("Error claiming task", {
                'task_id': task_id,
                'node_id': node_id,
                'error': str(e)
            })
            return False

    def _atomic_task_assignment(self, assignment: RegionalTaskAssignment) -> bool:
        """
        Atomically assign a task using Git's consistency guarantees.

        Returns:
            True if assignment was successful
        """
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Read current state
                assignments_data = self.git_manager.read_json_file("assignments.json")
                current_assignments = assignments_data.get('assignments', {})

                # Check for conflicts
                existing = current_assignments.get(assignment.task_id)
                if existing and isinstance(existing, dict):
                    existing_assignment = RegionalTaskAssignment.from_dict({
                        'task_id': assignment.task_id,
                        **existing
                    })

                    if not existing_assignment.is_expired():
                        # Task still assigned to someone else
                        if existing_assignment.region != assignment.region:
                            # Cross-region conflict
                            self.logger.warning("Cross-region assignment conflict detected", {
                                'task_id': assignment.task_id,
                                'existing_region': existing_assignment.region,
                                'new_region': assignment.region
                            })
                            return False

                        if existing_assignment.node_id != assignment.node_id:
                            # Different node in same region
                            return False

                # Create updated assignments
                updated_assignments = current_assignments.copy()
                updated_assignments[assignment.task_id] = assignment.to_dict()

                # Add regional metadata to the file
                updated_data = assignments_data.copy()
                updated_data['assignments'] = updated_assignments

                if self.geo_manager.is_sharding_enabled():
                    updated_data = self.geo_manager.add_regional_context(updated_data)

                # Atomic write with Git
                operation_id = str(uuid.uuid4())
                commit_msg = f"Claim task {assignment.task_id} by {assignment.node_id} in {assignment.region}"

                if self.git_manager.write_json_file("assignments.json", updated_data, commit_msg):
                    return True

            except Exception as e:
                self.logger.warning(f"Assignment attempt {attempt + 1} failed", {
                    'task_id': assignment.task_id,
                    'error': str(e)
                })

                if attempt < max_retries - 1:
                    # Exponential backoff
                    time.sleep(2 ** attempt)

        return False

    def release_task(self, task_id: str, node_id: str) -> bool:
        """Release a task assignment."""
        try:
            assignments_data = self.git_manager.read_json_file("assignments.json")
            assignments = assignments_data.get('assignments', {})

            if task_id not in assignments:
                return True  # Already released

            assignment_data = assignments[task_id]
            if isinstance(assignment_data, dict):
                # Verify ownership
                if assignment_data.get('node_id') != node_id:
                    self.logger.warning("Attempted to release task owned by different node", {
                        'task_id': task_id,
                        'requesting_node': node_id,
                        'owning_node': assignment_data.get('node_id')
                    })
                    return False

                # Remove assignment
                del assignments[task_id]
                updated_data = assignments_data.copy()
                updated_data['assignments'] = assignments

                commit_msg = f"Release task {task_id} by {node_id} in {self.geo_manager.current_region}"

                success = self.git_manager.write_json_file("assignments.json", updated_data, commit_msg)

                if success:
                    self.logger.info("Task released successfully", {
                        'task_id': task_id,
                        'node_id': node_id,
                        'region': self.geo_manager.current_region
                    })

                return success

        except Exception as e:
            self.logger.error("Error releasing task", {
                'task_id': task_id,
                'node_id': node_id,
                'error': str(e)
            })

        return False

    def detect_cross_region_conflicts(self) -> List[Dict[str, Any]]:
        """Detect and report cross-region task assignment conflicts."""
        conflicts = []

        try:
            assignments = self.get_regional_assignments()
            task_regions = {}

            # Group assignments by task
            for task_id, assignment in assignments.items():
                if not assignment.is_expired():
                    if task_id not in task_regions:
                        task_regions[task_id] = []
                    task_regions[task_id].append(assignment)

            # Check for cross-region conflicts
            for task_id, task_assignments in task_regions.items():
                if len(task_assignments) > 1:
                    regions = set(a.region for a in task_assignments)
                    if len(regions) > 1:
                        conflicts.append({
                            'task_id': task_id,
                            'conflicted_regions': list(regions),
                            'assignments': [a.to_dict() for a in task_assignments],
                            'detected_at': datetime.now(timezone.utc).isoformat()
                        })

        except Exception as e:
            self.logger.error("Error detecting cross-region conflicts", {'error': str(e)})

        if conflicts:
            self.logger.warning("Cross-region conflicts detected", {
                'conflict_count': len(conflicts),
                'conflicted_tasks': [c['task_id'] for c in conflicts]
            })

        return conflicts

    def resolve_cross_region_conflicts(self, conflicts: List[Dict[str, Any]]) -> int:
        """
        Resolve cross-region conflicts using configured strategies.

        Returns:
            Number of conflicts resolved
        """
        resolved_count = 0

        for conflict in conflicts:
            try:
                task_id = conflict['task_id']
                assignments_data = conflict['assignments']

                # Create ConflictedVersion objects
                versions = []
                for assignment_data in assignments_data:
                    # Create fake metadata for conflict resolution
                    fake_metadata = OperationMetadata(
                        operation_id=str(uuid.uuid4()),
                        region=assignment_data['region'],
                        timestamp=assignment_data['assigned_at'],
                        vector_clock=self.geo_manager.vector_clock,
                        consistency_level=ConsistencyLevel.REGIONAL,
                        conflict_resolution=self.geo_manager.get_consistency_policy('schedule_changes').get('conflict_resolution', 'region_priority')
                    )

                    versions.append(ConflictedVersion.create(
                        region=assignment_data['region'],
                        data=assignment_data,
                        metadata=fake_metadata
                    ))

                # Resolve the conflict
                resolution = self.conflict_resolver.resolve_conflict(
                    versions=versions,
                    operation_type='schedule_changes',
                    resolution_strategy=self.conflict_resolver.ConflictResolution.REGION_PRIORITY
                )

                # Apply the resolution
                if self._apply_conflict_resolution(task_id, resolution):
                    resolved_count += 1
                    self.logger.info("Cross-region conflict resolved", {
                        'task_id': task_id,
                        'strategy': resolution.resolution_strategy,
                        'winning_region': resolution.resolution_metadata.get('winning_region')
                    })

            except Exception as e:
                self.logger.error("Error resolving cross-region conflict", {
                    'task_id': conflict.get('task_id', 'unknown'),
                    'error': str(e)
                })

        return resolved_count

    def _apply_conflict_resolution(self, task_id: str, resolution: Any) -> bool:
        """Apply the result of conflict resolution to the assignments."""
        try:
            winning_assignment = resolution.resolved_data

            assignments_data = self.git_manager.read_json_file("assignments.json")
            assignments = assignments_data.get('assignments', {})

            # Update with winning assignment
            assignments[task_id] = winning_assignment

            updated_data = assignments_data.copy()
            updated_data['assignments'] = assignments

            commit_msg = f"Resolve cross-region conflict for {task_id} using {resolution.resolution_strategy}"

            return self.git_manager.write_json_file("assignments.json", updated_data, commit_msg)

        except Exception as e:
            self.logger.error("Error applying conflict resolution", {
                'task_id': task_id,
                'error': str(e)
            })
            return False

    def get_regional_statistics(self) -> Dict[str, Any]:
        """Get statistics about regional task distribution."""
        try:
            assignments = self.get_regional_assignments()
            active_assignments = {k: v for k, v in assignments.items() if not v.is_expired()}

            stats = {
                'total_assignments': len(assignments),
                'active_assignments': len(active_assignments),
                'current_region': self.geo_manager.current_region,
                'assignments_by_region': {},
                'cross_region_conflicts': len(self.detect_cross_region_conflicts()),
                'sharding_enabled': self.geo_manager.is_sharding_enabled()
            }

            # Count assignments by region
            for assignment in active_assignments.values():
                region = assignment.region
                if region not in stats['assignments_by_region']:
                    stats['assignments_by_region'][region] = 0
                stats['assignments_by_region'][region] += 1

            return stats

        except Exception as e:
            self.logger.error("Error getting regional statistics", {'error': str(e)})
            return {'error': str(e)}