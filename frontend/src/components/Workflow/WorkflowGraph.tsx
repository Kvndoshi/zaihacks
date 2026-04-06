import { useCallback, useMemo } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  type Node,
  type Edge,
  BackgroundVariant,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { useFrictionStore } from '@/store/useFrictionStore';
import { TicketNode } from './TicketNode';
import { LayerLabel } from './LayerLabel';

const ARCH_DOMAIN_COLORS: Record<string, string> = {
  frontend: '#8b5cf6',
  backend: '#3b82f6',
  database: '#10b981',
  api: '#06b6d4',
  auth: '#ef4444',
  infra: '#f97316',
  testing: '#eab308',
  docs: '#6b7280',
};

const nodeTypes = { ticket: TicketNode };

export function WorkflowGraph() {
  const { workflow, architectureGraph, workflowMode, selectTicket, toggleWorkflowMode, tickets } = useFrictionStore();

  // Build a map of ticket_id -> active for dimming inactive nodes
  const ticketActiveMap = useMemo(() => {
    const map: Record<string, boolean> = {};
    for (const t of tickets) {
      map[t.id] = t.active !== false;
    }
    return map;
  }, [tickets]);

  const activeGraph = workflowMode === 'highlevel' ? architectureGraph : workflow;

  const { nodes, edges } = useMemo(() => {
    if (!activeGraph) return { nodes: [], edges: [] };

    const isHighLevel = workflowMode === 'highlevel';

    const flowNodes: Node[] = activeGraph.nodes.map((n) => ({
      id: n.id,
      type: isHighLevel ? 'default' : 'ticket',
      position: { x: n.position_x, y: n.position_y },
      ...(isHighLevel
        ? {
            data: { label: n.label },
            style: {
              background: `${ARCH_DOMAIN_COLORS[n.domain] || '#3b82f6'}22`,
              border: `2px solid ${ARCH_DOMAIN_COLORS[n.domain] || '#3b82f6'}`,
              borderRadius: '12px',
              padding: '16px 20px',
              color: '#e5e7eb',
              fontSize: '13px',
              fontWeight: 600,
              width: 280,
              minHeight: 60,
              textAlign: 'center' as const,
            },
          }
        : {
            data: {
              ticketId: n.ticket_id,
              label: n.label,
              domain: n.domain,
              status: n.status,
              layer: n.layer,
            },
            style: ticketActiveMap[n.ticket_id] === false ? { opacity: 0.3 } : undefined,
          }),
    }));

    const flowEdges: Edge[] = activeGraph.edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      animated: e.animated,
      style: {
        stroke: e.animated ? '#f59e0b' : '#2a2a2a',
        strokeWidth: 2,
      },
    }));

    // Add layer labels (only for detailed view)
    if (!isHighLevel) {
      const layers = new Set(activeGraph.nodes.map((n) => n.layer));
      layers.forEach((layer) => {
        const minY = Math.min(
          ...activeGraph.nodes.filter((n) => n.layer === layer).map((n) => n.position_y),
        );
        flowNodes.push({
          id: `layer-label-${layer}`,
          type: 'default',
          position: { x: -180, y: minY + 10 },
          data: { label: `Layer ${layer}` },
          selectable: false,
          draggable: false,
          style: {
            background: 'transparent',
            border: 'none',
            color: '#6b7280',
            fontSize: '12px',
            fontWeight: 600,
            letterSpacing: '0.05em',
            textTransform: 'uppercase' as const,
          },
        });
      });
    }

    return { nodes: flowNodes, edges: flowEdges };
  }, [activeGraph, workflowMode]);

  const onNodeClick = useCallback(
    (_: unknown, node: Node) => {
      if (node.data?.ticketId) {
        selectTicket(node.data.ticketId as string);
      }
    },
    [selectTicket],
  );

  if (!workflow) {
    return (
      <div className="flex-1 flex items-center justify-center text-friction-muted">
        No workflow available
      </div>
    );
  }

  return (
    <div className="flex-1 relative">
      {/* Toggle pill */}
      <div className="absolute top-4 left-1/2 -translate-x-1/2 z-10 flex rounded-lg overflow-hidden border border-friction-border bg-friction-darker">
        <button
          onClick={() => workflowMode !== 'detailed' && toggleWorkflowMode()}
          className={`px-4 py-1.5 text-xs font-medium transition-colors ${
            workflowMode === 'detailed'
              ? 'bg-friction-amber text-black'
              : 'text-gray-400 hover:text-gray-200 hover:bg-friction-surface'
          }`}
        >
          Detailed
        </button>
        <button
          onClick={() => workflowMode !== 'highlevel' && toggleWorkflowMode()}
          className={`px-4 py-1.5 text-xs font-medium transition-colors ${
            workflowMode === 'highlevel'
              ? 'bg-friction-amber text-black'
              : 'text-gray-400 hover:text-gray-200 hover:bg-friction-surface'
          }`}
        >
          High Level
        </button>
      </div>

      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={onNodeClick}
        fitView
        fitViewOptions={{ padding: 0.3 }}
        proOptions={{ hideAttribution: true }}
        colorMode="dark"
        key={workflowMode}
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#1a1a1a" />
        <Controls
          showInteractive={false}
          className="[&_button]:bg-friction-surface [&_button]:border-friction-border [&_button]:text-gray-400 [&_button:hover]:bg-friction-border"
        />
      </ReactFlow>
    </div>
  );
}
