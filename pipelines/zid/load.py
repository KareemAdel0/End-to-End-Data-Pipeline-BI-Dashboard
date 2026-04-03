import pandas as pd
import sqlalchemy as sa
import os
from dotenv import load_dotenv
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import inspect, MetaData

# Import shared utilities
from shared.db_utils import engine, check_db_connection  # Reuse shared engine and connection check
from shared.logger import setup_logger  # Shared logger setup

# ==========================================
# 1. LOGGING CONFIGURATION
# ==========================================

logger = setup_logger(__name__)  # Use shared logger

# ==========================================
# 2. SETUP & CONFIGURATION
# ==========================================

load_dotenv()

# Database credentials are already loaded in db_utils; no need to reload here

# Upsert configuration: table_name -> list of primary key columns
UPSERT_CONFIG = {
    "zid_dim_categories_main": ["category_id"],
    "zid_dim_categories_subs": ["sub_category_id"],
    "zid_dim_products": ["product_id"],
    "zid_bridge_product_categories": ["product_id", "category_id", "sub_category_id"],
    "zid_fact_product_stocks": ["product_id", "location_id"],
    "zid_dim_customers": ["customer_id"],
    "zid_fact_orders": ["order_id"],
    "zid_fact_order_shipping": ["order_id"],
    "zid_fact_order_items": ["order_id", "product_id"],
    "zid_dim_locations": ["location_id"],
    "zid_dim_shipping_methods": ["shipping_method_id"],
    "zid_bridge_shipping_cities": ["shipping_method_id", "city_id"],
    "zid_fact_abandoned_carts": ["abandoned_carts_id"],
    "zid_dim_coupons": ["coupon_id"],
    # New Table Added
    "zid_fact_product_reviews": ["review_id"]
}

# Batch size for loading to avoid timeouts
BATCH_SIZE = 500

# ==========================================
# 3. CORE FUNCTIONS
# ==========================================

def batch_upsert(engine, table, data, pk_columns):
    """
    Perform upsert in batches to avoid timeouts.
    """
    # Create the update dictionary: update all columns EXCEPT the Primary Keys
    update_dict = {
        col.name: getattr(insert(table).excluded, col.name)
        for col in table.columns
        if col.name not in pk_columns
    }
    
    for i in range(0, len(data), BATCH_SIZE):
        batch = data[i:i + BATCH_SIZE]
        insert_stmt = insert(table).values(batch)
        
        if update_dict:
            # Upsert: Update if conflict
            upsert_stmt = insert_stmt.on_conflict_do_update(
                index_elements=pk_columns,
                set_=update_dict
            )
        else:
            # If no columns to update (only PK table), just skip duplicates
            upsert_stmt = insert_stmt.on_conflict_do_nothing(index_elements=pk_columns)
        
        with engine.connect() as conn:
            conn.execute(upsert_stmt)
            conn.commit()
        logger.debug(f"Upserted batch {i//BATCH_SIZE + 1} for table {table.name}")

# ==========================================
# 4. MAIN LOADER FUNCTION
# ==========================================

