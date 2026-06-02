import os
import sys
import asyncio
from dotenv import load_dotenv
from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker

# Add app to path to import models
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

def sync_migrate():
    # PostgreSQL URL (synchronous, use psycopg2)
    pg_url = os.getenv("DATABASE_URL")
    if not pg_url:
        print("Error: DATABASE_URL not found in .env")
        return

    # Replace asyncpg with psycopg2 for the synchronous script
    if "postgresql+asyncpg" in pg_url:
        pg_url = pg_url.replace("postgresql+asyncpg", "postgresql+psycopg2")
    elif pg_url.startswith("postgres://"):
        pg_url = pg_url.replace("postgres://", "postgresql+psycopg2://", 1)

    # Handle psycopg2 ssl parameter
    if "?ssl=require" in pg_url:
        pg_url = pg_url.replace("?ssl=require", "?sslmode=require")

    print(f"Connecting to PostgreSQL: {pg_url}")
    pg_engine = create_engine(pg_url)
    pg_meta = MetaData()
    pg_meta.reflect(bind=pg_engine)

    # SQLite URL (synchronous)
    sqlite_url = "sqlite:///./etzan.db"
    print(f"Connecting to SQLite: {sqlite_url}")
    sqlite_engine = create_engine(sqlite_url)
    
    # Initialize SQLite Schema using the app's Base
    from app.database.base import Base
    from app.auth.models import User
    from app.models.history import AssessmentHistory
    from app.models.payment import PaymentRecord
    from app.models.settings import SystemSetting
    from app.models.question import AssessmentQuestion
    from app.models.letter_guidance import LetterGuidance
    from app.models.device_token import UserDeviceToken
    from app.models.notification import NotificationLog
    from app.models.subscription import UserSubscription

    # Force UUID to render as CHAR(32) in SQLite to avoid NUMERIC affinity issues
    from sqlalchemy.ext.compiler import compiles
    from sqlalchemy import UUID
    @compiles(UUID, 'sqlite')
    def compile_uuid_sqlite(type_, compiler, **kw):
        return "CHAR(32)"

    print("Creating SQLite tables...")
    Base.metadata.create_all(sqlite_engine)

    # Migrate data table by table
    pg_conn = pg_engine.connect()
    sqlite_conn = sqlite_engine.connect()

    sqlite_meta = MetaData()
    sqlite_meta.reflect(bind=sqlite_engine)

    for table_name, table in pg_meta.tables.items():
        if table_name not in sqlite_meta.tables:
            print(f"Skipping table {table_name} as it is not in SQLite schema.")
            continue
            
        print(f"Migrating table: {table_name}...")
        
        # Read all rows from PostgreSQL
        pg_rows = pg_conn.execute(table.select()).fetchall()
        
        if not pg_rows:
            print(f"  No rows in {table_name}.")
            continue
            
        print(f"  Found {len(pg_rows)} rows. Inserting into SQLite...")
        
        # We use sqlite_meta.tables[table_name] to get the target table
        sqlite_table = sqlite_meta.tables[table_name]
        
        import uuid
        import json
        
        records = []
        for row in pg_rows:
            record = dict(zip(table.columns.keys(), row))
            for k, v in record.items():
                if isinstance(v, uuid.UUID):
                    record[k] = str(v)
                elif isinstance(v, (dict, list)):
                    record[k] = json.dumps(v)
            records.append(record)
        
        try:
            sqlite_conn.execute(sqlite_table.insert(), records)
            sqlite_conn.commit()
            print(f"  Successfully migrated {table_name}.")
        except Exception as e:
            print(f"  Error migrating {table_name}: {e}")

    pg_conn.close()
    sqlite_conn.close()
    print("Migration complete!")

if __name__ == "__main__":
    sync_migrate()
