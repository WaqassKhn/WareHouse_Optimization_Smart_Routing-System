import React, { useEffect, useMemo, useState } from 'react';
import Plot from 'react-plotly.js';
import {
  Activity,
  Box,
  ClipboardList,
  FileText,
  LocateFixed,
  Play,
  RefreshCw,
  Route,
  Truck,
  Upload,
  Warehouse,
} from 'lucide-react';
import {
  fetchDashboard,
  fetchLayoutWithObstacles,
  fetchOperationalReport,
  loginDemo,
  optimizeDelivery,
  optimizeInventory,
  optimizePicking,
  uploadInventory,
} from './api.js';
import KpiCard from './components/KpiCard.jsx';
import WarehouseGrid from './components/WarehouseGrid.jsx';

const plotConfig = { displayModeBar: false, responsive: true };
const plotLayout = {
  margin: { l: 34, r: 16, t: 12, b: 32 },
  paper_bgcolor: 'rgba(0,0,0,0)',
  plot_bgcolor: 'rgba(0,0,0,0)',
  font: { family: 'Inter, system-ui, sans-serif', size: 11, color: '#26323f' },
};

const challengeCards = [
  {
    title: 'OEM service reliability',
    text: 'Keep fast-moving coils, fins, tubes, and spare components close to dispatch.',
    owner: 'Warehouse',
  },
  {
    title: 'Material traceability',
    text: 'Separate fragile, oversized, hazardous, and temperature-sensitive stock.',
    owner: 'Stores',
  },
  {
    title: 'Export dispatch pressure',
    text: 'Plan routes and loading windows around traffic, deadlines, and vehicle capacity.',
    owner: 'Logistics',
  },
  {
    title: 'Shop-floor congestion',
    text: 'Reduce blocked aisles and picker conflicts during production support waves.',
    owner: 'Operations',
  },
];

function pickerStarts(count) {
  const starts = [
    { x: 1, y: 14 },
    { x: 5, y: 14 },
    { x: 2, y: 15 },
    { x: 7, y: 15 },
  ];
  return Array.from({ length: count }, (_, index) => ({
    id: `PICKER-${index + 1}`,
    start: starts[index % starts.length],
    shift_minutes_remaining: index === 3 ? 300 : 420,
  }));
}

