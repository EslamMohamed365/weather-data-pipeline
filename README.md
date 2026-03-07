<div align="center">

# Weather Data Pipeline

_Production-ready ETL system for weather data using Open-Meteo API, PostgreSQL, and Streamlit_

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![PostgreSQL](https://img.shields.io/badge/postgresql-15-336791.svg)](https://www.postgresql.org/)
[![Polars](https://img.shields.io/badge/polars-0.20+-CD792C.svg)](https://pola.rs/)
[![Streamlit](https://img.shields.io/badge/streamlit-1.35+-FF4B4B.svg)](https://streamlit.io/)
[![Docker](https://img.shields.io/badge/docker--compose-2496ED.svg)](https://docs.docker.com/compose/)

[Overview](#overview) • [Quick Start](#quick-start) • [Dashboard](#dashboard) • [Documentation](#documentation)

</div>

---

## Overview

A complete ETL pipeline that extracts real-time weather data from the Open-Meteo API, transforms it using Polars DataFrames, loads it into PostgreSQL, and provides an interactive Streamlit dashboard for visualization.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Weather Data Pipeline                         │
└─────────────────────────────────────────────────────────────────┘

  EXTRACT              TRANSFORM              LOAD              VISUALIZE
     │                     │                    │                    │
┌────▼────┐          ┌────▼────┐         ┌────▼────┐         ┌─────▼────┐
│ Open-  │   JSON    │ Polars  │  Batch  │Postgre- │  Query  │Streamlit │
│ Meteo  │──────────►│ Engine  │────────►│ SQL 15  │────────►│Dashboard │
│  API   │           │         │         │         │         │          │
└─────────┘           └─────────┘         └─────────┘         └──────────┘
• Retry logic      • Validation        • Connection pool    • Plotly charts
• Rate limiting    • Type safety       • Idempotent writes  • Smart caching
```

### Features

- **High Performance**: Polars DataFrames process data 5-10x faster than pandas
- **Reliable**: Automatic retry logic with exponential backoff
- **Secure**: Parameterized queries prevent SQL injection
- **Scalable**: Connection pooling supports 100+ cities
- **Interactive Dashboard**: Three-page Streamlit app with filtering and visualizations

## Quick Start

### Prerequisites

- Python 3.11+
- Docker and Docker Compose

### Setup

1. **Clone and install dependencies**:

```bash
git clone <repository-url>
cd weather-data-pipeline

# With uv (recommended)
uv sync

# Or with pip
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

2. **Start the database**:

```bash
docker-compose up -d
```

3. **Run the pipeline**:

```bash
uv run python src/pipeline.py
```

4. **Launch the dashboard**:

```bash
uv run streamlit run dashboard/app.py
```

> [!TIP]
> Access the dashboard at `http://localhost:8501` and pgAdmin at `http://localhost:5050`

### Default Cities

The pipeline fetches weather data for 5 cities by default:
- Cairo, London, Tokyo, New York, Sydney

### Environment Variables

Default values work for local development. Create a `.env` file if needed:

```bash
cp .env.example .env
```

Key variables:
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` - Database connection
- `API_BASE_URL` - Open-Meteo API endpoint (default provided)
- `DASHBOARD_PORT` - Streamlit port (default: 8501)

## Dashboard

The Streamlit dashboard provides three pages:

| Page | Description |
|------|-------------|
| **Current Conditions** | Real-time weather with temperature, humidity, wind, precipitation |
| **Historical Trends** | Time-series charts over custom date ranges |
| **City Comparison** | Side-by-side metrics across multiple cities |

**Interactive Controls**:
- Multi-city selection filter
- Date range picker
- Temperature unit toggle (°C / °F)
- 5-minute automatic data caching

## Documentation

Detailed guides available in `docs/`:

- **[Setup Guide](docs/SETUP.md)** - Installation, configuration, troubleshooting
- **[Architecture](docs/ARCHITECTURE.md)** - System design and data flow
- **[Performance](docs/PERFORMANCE.md)** - Benchmarks and optimization strategies
- **[API Reference](docs/API.md)** - Developer guide for extensions

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.11+ |
| Data Processing | Polars 0.20+ |
| Database | PostgreSQL 15 |
| Dashboard | Streamlit 1.35+ |
| Visualization | Plotly |
| Containerization | Docker Compose |

## Troubleshooting

**Database connection failed**

```bash
docker-compose ps           # Check container status
docker-compose logs db      # View error logs
```

**Pipeline fails with API errors**

```bash
curl -I https://api.open-meteo.com  # Check connectivity
```

**Dashboard shows no data**

```bash
uv run python src/pipeline.py  # Run pipeline first
```

---

<div align="center">

Built by [Eslam Mohamed](https://github.com/EslamMohamed365)

</div>
