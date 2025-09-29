#!/usr/bin/env python3
"""
Swarm Simulator for Shortlist.

This tool runs simulated swarm nodes with configurable chaos conditions
to test system resilience and performance.
"""

import os
import sys
import json
import time
import random
import argparse
import threading
import tempfile
import shutil
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set
from pathlib import Path

import rich
from rich.live import Live
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn
from rich.console import Console
from rich import print as rprint

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from node import Node  # Assuming Node class accepts git_manager in __init__
from utils.chaos_git_manager import ChaosGitManager, ChaosConfig
from utils.roles import NodeRoles

# Initialize rich console
console = Console()

def create_initial_state() -> Dict[str, Any]:
    """Create initial repository state for simulation."""
    return {
        "shortlist.json": {
            "items": [
                "Test item 1",
                "Test item 2",
                "Test item 3"
            ]
        },
        "schedule.json": {
            "tasks": [
                {
                    "id": "system_governor",
                    "type": "governor",
                    "priority": -2,
                    "required_role": "system"
                },
                {
                    "id": "system_healer",
                    "type": "healer",
                    "priority": -1,
                    "required_role": "system"
                },
                {
                    "id": "video_stream",
                    "type": "video",
                    "priority": 5,
                    "required_role": "media"
                }
            ]
        },
        "roster.json": {
            "nodes": {}
        },
        "assignments.json": {
            "assignments": {}
        }
    }

class SwarmSimulator:
    """Manages a simulated Shortlist swarm."""
    
    def __init__(
        self,
        num_nodes: int,
        role_distribution: Dict[str, float],
        chaos_config: ChaosConfig,
        duration: timedelta
    ):
        """Initialize the simulator.
        
        Args:
            num_nodes: Number of nodes to simulate
            role_distribution: Mapping of role to probability
            chaos_config: Chaos testing configuration
            duration: How long to run simulation
        """
        self.num_nodes = num_nodes
        self.role_distribution = role_distribution
        self.chaos_config = chaos_config
        self.duration = duration
        
        # Create shared git manager
        self.git_manager = ChaosGitManager(
            config=chaos_config,
            initial_state=create_initial_state()
        )
        
        # Track nodes
        self.nodes: List[Node] = []
        self.node_threads: List[threading.Thread] = []
        self.stop_event = threading.Event()
    
    def _assign_node_roles(self) -> Set[str]:
        """Randomly assign roles to a node based on distribution."""
        roles = set()
        for role, probability in self.role_distribution.items():
            if random.random() < probability:
                roles.add(role)
        return roles or {"system"}  # Default to system if no roles assigned
    
    def create_nodes(self) -> None:
        """Create all simulation nodes."""
        for i in range(self.num_nodes):
            # Create node with random roles
            roles = self._assign_node_roles()
            node = Node(
                git_manager=self.git_manager,
                roles=NodeRoles(roles),
                node_id=f"sim_node_{i+1}"
            )
            
            # Create thread
            thread = threading.Thread(
                target=node.run,
                args=(self.stop_event,),
                name=f"Node-{i+1}"
            )
            
            self.nodes.append(node)
            self.node_threads.append(thread)
    
    def update_display(
        self,
        table: Table,
        start_time: datetime
    ) -> None:
        """Update the live display with current metrics."""
        table.clear()
        
        # Add headers
        table.add_column("Metric")
        table.add_column("Value")
        
        # Get metrics
        metrics = self.git_manager.get_metrics()
        elapsed = datetime.now() - start_time
        
        # Basic stats
        table.add_row(
            "Runtime",
            str(elapsed).split('.')[0]
        )
        table.add_row(
            "Active Nodes",
            str(len([n for n in self.nodes if n.is_alive()]))
        )
        
        # Git operations
        ops = metrics["operations"]
        for op_type, stats in ops.items():
            success_rate = (
                (stats["total"] - stats["failed"]) /
                max(1, stats["total"]) * 100
            )
            table.add_row(
                f"{op_type.title()} Operations",
                f"Total: {stats['total']}, Success Rate: {success_rate:.1f}%, "
                f"Avg Latency: {stats['avg_latency']*1000:.0f}ms"
            )
        
        # Network status
        table.add_row(
            "Network Status",
            "🔴 Partitioned" if metrics["current_partition"] else "🟢 Connected"
        )
        
        # Rate limiting
        rate = metrics["rate_limiting"]
        table.add_row(
            "Operations/Minute",
            f"{rate['operations_last_minute']}/{rate['max_operations_per_minute']}"
        )
    
    def run(self) -> None:
        """Run the simulation."""
        console.clear()
        console.rule("[bold blue]Shortlist Swarm Simulator[/]")
        
        # Create progress display
        table = Table(show_header=True)
        
        try:
            # Start nodes
            self.create_nodes()
            for thread in self.node_threads:
                thread.start()
            
            # Run display loop
            start_time = datetime.now()
            with Live(table, refresh_per_second=1) as live:
                while (
                    datetime.now() - start_time < self.duration and
                    not self.stop_event.is_set()
                ):
                    self.update_display(table, start_time)
                    time.sleep(1)
            
        except KeyboardInterrupt:
            console.print("\n[yellow]Simulation interrupted![/]")
        finally:
            # Stop all nodes
            self.stop_event.set()
            for thread in self.node_threads:
                thread.join(timeout=5)
            
            # Print final stats
            console.rule("[bold blue]Simulation Complete[/]")
            metrics = self.git_manager.get_metrics()
            console.print_json(data=metrics)

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Shortlist Swarm Simulator")
    
    # Basic settings
    parser.add_argument(
        "--nodes",
        type=int,
        default=5,
        help="Number of nodes to simulate"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=300,
        help="Simulation duration in seconds"
    )
    
    # Role distribution
    parser.add_argument(
        "--system-probability",
        type=float,
        default=0.3,
        help="Probability of a node having system role"
    )
    parser.add_argument(
        "--media-probability",
        type=float,
        default=0.3,
        help="Probability of a node having media role"
    )
    parser.add_argument(
        "--web-probability",
        type=float,
        default=0.3,
        help="Probability of a node having web role"
    )
    
    # Chaos settings
    parser.add_argument(
        "--min-latency",
        type=float,
        default=0.1,
        help="Minimum simulated latency in seconds"
    )
    parser.add_argument(
        "--max-latency",
        type=float,
        default=2.0,
        help="Maximum simulated latency in seconds"
    )
    parser.add_argument(
        "--failure-rate",
        type=float,
        default=0.1,
        help="Base rate for operation failures"
    )
    parser.add_argument(
        "--partition-probability",
        type=float,
        default=0.01,
        help="Probability of network partition per minute"
    )
    
    args = parser.parse_args()
    
    # Create role distribution
    role_distribution = {
        "system": args.system_probability,
        "media": args.media_probability,
        "web": args.web_probability
    }
    
    # Create chaos config
    chaos_config = ChaosConfig(
        min_latency=args.min_latency,
        max_latency=args.max_latency,
        read_failure_rate=args.failure_rate,
        write_failure_rate=args.failure_rate * 1.5,
        sync_failure_rate=args.failure_rate * 2,
        push_failure_rate=args.failure_rate * 2.5,
        partition_probability=args.partition_probability
    )
    
    # Create and run simulator
    simulator = SwarmSimulator(
        num_nodes=args.nodes,
        role_distribution=role_distribution,
        chaos_config=chaos_config,
        duration=timedelta(seconds=args.duration)
    )
    
    simulator.run()

if __name__ == "__main__":
    main()