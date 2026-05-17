# Warehouse Optimization & Smart Routing System

Full-stack simulation platform for manufacturing and supply chain operations. The app models a smart warehouse, optimizes inventory placement and picking routes, schedules deliveries, and exposes operational analytics through a React dashboard backed by FastAPI.

## Stack

- Frontend: React, Vite, Plotly, Lucide icons
- Backend: FastAPI, SQLAlchemy, PostgreSQL-ready persistence
- Optimization: NetworkX-style graph traversal with built-in fallbacks, Pandas/NumPy/scikit-learn hooks
- Runtime: Docker Compose for PostgreSQL, local dev servers for API and UI

## Features

- Interactive grid warehouse with shelves, aisles, dispatch, cold storage, hazmat, oversized, restricted, and dynamic blocked zones
- ABC inventory analysis and slotting rules for fast movers, oversized goods, hazardous items, fragile products, and temperature-sensitive stock
- Dijkstra and A* picking route optimization with multi-picker assignment, congestion costs, blocked aisle handling, and route recalculation
- Vehicle routing and delivery scheduling with capacity, traffic, fuel, deadlines, overload detection, and dynamic rerouting assumptions
- Dashboard KPIs for throughput, picking efficiency, order cycle time, warehouse utilization, fuel cost, labor efficiency, and savings
- Congestion heatmaps, route animation, delivery route visualization, CSV upload, report endpoint, authentication, and role checks

## Quick Start

1. Start PostgreSQL:

   ```powershell
   docker compose up -d postgres
   ```

2. Configure the backend:

   ```powershell
   Copy-Item .env.example backend\.env
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   uvicorn app.main:app --reload --port 8000
   ```

3. Start the frontend:

   ```powershell
   cd frontend
   npm install
   npm run dev
   ```

4. Open [http://localhost:5173](http://localhost:5173).

Demo login:

- Username: `admin@supplychain.ai`
- Password: `admin123`

## API Highlights

- `GET /health`
- `POST /api/auth/login`
- `GET /api/warehouse/layout`
- `POST /api/inventory/optimize`
- `POST /api/inventory/upload`
- `POST /api/picking/optimize`
- `POST /api/delivery/optimize`
- `GET /api/analytics/dashboard`
- `GET /api/recommendations`
- `GET /api/reports/operational`

## CSV Upload Format

Required columns:

```csv
sku,name,category,velocity,unit_cost,quantity,length,width,height,weight,hazardous,fragile,temperature_sensitive
```

Boolean fields accept `true`, `false`, `1`, `0`, `yes`, or `no`.

## Development Notes

The API is designed to be useful even when PostgreSQL is not running: simulation and optimization endpoints use deterministic demo data. PostgreSQL models and Docker wiring are included for production persistence, audit trails, users, uploads, and report metadata.

