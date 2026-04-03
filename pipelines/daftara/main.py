import os
from pipelines.daftara.extract import DaftraExtractor
from pipelines.daftara.transform import DaftraTransformer
from pipelines.daftara.load import load_data

# Shared logger
from shared.logger import setup_logger

logger = setup_logger(__name__)


def main(incremental: bool = True):
    logger.info("=" * 50)
    logger.info("      DAFTARA ETL PIPELINE STARTED")
    logger.info("=" * 50)

    try:
        # -------------------------
        # Step 1: Extract
        # -------------------------
        logger.info("Starting extraction from Daftra API...")
        extractor = DaftraExtractor()

        # NOTE:
        # incremental flag currently not used directly here
        # Daftra incremental is handled internally via etl_state
        raw_data_catalog = extractor.extract_all()

        logger.info(
            f"Extraction completed. Entities extracted: {list(raw_data_catalog.keys())}"
        )

        if not raw_data_catalog:
            logger.warning("No data extracted from Daftra. Pipeline will stop.")
            return

        # -------------------------
        # Step 2: Transform
        # -------------------------
        logger.info("Starting transformation...")
        transformer = DaftraTransformer()

        processed_data_catalog = transformer.transform_all(raw_data_catalog)

        logger.info(
            f"Transformation completed. Tables ready for load: {list(processed_data_catalog.keys())}"
        )

        if not processed_data_catalog:
            logger.warning("No transformed data available. Pipeline will stop.")
            return

        # -------------------------
        # Step 3: Load
        # -------------------------
        logger.info("Starting load to database...")
        load_data(processed_data_catalog)

        logger.info("Load completed successfully.")

    except Exception as e:
        logger.exception(f"DAFTARA ETL PIPELINE FAILED: {str(e)}")
        raise

    finally:
        logger.info("=" * 50)
        logger.info("      DAFTARA ETL PIPELINE COMPLETED")
        logger.info("=" * 50)


if __name__ == "__main__":
    # Daftra extraction is incremental by default (handled via etl_state)
    incremental = os.getenv("INCREMENTAL", "1") == "1"
    main(incremental=incremental)
