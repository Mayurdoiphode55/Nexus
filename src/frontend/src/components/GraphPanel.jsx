import { useEffect, useRef, useState, useCallback } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { fetchGraph } from '../api';

const LEGEND = [
  { type: 'Customer', color: '#4CAF50' },
  { type: 'Order', color: '#2196F3' },
  { type: 'Delivery', color: '#FF9800' },
  { type: 'Invoice', color: '#9C27B0' },
  { type: 'Product', color: '#F44336' },
  { type: 'Payment', color: '#00BCD4' },
];

export default function GraphPanel() {
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const [selectedNode, setSelectedNode] = useState(null);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({ nodes: 0, edges: 0 });
  const [filter, setFilter] = useState(null); // null = all
  const containerRef = useRef(null);
  const graphRef = useRef(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });

  // Responsive sizing
  useEffect(() => {
    const updateSize = () => {
      if (containerRef.current) {
        setDimensions({
          width: containerRef.current.offsetWidth,
          height: containerRef.current.offsetHeight,
        });
      }
    };
    updateSize();
    window.addEventListener('resize', updateSize);
    return () => window.removeEventListener('resize', updateSize);
  }, []);

  // Load graph data
  const loadGraph = useCallback(async (customerId = null) => {
    setLoading(true);
    try {
      const data = await fetchGraph(customerId);
      // Rename edges → links for react-force-graph
      const formatted = {
        nodes: data.nodes || [],
        links: (data.edges || []).map(e => ({
          source: e.source,
          target: e.target,
          relation: e.relation,
        })),
      };
      setGraphData(formatted);
      setStats({ nodes: formatted.nodes.length, edges: formatted.links.length });
    } catch (err) {
      console.error('Failed to load graph:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadGraph(filter);
  }, [filter, loadGraph]);

  // Zoom to fit after data loads
  useEffect(() => {
    if (graphRef.current && graphData.nodes.length > 0) {
      setTimeout(() => {
        graphRef.current.zoomToFit(400, 60);
      }, 500);
    }
  }, [graphData]);

  // Node rendering
  const nodeCanvasObject = useCallback((node, ctx, globalScale) => {
    const fontSize = Math.max(10 / globalScale, 3);
    const nodeSize = node.type === 'Customer' ? 8 : 5;

    // Glow effect on hover
    if (selectedNode && selectedNode.id === node.id) {
      ctx.beginPath();
      ctx.arc(node.x, node.y, nodeSize + 4, 0, 2 * Math.PI);
      ctx.fillStyle = node.color + '30';
      ctx.fill();
    }

    // Node circle
    ctx.beginPath();
    ctx.arc(node.x, node.y, nodeSize, 0, 2 * Math.PI);
    ctx.fillStyle = node.color;
    ctx.fill();

    // White border
    ctx.strokeStyle = 'rgba(255,255,255,0.2)';
    ctx.lineWidth = 0.5;
    ctx.stroke();

    // Label
    if (globalScale > 0.8 || node.type === 'Customer') {
      ctx.font = `${fontSize}px Inter, sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      ctx.fillStyle = 'rgba(255,255,255,0.7)';
      ctx.fillText(node.label, node.x, node.y + nodeSize + 2);
    }
  }, [selectedNode]);

  const handleNodeClick = useCallback((node) => {
    setSelectedNode(node);
    // If clicking a customer, filter the graph
    if (node.type === 'Customer' && node.metadata?.business_partner) {
      setFilter(node.metadata.business_partner);
    }
  }, []);

  // Get unique customers for filter buttons
  const customers = graphData.nodes.filter(n => n.type === 'Customer');

  return (
    <div className="graph-panel">
      <div className="graph-panel__header">
        <div className="graph-panel__title">
          <div className="graph-panel__title-icon">🔗</div>
          <div>
            <div>Order to Cash Graph</div>
            <div className="graph-stats">
              <span>⬡ {stats.nodes} nodes</span>
              <span>— {stats.edges} edges</span>
            </div>
          </div>
        </div>
        <div className="graph-filters">
          <button
            className={`graph-filter-btn ${filter === null ? 'graph-filter-btn--active' : ''}`}
            onClick={() => { setFilter(null); setSelectedNode(null); }}
          >
            All
          </button>
          {customers.slice(0, 4).map(c => (
            <button
              key={c.id}
              className={`graph-filter-btn ${filter === c.metadata?.business_partner ? 'graph-filter-btn--active' : ''}`}
              onClick={() => setFilter(c.metadata?.business_partner)}
            >
              {c.label.substring(0, 12)}
            </button>
          ))}
        </div>
      </div>

      <div className="graph-panel__canvas" ref={containerRef}>
        {loading ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
            <div className="typing-indicator">
              <div className="typing-dot" />
              <div className="typing-dot" />
              <div className="typing-dot" />
            </div>
          </div>
        ) : (
          <ForceGraph2D
            ref={graphRef}
            graphData={graphData}
            width={dimensions.width}
            height={dimensions.height}
            backgroundColor="transparent"
            nodeCanvasObject={nodeCanvasObject}
            nodePointerAreaPaint={(node, color, ctx) => {
              ctx.beginPath();
              ctx.arc(node.x, node.y, 10, 0, 2 * Math.PI);
              ctx.fillStyle = color;
              ctx.fill();
            }}
            onNodeClick={handleNodeClick}
            linkColor={() => 'rgba(255,255,255,0.06)'}
            linkWidth={0.5}
            linkDirectionalArrowLength={3}
            linkDirectionalArrowRelPos={1}
            cooldownTicks={100}
            d3AlphaDecay={0.02}
            d3VelocityDecay={0.3}
          />
        )}

        {/* Legend */}
        <div className="graph-legend">
          {LEGEND.map(l => (
            <div className="legend-item" key={l.type}>
              <div className="legend-dot" style={{ background: l.color }} />
              {l.type}
            </div>
          ))}
        </div>

        {/* Node detail panel */}
        {selectedNode && (
          <div className="node-detail">
            <button className="node-detail__close" onClick={() => setSelectedNode(null)}>✕</button>
            <div
              className="node-detail__type"
              style={{ background: selectedNode.color + '20', color: selectedNode.color }}
            >
              {selectedNode.type}
            </div>
            <div className="node-detail__label">{selectedNode.label}</div>
            <div className="node-detail__meta">
              {selectedNode.metadata && Object.entries(selectedNode.metadata).map(([key, val]) => (
                <div className="node-detail__meta-item" key={key}>
                  <span className="node-detail__meta-key">{key.replace(/_/g, ' ')}</span>
                  <span className="node-detail__meta-value">{String(val ?? '—')}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
