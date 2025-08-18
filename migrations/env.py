# migrations/env.py
import os
from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool

# Alembic Config object (provides access to values in alembic.ini)
config = context.config

# Configure Python logging using the alembic.ini file
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import project models to get the Base metadata for autogenerate support
# Important: run Alembic commands from the repo root so "backend" is importable
try:
    from backend import models as project_models
except ModuleNotFoundError:
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from backend import models as project_models

# Use SQLAlchemy metadata from project Base
target_metadata = project_models.Base.metadata

# Database URL (synchronous driver for Alembic, psycopg2)
SYNC_DATABASE_URL = os.environ.get("SYNC_DATABASE_URL") or os.environ.get("DATABASE_URL")
if SYNC_DATABASE_URL:
    config.set_main_option("sqlalchemy.url", SYNC_DATABASE_URL)


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.
    Generates SQL scripts without connecting to a database.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.
    Connects to the database and applies migrations directly.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
