End-to-End-Data-Pipeline-BI-Dashboard-Project

ETL pipeline for integrating Zid (e-commerce) and Daftarah (accounting/ERP) data into Supabase PostgreSQL for Power BI dashboards.

## Overview
- **Zid Pipeline**: Handles extraction, transformation, and loading from Zid API. Supports incremental updates and webhooks for real-time sync.
- **Daftarah Pipeline**: Placeholder for Daftarah integration (collaborator to implement).
- **Shared Components**: Common utilities for DB connections and logging.
- **Scheduling**: GitHub Actions for nightly incremental updates.
- **Webhooks**: Real-time handler for Zid events (deploy to Supabase Edge Functions).

## Setup
1. Clone the repo: `git clone https://github.com/your-username/Rahma-Store-ETL-Project.git`
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in credentials.
4. For Zid: Run `python pipelines/zid/main.py` (or global `python main.py` for both).

## Running ETL
- **Full Run (Both)**: `python main.py`
- **Zid Only**: `python pipelines/zid/main.py`
- **Daftarah Only**: `python pipelines/daftarah/main.py`
- **Incremental Mode**: Add `--incremental` flag (implement in main.py if needed).

## Scheduling (GitHub Actions)
- Nightly incremental sync configured in `.github/workflows/update-data.yml`.
- Manual trigger via GitHub UI.

## Webhooks (Zid Real-Time)
- Deploy `webhooks/handler.py` to Supabase Edge Functions.
- Register with Zid using the provided script.
- URL: https://your-supabase-project.supabase.co/functions/v1/zid-webhook-handler

## Collaboration
- Zid work: `pipelines/zid/`
- Daftarah work: `pipelines/daftarah/`
- Use branches for features (e.g., `zid-incremental`).

## Tests
- Add tests in `tests/` using pytest.
