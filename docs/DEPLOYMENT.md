# FundFlow Sentinel — Production Deployment Runbook

## Overview

FundFlow Sentinel is a high-reliability quantitative risk and mutual fund research platform designed to operate either offline from cryptographically signed snapshots or in live integration with verified public financial data registries.

---

## 1. Quick Start Deployments

### Option A: Docker Deployment (Recommended)

1. **Build Container Image:**
   ```bash
   docker build -t fundflow-sentinel:production .
   ```

2. **Run Container:**
   ```bash
   docker run -d \
     --name fundflow_sentinel \
     -p 8501:8501 \
     -e FUNDFLOW_DATA_MODE=offline_snapshot \
     --restart unless-stopped \
     fundflow-sentinel:production
   ```

3. **Verify Health:**
   ```bash
   docker exec fundflow_sentinel python scripts/healthcheck.py
   # Output: [Healthcheck] Status 200 OK from http://localhost:8501/_stcore/health
   ```

### Option B: Docker Compose

```bash
docker-compose up -d
docker-compose ps
```

### Option C: Cloud PaaS (Render / Railway / Fly.io / Heroku)

The repository includes a production `Procfile`:
```
web: streamlit run app/Home.py --server.port $PORT --server.address 0.0.0.0 --server.headless true
```
* **Build Command:** `pip install -r requirements.txt`
* **Start Command:** Detected automatically from `Procfile`.
* **Port:** Auto-injected `$PORT`.

---

## 2. Environment Configuration

All environment variables can be provided in `.env`:

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `8501` | HTTP listening port |
| `FUNDFLOW_DATA_MODE` | `offline_snapshot` | Mode indicator (`offline_snapshot`, `live`, `synthetic`) |
| `FUNDFLOW_FIXTURE_DIR` | `data/snapshots` | Root directory for offline data bundles |
| `FUNDFLOW_LOG_LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `STREAMLIT_SERVER_HEADLESS` | `true` | Headless execution mode |
| `STREAMLIT_SERVER_ENABLE_CORS` | `true` | Cross-origin resource sharing policy |
| `STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION` | `true` | Cross-site request forgery prevention |

---

## 3. Pre-Flight Verification & Quality Gates

Run the automated contract and snapshot checks prior to any release:

```bash
# 1. Bytecode Compilation
python -m compileall src app tests -q

# 2. Schema Contract Validation
python -m pytest -q tests/test_contracts.py

# 3. Snapshot Integrity Verification
python -m fundflow.cli snapshot --verify

# 4. Full Deterministic Suite
make check
```

---

## 4. Live Data Refresh & Atomic Rollback Runbook

### Data Refresh Procedure
FundFlow Sentinel employs transactional snapshot staging to prevent corrupt or partial downloads from ever reaching the live application:

1. **Stage Data Ingestion:**
   ```bash
   python -m fundflow.cli ingest amfi --cache data/cache
   ```
2. **Recompute Features & Alerts:**
   ```bash
   python -m fundflow.cli features build
   python -m fundflow.cli forecast run
   python -m fundflow.cli alerts generate
   ```
3. **Transactionally Publish Snapshot:**
   ```bash
   python -m fundflow.cli snapshot create --publish
   ```
   *If any validation check fails during staging, the transaction aborts and the last known good snapshot remains untouched.*

### Rollback Procedure
If a regression or data anomaly is detected in production:
1. Revert data root to previous verified snapshot:
   ```bash
   cp data/snapshots/manifest.json.bak data/snapshots/manifest.json
   ```
2. Restart application service:
   ```bash
   docker restart fundflow_sentinel
   ```
3. Execute health check:
   ```bash
   python scripts/healthcheck.py
   ```
