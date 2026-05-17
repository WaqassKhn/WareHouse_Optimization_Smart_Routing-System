import React from 'react';

export default function KpiCard({ label, value, suffix = '', tone = 'neutral' }) {
  return (
    <div className={`kpi-tile ${tone}`}>
      <span>{label}</span>
      <strong>
        {value}
        {suffix}
      </strong>
    </div>
  );
}
