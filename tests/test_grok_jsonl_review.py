"""The Hermes Grok adapter must send only the selected local patch via OAuth."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from hermes_gate.grok_review import (
    API_KEY_ENV_VARS,
    VERSION,
    _fixture_diff,
    _parse_envelope,
    _review,
    _selected_diff,
    _validate_findings,
    main,
)
from hermes_gate.gitstate import scope_paths


def test_version_flag(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(sys, "argv", ["hermes-gate-grok-review", "--version"])
    assert main() == 0
    assert capsys.readouterr().out.strip() == VERSION


def test_usage_rejects_extra_args(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["hermes-gate-grok-review", "--diff-file", "x"])
    assert main() == 2
    output = capsys.readouterr()
    assert "usage: hermes-gate-grok-review" in output.err
    assert '"type": "complete"' not in output.out


def test_selected_diff_includes_untracked_and_excludes_other_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test"], check=True)
    (tmp_path / "tracked.py").write_text("value = 1\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "base"], check=True)
    (tmp_path / "tracked.py").write_text("value = 2\n")
    (tmp_path / "new.py").write_text("fresh = True\n")
    (tmp_path / "other.py").write_text("secret = 'outside scope'\n")
    monkeypatch.chdir(tmp_path)
    diff = _selected_diff(["tracked.py", "new.py"])
    assert "+value = 2" in diff
    assert "+fresh = True" in diff
    assert "outside scope" not in diff


def test_saved_diff_rejects_non_patch_payload(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture.json"
    fixture.write_text(json.dumps([{"filename": "x.py", "diff": "patch"}]))
    assert _fixture_diff(fixture) == "patch"
    fixture.write_text(json.dumps([{"filename": "x.py", "diff": 12}]))
    with pytest.raises(ValueError, match="fixture"):
        _fixture_diff(fixture)


def test_committed_diff_uses_same_no_upstream_base_as_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test"], check=True)
    (tmp_path / "first.py").write_text("first = 1\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "first"], check=True)
    (tmp_path / "first.py").write_text("first = 2\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "second"], check=True)
    (tmp_path / "second.py").write_text("second = 3\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "third"], check=True)
    monkeypatch.chdir(tmp_path)
    selected = scope_paths(tmp_path)
    assert selected == ["second.py"]
    diff = _selected_diff(selected)
    assert "+second = 3" in diff
    assert "first = 2" not in diff


def test_validate_findings_rejects_out_of_scope_and_bad_fields() -> None:
    paths = ["src/a.py"]
    assert _validate_findings([], paths) == []
    good = {
        "severity": "major",
        "category": "correctness",
        "path": "src/a.py",
        "line": 3,
        "message": "off-by-one on empty input",
    }
    assert _validate_findings([good], paths) == [good]
    with pytest.raises(ValueError, match="outside selected paths"):
        _validate_findings([{**good, "path": "other.py"}], paths)
    with pytest.raises(ValueError, match="invalid severity"):
        _validate_findings([{**good, "severity": "blocker"}], paths)
    with pytest.raises(ValueError, match="invalid category"):
        _validate_findings([{**good, "category": "style"}], paths)
    with pytest.raises(ValueError, match="no explanation"):
        _validate_findings([{**good, "message": "  "}], paths)
    with pytest.raises(ValueError, match="invalid line"):
        _validate_findings([{**good, "line": 0}], paths)


def test_parse_envelope_prefers_structured_output() -> None:
    findings = [
        {
            "severity": "critical",
            "category": "security",
            "path": "a.py",
            "line": 1,
            "message": "sql injection via f-string",
        }
    ]
    from_structured = _parse_envelope(
        json.dumps({"text": '{"findings":[]}', "structuredOutput": {"findings": findings}})
    )
    assert from_structured == findings
    from_text = _parse_envelope(json.dumps({"text": json.dumps({"findings": findings})}))
    assert from_text == findings
    with pytest.raises(ValueError, match="invalid review object"):
        _parse_envelope("not-json")


def test_review_strips_api_keys_and_uses_oauth_tool_less_invocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_which(name: str) -> str | None:
        return "/fake/bin/grok" if name == "grok" else None

    def fake_run(argv: list[str] | tuple[str, ...], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append({"argv": list(argv), "env": kwargs.get("env")})
        env = kwargs.get("env") or {}
        if list(argv)[:2] == ["/fake/bin/grok", "models"]:
            for key in API_KEY_ENV_VARS:
                assert key not in env
            return subprocess.CompletedProcess(argv, 0, "You are logged in with grok.com.\n", "")
        assert argv[0] == "/fake/bin/grok"
        assert argv[1] == "-p"
        assert "--continue" not in argv and "--resume" not in argv
        assert "--no-subagents" in argv
        assert "--disable-web-search" in argv
        assert "--max-turns" in argv and argv[argv.index("--max-turns") + 1] == "1"
        assert "--tools" in argv and argv[argv.index("--tools") + 1] == ""
        assert "--json-schema" in argv
        for key in API_KEY_ENV_VARS:
            assert key not in env
        payload = {
            "text": '{"findings":[]}',
            "structuredOutput": {"findings": []},
            "stopReason": "end_turn",
        }
        return subprocess.CompletedProcess(argv, 0, json.dumps(payload), "")

    monkeypatch.setattr("hermes_gate.grok_review.shutil.which", fake_which)
    monkeypatch.setattr("hermes_gate.grok_review.subprocess.run", fake_run)
    for key in API_KEY_ENV_VARS:
        monkeypatch.setenv(key, "should-not-leak")

    assert _review("diff --git a/a.py b/a.py\n+x=1\n", ["a.py"]) == []
    assert len(calls) == 2
    assert calls[0]["argv"] == ["/fake/bin/grok", "models"]
    assert calls[1]["argv"][1] == "-p"
    assert "Wittgenstein relational review" in calls[1]["argv"][2]
    assert "PATCH:" in calls[1]["argv"][2]


def test_main_emits_jsonl_complete_with_mocked_review(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test"], check=True)
    (tmp_path / "a.py").write_text("x = 1\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "base"], check=True)
    (tmp_path / "a.py").write_text("x = 2\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HERMES_GATE_DIFF_DIGEST", "digest-abc")
    monkeypatch.setenv("HERMES_GATE_REVIEWED_PATHS", json.dumps(["a.py"]))
    monkeypatch.setattr(sys, "argv", ["hermes-gate-grok-review"])

    finding = {
        "severity": "major",
        "category": "correctness",
        "path": "a.py",
        "line": 1,
        "message": "assignment flips meaning for callers expecting 1",
    }

    def fake_review(diff: str, paths: list[str]) -> list[dict[str, object]]:
        assert "a.py" in paths
        assert "+x = 2" in diff
        return [finding]

    monkeypatch.setattr("hermes_gate.grok_review._review", fake_review)
    assert main() == 0
    lines = [json.loads(line) for line in capsys.readouterr().out.strip().splitlines()]
    assert lines[0] == {"type": "finding", **finding}
    assert lines[1] == {
        "type": "complete",
        "digest": "digest-abc",
        "reviewed_paths": ["a.py"],
    }
