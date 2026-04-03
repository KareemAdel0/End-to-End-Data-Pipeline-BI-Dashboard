import os
import requests
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime
import sqlalchemy as sa

# Shared DB utils
from shared.db_utils import engine, check_db_connection
from shared.logger import setup_logger

# ==========================================
# 1. SETUP
# ==========================================
load_dotenv()

logger = setup_logger(__name__)

DAFTARA_SUBDOMAIN = os.getenv("DAFTARA_SUBDOMAIN")
DAFTARA_API_KEY = os.getenv("DAFTARA_API_KEY")

BASE_URL = f"https://{DAFTARA_SUBDOMAIN}.daftra.com/v2/api"

# ==========================================
# 2. ENTITY DATE CONFIG (Incremental)
# ==========================================
ENTITY_DATE_COLUMN = {
    "invoice": "modified",
    "invoice_item": "modified",
    "invoice_payment": "created",
    "refund_receipt": "modified",
    "estimate": "modified",
    "purchase_order": "modified",
    "purchase_refund": "modified",
    "client": "modified",
    "product": "modified",
    "product_category": "modified",
    "expense": "modified",
    "tax": "modified",
    "treasury": "modified",
    "staff": "created",
}

# ==========================================
# 3. ETL STATE HELPERS
# ==========================================
def get_last_modified(entity: str):
    if not check_db_connection():
        logger.warning("DB connection unavailable. Incremental disabled.")
        return None

    try:
        with engine.connect() as conn:
            result = conn.execute(
                sa.text(
                    """
                    SELECT last_modified_at
                    FROM etl_state
                    WHERE entity_name = :entity
                    """
                ),
                {"entity": entity},
            ).scalar()
            return result
    except Exception as e:
        logger.warning(f"Failed to get last_modified for {entity}: {e}")
        return None


def update_last_modified(entity: str, value: datetime):
    if not check_db_connection():
        return

    try:
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    """
                    INSERT INTO etl_state (entity_name, last_modified_at)
                    VALUES (:entity, :value)
                    ON CONFLICT (entity_name)
                    DO UPDATE SET last_modified_at = EXCLUDED.last_modified_at
                    """
                ),
                {"entity": entity, "value": value},
            )
    except Exception as e:
        logger.warning(f"Failed to update last_modified for {entity}: {e}")

# ==========================================
# 4. EXTRACTOR
# ==========================================
class DaftraExtractor:
    def __init__(self):
        self.headers = {
            "apikey": DAFTARA_API_KEY,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _get(self, endpoint: str):
        url = f"{BASE_URL}/{endpoint}"
        try:
            response = requests.get(url, headers=self.headers, timeout=60)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"API failed -> {endpoint} | {e}")
            return None

    def _fetch_invoice_api1(self) -> pd.DataFrame:
        logger.info("Start extracting invoice (api2)")
    
        page = 1
        limit = 1000
        all_rows = []
    
        date_column = ENTITY_DATE_COLUMN.get("invoice")  # modified
        last_modified = get_last_modified("invoice")
        run_time = datetime.utcnow()
    
        while True:
            params = {
                "page": page,
                "limit": limit,
            }
    
            # incremental filter
            if date_column and last_modified:
                params["modified_from"] = last_modified.strftime("%Y-%m-%d %H:%M:%S")
                params["modified_to"] = run_time.strftime("%Y-%m-%d %H:%M:%S")
    
            logger.info(f"[EXTRACT] invoice (api2) | page {page}")
    
            try:
                response = requests.get(
                    f"https://{DAFTARA_SUBDOMAIN}.daftra.com/api2/invoices",
                    headers=self.headers,
                    params=params,
                    timeout=60,
                )
                response.raise_for_status()
                payload = response.json()
            except Exception as e:
                logger.error(f"Invoice failed | page {page} -> {e}")
                break
    
            rows = payload.get("data", [])
            if not rows:
                break
    
            for r in rows:
                invoice = r.get("Invoice", {})
    
                invoice.pop("Client", None)
    
                all_rows.append(invoice)
    
            pagination = payload.get("pagination", {})
            if page >= pagination.get("page_count", page):
                break
    
            page += 1
    
        df = pd.DataFrame(all_rows)
        logger.info(f"[EXTRACT DONE] invoice -> {len(df)} rows")
    
        if not df.empty and date_column in df.columns:
            df[date_column] = pd.to_datetime(df[date_column], errors="coerce")
            max_date = df[date_column].max()
            if pd.notna(max_date):
                update_last_modified("invoice", max_date)
    
        return df


    def _fetch_entity(self, entity: str, level: int = 1) -> pd.DataFrame:
        logger.info(f"Start extracting entity: {entity}")

        page = 1
        all_rows = []

        date_column = ENTITY_DATE_COLUMN.get(entity)
        last_modified = get_last_modified(entity)
        run_time = datetime.utcnow()

        while True:
            endpoint = f"entity/{entity}/list/{level}?page={page}"

            if date_column and last_modified:
                endpoint += (
                    f"&filter[{date_column}][gte]={last_modified.strftime('%Y-%m-%d %H:%M:%S')}"
                    f"&filter[{date_column}][lte]={run_time.strftime('%Y-%m-%d %H:%M:%S')}"
                )

            logger.info(f"[EXTRACT] {entity} | page {page}")

            response = self._get(endpoint)

            if not response or "data" not in response:
                logger.warning(f"[SKIP PAGE] {entity} page {page}")
                page += 1
                continue

            data = response.get("data", [])
            if not data:
                break

            all_rows.extend(data)

            meta = response.get("meta", {})
            last_page = meta.get("last_page")
            if last_page and page >= last_page:
                break

            page += 1

        df = pd.DataFrame(all_rows)
        logger.info(f"[EXTRACT DONE] {entity} -> {len(df)} rows")

        # Update incremental state
        if not df.empty and date_column and date_column in df.columns:
            df[date_column] = pd.to_datetime(df[date_column], errors="coerce")
            max_date = df[date_column].max()
            if pd.notna(max_date):
                update_last_modified(entity, max_date)

        return df

    # ======================================
    # 5. PUBLIC API
    # ======================================
    def extract_all(self) -> dict[str, pd.DataFrame]:
        logger.info("=" * 50)
        logger.info("      DAFTRA DATA EXTRACTION STARTED")
        logger.info("=" * 50)

        data = {
            "invoice": self._fetch_invoice_api1(),
            "invoice_item": self._fetch_entity("invoice_item"),
            "invoice_payment": self._fetch_entity("invoice_payment"),
            "refund_receipt": self._fetch_entity("refund_receipt"),
            "estimate": self._fetch_entity("estimate"),

            "client": self._fetch_entity("client"),
            "supplier": self._fetch_entity("supplier"),

            "product": self._fetch_entity("product"),
            "product_category": self._fetch_entity("product_category"),
            "store": self._fetch_entity("store"),

            "expense": self._fetch_entity("expense"),
            "purchase_order": self._fetch_entity("purchase_order"),
            "purchase_refund": self._fetch_entity("purchase_refund"),
            "treasury": self._fetch_entity("treasury"),

            "staff": self._fetch_entity("staff"),
            "tax": self._fetch_entity("tax"),
        }

        logger.info("=" * 50)
        logger.info("      DAFTRA DATA EXTRACTION COMPLETED")
        logger.info("=" * 50)

        return data


