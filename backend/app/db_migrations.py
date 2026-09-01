from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def _add_column_if_missing(connection, table: str, column: str, definition: str, existing: set[str]) -> None:
    if column not in existing:
        connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))


def ensure_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    if "imports" in tables:
        columns = {column["name"] for column in inspector.get_columns("imports")}
        with engine.begin() as connection:
            _add_column_if_missing(connection, "imports", "reference_year", "INTEGER", columns)
            _add_column_if_missing(connection, "imports", "reference_month", "INTEGER", columns)
            _add_column_if_missing(connection, "imports", "source", "VARCHAR(20) DEFAULT 'csv'", columns)

    if "activities" in tables:
        columns = {column["name"] for column in inspector.get_columns("activities")}
        with engine.begin() as connection:
            _add_column_if_missing(
                connection,
                "activities",
                "activity_category",
                "VARCHAR(200)",
                columns,
            )
            _add_column_if_missing(connection, "activities", "source", "VARCHAR(20) DEFAULT 'csv'", columns)
