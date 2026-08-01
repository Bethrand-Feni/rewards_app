from __future__ import annotations

import ast
import re
from pathlib import Path


APP = Path(__file__).parents[1] / "app"
SQL = re.compile(
    r"\b(SELECT\b[\s\S]{0,500}\bFROM|INSERT\s+INTO|"
    r"UPDATE\s+\w+\s+SET|DELETE\s+FROM)\b",
    re.IGNORECASE,
)


def python_files(directory: str) -> list[Path]:
    return sorted((APP / directory).glob("*.py"))


def test_routes_do_not_import_repositories() -> None:
    for path in python_files("routes"):
        tree = ast.parse(path.read_text())
        imports = [
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        ]
        assert not any("repositories" in module for module in imports), path


def test_transport_and_services_do_not_contain_sql_literals() -> None:
    paths = [
        APP / "main.py",
        APP / "dependencies.py",
        *python_files("routes"),
        *python_files("services"),
    ]
    for path in paths:
        tree = ast.parse(path.read_text())
        sql_literals = [
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and SQL.search(node.value)
        ]
        assert sql_literals == [], path


def test_direct_d1_binding_access_is_confined_to_db_adapter() -> None:
    offenders: list[Path] = []
    for path in APP.rglob("*.py"):
        if path.name == "db.py":
            continue
        source = path.read_text()
        if ".DB.prepare(" in source or ".DB.batch(" in source:
            offenders.append(path)
    assert offenders == []


def test_repository_sql_uses_numbered_parameters() -> None:
    bare_parameter = re.compile(r"(?<!\?)\?(?!\d)")
    for path in python_files("repositories"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and SQL.search(node.value)
            ):
                continue
            assert not bare_parameter.search(node.value), (
                path,
                node.value,
            )


def test_main_is_wiring_only() -> None:
    source = (APP / "main.py").read_text()
    assert "Database(" not in source
    assert len(source.splitlines()) < 180