def load_data(processed_data_catalog):
    logger.info("=" * 50)
    logger.info("      DATA LOADING ENGINE STARTED")
    logger.info("=" * 50)

    if not check_db_connection():
        return

    inspector = inspect(engine)

    for table_name, df in processed_data_catalog.items():
        if df is None or df.empty:
            logger.warning(f"No data to load for table: {table_name}")
            continue

        pk_columns = UPSERT_CONFIG.get(table_name, [])
        
        # Scenario A: No PK defined -> Full Replace (Truncate & Load)
        if not pk_columns:
            logger.warning(f"No upsert config for {table_name}. Performing Full Replace.")
            try:
                df.to_sql(table_name, engine, if_exists='replace', index=False, chunksize=BATCH_SIZE)
                logger.info(f"Loaded (replace) {len(df)} rows into table: {table_name}")
            except Exception as e:
                logger.error(f"Error loading (replace) table {table_name}: {str(e)}")
            continue
        
        # Scenario B: Upsert Logic
        has_table = inspector.has_table(table_name)
        
        try:
            if not has_table:
                # Handle duplicates within the dataframe itself before initial load
                duplicates = df.duplicated(subset=pk_columns).sum()
                if duplicates > 0:
                    logger.warning(f"Found {duplicates} duplicate rows based on PK in {table_name}. Keeping last occurrence.")
                    df = df.drop_duplicates(subset=pk_columns, keep='last')
                
                # 1. Create table and insert data (First Run)
                df.to_sql(table_name, engine, index=False, chunksize=BATCH_SIZE)
                logger.info(f"Created table {table_name} and inserted {len(df)} rows")
                
                # Add primary key constraint
                try:
                    pk_str = ', '.join(pk_columns)
                    with engine.begin() as conn:
                        conn.execute(sa.text(f"ALTER TABLE {table_name} ADD PRIMARY KEY ({pk_str})"))
                    logger.info(f"Added primary key constraint to {table_name}")
                except Exception as pk_e:
                    logger.error(f"Failed to add PK to {table_name}: {str(pk_e)}. Table created without PK.")
            
            else:
                # 2. Check for Schema Drift (Columns Mismatch)
                existing_columns = [col['name'] for col in inspector.get_columns(table_name)]
                
                # Check if we have new columns in DataFrame that aren't in DB
                if set(df.columns) != set(existing_columns):
                    logger.warning(f"Schema mismatch detected for {table_name}. Recreating table to sync schema...")
                    logger.info(f"Mismatch: {set(df.columns) ^ set(existing_columns)}")
                    
                    # Drop and Recreate
                    with engine.begin() as conn:
                        conn.execute(sa.text(f"DROP TABLE IF EXISTS {table_name} CASCADE"))
                    
                    # Handle duplicates before load
                    duplicates = df.duplicated(subset=pk_columns).sum()
                    if duplicates > 0:
                        logger.warning(f"Found {duplicates} duplicate rows based on PK in {table_name}. Keeping last occurrence.")
                        df = df.drop_duplicates(subset=pk_columns, keep='last')
                    
                    df.to_sql(table_name, engine, index=False, chunksize=BATCH_SIZE)
                    logger.info(f"Recreated table {table_name} and inserted {len(df)} rows")
                    
                    # Re-apply PK
                    try:
                        pk_str = ', '.join(pk_columns)
                        with engine.begin() as conn:
                            conn.execute(sa.text(f"ALTER TABLE {table_name} ADD PRIMARY KEY ({pk_str})"))
                        logger.info(f"Re-applied primary key constraint to {table_name}")
                    except Exception as pk_e:
                        logger.error(f"Failed to add PK to {table_name}: {str(pk_e)}. Table recreated without PK.")
                    
                    continue  # Skip upsert logic since we just recreated

                # 3. Handle duplicates before upsert
                duplicates = df.duplicated(subset=pk_columns).sum()
                if duplicates > 0:
                    logger.warning(f"Found {duplicates} duplicate rows based on PK in {table_name}. Keeping last occurrence.")
                    df = df.drop_duplicates(subset=pk_columns, keep='last')

                # 4. Perform Upsert (If Schema Matches)
                data = df.to_dict(orient='records')
                if not data:
                    continue
                
                meta = MetaData()
                table = sa.Table(table_name, meta, autoload_with=engine)
                
                batch_upsert(engine, table, data, pk_columns)
                logger.info(f"Upserted {len(df)} rows into table: {table_name}")
        
        except Exception as e:
            logger.error(f"Error loading table {table_name}: {str(e)}")

    logger.info("=" * 50)
    logger.info("      LOADING COMPLETED")
    logger.info("=" * 50)

# ==========================================
# 5. EXECUTION ENTRY POINT (FOR TESTING)
# ==========================================
if __name__ == "__main__":
    # For testing: Assume processed_data_catalog is provided or empty
    load_data({})