export default function App() {
  const [token, setToken] = useState('');
  const [snapshot, setSnapshot] = useState(null);
  const [layout, setLayout] = useState(null);
  const [picking, setPicking] = useState(null);
  const [delivery, setDelivery] = useState(null);
  const [inventory, setInventory] = useState(null);
  const [recommendations, setRecommendations] = useState([]);
  const [report, setReport] = useState(null);
  const [obstacles, setObstacles] = useState([
    { x: 10, y: 7 },
    { x: 14, y: 9 },
  ]);
  const [algorithm, setAlgorithm] = useState('astar');
  const [pickerCount, setPickerCount] = useState(3);
  const [traffic, setTraffic] = useState('normal');
  const [activeTick, setActiveTick] = useState(0);
  const [status, setStatus] = useState('Loading operations view');
  const [busyAction, setBusyAction] = useState('');
  const [actionResult, setActionResult] = useState({
    title: 'Ready',
    detail: 'Use the planning buttons to recalculate pick routes, delivery plans, or stock placement.',
    metrics: [],
  });
  const [selectedCell, setSelectedCell] = useState(null);

  useEffect(() => {
    loadInitial();
  }, []);

  useEffect(() => {
    const routes = picking?.routes || [];
    const maxPath = Math.max(...routes.map((route) => route.path?.length || 0), 1);
    const timer = window.setInterval(() => {
      setActiveTick((tick) => (tick + 1) % maxPath);
    }, 520);
    return () => window.clearInterval(timer);
  }, [picking]);

  async function authToken() {
    if (token) return token;
    const session = await loginDemo();
    setToken(session.access_token);
    return session.access_token;
  }

  async function loadInitial() {
    try {
      setStatus('Loading operations view');
      const session = await loginDemo().catch(() => null);
      if (session) setToken(session.access_token);
      const data = await fetchDashboard();
      setSnapshot(data);
      setLayout(data.warehouse);
      setPicking(data.picking);
      setDelivery(data.delivery);
      setInventory(data.inventory);
      setRecommendations(data.recommendations || []);
      setStatus('Ready for operations review');
      setActionResult({
        title: 'Operations view loaded',
        detail: 'The dashboard is using live API data from the local FastAPI service.',
        metrics: [
          ['Pick lines', data.picking?.summary?.line_count ?? 0],
          ['Dispatch routes', data.delivery?.routes?.length ?? 0],
          ['Stock slots used', data.inventory?.slotting_summary?.occupied_slots ?? 0],
        ],
      });
    } catch (error) {
      setStatus(error.message);
      setActionResult({ title: 'Load failed', detail: error.message, metrics: [] });
    }
  }

  async function runPicking() {
    try {
      setBusyAction('picking');
      setStatus('Optimizing warehouse pick wave');
      const auth = await authToken();
      const [nextLayout, result] = await Promise.all([
        fetchLayoutWithObstacles(obstacles),
        optimizePicking(
          {
            algorithm,
            blocked: obstacles,
            pickers: pickerStarts(Number(pickerCount)),
            order_lines: [],
            congestion_weight: true,
          },
          auth,
        ),
      ]);
      setLayout(nextLayout);
      setPicking(result);
      setActiveTick(0);
      setStatus(`Pick wave optimized with ${algorithm.toUpperCase()}`);
      setActionResult({
        title: 'Pick wave optimized',
        detail: 'Routes were recalculated around blocked aisles and congestion.',
        metrics: [
          ['Lines', `${result.summary.line_count - result.summary.missing_inventory_count}/${result.summary.line_count}`],
          ['Distance', `${result.summary.total_travel_distance} cells`],
          ['Time', `${result.summary.estimated_picking_time_minutes}m`],
          ['Travel saved', `${result.summary.travel_reduction_pct}%`],
        ],
      });
    } catch (error) {
      setStatus(error.message);
      setActionResult({ title: 'Pick optimization failed', detail: error.message, metrics: [] });
    } finally {
      setBusyAction('');
    }
  }

  async function runDelivery() {
    try {
      setBusyAction('delivery');
      setStatus('Optimizing dispatch routes');
      const auth = await authToken();
      const result = await optimizeDelivery({ traffic, dynamic_reroute: true }, auth);
      setDelivery(result);
      setStatus(`Delivery routes optimized for ${traffic} traffic`);
      setActionResult({
        title: 'Dispatch plan updated',
        detail: 'Vehicle routes were recalculated with capacity, traffic, fuel, and delivery windows.',
        metrics: [
          ['Stops', result.summary.assigned_stops],
          ['Distance', `${result.summary.total_distance_km} km`],
          ['On time', `${result.summary.on_time_rate_pct}%`],
          ['Fuel cost', `$${result.summary.fuel_cost}`],
        ],
      });
    } catch (error) {
      setStatus(error.message);
      setActionResult({ title: 'Dispatch planning failed', detail: error.message, metrics: [] });
    } finally {
      setBusyAction('');
    }
  }

  async function runInventory() {
    try {
      setBusyAction('inventory');
      setStatus('Re-slotting inventory');
      const result = await optimizeInventory({ blocked: obstacles });
      setInventory({
        abc_summary: result.abc_summary,
        slotting_summary: result.slotting_summary,
        top_placements: result.placements.slice(0, 18),
        unplaced: result.unplaced,
      });
      setStatus('Inventory slotting updated');
      setActionResult({
        title: 'Stock placement updated',
        detail: 'ABC analysis and special-handling rules were applied to the current floor constraints.',
        metrics: [
          ['Utilization', `${result.slotting_summary.utilization_pct}%`],
          ['Occupied slots', result.slotting_summary.occupied_slots],
          ['A items', result.abc_summary.count_by_class.A],
          ['Exceptions', result.unplaced.length],
        ],
      });
    } catch (error) {
      setStatus(error.message);
      setActionResult({ title: 'Stock re-slotting failed', detail: error.message, metrics: [] });
    } finally {
      setBusyAction('');
    }
  }

  async function generateReport() {
    try {
      setBusyAction('report');
      setStatus('Generating operations report');
      const auth = await authToken();
      const result = await fetchOperationalReport(auth);
      setReport(result);
      setStatus('Report generated');
      setActionResult({
        title: 'Report generated',
        detail: `${result.health.risk_level} risk - ${result.health.primary_constraint}`,
        metrics: [
          ['Score', result.health.overall_score],
          ['Risk', result.health.risk_level],
        ],
      });
    } catch (error) {
      setStatus(error.message);
      setActionResult({ title: 'Report failed', detail: error.message, metrics: [] });
    } finally {
      setBusyAction('');
    }
  }

  async function handleUpload(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      setBusyAction('upload');
      setStatus(`Uploading ${file.name}`);
      const auth = await authToken();
      const result = await uploadInventory(file, auth);
      setInventory({
        abc_summary: result.optimization.abc_summary,
        slotting_summary: result.optimization.slotting_summary,
        top_placements: result.optimization.placements.slice(0, 18),
        unplaced: result.optimization.unplaced,
      });
      setStatus(`${result.row_count} CSV rows optimized`);
      setActionResult({
        title: 'Inventory CSV optimized',
        detail: `${result.row_count} rows were uploaded and re-slotted.`,
        metrics: [
          ['Rows', result.row_count],
          ['Slots used', result.optimization.slotting_summary.occupied_slots],
          ['Exceptions', result.optimization.unplaced.length],
        ],
      });
    } catch (error) {
      setStatus(error.message);
      setActionResult({ title: 'CSV upload failed', detail: error.message, metrics: [] });
    } finally {
      setBusyAction('');
    }
  }

  const kpis = snapshot?.kpis || {};
  const routePaths = picking?.routes || [];
  const heatmap = picking?.heatmap || [];

  const congestionMatrix = useMemo(() => {
    if (!layout) return [];
    const heatByKey = new Map(heatmap.map((cell) => [`${cell.x}:${cell.y}`, cell.combined]));
    const cellByKey = new Map(layout.cells.map((cell) => [`${cell.x}:${cell.y}`, cell]));
    return Array.from({ length: layout.height }, (_, y) =>
      Array.from({ length: layout.width }, (_, x) => {
        const key = `${x}:${y}`;
        return heatByKey.get(key) ?? cellByKey.get(key)?.congestion ?? 0;
      }),
    );
  }, [layout, heatmap]);

  const deliveryTraces = useMemo(() => {
    return (delivery?.routes || []).map((route) => ({
      type: 'scatter',
      mode: 'lines+markers',
      name: route.vehicle_id,
      x: route.polyline.map((point) => point.x),
      y: route.polyline.map((point) => point.y),
      line: { width: 3 },
      marker: { size: 7 },
    }));
  }, [delivery]);

  const completedLines = picking?.routes?.reduce((total, route) => total + route.completed_lines, 0) ?? 0;
  const assignedLines = picking?.routes?.reduce((total, route) => total + route.assigned_lines, 0) ?? 0;
  const isBusy = Boolean(busyAction);

  return (
    <main className="app-shell">
      <header className="topbar compact">
        <div>
          <div className="eyebrow">HVAC / heat-exchanger supply chain</div>
          <h1>Warehouse & Dispatch Control Tower</h1>
          <p className="header-note">
            A practical view for stores, warehouse, and logistics teams managing OEM-ready components.
          </p>
        </div>
        <div className="status-pill">
          <Activity size={16} />
          <span>{status}</span>
        </div>
      </header>

      <section className="challenge-grid" aria-label="Industry challenges">
        {challengeCards.map((item) => (
          <article className="challenge-tile" key={item.title}>
            <span>{item.owner}</span>
            <strong>{item.title}</strong>
            <p>{item.text}</p>
          </article>
        ))}
      </section>

      <section className="kpi-grid focused" aria-label="Operational KPIs">
        <KpiCard label="Utilization" value={kpis.warehouse_utilization_pct ?? '--'} suffix="%" tone="blue" />
        <KpiCard label="Throughput" value={kpis.throughput_lines_per_hour ?? '--'} suffix="/hr" tone="green" />
        <KpiCard label="Pick Score" value={picking?.summary?.efficiency_score ?? kpis.picking_efficiency_score ?? '--'} tone="amber" />
        <KpiCard label="Fulfillment" value={kpis.order_fulfillment_rate_pct ?? '--'} suffix="%" tone="green" />
        <KpiCard label="Travel Saved" value={picking?.summary?.travel_reduction_pct ?? kpis.travel_reduction_pct ?? '--'} suffix="%" tone="blue" />
        <KpiCard label="Dispatch Cost" value={`$${delivery?.summary?.fuel_cost ?? kpis.fuel_cost ?? '--'}`} tone="red" />
      </section>

      <section className="main-layout">
        <div className="panel map-panel">
          <div className="panel-header">
            <div>
              <span className="section-icon"><Warehouse size={16} /></span>
              <h2>Warehouse floor</h2>
            </div>
            <button type="button" className="icon-button" onClick={runPicking} title="Recalculate routes">
              <RefreshCw size={16} />
            </button>
          </div>
          <WarehouseGrid
            layout={layout}
            routes={routePaths}
            heatmap={heatmap}
            obstacles={obstacles}
            setObstacles={setObstacles}
            activeTick={activeTick}
            onCellSelect={setSelectedCell}
          />
          <div className="legend-row">
            {['aisle', 'shelf', 'dispatch', 'cold_storage', 'hazmat', 'oversized', 'restricted', 'blocked'].map((item) => (
              <span key={item}><i className={`legend-dot ${item}`} />{item.replace('_', ' ')}</span>
            ))}
          </div>
        </div>

        <aside className="panel controls-panel">
          <div className="panel-header">
            <div>
              <span className="section-icon"><LocateFixed size={16} /></span>
              <h2>Daily planning</h2>
            </div>
          </div>

          <div className="field-grid">
            <label>
              Pick routing
              <select value={algorithm} onChange={(event) => setAlgorithm(event.target.value)}>
                <option value="astar">A* search</option>
                <option value="dijkstra">Dijkstra</option>
              </select>
            </label>
            <label>
              Pickers
              <input
                type="number"
                min="1"
                max="4"
                value={pickerCount}
                onChange={(event) => setPickerCount(event.target.value)}
              />
            </label>
            <label>
              Traffic
              <select value={traffic} onChange={(event) => setTraffic(event.target.value)}>
                <option value="light">Light</option>
                <option value="normal">Normal</option>
                <option value="heavy">Heavy</option>
                <option value="incident">Incident</option>
              </select>
            </label>
          </div>

          <div className="button-row">
            <button type="button" onClick={runPicking} disabled={isBusy}><Route size={16} /> Optimize Pick Wave</button>
            <button type="button" onClick={runDelivery} disabled={isBusy}><Truck size={16} /> Plan Dispatch</button>
            <button type="button" onClick={runInventory} disabled={isBusy}><Box size={16} /> Re-slot Stock</button>
          </div>

          <div className="secondary-actions">
            <label className={`file-button ${isBusy ? 'disabled' : ''}`}>
              <Upload size={16} />
              <span>Upload Inventory CSV</span>
              <input type="file" accept=".csv" onChange={handleUpload} disabled={isBusy} />
            </label>
            <button type="button" className="secondary-button" onClick={generateReport} disabled={isBusy}>
              <FileText size={16} /> Report
            </button>
          </div>

          <div className="action-result">
            <span>Last action</span>
            <strong>{busyAction ? 'Working...' : actionResult.title}</strong>
            <p>{busyAction ? 'The API is recalculating the current plan.' : actionResult.detail}</p>
            {actionResult.metrics.length > 0 && (
              <div className="result-metrics">
                {actionResult.metrics.map(([label, value]) => (
                  <div key={label}>
                    <small>{label}</small>
                    <b>{value}</b>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="summary-strip vertical">
            <div><span>Blocked aisles</span><strong>{obstacles.length}</strong></div>
            <div><span>Pick lines</span><strong>{completedLines}/{assignedLines}</strong></div>
            <div><span>Late deliveries</span><strong>{delivery?.summary?.late_deliveries ?? 0}</strong></div>
          </div>

          {report && (
            <div className="report-box">
              <strong>Report Score: {report.health.overall_score}</strong>
              <span>{report.health.risk_level} risk - {report.health.primary_constraint}</span>
            </div>
          )}

          <div className="cell-inspector">
            <span>Selected floor cell</span>
            {selectedCell ? (
              <>
                <strong>{selectedCell.label || selectedCell.type}</strong>
                <p>
                  ({selectedCell.x}, {selectedCell.y}) - {selectedCell.canToggle ? 'open aisle can be blocked or cleared' : 'fixed storage/dispatch zone'}
                </p>
              </>
            ) : (
              <p>Click any floor cell to inspect it. Open aisles toggle as blocked obstacles.</p>
            )}
          </div>
        </aside>
      </section>

      <section className="ops-grid">
        <div className="panel">
          <div className="panel-header"><h2>Picking work</h2></div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Picker</th>
                  <th>Lines</th>
                  <th>Distance</th>
                  <th>Time</th>
                  <th>Score</th>
                </tr>
              </thead>
              <tbody>
                {(picking?.routes || []).map((route) => (
                  <tr key={route.picker_id}>
                    <td>{route.picker_id}</td>
                    <td>{route.completed_lines}/{route.assigned_lines}</td>
                    <td>{route.travel_distance} cells</td>
                    <td>{route.estimated_picking_time_minutes}m</td>
                    <td>{route.efficiency_score}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <div>
              <span className="section-icon"><ClipboardList size={16} /></span>
              <h2>System recommendations</h2>
            </div>
          </div>
          <div className="recommendation-list">
            {(recommendations || []).slice(0, 4).map((item) => (
              <article key={`${item.type}-${item.title}`} className={`recommendation ${item.priority}`}>
                <span>{item.priority}</span>
                <h3>{item.title}</h3>
                <p>{item.evidence}</p>
                <strong>{item.action}</strong>
              </article>
            ))}
          </div>
        </div>

        <div className="panel">
          <div className="panel-header"><h2>Dispatch summary</h2></div>
          <div className="dispatch-list">
            {(delivery?.routes || []).map((route) => (
              <div className="dispatch-row" key={route.vehicle_id}>
                <span>{route.vehicle_id}</span>
                <strong>{route.route_distance_km} km</strong>
                <em>{route.capacity_utilization_pct}% capacity</em>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="insight-grid">
        <div className="panel">
          <div className="panel-header"><h2>Congestion</h2></div>
          <Plot
            data={[{
              z: congestionMatrix,
              type: 'heatmap',
              colorscale: [[0, '#eef4f1'], [0.55, '#87b7a6'], [0.8, '#e2a752'], [1, '#c75b52']],
              showscale: false,
            }]}
            layout={{ ...plotLayout, height: 240 }}
            config={plotConfig}
            className="plot"
            useResizeHandler
          />
        </div>

        <div className="panel">
          <div className="panel-header"><h2>Delivery route preview</h2></div>
          <Plot
            data={deliveryTraces}
            layout={{
              ...plotLayout,
              height: 240,
              xaxis: { title: 'km east', zeroline: false },
              yaxis: { title: 'km north', zeroline: false },
              legend: { orientation: 'h' },
            }}
            config={plotConfig}
            className="plot"
            useResizeHandler
          />
        </div>

        <div className="panel">
          <div className="panel-header"><h2>Priority stock</h2></div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>SKU</th>
                  <th>Class</th>
                  <th>Slot</th>
                  <th>Handling</th>
                </tr>
              </thead>
              <tbody>
                {(inventory?.top_placements || []).slice(0, 8).map((item) => (
                  <tr key={item.sku}>
                    <td>{item.sku}</td>
                    <td>{item.abc_class}</td>
                    <td>{item.slot.x},{item.slot.y}</td>
                    <td>{item.special_handling.join(', ')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </main>
  );
}
