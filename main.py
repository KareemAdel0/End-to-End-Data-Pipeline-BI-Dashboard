import os
from pipelines.zid.main import main as zid_main  # Import Zid ETL main
from pipelines.daftara.main import main as daftra_main # Import daftra ETL main

# Use shared logger
from shared.logger import setup_logger

logger = setup_logger(__name__)

def main():
    logger.info("=" * 50)
    logger.info("      FULL ETL PIPELINE STARTED")
    logger.info("=" * 50)
    
    # Determine incremental mode from environment variable
    incremental = os.getenv("INCREMENTAL", "0") == "1"
    
    # Run Zid ETL pipeline
    zid_main(incremental=incremental)
    
    # Run Daftra ETL
    daftra_main(incremental=incremental)
    
    logger.info("=" * 50)
    logger.info("      ETL PIPELINE COMPLETED")
    logger.info("=" * 50)

if __name__ == "__main__":

    main()


