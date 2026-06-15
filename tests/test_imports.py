"""Python 3.14 compatibility smoke test (research R9 gate)."""
import importlib


REQUIRED_MODULES = [
    "fastapi",
    "sqlalchemy",
    "alembic",
    "pydantic",
    "pydantic_settings",
    "pandas",
    "numpy",
    "streamlit",
    "mcp",
    "argon2",
    "jwt",
    "httpx",
    "structlog",
    "apscheduler",
    "plaid",
    "yaml",
    "psycopg",
]


def test_all_required_modules_importable() -> None:
    failed = []
    for module in REQUIRED_MODULES:
        try:
            importlib.import_module(module)
        except ImportError as exc:
            failed.append(f"{module}: {exc}")
    assert not failed, "Import failures on Python 3.14:\n" + "\n".join(failed)
