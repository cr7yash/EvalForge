from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
from .config import get_settings

settings = get_settings()

# Create SQLAlchemy engine
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency for getting database session.

    Usage:
        @app.get("/items")
        def get_items(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _add_missing_columns() -> None:
    """
    Add columns that exist on the models but not yet in the database.

    ``create_all`` creates missing *tables* but never alters existing ones,
    so adding a column to a model used to mean deleting the database and
    losing every stored evaluation. SQLite supports ``ADD COLUMN`` for
    nullable columns, which is all the schema has ever needed, so new
    columns can be applied in place instead.

    Only ever adds; nothing here drops or rewrites existing data.
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as connection:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue  # create_all handles brand-new tables

            present = {col["name"] for col in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in present:
                    continue
                if not column.nullable and column.default is None:
                    # Can't backfill a NOT NULL column for existing rows;
                    # surface it rather than silently skipping.
                    raise RuntimeError(
                        f"Cannot auto-add non-nullable column "
                        f"'{table.name}.{column.name}' to an existing table. "
                        f"A manual migration is required."
                    )
                col_type = column.type.compile(dialect=engine.dialect)
                connection.execute(
                    text(f'ALTER TABLE {table.name} ADD COLUMN {column.name} {col_type}')
                )


def init_db() -> None:
    """Initialize database (create tables, then apply additive migrations)."""
    Base.metadata.create_all(bind=engine)
    _add_missing_columns()
