"""Dependency graph operations: validation, topological sort, layout, and
conversion to a ReactFlow-compatible WorkflowGraph."""

from __future__ import annotations

import logging
from collections import defaultdict, deque

from backend.models.ticket import Ticket, TicketStatus
from backend.models.workflow import WorkflowEdge, WorkflowGraph, WorkflowNode

logger = logging.getLogger(__name__)

# Layout constants (pixels)
_LAYER_Y_GAP = 200
_NODE_X_GAP = 300


class DependencyGraphBuilder:
    """Builds, validates, and lays out a dependency graph of tickets."""

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------

    def build_graph(self, tickets: list[Ticket]) -> WorkflowGraph:
        """Convert tickets to a ReactFlow-compatible WorkflowGraph.

        Creates one WorkflowNode per ticket and one WorkflowEdge for each
        dependency relationship. Nodes are positioned by layer (y-axis)
        and spread evenly within each layer (x-axis).
        """
        positions = self.compute_layout(tickets)
        ticket_id_to_node_id: dict[str, str] = {}

        nodes: list[WorkflowNode] = []
        for t in tickets:
            x, y = positions.get(t.id, (0.0, 0.0))
            node = WorkflowNode(
                ticket_id=t.id,
                label=f"{t.id}: {t.title}",
                layer=t.layer,
                domain=t.domain,
                status=t.status,
                position_x=x,
                position_y=y,
            )
            nodes.append(node)
            ticket_id_to_node_id[t.id] = node.id

        edges: list[WorkflowEdge] = []
        for t in tickets:
            for dep_id in t.depends_on:
                source_node_id = ticket_id_to_node_id.get(dep_id)
                target_node_id = ticket_id_to_node_id.get(t.id)
                if source_node_id and target_node_id:
                    animated = t.status == TicketStatus.IN_PROGRESS
                    edges.append(
                        WorkflowEdge(
                            source=source_node_id,
                            target=target_node_id,
                            animated=animated,
                        )
                    )

        return WorkflowGraph(nodes=nodes, edges=edges)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_graph(self, tickets: list[Ticket]) -> list[str]:
        """Detect cycles and missing dependency references.

        Returns:
            A list of human-readable error strings.  Empty list means the
            graph is valid.
        """
        errors: list[str] = []
        ticket_ids = {t.id for t in tickets}

        # Check for references to non-existent tickets
        for t in tickets:
            for dep_id in t.depends_on:
                if dep_id not in ticket_ids:
                    errors.append(
                        f"Ticket {t.id} depends on {dep_id} which does not exist"
                    )

        # Cycle detection via topological sort (Kahn's algorithm)
        in_degree: dict[str, int] = {t.id: 0 for t in tickets}
        adjacency: dict[str, list[str]] = defaultdict(list)

        for t in tickets:
            for dep_id in t.depends_on:
                if dep_id in ticket_ids:
                    adjacency[dep_id].append(t.id)
                    in_degree[t.id] += 1

        queue: deque[str] = deque(
            tid for tid, deg in in_degree.items() if deg == 0
        )
        visited_count = 0

        while queue:
            current = queue.popleft()
            visited_count += 1
            for neighbor in adjacency[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if visited_count != len(tickets):
            # Find the cycle participants
            cycle_members = [
                tid for tid, deg in in_degree.items() if deg > 0
            ]
            errors.append(
                f"Dependency cycle detected involving tickets: "
                f"{', '.join(cycle_members)}"
            )

        return errors

    # ------------------------------------------------------------------
    # Topological sort
    # ------------------------------------------------------------------

    def topological_sort(self, tickets: list[Ticket]) -> list[Ticket]:
        """Return tickets in dependency order using Kahn's algorithm.

        Tickets with no remaining dependencies come first.  Within the
        same topological level, tickets are sorted by (layer, priority).
        Raises ValueError if a cycle is detected.
        """
        ticket_map = {t.id: t for t in tickets}
        ticket_ids = set(ticket_map.keys())

        in_degree: dict[str, int] = {t.id: 0 for t in tickets}
        adjacency: dict[str, list[str]] = defaultdict(list)

        for t in tickets:
            for dep_id in t.depends_on:
                if dep_id in ticket_ids:
                    adjacency[dep_id].append(t.id)
                    in_degree[t.id] += 1

        # Seed with zero in-degree, sorted by layer then priority
        queue: deque[str] = deque(
            sorted(
                (tid for tid, deg in in_degree.items() if deg == 0),
                key=lambda tid: (ticket_map[tid].layer, ticket_map[tid].priority.value),
            )
        )

        result: list[Ticket] = []
        while queue:
            current = queue.popleft()
            result.append(ticket_map[current])

            # Collect newly freed neighbors, then sort before extending
            freed: list[str] = []
            for neighbor in adjacency[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    freed.append(neighbor)
            freed.sort(
                key=lambda tid: (ticket_map[tid].layer, ticket_map[tid].priority.value)
            )
            queue.extend(freed)

        if len(result) != len(tickets):
            raise ValueError(
                "Cannot topologically sort tickets: dependency cycle detected"
            )

        return result

    # ------------------------------------------------------------------
    # Unblocked ticket detection
    # ------------------------------------------------------------------

    def get_unblocked_tickets(self, tickets: list[Ticket]) -> list[Ticket]:
        """Return tickets whose dependencies are all COMPLETED.

        Only considers tickets that are currently BLOCKED or READY.
        A ticket with an empty depends_on list and status BLOCKED is
        also considered unblocked (should be READY).
        """
        ticket_map = {t.id: t for t in tickets}
        unblocked: list[Ticket] = []

        for t in tickets:
            if t.status not in (TicketStatus.BLOCKED, TicketStatus.READY):
                continue

            all_deps_done = all(
                ticket_map.get(dep_id, t).status == TicketStatus.COMPLETED
                for dep_id in t.depends_on
            )

            if all_deps_done:
                unblocked.append(t)

        return unblocked

    # ------------------------------------------------------------------
    # Layout computation
    # ------------------------------------------------------------------

    def compute_layout(self, tickets: list[Ticket]) -> dict[str, tuple[float, float]]:
        """Compute (x, y) positions for ReactFlow nodes.

        Tickets are grouped by layer.  Each layer sits at
        ``y = layer * 200``.  Within a layer, tickets are spread
        horizontally and centered around x = 0.
        """
        # Group tickets by layer
        layers: dict[int, list[Ticket]] = defaultdict(list)
        for t in tickets:
            layers[t.layer].append(t)

        positions: dict[str, tuple[float, float]] = {}

        for layer_idx in sorted(layers.keys()):
            layer_tickets = layers[layer_idx]
            count = len(layer_tickets)
            y = layer_idx * _LAYER_Y_GAP

            # Center the row: total width = (count - 1) * gap
            total_width = (count - 1) * _NODE_X_GAP
            start_x = -total_width / 2.0

            for i, t in enumerate(layer_tickets):
                x = start_x + i * _NODE_X_GAP
                positions[t.id] = (x, y)

        return positions
