import os
import time
import schedule

from pipelines.zid.main import main as zid_main
from pipelines.daftarah.main import main as daftra_main

from shared.logger import setup_logger

logger = setup_logger(__name__)


def run_incremental_etl():
    """
    Run Zid + Daftra ETL pipelines in incremental mode.
    """
    logger.info("=" * 50)
    logger.info("Starting scheduled incremental ETL run...")
    logger.info("=" * 50)

    os.environ["INCREMENTAL"] = "1" # Set env var for incremental mode (shared)

    try:
        # Run Zid ETL
        logger.info("Running Zid incremental ETL...")
        zid_main(incremental=True)

        # Run Daftra ETL
        logger.info("Running Daftra incremental ETL...")
        daftra_main(incremental=True)

        logger.info("Incremental ETL run completed successfully.")

    except Exception as e:
        logger.exception(f"Incremental ETL run failed: {e}")

    logger.info("=" * 50)


if __name__ == "__main__":
    # Run every 12 hours
    schedule.every(12).hours.do(run_incremental_etl)

    logger.info("Local incremental scheduler started. Press Ctrl+C to exit.")

    while True:
        schedule.run_pending()
        time.sleep(60)
