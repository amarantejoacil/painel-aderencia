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

    if "azure_devops_settings" in tables:
        columns = {column["name"] for column in inspector.get_columns("azure_devops_settings")}
        with engine.begin() as connection:
            _add_column_if_missing(connection, "azure_devops_settings", "projects", "JSONB", columns)
            _add_column_if_missing(
                connection,
                "azure_devops_settings",
                "completed_hours_field",
                "VARCHAR(200)",
                columns,
            )
            _add_column_if_missing(
                connection,
                "azure_devops_settings",
                "ignored_assignees",
                "JSONB",
                columns,
            )
            _add_column_if_missing(
                connection,
                "azure_devops_settings",
                "ignored_project_scope_keys",
                "JSONB",
                columns,
            )

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

    if "issue_audit_queries" in tables:
        columns = {column["name"] for column in inspector.get_columns("issue_audit_queries")}
        with engine.begin() as connection:
            _add_column_if_missing(connection, "issue_audit_queries", "profile_id", "VARCHAR(80)", columns)
            _add_column_if_missing(connection, "issue_audit_queries", "state_filter", "VARCHAR(200)", columns)
            _add_column_if_missing(connection, "issue_audit_queries", "period_start", "DATE", columns)
            _add_column_if_missing(connection, "issue_audit_queries", "period_end", "DATE", columns)

    if "collaborator_absences" in tables:
        columns = {column["name"] for column in inspector.get_columns("collaborator_absences")}
        with engine.begin() as connection:
            _add_column_if_missing(
                connection,
                "collaborator_absences",
                "excused_hours",
                "NUMERIC(6, 2)",
                columns,
            )
