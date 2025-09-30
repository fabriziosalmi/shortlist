"""
Conflict resolution system for geographic distribution.
Handles merging and conflict resolution for cross-region operations.
"""

import json
import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum

from .logging_utils import ComponentLogger
from .geographic import ConflictResolution, OperationMetadata, VectorClock


@dataclass
class ConflictedVersion:
    """Represents a conflicted version of data from a specific region."""
    region: str
    timestamp: str
    data: Any
    metadata: OperationMetadata
    content_hash: str

    @classmethod
    def create(cls, region: str, data: Any, metadata: OperationMetadata) -> 'ConflictedVersion':
        """Create a conflicted version with computed hash."""
        content_str = json.dumps(data, sort_keys=True) if isinstance(data, dict) else str(data)
        content_hash = hashlib.sha256(content_str.encode()).hexdigest()[:16]

        return cls(
            region=region,
            timestamp=metadata.timestamp,
            data=data,
            metadata=metadata,
            content_hash=content_hash
        )


@dataclass
class ResolutionResult:
    """Result of conflict resolution."""
    resolved_data: Any
    resolution_strategy: str
    conflicts_detected: int
    regions_involved: List[str]
    resolution_metadata: Dict[str, Any]


class ConflictResolver:
    """Handles conflict resolution for cross-region data synchronization."""

    def __init__(self):
        from .logging_config import get_logger
        self.logger = get_logger("conflict_resolver")

    def resolve_conflict(
        self,
        versions: List[ConflictedVersion],
        operation_type: str,
        resolution_strategy: ConflictResolution
    ) -> ResolutionResult:
        """Resolve conflicts between multiple versions of data."""

        if len(versions) <= 1:
            # No conflict, return the single version
            return ResolutionResult(
                resolved_data=versions[0].data if versions else None,
                resolution_strategy="no_conflict",
                conflicts_detected=0,
                regions_involved=[v.region for v in versions],
                resolution_metadata={}
            )

        self.logger.info("Resolving conflict", {
            'operation_type': operation_type,
            'strategy': resolution_strategy.value,
            'versions': len(versions),
            'regions': [v.region for v in versions]
        })

        # Apply the appropriate resolution strategy
        if resolution_strategy == ConflictResolution.LAST_WRITER_WINS:
            return self._resolve_last_writer_wins(versions, operation_type)
        elif resolution_strategy == ConflictResolution.SEMANTIC_MERGE:
            return self._resolve_semantic_merge(versions, operation_type)
        elif resolution_strategy == ConflictResolution.REGION_PRIORITY:
            return self._resolve_region_priority(versions, operation_type)
        elif resolution_strategy == ConflictResolution.TIMESTAMP_PRIORITY:
            return self._resolve_timestamp_priority(versions, operation_type)
        else:
            # Fallback to last writer wins
            return self._resolve_last_writer_wins(versions, operation_type)

    def _resolve_last_writer_wins(
        self,
        versions: List[ConflictedVersion],
        operation_type: str
    ) -> ResolutionResult:
        """Resolve using last-writer-wins strategy."""

        # Sort by timestamp (newest first)
        sorted_versions = sorted(
            versions,
            key=lambda v: datetime.fromisoformat(v.timestamp.replace('Z', '+00:00')),
            reverse=True
        )

        winner = sorted_versions[0]

        return ResolutionResult(
            resolved_data=winner.data,
            resolution_strategy="last_writer_wins",
            conflicts_detected=len(versions) - 1,
            regions_involved=[v.region for v in versions],
            resolution_metadata={
                'winning_region': winner.region,
                'winning_timestamp': winner.timestamp,
                'losing_versions': len(versions) - 1
            }
        )

    def _resolve_semantic_merge(
        self,
        versions: List[ConflictedVersion],
        operation_type: str
    ) -> ResolutionResult:
        """Resolve using semantic merge strategy."""

        if operation_type == "shortlist_updates":
            return self._merge_shortlist_items(versions)
        elif operation_type == "node_roster":
            return self._merge_node_roster(versions)
        elif operation_type == "schedule_changes":
            return self._merge_schedule_changes(versions)
        else:
            # Fallback to last writer wins for unknown types
            return self._resolve_last_writer_wins(versions, operation_type)

    def _resolve_region_priority(
        self,
        versions: List[ConflictedVersion],
        operation_type: str
    ) -> ResolutionResult:
        """Resolve using region priority strategy."""

        # Region priority order (lower number = higher priority)
        region_priorities = {
            'us-east': 1,
            'eu-west': 2,
            'asia-pacific': 3,
            'default': 10
        }

        # Sort by region priority
        sorted_versions = sorted(
            versions,
            key=lambda v: region_priorities.get(v.region, 99)
        )

        winner = sorted_versions[0]

        return ResolutionResult(
            resolved_data=winner.data,
            resolution_strategy="region_priority",
            conflicts_detected=len(versions) - 1,
            regions_involved=[v.region for v in versions],
            resolution_metadata={
                'winning_region': winner.region,
                'region_priority': region_priorities.get(winner.region, 99),
                'priority_order': [region_priorities.get(v.region, 99) for v in sorted_versions]
            }
        )

    def _resolve_timestamp_priority(
        self,
        versions: List[ConflictedVersion],
        operation_type: str
    ) -> ResolutionResult:
        """Resolve using timestamp priority (oldest wins for stability)."""

        # Sort by timestamp (oldest first)
        sorted_versions = sorted(
            versions,
            key=lambda v: datetime.fromisoformat(v.timestamp.replace('Z', '+00:00'))
        )

        winner = sorted_versions[0]

        return ResolutionResult(
            resolved_data=winner.data,
            resolution_strategy="timestamp_priority",
            conflicts_detected=len(versions) - 1,
            regions_involved=[v.region for v in versions],
            resolution_metadata={
                'winning_region': winner.region,
                'winning_timestamp': winner.timestamp,
                'oldest_timestamp': True
            }
        )

    def _merge_shortlist_items(self, versions: List[ConflictedVersion]) -> ResolutionResult:
        """Merge shortlist items semantically."""

        all_items = set()
        item_sources = {}  # Track which region contributed each item

        for version in versions:
            data = version.data
            if isinstance(data, dict) and 'items' in data:
                items = data['items']
                if isinstance(items, list):
                    for item in items:
                        item_str = str(item).strip()
                        if item_str:
                            all_items.add(item_str)
                            if item_str not in item_sources:
                                item_sources[item_str] = []
                            item_sources[item_str].append(version.region)

        # Deduplicate and sort
        merged_items = list(all_items)
        merged_items.sort()

        # Create merged data structure
        template_data = versions[0].data if versions else {}
        if isinstance(template_data, dict):
            merged_data = template_data.copy()
            merged_data['items'] = merged_items
        else:
            merged_data = {'items': merged_items}

        return ResolutionResult(
            resolved_data=merged_data,
            resolution_strategy="semantic_merge_shortlist",
            conflicts_detected=len(versions) - 1,
            regions_involved=[v.region for v in versions],
            resolution_metadata={
                'total_items': len(merged_items),
                'item_sources': item_sources,
                'duplicates_removed': sum(len(versions) for versions in item_sources.values()) - len(merged_items)
            }
        )

    def _merge_node_roster(self, versions: List[ConflictedVersion]) -> ResolutionResult:
        """Merge node roster data."""

        all_nodes = {}  # node_id -> latest node data

        for version in versions:
            data = version.data
            if isinstance(data, dict) and 'nodes' in data:
                nodes = data['nodes']
                if isinstance(nodes, list):
                    for node in nodes:
                        if isinstance(node, dict) and 'id' in node:
                            node_id = node['id']

                            # Use the most recent data for each node
                            if node_id not in all_nodes:
                                all_nodes[node_id] = node.copy()
                                all_nodes[node_id]['_source_region'] = version.region
                            else:
                                # Compare timestamps if available
                                existing_timestamp = all_nodes[node_id].get('last_seen', '')
                                new_timestamp = node.get('last_seen', '')

                                if new_timestamp > existing_timestamp:
                                    all_nodes[node_id] = node.copy()
                                    all_nodes[node_id]['_source_region'] = version.region

        # Clean up temporary fields and create final structure
        merged_nodes = []
        for node_data in all_nodes.values():
            clean_node = node_data.copy()
            source_region = clean_node.pop('_source_region', 'unknown')

            # Ensure region is set
            if 'region' not in clean_node:
                clean_node['region'] = source_region

            merged_nodes.append(clean_node)

        # Sort nodes by ID for consistency
        merged_nodes.sort(key=lambda n: n.get('id', ''))

        merged_data = {'nodes': merged_nodes}

        return ResolutionResult(
            resolved_data=merged_data,
            resolution_strategy="semantic_merge_roster",
            conflicts_detected=len(versions) - 1,
            regions_involved=[v.region for v in versions],
            resolution_metadata={
                'total_nodes': len(merged_nodes),
                'nodes_by_region': {region: sum(1 for n in merged_nodes if n.get('region') == region)
                                  for region in set(n.get('region', 'unknown') for n in merged_nodes)}
            }
        )

    def _merge_schedule_changes(self, versions: List[ConflictedVersion]) -> ResolutionResult:
        """Merge schedule changes using priority-based resolution."""

        # For schedule changes, we use region priority to avoid conflicts
        # in task assignments which could cause split-brain scenarios
        return self._resolve_region_priority(versions, "schedule_changes")

    def detect_content_similarity(self, data1: Any, data2: Any) -> float:
        """Calculate similarity between two data structures (0.0 to 1.0)."""

        if data1 == data2:
            return 1.0

        # Convert to comparable strings
        str1 = json.dumps(data1, sort_keys=True) if isinstance(data1, (dict, list)) else str(data1)
        str2 = json.dumps(data2, sort_keys=True) if isinstance(data2, (dict, list)) else str(data2)

        if str1 == str2:
            return 1.0

        # Simple character-based similarity
        if not str1 and not str2:
            return 1.0
        if not str1 or not str2:
            return 0.0

        # Calculate Jaccard similarity on words
        words1 = set(str1.split())
        words2 = set(str2.split())

        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))

        return intersection / union if union > 0 else 0.0

    def is_safe_to_merge(self, versions: List[ConflictedVersion], operation_type: str) -> bool:
        """Determine if it's safe to automatically merge versions."""

        if len(versions) <= 1:
            return True

        # Check if all versions are very similar
        similarity_threshold = 0.8
        for i, version1 in enumerate(versions):
            for version2 in versions[i+1:]:
                similarity = self.detect_content_similarity(version1.data, version2.data)
                if similarity < similarity_threshold:
                    self.logger.warning("Low similarity detected, merge may not be safe", {
                        'operation_type': operation_type,
                        'region1': version1.region,
                        'region2': version2.region,
                        'similarity': similarity
                    })
                    return False

        return True