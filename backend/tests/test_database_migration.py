"""
Tests for additive schema migration.

These exist because adding a column to a model used to mean deleting the
database -- and every evaluation stored in it. Adding a column must never
cost a user their data again.
"""

import sqlite3

import pytest
from sqlalchemy import Column, MetaData, String, Table, create_engine, inspect, text

from src.core import database as db_module


@pytest.fixture
def sqlite_db(tmp_path, monkeypatch):
    """Point the database module at a throwaway SQLite file."""
    path = tmp_path / "migrate.db"
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    monkeypatch.setattr(db_module, "engine", engine)
    return path, engine


def test_adds_a_missing_column_without_touching_existing_rows(sqlite_db, monkeypatch):
    """
    The exact scenario that caused data loss: a table exists with rows, the
    model gains a new nullable column, and startup must add the column in
    place rather than requiring the file be deleted.
    """
    path, engine = sqlite_db

    # A table that predates the new column, holding real data.
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE widgets (id TEXT PRIMARY KEY, name TEXT)"))
        conn.execute(text("INSERT INTO widgets VALUES ('1', 'precious data')"))

    # The model now declares an extra column.
    metadata = MetaData()
    Table(
        "widgets", metadata,
        Column("id", String, primary_key=True),
        Column("name", String),
        Column("comparison_id", String, nullable=True),
    )
    monkeypatch.setattr(db_module.Base, "metadata", metadata)

    db_module._add_missing_columns()

    columns = {c["name"] for c in inspect(engine).get_columns("widgets")}
    assert "comparison_id" in columns

    # The whole point: the pre-existing row is still there.
    rows = list(sqlite3.connect(path).execute("SELECT id, name FROM widgets"))
    assert rows == [("1", "precious data")]


def test_is_idempotent(sqlite_db, monkeypatch):
    """Running twice must not fail with 'duplicate column'."""
    path, engine = sqlite_db

    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE widgets (id TEXT PRIMARY KEY)"))
        conn.execute(text("INSERT INTO widgets VALUES ('1')"))

    metadata = MetaData()
    Table(
        "widgets", metadata,
        Column("id", String, primary_key=True),
        Column("extra", String, nullable=True),
    )
    monkeypatch.setattr(db_module.Base, "metadata", metadata)

    db_module._add_missing_columns()
    db_module._add_missing_columns()  # would raise if not guarded

    rows = list(sqlite3.connect(path).execute("SELECT id FROM widgets"))
    assert rows == [("1",)]


def test_leaves_matching_schema_untouched(sqlite_db, monkeypatch):
    path, engine = sqlite_db

    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE widgets (id TEXT PRIMARY KEY, name TEXT)"))
        conn.execute(text("INSERT INTO widgets VALUES ('1', 'unchanged')"))

    metadata = MetaData()
    Table("widgets", metadata,
          Column("id", String, primary_key=True),
          Column("name", String))
    monkeypatch.setattr(db_module.Base, "metadata", metadata)

    db_module._add_missing_columns()

    rows = list(sqlite3.connect(path).execute("SELECT id, name FROM widgets"))
    assert rows == [("1", "unchanged")]


def test_refuses_to_guess_at_a_non_nullable_column(sqlite_db, monkeypatch):
    """
    A NOT NULL column can't be backfilled for existing rows. Raising beats
    silently skipping it and leaving the schema subtly wrong.
    """
    path, engine = sqlite_db

    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE widgets (id TEXT PRIMARY KEY)"))

    metadata = MetaData()
    Table("widgets", metadata,
          Column("id", String, primary_key=True),
          Column("required", String, nullable=False))
    monkeypatch.setattr(db_module.Base, "metadata", metadata)

    with pytest.raises(RuntimeError, match="manual migration"):
        db_module._add_missing_columns()
