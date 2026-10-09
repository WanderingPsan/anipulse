"""Checks that the Docker and Render config files agree with the rest of the repo.

These files only run on other machines (Docker, Render), so a mistake in them would show up
late. Plain text checks catch the easy ones here, with no extra dependency.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_dockerfile_python_matches_python_version_file() -> None:
    """Bumping .python-version without the Dockerfile would run two different Pythons."""
    match = re.search(r"^ARG PYTHON_VERSION=(\S+)$", read("Dockerfile"), re.MULTILINE)
    assert match is not None
    assert match.group(1) == read(".python-version").strip()


def test_render_yaml_matches_the_spec() -> None:
    render = read("render.yaml")
    assert "buildCommand: pip install -r api/requirements.txt" in render
    assert "startCommand: uvicorn api.main:app --host 0.0.0.0 --port $PORT" in render
    assert "healthCheckPath: /health" in render
    assert "plan: free" in render


def test_render_yaml_takes_python_from_the_version_file() -> None:
    """A PYTHON_VERSION env var would override .python-version on Render."""
    settings = [
        line for line in read("render.yaml").splitlines() if not line.lstrip().startswith("#")
    ]
    assert not any("PYTHON_VERSION" in line for line in settings)


def test_dockerignore_never_lets_env_through() -> None:
    lines = [line.strip() for line in read(".dockerignore").splitlines()]
    rules = [line for line in lines if line and not line.startswith("#")]
    assert rules[0] == "*"
    assert not any(rule.startswith("!") and ".env" in rule for rule in rules)
