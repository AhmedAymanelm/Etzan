import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

def get_sqlite_engine(database_url: str):
    if not database_url:
        print(" SQLITE_URL not found in environment variables.")
        raise RuntimeError("SQLITE_URL is missing!")

    print(f"[DB] Attempting SQLite connection to: {database_url}")

    engine = create_async_engine(
        database_url,
        echo=False,
        # pool_pre_ping is useful for remote, but safe to leave
        # SQLite doesn't strictly need these pool settings but we can leave safe defaults
    )

    async_session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    return engine, async_session_maker
