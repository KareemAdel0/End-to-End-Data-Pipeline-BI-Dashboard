import requests
import pandas as pd
import os
import time
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Import shared utilities
from shared.db_utils import get_last_timestamp, check_db_connection  # For incremental fetching
from shared.logger import setup_logger  # Shared logger setup

# ==========================================
# 1. SETUP & CONFIGURATION
# ==========================================

# Load environment variables
load_dotenv()

ZID_AUTHORIZATION_TOKEN = os.getenv("ZID_AUTHORIZATION_TOKEN")
ZID_MANAGER_TOKEN = os.getenv("ZID_MANAGER_TOKEN")
ZID_STORE_ID = os.getenv("ZID_STORE_ID")

BASE_URL = "https://api.zid.sa/v1"

HEADERS = {
    "Authorization": f"Bearer {str(ZID_AUTHORIZATION_TOKEN).strip()}",
    "X-Manager-Token": str(ZID_MANAGER_TOKEN).strip(),
    "Store-Id": str(ZID_STORE_ID),
    "Accept-Language": "ar",
    "Content-Type": "application/json",
    "User-Agent": "Zid-Data-Engine/In-Memory"
}

# Mapping: Friendly Name -> (API Endpoint Suffix, JSON Key to Extract)
ENDPOINTS = {
    "Orders":           ("/managers/store/orders", "orders"),
    "Products":         ("/products/", "products"),
    "Customers":        ("/managers/store/customers", "customers"),
    "Categories":       ("/managers/store/categories", "categories"),
    "Locations":        ("/locations/", "locations"),
    "Shipping_Methods": ("/managers/store/delivery-options", "delivery_options"),
    "Abandoned_Carts":  ("/managers/store/abandoned-carts", "abandoned-carts"),
    "Coupons":          ("/managers/store/coupons", "coupons"),
    # New Endpoint Added Here
    "Product_Reviews":  ("/managers/store/reviews/product", "reviews") 
}

# Endpoints that support date-based incremental filtering per Zid API docs
INCREMENTAL_SUPPORTED = ["Orders", "Abandoned_Carts"]

# Mapping for DB table and timestamp_col for incremental
INCREMENTAL_DB_MAP = {
    "Orders": ("zid_fact_orders", "updated_at"),
    "Abandoned_Carts": ("zid_fact_abandoned_carts", "updated_at")
}

# ==========================================
# 2. LOGGING CONFIGURATION
# ==========================================

logger = setup_logger(__name__)  # Use shared logger

# ==========================================
# 3. CORE FUNCTIONS
# ==========================================

def check_api_connection():
    """
    Performs a health check on the Zid API connection.
    Returns True if successful, False otherwise.
    """
    logger.info("Connecting to Zid API...")
    try:
        if not ZID_AUTHORIZATION_TOKEN or not ZID_MANAGER_TOKEN:
            logger.critical("Missing API tokens in .env file.")
            return False

        test_url = f"{BASE_URL}/managers/store/orders"
        response = requests.get(test_url, headers=HEADERS, params={"page": 1, "per_page": 1})
        
        if response.status_code == 200:
            logger.info("Connection established (HTTP 200).")
            return True
        else:
            logger.error(f"Connection failed. Status: {response.status_code}")
            return False
    except Exception as e:
        logger.critical(f"Connection error: {str(e)}")
        return False

