import React from 'react';
import { Package, ShieldAlert, Snowflake, Truck, X } from 'lucide-react';

const typeIcon = {
  dispatch: <Truck size={13} />,
  restricted: <ShieldAlert size={13} />,
  cold_storage: <Snowflake size={13} />,
  hazmat: <ShieldAlert size={13} />,
  oversized: <Package size={13} />,
  blocked: <X size={13} />,
};

export default function WarehouseGrid({ layout, routes = [], heatmap = [], obstacles, setObstacles, activeTick }) {
  if (!layout) return null;

  const obstacleKeys = new Set(obstacles.map((point) => `${point.x}:${point.y}`));
  const routeKeys = new Set(routes.flatMap((route) => route.path || []).map((point) => `${point.x}:${point.y}`));
  const heatByKey = new Map(heatmap.map((cell) => [`${cell.x}:${cell.y}`, cell.combined || 0]));
  const activeByKey = new Map(
    routes
      .map((route) => {
        const point = route.path?.[Math.min(activeTick, Math.max(route.path.length - 1, 0))];
        return point ? [`${point.x}:${point.y}`, route.picker_id] : null;
      })
      .filter(Boolean),
  );

  function toggleObstacle(cell) {
    if (!cell.walkable || cell.type === 'dispatch') return;
    const key = `${cell.x}:${cell.y}`;
    if (obstacleKeys.has(key)) {
      setObstacles(obstacles.filter((point) => `${point.x}:${point.y}` !== key));
    } else {
      setObstacles([...obstacles, { x: cell.x, y: cell.y }]);
    }
  }

  return (
    <div className="warehouse-grid" style={{ gridTemplateColumns: `repeat(${layout.width}, minmax(18px, 1fr))` }}>
      {layout.cells.map((cell) => {
        const key = `${cell.x}:${cell.y}`;
        const heat = heatByKey.get(key) || cell.congestion || 0;
        const active = activeByKey.get(key);
        const classes = ['warehouse-cell', cell.type];
        if (routeKeys.has(key)) classes.push('route');
        if (active) classes.push('active');
        return (
          <button
            type="button"
            key={key}
            title={`${cell.label || cell.type} (${cell.x}, ${cell.y})`}
            className={classes.join(' ')}
            style={{ '--heat': Math.min(1, heat) }}
            onClick={() => toggleObstacle(cell)}
          >
            {active ? <span className="picker-dot">{active.replace('PICKER-', 'P')}</span> : typeIcon[cell.type] || null}
          </button>
        );
      })}
    </div>
  );
}
