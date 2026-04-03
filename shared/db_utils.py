import os
import sqlalchemy as sa
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Database credentials from .env
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# Create SQLAlchemy engine (shared across the pipeline)
connection_string = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = sa.create_engine(connection_string)

def check_db_connection():
    """Test Supabase connection."""
    try:
        with engine.connect() as conn:
            conn.execute(sa.text("SELECT 1"))
        return True
    except Exception as e:
        print(f"DB connection error: {str(e)}")  # Use print or logger; import if needed
        return False

def get_last_timestamp(table_name: str, timestamp_col: str, default_date: str = "2020-01-01T00:00:00") -> datetime:
    """
    Query Supabase for the max timestamp in the specified table and column.
    Returns datetime object or default if table/column not found or error.
    """
    if not check_db_connection():
        return datetime.fromisoformat(default_date)
    
    try:
        with engine.connect() as conn:
            # Check if table exists
            if not sa.inspect(engine).has_table(table_name):
                raise ValueError(f"Table {table_name} does not exist.")
            
            query = sa.text(f"SELECT MAX({timestamp_col}) FROM {table_name}")
            result = conn.execute(query).scalar()
            if result:
                # Assume timestamp is datetime; parse if string
                if isinstance(result, str):
                    return datetime.fromisoformat(result.replace('Z', '+00:00'))  # Handle ISO with Z
                return result
            return datetime.fromisoformat(default_date)
    except Exception as e:
        print(f"Error querying last timestamp for {table_name}: {str(e)}")
        return datetime.fromisoformat(default_date)