def fetch_data_from_endpoint(category_name, endpoint_path, json_key, incremental=False):
    """
    Fetches all paginated data from a specific endpoint.
    Supports incremental mode for endpoints that allow date filtering.
    Returns a pandas DataFrame containing the raw records.
    """
    full_url = f"{BASE_URL}{endpoint_path}"
    all_records = []
    page = 1
    seen_ids = set()  # To prevent infinite loops
    
    logger.info(f"Starting extraction: {category_name} (Incremental: {incremental})")
    
    # Default dates
    now = datetime.utcnow()  # Use UTC for consistency with API
    start_date = "2020-01-01"
    
    # Incremental logic: Only for supported endpoints
    last_ts = None
    if incremental and category_name in INCREMENTAL_SUPPORTED:
        try:
            table_name, timestamp_col = INCREMENTAL_DB_MAP[category_name]
            last_ts = get_last_timestamp(table_name, timestamp_col)
            if last_ts:
                # Add 1 second to avoid duplicates
                last_ts += timedelta(seconds=1)
                start_date = last_ts.strftime("%Y-%m-%d")  # Base format
                logger.info(f"Incremental fetch from {start_date} based on last timestamp.")
            else:
                logger.warning(f"No last timestamp found for {category_name}. Falling back to full fetch.")
                incremental = False
        except ValueError as e:
            logger.warning(f"Incremental not supported for {category_name}: {str(e)}. Full fetch.")
            incremental = False
    else:
        if incremental:
            logger.info(f"Incremental mode requested but not supported for {category_name}. Performing full fetch.")
        incremental = False

    while True:
        try:
            params = {"page": page}
            
            # Endpoint-specific pagination and parameters
            # Product_Reviews typically uses 'per_page', so it falls into the else block
            if category_name in ["Products", "Abandoned_Carts"]:
                params["page_size"] = 100
            else:
                params["per_page"] = 100
            
            # Incremental date filters for supported endpoints
            if incremental:
                if category_name == "Orders":
                    # Per docs: ISO 8601 with timezone offset
                    params["date_from"] = last_ts.strftime("%Y-%m-%dT%H:%M:%S.000+0000")
                    params["date_to"] = now.strftime("%Y-%m-%dT%H:%M:%S.000+0000")
                    params["date_attribute"] = "updated_at"
                elif category_name == "Abandoned_Carts":
                    params["date_from"] = last_ts.strftime("%Y-%m-%d")
                    params["date_to"] = now.strftime("%Y-%m-%d")

            # Request detailed payload for complex objects
            if category_name in ["Orders", "Products"]:
                params["payload_type"] = "default"

            response = requests.get(full_url, headers=HEADERS, params=params)
            
            if response.status_code == 200:
                data = response.json()
                
                # Dynamic extraction of records
                batch = data.get(json_key, [])
                
                # Fallback for inconsistent response keys
                if not batch:
                    fallback_keys = ['abandoned-carts', 'abandoned_carts', 'products', 'results', 'reviews']
                    for key in fallback_keys:
                        if key in data:
                            batch = data[key]
                            break
                    if isinstance(data, list):
                        batch = data
                
                # Stop if no more records
                if not batch:
                    logger.info(f"Finished at page {page}.")
                    break
                
                # Loop protection: detect repeated IDs
                first_item_id = str(batch[0].get('id', 'unknown')) if batch and isinstance(batch[0], dict) else None
                if first_item_id and first_item_id != 'unknown':
                    if first_item_id in seen_ids and page > 1:
                        logger.warning(f"Infinite loop detected at page {page}. Stopping.")
                        break
                    for item in batch:
                        item_id = item.get('id')
                        if item_id is not None:
                            seen_ids.add(str(item_id))
                
                all_records.extend(batch)
                logger.info(f"Page {page}: {len(batch)} records fetched (Total: {len(all_records)})")
                
                page += 1
                time.sleep(0.1)  # Rate limit protection
                
            elif response.status_code == 404:
                logger.warning(f"404 Reached end of pagination for {category_name} at page {page}. Stopping safely.")
                break

            elif response.status_code == 422:
                logger.error("Unprocessable Entity (422). Check parameters.")
                break
            else:
                logger.error(f"API Error {response.status_code} at page {page}.")
                break
                
        except Exception as e:
            logger.critical(f"Runtime error: {str(e)}")
            break
            
    return pd.DataFrame(all_records)

# ==========================================
# 4. MAIN EXTRACTOR FUNCTION
# ==========================================

def extract_data(incremental=False):
    """
    Main entry point for extraction.
    Returns a dictionary of DataFrames: {'CategoryName': DataFrame, ...}
    """
    logger.info("=" * 50)
    logger.info("      ZID DATA EXTRACTION ENGINE STARTED")
    logger.info("=" * 50)

    # Check DB connection if incremental (for last timestamps)
    if incremental and not check_db_connection():
        logger.warning("DB connection failed. Falling back to full extraction.")
        incremental = False

    if not check_api_connection():
        return {}

    raw_data_catalog = {}

    for category, (path, key) in ENDPOINTS.items():
        df = fetch_data_from_endpoint(category, path, key, incremental=incremental)
        if not df.empty:
            raw_data_catalog[category] = df
        else:
            logger.warning(f"No data found for {category}")

    logger.info("=" * 50)
    logger.info("      EXTRACTION COMPLETED")
    logger.info("=" * 50)
    
    return raw_data_catalog

# ==========================================
# 5. EXECUTION ENTRY POINT
# ==========================================
if __name__ == "__main__":
    # For testing: Check env for incremental mode
    incremental = os.getenv("INCREMENTAL", "0") == "1"
    data = extract_data(incremental=incremental)
    for key, df in data.items():
        logger.info(f"DataFrame: {key} -> Shape: {df.shape}")
