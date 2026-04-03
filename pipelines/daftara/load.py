import pandas as pd
from psycopg2.extras import execute_values

from shared.db_utils import engine, check_db_connection
from shared.logger import setup_logger

# ----------------------------------
# Logger
# ----------------------------------
logger = setup_logger(__name__)


# ----------------------------------
# Core Loader
# ----------------------------------
def load_dataframe(df: pd.DataFrame, table_name: str, conn):
    if df is None or df.empty:
        logger.info(f"[SKIP] {table_name} is empty")
        return

    df = df.copy()

    # Clean NaNs / invalid values
    df = df.replace([pd.NA, float("nan"), float("inf"), float("-inf")], None)
    df = df.replace("", None)

    columns = list(df.columns)

    if "id" not in columns:
        raise Exception(f"{table_name} has no id column (required for upsert)")

    values = [tuple(row) for row in df.to_numpy()]
    update_columns = [c for c in columns if c != "id"]

    insert_query = f"""
        INSERT INTO {table_name} ({",".join(columns)})
        VALUES %s
        ON CONFLICT (id) DO UPDATE SET
        {",".join([f"{c}=EXCLUDED.{c}" for c in update_columns])}
    """

    cursor = conn.cursor()
    try:
        execute_values(cursor, insert_query, values, page_size=1000)
        conn.commit()
        logger.info(f"[LOADED] {table_name} | rows={len(df)}")
    except Exception:
        conn.rollback()
        logger.exception(f"[FAILED] {table_name}")
        raise
    finally:
        cursor.close()


# ----------------------------------
# Public API
# ----------------------------------
def load_data(processed_data_catalog: dict[str, pd.DataFrame]):
    logger.info("=" * 50)
    logger.info("      DAFTRA DATA LOAD STARTED")
    logger.info("=" * 50)

    if not check_db_connection():
        logger.critical("DB connection failed. Load aborted.")
        return

    conn = engine.raw_connection()

    try:
        for entity, df in processed_data_catalog.items():
            table_name = entity  # entity already like daftra_invoice
            try:
                load_dataframe(df, table_name, conn)
            except Exception:
                # already logged inside load_dataframe
                continue
    finally:
        conn.close()
        logger.info("DB connection closed.")

    logger.info("=" * 50)
    logger.info("      DAFTRA DATA LOAD COMPLETED")
    logger.info("=" * 50)
