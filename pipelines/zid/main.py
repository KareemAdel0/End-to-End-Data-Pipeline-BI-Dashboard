import os
from pipelines.zid.extract import extract_data
from pipelines.zid.transform import transform_data
from pipelines.zid.load import load_data

# Use shared logger
from shared.logger import setup_logger

logger = setup_logger(__name__)

def main(incremental=False):
    logger.info("=" * 50)
    logger.info(f"      ZID ETL PIPELINE STARTED (Incremental: {incremental})")
    logger.info("=" * 50)
    
    # Step 1: Extract raw data from Zid API
    raw_data_catalog = extract_data(incremental=incremental)
    
    # Step 2: Transform the raw data
    processed_data_catalog = transform_data(raw_data_catalog)
    
    # Step 3: Load transformed data into Supabase (with upsert)
    load_data(processed_data_catalog)
    
    logger.info("=" * 50)
    logger.info("      ETL PIPELINE COMPLETED")
    logger.info("=" * 50)

if __name__ == "__main__":
    # Check environment variable for incremental mode
    incremental = os.getenv("INCREMENTAL", "0") == "1"
    main(incremental=incremental)