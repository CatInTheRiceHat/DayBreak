from pathlib import Path

from core.database import DEFAULT_DATABASE_PATH, PROJECT_ROOT, resolve_database_path


def test_default_database_path_is_project_root_db(monkeypatch):
    monkeypatch.delenv("DATABASE_PATH", raising=False)
    assert resolve_database_path() == DEFAULT_DATABASE_PATH
    assert resolve_database_path().parent == PROJECT_ROOT


def test_relative_database_path_resolves_from_project_root(monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", "tmp/dev.db")
    assert resolve_database_path() == PROJECT_ROOT / "tmp/dev.db"


def test_absolute_database_path_is_preserved(monkeypatch, tmp_path):
    db_path = tmp_path / "custom.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    assert resolve_database_path() == Path(db_path)
