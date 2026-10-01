"""CLI tests for adaptive-kwik calibrate v2."""

from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
CALIBRATE = ROOT / "calibrate.py"
FIXTURES = ROOT / "fixtures"


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CALIBRATE), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def _payload(proc: subprocess.CompletedProcess[str]) -> dict:
    assert proc.stdout, proc.stderr
    return json.loads(proc.stdout)


def test_fixture_python_only() -> None:
    proc = _cli(str(FIXTURES / "python-only"))
    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc)
    assert payload["calibrate_version"] == 2
    assert payload["priors"]["python"] is True
    assert payload["priors"]["instruction_surface"] is False
    assert "ruff" in payload["requires"]
    assert "lintlang" not in payload["requires"]
    proposal = tomllib.loads(payload["proposed_toml"])
    assert proposal["gate"]["fast_budget_seconds"] == 8.0
    assert "exclusions" in proposal["gate"]
    assert proposal["adapter"]["name"] == "native"
    assert proposal["lintlang"]["enabled"] is False
    assert proposal["review"]["provider"] == "coderabbit"
    assert proposal["fast"][0]["argv"] == ["ruff", "check", "{files}"]
    assert "intent-verify" not in payload["proposed_toml"]


def test_fixture_js_only_no_python_checks() -> None:
    proc = _cli(str(FIXTURES / "js-only"), "--dry-run")
    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc)
    assert payload["priors"]["python"] is False
    assert payload["priors"]["package_managers"] == ["npm"]
    assert payload["requires"] == []
    proposal = tomllib.loads(payload["proposed_toml"])
    assert "fast" not in proposal
    assert "full" not in proposal
    assert not (FIXTURES / "js-only" / ".hermes" / "gate.toml").exists()


def test_fixture_intent_surface_proposes_lintlang_and_intent_verify() -> None:
    proc = _cli(str(FIXTURES / "intent-surface"))
    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc)
    priors = payload["priors"]
    assert priors["instruction_surface"] is True
    assert "INTENT.md" in priors["instruction_files"]
    assert "AGENTS.md" in priors["instruction_files"]
    assert priors["skills_dir"] is True
    assert priors["intent_spec"] == "INTENT.md"
    assert "lintlang" in payload["requires"]
    assert "intent-verify" in payload["requires"]
    proposal = tomllib.loads(payload["proposed_toml"])
    # enabled only if tool available; presence of table is required
    assert "lintlang" in proposal
    assert proposal["lintlang"]["argv"][0] == "lintlang"
    full_names = [item["name"] for item in proposal.get("full", [])]
    assert "intent-verify" in full_names
    assert "lintlang-scan" in full_names
    assert "requires: intent-verify" in payload["proposed_toml"]
    assert "requires: lintlang" in payload["proposed_toml"]
    intent_check = next(item for item in proposal["full"] if item["name"] == "intent-verify")
    assert intent_check["argv"] == ["intent-verify", "check", "--spec", "INTENT.md"]


def test_fixture_mixed_python_and_intent() -> None:
    proc = _cli(str(FIXTURES / "mixed-python-intent"))
    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc)
    assert payload["priors"]["python"] is True
    assert payload["priors"]["intent_spec"] == "SPEC.md"
    assert set(payload["requires"]) >= {"ruff", "pytest", "lintlang", "intent-verify"}
    proposal = tomllib.loads(payload["proposed_toml"])
    full_names = [item["name"] for item in proposal["full"]]
    assert "python-test" in full_names
    assert "intent-verify" in full_names
    intent_check = next(item for item in proposal["full"] if item["name"] == "intent-verify")
    assert intent_check["argv"][-1] == "SPEC.md"


def test_dry_run_does_not_write(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\n', encoding="utf-8")
    hermes = tmp_path / ".hermes"
    hermes.mkdir()
    existing = hermes / "gate.toml"
    existing.write_text("owner bytes\n", encoding="utf-8")

    default = _cli(str(tmp_path))
    explicit = _cli(str(tmp_path), "--dry-run")

    assert default.returncode == 0, default.stderr
    assert explicit.returncode == 0, explicit.stderr
    assert existing.read_text(encoding="utf-8") == "owner bytes\n"
    assert _payload(default)["wrote"] is False
    assert _payload(default)["mode"] == "dry-run"
    assert _payload(default)["priors"]["gate_toml_exists"] is True


def test_write_creates_file(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text("pytest\n", encoding="utf-8")

    proc = _cli(str(tmp_path), "--write")
    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc)
    dest = tmp_path / ".hermes" / "gate.toml"

    assert payload["wrote"] is True
    assert dest.is_file()
    assert dest.read_text(encoding="utf-8") == payload["proposed_toml"]
    proposal = tomllib.loads(dest.read_text(encoding="utf-8"))
    assert proposal["gate"]["name"] == tmp_path.name
    assert list((tmp_path / ".hermes").glob("*.tmp")) == []


def test_refuse_overwrite_without_force(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\n', encoding="utf-8")
    dest = tmp_path / ".hermes" / "gate.toml"
    dest.parent.mkdir()
    dest.write_text("owner bytes\n", encoding="utf-8")

    proc = _cli(str(tmp_path), "--write")

    assert proc.returncode == 2
    assert dest.read_text(encoding="utf-8") == "owner bytes\n"
    payload = _payload(proc)
    assert payload["wrote"] is False
    assert payload["refused"] is True
    assert "without --force" in (payload["reason"] or "")


def test_force_overwrites_existing_gate(tmp_path: Path) -> None:
    (tmp_path / "setup.py").write_text("from setuptools import setup\nsetup()\n", encoding="utf-8")
    dest = tmp_path / ".hermes" / "gate.toml"
    dest.parent.mkdir()
    dest.write_text("owner bytes\n", encoding="utf-8")

    proc = _cli(str(tmp_path), "--write", "--force")

    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc)
    assert payload["wrote"] is True
    assert dest.read_text(encoding="utf-8") == payload["proposed_toml"]
    assert "owner bytes" not in dest.read_text(encoding="utf-8")


def test_proposal_loads_with_hermes_gate_config() -> None:
    """Schema check against shipping loader when hermes_gate is importable."""
    # docs/adaptive-calibrate/v2 -> repo root / src
    src = ROOT.parents[2] / "src"
    if not (src / "hermes_gate" / "config.py").is_file():
        # Fall back for out-of-tree spike checkouts
        src = Path("/workspace/kwik-e-gate/src")
    if not (src / "hermes_gate" / "config.py").is_file():
        pytest.skip("kwik-e-gate src not present")
    proc = _cli(str(FIXTURES / "mixed-python-intent"))
    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc)
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        hermes = root / ".hermes"
        hermes.mkdir()
        (hermes / "gate.toml").write_text(payload["proposed_toml"], encoding="utf-8")
        sys.path.insert(0, str(src))
        try:
            from hermes_gate.config import load_config

            config = load_config(root)
        finally:
            sys.path.pop(0)
        assert config.fast_budget_seconds == 8.0
        assert any(cmd.name == "python-ruff" for cmd in config.fast)
        assert any(cmd.name == "intent-verify" for cmd in config.full)
        assert config.review.provider == "coderabbit"
