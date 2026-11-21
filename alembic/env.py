
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Konfigurasi Alembic
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Mengambil Base dari database
from app.database import Base

# Mendaftarkan semua model database
import app.models

# Metadata seluruh tabel
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Menjalankan migrasi tanpa koneksi langsung."""

    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Menjalankan migrasi menggunakan koneksi database."""

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
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
