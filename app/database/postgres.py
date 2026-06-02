import os
import ssl as ssl_module
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

def get_postgres_engine(database_url: str):
    if not database_url:
        print(" DATABASE_URL not found in environment variables.")
        raise RuntimeError("DATABASE_URL is missing!")

    # Fix for Railway/Heroku postgres:// vs postgresql:// and adding asyncpg driver
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    # Robustly remove incompatible query params for asyncpg (sslmode, channel_binding, etc.)
    ASYNCPG_INCOMPATIBLE_PARAMS = {"sslmode", "channel_binding"}
    if "?" in database_url:
        base_url, query_str = database_url.split("?", 1)
        params = [p for p in query_str.split("&") if p.split("=")[0] not in ASYNCPG_INCOMPATIBLE_PARAMS]
        database_url = base_url + ("?" + "&".join(params) if params else "")

    # Masked URL for logging
    masked_url = database_url
    if "@" in masked_url:
        prefix, suffix = masked_url.split("@", 1)
        if ":" in prefix:
            proto_user, _ = prefix.rsplit(":", 1)
            masked_url = f"{proto_user}:****@{suffix}"

    print(f"[DB] Attempting PostgreSQL connection to: {masked_url}")

    ssl_ctx = ssl_module.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl_module.CERT_NONE

    engine = create_async_engine(
        database_url,
        echo=False,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=10,
        max_overflow=20,
        pool_timeout=30,
        connect_args={"ssl": ssl_ctx}
    )

    async_session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    return engine, async_session_maker
