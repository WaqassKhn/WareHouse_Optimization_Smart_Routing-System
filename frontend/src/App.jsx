import React, { useEffect, useMemo, useState } from 'react';
import Plot from 'react-plotly.js';
import {
  Activity,
  BarChart3,
  FileText,
  LocateFixed,
  Play,
  RefreshCw,
  Route,
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
  margin: { l: 34, r: 18, t: 16, b: 34 },
  paper_bgcolor: 'rgba(0,0,0,0)',
  plot_bgcolor: 'rgba(0,0,0,0)',
  font: { family: 'Inter, system-ui, sans-serif', size: 11, color: '#26323f' },
};

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
  const [report, setReport] = useState(null);
  const [obstacles, setObstacles] = useState([
    { x: 10, y: 7 },
    { x: 14, y: 9 },
  ]);
  const [algorithm, setAlgorithm] = useState('astar');
  const [pickerCount, setPickerCount] = useState(3);
  const [traffic, setTraffic] = useState('normal');
  const [activeTick, setActiveTick] = useState(0);
  const [status, setStatus] = useState('Loading dashboard');

  useEffect(() => {
    loadInitial();
  }, []);

  useEffect(() => {
    const routes = picking?.routes || [];
    const maxPath = Math.max(...routes.map((route) => route.path?.length || 0), 1);
    const timer = window.setInterval(() => {
      setActiveTick((tick) => (tick + 1) % maxPath);
    }, 420);
    return () => window.clearInterval(timer);
  }, [picking]);

  async function authToken() {
    if (token) return token;
    const session = await loginDemo();
    setToken(session.access_token);
    return session.access_token;
  }

  async function loadInitial() {
    setStatus('Loading dashboard');
    const session = await loginDemo().catch(() => null);
    if (session) setToken(session.access_token);
    const data = await fetchDashboard();
    setSnapshot(data);
    setLayout(data.warehouse);
    setPicking(data.picking);
    setDelivery(data.delivery);
    setInventory(data.inventory);
    setStatus('Live simulation ready');
  }

  async function runPicking() {
    setStatus('Optimizing pick wave');
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
  }

  async function runDelivery() {
    setStatus('Optimizing delivery schedule');
    const auth = await authToken();
    const result = await optimizeDelivery({ traffic, dynamic_reroute: true }, auth);
    setDelivery(result);
    setStatus(`Delivery routes optimized for ${traffic} traffic`);
  }

  async function runInventory() {
    setStatus('Recalculating inventory slotting');
    const result = await optimizeInventory({ blocked: obstacles });
    setInventory({
      abc_summary: result.abc_summary,
      slotting_summary: result.slotting_summary,
      top_placements: result.placements.slice(0, 18),
      unplaced: result.unplaced,
    });
    setStatus('Inventory slotting updated');
  }

  async function generateReport() {
    setStatus('Generating report');
    const auth = await authToken();
    const result = await fetchOperationalReport(auth);
    setReport(result);
    setStatus('Report generated');
  }

  async function handleUpload(event) {
    const file = event.target.files?.[0];
    if (!file) return;
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
  }

  const kpis = snapshot?.kpis || {};
  const routePaths = picking?.routes || [];
  const heatmap = picking?.heatmap || [];
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

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <div className="eyebrow">Manufacturing Operations</div>
          <h1>Warehouse Optimization & Smart Routing</h1>
        </div>
        <div className="status-pill">
          <Activity size={16} />
          <span>{status}</span>
        </div>
      </header>

      <section className="kpi-grid" aria-label="Operational KPIs">
        <KpiCard label="Utilization" value={kpis.warehouse_utilization_pct ?? '--'} suffix="%" tone="blue" />
        <KpiCard label="Throughput" value={kpis.throughput_lines_per_hour ?? '--'} suffix="/hr" tone="green" />
        <KpiCard label="Pick Efficiency" value={kpis.picking_efficiency_score ?? '--'} tone="amber" />
        <KpiCard label="Fulfillment" value={kpis.order_fulfillment_rate_pct ?? '--'} suffix="%" tone="green" />
        <KpiCard label="Travel Reduction" value={picking?.summary?.travel_reduction_pct ?? kpis.travel_reduction_pct ?? '--'} suffix="%" tone="blue" />
        <KpiCard label="Fuel Cost" value={`$${delivery?.summary?.fuel_cost ?? kpis.fuel_cost ?? '--'}`} tone="red" />
        <KpiCard label="Cycle Time" value={kpis.order_cycle_time_minutes ?? '--'} suffix="m" tone="neutral" />
        <KpiCard label="Savings" value={`$${kpis.operational_savings_estimate ?? '--'}`} tone="green" />
      </section>

      <section className="workspace-grid">
        <div className="panel map-panel">
          <div className="panel-header">
            <div>
              <span className="section-icon"><Warehouse size={16} /></span>
              <h2>Warehouse Map</h2>
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
          />
          <div className="legend-row">
            {['aisle', 'shelf', 'dispatch', 'cold_storage', 'hazmat', 'oversized', 'restricted', 'blocked'].map((item) => (
              <span key={item}><i className={`legend-dot ${item}`} />{item.replace('_', ' ')}</span>
            ))}
          </div>
        </div>

        <div className="panel controls-panel">
          <div className="panel-header">
            <div>
              <span className="section-icon"><LocateFixed size={16} /></span>
              <h2>Optimization Controls</h2>
            </div>
          </div>
          <label>
            Algorithm
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
          <div className="button-row">
            <button type="button" onClick={runPicking}><Route size={16} /> Optimize Picking</button>
            <button type="button" onClick={runDelivery}><Play size={16} /> Schedule Delivery</button>
            <button type="button" onClick={runInventory}><BarChart3 size={16} /> Re-slot Inventory</button>
          </div>
          <label className="file-button">
            <Upload size={16} />
            <span>Upload CSV</span>
            <input type="file" accept=".csv" onChange={handleUpload} />
          </label>
          <button type="button" className="secondary-button" onClick={generateReport}><FileText size={16} /> Generate Report</button>

          <div className="summary-strip">
            <div><span>Blocked Cells</span><strong>{obstacles.length}</strong></div>
            <div><span>Missing SKU</span><strong>{picking?.summary?.missing_inventory_count ?? 0}</strong></div>
            <div><span>Late Drops</span><strong>{delivery?.summary?.late_deliveries ?? 0}</strong></div>
          </div>
        </div>
      </section>

      <section className="analytics-grid">
        <div className="panel">
          <div className="panel-header"><h2>Congestion Heatmap</h2></div>
          <Plot
            data={[{
              z: snapshot?.charts?.congestion_heatmap?.z || [],
              type: 'heatmap',
              colorscale: [[0, '#eef6f2'], [0.45, '#72b7a1'], [0.75, '#f0b35a'], [1, '#cc4b4b']],
              showscale: false,
            }]}
            layout={{ ...plotLayout, height: 260 }}
            config={plotConfig}
            className="plot"
            useResizeHandler
          />
        </div>

        <div className="panel">
          <div className="panel-header"><h2>ABC Inventory</h2></div>
          <Plot
            data={[{
              x: Object.keys(inventory?.abc_summary?.count_by_class || {}),
              y: Object.values(inventory?.abc_summary?.count_by_class || {}),
              type: 'bar',
              marker: { color: ['#2563eb', '#0f9f6e', '#f59e0b'] },
            }]}
            layout={{ ...plotLayout, height: 260 }}
            config={plotConfig}
            className="plot"
            useResizeHandler
          />
        </div>

        <div className="panel delivery-panel">
          <div className="panel-header"><h2>Delivery Routes</h2></div>
          <Plot
            data={deliveryTraces}
            layout={{
              ...plotLayout,
              height: 300,
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
          <div className="panel-header"><h2>Fuel Analytics</h2></div>
          <Plot
            data={[{
              x: (delivery?.routes || []).map((route) => route.vehicle_id),
              y: (delivery?.routes || []).map((route) => route.fuel_cost),
              type: 'bar',
              marker: { color: '#d45b4f' },
            }]}
            layout={{ ...plotLayout, height: 300 }}
            config={plotConfig}
            className="plot"
            useResizeHandler
          />
        </div>
      </section>

      <section className="bottom-grid">
        <div className="panel">
          <div className="panel-header"><h2>Picker Routes</h2></div>
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
          <div className="panel-header"><h2>AI Recommendations</h2></div>
          <div className="recommendation-list">
            {(snapshot?.recommendations || []).map((item) => (
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
          <div className="panel-header"><h2>Top Slot Assignments</h2></div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>SKU</th>
                  <th>ABC</th>
                  <th>Slot</th>
                  <th>Handling</th>
                </tr>
              </thead>
              <tbody>
                {(inventory?.top_placements || []).slice(0, 9).map((item) => (
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
          {report && (
            <div className="report-box">
              <strong>Report Score: {report.health.overall_score}</strong>
              <span>{report.health.risk_level} risk · {report.health.primary_constraint}</span>
            </div>
          )}
        </div>
      </section>
    </main>
  );
}
