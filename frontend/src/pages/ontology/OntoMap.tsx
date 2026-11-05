import { useMemo } from 'react'
import {
  Background, BaseEdge, Controls, EdgeLabelRenderer, Handle, MarkerType, MiniMap, Position,
  ReactFlow, useInternalNode, type Edge, type EdgeProps, type Node, type NodeProps,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { KeyRound, TriangleAlert } from 'lucide-react'
import type { OntoView } from '../../api/types'
import { flowLayout, formatCount, type FlowNodeData } from '../../utils/onto'

type ThingNode = Node<FlowNodeData & { selected: boolean }, 'thing'>

function ThingCard({ data }: NodeProps<ThingNode>) {
  return (
    <div className={`flow-thing${data.selected ? ' is-selected' : ''}`}>
      <Handle type="target" position={Position.Left} className="flow-thing__handle" />
      <div className="flow-thing__name">{data.name}</div>
      <div className="flow-thing__meta">
        {data.fields} fields{data.records ? ` · ${formatCount(data.records)} records` : ''}
      </div>
      {data.keys.length ? (
        <div className="flow-thing__keys"><KeyRound size={12} aria-hidden="true" /> {data.keys.join(', ')}</div>
      ) : null}
      {data.conflicts ? (
        <div className="flow-thing__warn"><TriangleAlert size={12} aria-hidden="true" /> {data.conflicts} to check</div>
      ) : null}
      <Handle type="source" position={Position.Right} className="flow-thing__handle" />
    </div>
  )
}

const NODE_TYPES = { thing: ThingCard }

/** Where the line from a box's centre towards a point leaves the box. */
function border(cx: number, cy: number, w: number, h: number, tx: number, ty: number) {
  const dx = tx - cx
  const dy = ty - cy
  if (!dx && !dy) return { x: cx, y: cy }
  const s = Math.min(dx ? (w / 2) / Math.abs(dx) : Infinity, dy ? (h / 2) / Math.abs(dy) : Infinity)
  return { x: cx + dx * s, y: cy + dy * s }
}

/**
 * A "floating" edge: a straight line from box edge to box edge, aimed centre to
 * centre, so lines in a dense map never loop around the boxes.
 */
function FloatingEdge({ id, source, target, label, markerEnd, style }: EdgeProps) {
  const a = useInternalNode(source)
  const b = useInternalNode(target)
  if (!a || !b) return null
  const aw = a.measured.width ?? 0
  const ah = a.measured.height ?? 0
  const bw = b.measured.width ?? 0
  const bh = b.measured.height ?? 0
  const ac = { x: a.internals.positionAbsolute.x + aw / 2, y: a.internals.positionAbsolute.y + ah / 2 }
  const bc = { x: b.internals.positionAbsolute.x + bw / 2, y: b.internals.positionAbsolute.y + bh / 2 }
  const s = border(ac.x, ac.y, aw + 8, ah + 8, bc.x, bc.y)
  const t = border(bc.x, bc.y, bw + 8, bh + 8, ac.x, ac.y)
  const path = `M ${s.x},${s.y} L ${t.x},${t.y}`
  return (
    <>
      <BaseEdge id={id} path={path} markerEnd={markerEnd} style={style} />
      {label ? (
        <EdgeLabelRenderer>
          <div className="flow-edge-label nodrag nopan"
            style={{ transform: `translate(-50%, -50%) translate(${(s.x + t.x) / 2}px, ${(s.y + t.y) / 2}px)` }}>
            {label}
          </div>
        </EdgeLabelRenderer>
      ) : null}
    </>
  )
}

const EDGE_TYPES = { floating: FloatingEdge }

/** The ontology as a zoomable diagram. Click a thing to open it. */
export function OntoMap({ view, selected, onOpen }: {
  view: OntoView
  selected?: string
  onOpen: (thingKey: string) => void
}) {
  const { nodes, edges, dense } = useMemo(() => {
    const layout = flowLayout(view.things, view.links)
    const flowNodes: ThingNode[] = layout.nodes.map((n) => ({
      id: n.id, type: 'thing', position: { x: n.x, y: n.y },
      data: { ...n.data, selected: n.id === selected }, draggable: true,
    }))
    const flowEdges: Edge[] = layout.edges.map((e) => ({
      id: e.id, source: e.source, target: e.target, label: e.label,
      // A dense graph reads best as gentle curves; a flow as right angles.
      type: layout.dense ? 'floating' : 'smoothstep',
      ...(e.directed ? { markerEnd: { type: MarkerType.ArrowClosed, width: 18, height: 18 } } : {}),
      className: 'flow-edge', labelBgPadding: [6, 3] as [number, number], labelBgBorderRadius: 4,
    }))
    return { nodes: flowNodes, edges: flowEdges, dense: layout.dense }
  }, [view, selected])
  const keyOf = useMemo(() => new Map(view.things.map((t) => [t.name, t.key])), [view])

  return (
    <div className={`onto-flow${dense ? ' onto-flow--dense' : ''}`} aria-label="Map of business things and their links">
      <ReactFlow nodes={nodes} edges={edges} nodeTypes={NODE_TYPES} edgeTypes={EDGE_TYPES} fitView
        fitViewOptions={{ padding: 0.15 }} minZoom={0.2} maxZoom={1.6}
        nodesConnectable={false}
        onNodeClick={(_, node) => { const k = keyOf.get(node.id); if (k) onOpen(k) }}>
        <Background gap={20} size={1} />
        <MiniMap pannable zoomable className="onto-flow__minimap" nodeColor="#2e2e38" nodeStrokeWidth={0} maskColor="rgba(246,246,250,0.7)" />
        <Controls showInteractive={false} />
      </ReactFlow>
      <p className="onto-flow__legend">
        {dense ? 'Each line joins two things that are related; its label says how many relations. '
          : 'Arrows point from the many side to the one side. '}
        Drag to move, scroll to zoom, click a thing to open it.
      </p>
    </div>
  )
}
