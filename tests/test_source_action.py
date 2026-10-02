from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github/actions/kwik-e-gate/run.py"


@pytest.mark.parametrize("case", ["pass", "fail", "invalid-mode", "missing-profile"])
def test_pinned_source_action_preserves_failure_receipts(tmp_path: Path, case: str) -> None:
    repo = tmp_path / "consumer"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    # A project-local module must not shadow the Action's reviewed source.
    (repo / "hermes_gate.py").write_text("raise RuntimeError('wrong implementation')\n")
    if case != "missing-profile":
        (repo / ".hermes").mkdir()
        code = "import sys; sys.exit(1)" if case == "fail" else "pass"
        command = json.dumps([sys.executable, "-c", code])
        (repo / ".hermes/gate.toml").write_text(
            f'[[fast]]\nname="check"\nargv={command}\n'
            f'[[full]]\nname="check"\nargv={command}\n'
        )
    output = tmp_path / "outputs"
    env = dict(os.environ, RUNNER_TEMP=str(tmp_path), GITHUB_OUTPUT=str(output),
               KWIK_GATE_DIRECTORY=str(repo), KWIK_GATE_BASE="",
               KWIK_GATE_MODE="invalid" if case == "invalid-mode" else "full")
    env.pop("HERMES_GATE_BASE", None)
    process = subprocess.run(
        [sys.executable, "-I", str(SCRIPT)], cwd=repo, env=env,
        capture_output=True, text=True, timeout=30, check=False,
    )
    result = json.loads(process.stdout)
    expected = "PASS" if case == "pass" else "FAIL"
    assert result["status"] == expected, process.stderr
    assert process.returncode == (0 if case == "pass" else 1)
    assert result["receipt"]["schema"] == "hermes-gate/receipt-v1"
    export = Path(result["export_path"])
    assert export.is_file()
    assert json.loads(export.read_text()) == result["receipt"]
    assert f"status={expected}\n" in output.read_text()
    assert f"receipt-path={export}\n" in output.read_text()


@pytest.mark.parametrize("case", [
    "unsupported-python", "missing-core", "missing-initializer", "unwritable-export",
    "symlink-loop", "missing-directory", "not-a-directory", "directory-symlink",
])
def test_action_bootstrap_failure_is_receipted(tmp_path: Path, case: str) -> None:
    repo = tmp_path / "consumer"
    repo.mkdir()
    script = SCRIPT
    if case in {"missing-core", "missing-initializer"}:
        script = tmp_path / "broken/.github/actions/kwik-e-gate/run.py"
        script.parent.mkdir(parents=True)
        script.write_bytes(SCRIPT.read_bytes())
        if case == "missing-initializer":
            workflow = tmp_path / "broken/src/hermes_gate/workflow.py"
            workflow.parent.mkdir(parents=True)
            workflow.write_text("raise RuntimeError('must not import this stub')\n")
    runner_temp = tmp_path / "missing-temp" if case == "unwritable-export" else tmp_path
    directory = repo
    if case == "symlink-loop":
        directory = tmp_path / "loop"
        directory.symlink_to("loop")
    elif case == "missing-directory":
        directory = tmp_path / "missing-consumer"
    elif case == "not-a-directory":
        directory = tmp_path / "consumer-file"
        directory.write_text("not a checkout\n")
    elif case == "directory-symlink":
        directory = tmp_path / "consumer-alias"
        directory.symlink_to(repo, target_is_directory=True)
    output = tmp_path / "outputs"
    env = dict(os.environ, RUNNER_TEMP=str(runner_temp), GITHUB_OUTPUT=str(output),
               KWIK_GATE_DIRECTORY=str(directory), KWIK_GATE_MODE="full")
    code = "import runpy,sys; "
    if case not in {"missing-core", "missing-initializer"}:
        code += "sys.version_info=(3,10,0); "
    code += "runpy.run_path(sys.argv[1],run_name='__main__')"
    process = subprocess.run(
        [sys.executable, "-I", "-c", code, str(script)], cwd=repo, env=env,
        capture_output=True, text=True, timeout=30, check=False,
    )
    result = json.loads(process.stdout)
    assert process.returncode == 1
    assert result["status"] == result["receipt"]["status"] == "FAIL"
    assert result["receipt"]["reason_code"] == "ACTION_BOOTSTRAP_ERROR"
    assert result["receipt"]["checks"] == []
    assert result["receipt"]["kind"] == "full"
    if case in {"missing-core", "missing-initializer"}:
        assert "pinned core source is missing" in result["reason"]
    assert "status=FAIL\n" in output.read_text()
    if case in {"unwritable-export", "symlink-loop", "missing-directory", "not-a-directory"}:
        assert result["export_path"] is None
        assert "receipt-path=\n" in output.read_text()
        assert "receipt export failed" in result["reason"]
    else:
        export = Path(result["export_path"])
        assert json.loads(export.read_text()) == result["receipt"]
        assert f"receipt-path={export}\n" in output.read_text()


@pytest.mark.parametrize("runner_temp_present", [True, False])
def test_action_temp_selection_failure_is_receipted(
    tmp_path: Path, runner_temp_present: bool,
) -> None:
    repo = tmp_path / "consumer"
    repo.mkdir()
    output = tmp_path / "outputs"
    env = dict(os.environ, GITHUB_OUTPUT=str(output),
               KWIK_GATE_DIRECTORY=str(repo), KWIK_GATE_MODE="full")
    env.pop("RUNNER_TEMP", None)
    if runner_temp_present:
        env["RUNNER_TEMP"] = str(tmp_path)
    code = """import runpy, sys, tempfile
def unavailable_temp():
    raise FileNotFoundError('no usable system temporary directory')
tempfile.gettempdir = unavailable_temp
sys.version_info = (3, 10, 0)
runpy.run_path(sys.argv[1], run_name='__main__')
"""
    process = subprocess.run(
        [sys.executable, "-I", "-c", code, str(SCRIPT)], cwd=repo, env=env,
        capture_output=True, text=True, timeout=30, check=False,
    )
    result = json.loads(process.stdout)
    assert process.returncode == 1
    assert result["status"] == result["receipt"]["status"] == "FAIL"
    assert result["receipt"]["reason_code"] == "ACTION_BOOTSTRAP_ERROR"
    assert "binding" not in result["receipt"]
    assert "status=FAIL\n" in output.read_text()
    if runner_temp_present:
        # The host-provided directory must avoid consulting broken system defaults.
        assert "requires Python 3.11" in result["reason"]
        export = Path(result["export_path"])
        assert json.loads(export.read_text()) == result["receipt"]
        assert f"receipt-path={export}\n" in output.read_text()
    else:
        assert "no usable system temporary directory" in result["reason"]
        assert result["export_path"] is None
        assert "receipt-path=\n" in output.read_text()


def test_core_action_publishes_bounded_job_summary_step() -> None:
    action = (ROOT / ".github/actions/kwik-e-gate/action.yml").read_text(encoding="utf-8")
    summary_index = action.index("- name: Publish Kwik-e-gate summary")
    gate_index = action.index("- name: Run the pinned source core")
    assert summary_index > gate_index
    assert "if: always()" in action[summary_index:]
    assert "ci_summary.py" in action[summary_index:]
    assert "GITHUB_STEP_SUMMARY" in action[summary_index:]
    assert "value: ${{ steps.gate.outputs.status }}" in action
    assert "value: ${{ steps.gate.outputs.receipt-path }}" in action


def test_job_summary_renders_status_routing_and_checks(tmp_path: Path) -> None:
    from importlib.util import module_from_spec, spec_from_file_location

    summary_path = ROOT / ".github/actions/kwik-e-gate/ci_summary.py"
    spec = spec_from_file_location("kwik_e_gate_ci_summary", summary_path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)

    receipt = {
        "schema": "hermes-gate/receipt-v1",
        "kind": "full",
        "status": "PASS",
        "reason_code": "PASS",
        "routing": {
            "mode": "full",
            "reason": "explicit full mode",
            "requested_mode": "full",
        },
        "checks": [
            {"name": "lint", "status": "PASS", "stdout": "secret-must-not-appear", "argv": ["evil"]},
            {"name": "tests", "status": "FAIL", "stderr": "token=abc"},
        ],
    }
    export = tmp_path / "receipt.json"
    export.write_text(json.dumps(receipt), encoding="utf-8")
    rendered = module.render_job_summary(
        gate_status="PASS",
        receipt=receipt,
        receipt_path=str(export),
    )
    assert "Kwik-e-gate" in rendered
    assert "https://github.com/hermes-labs-ai/kwik-e-gate" in rendered
    assert "| Status | `PASS` |" in rendered
    assert "| Mode / kind | `full` / `full` |" in rendered
    assert "explicit full mode" in rendered
    assert "2 total; 1 pass; 1 fail;" in rendered
    assert "- lint: `PASS`" in rendered
    assert "- tests: `FAIL`" in rendered
    assert str(export) in rendered
    assert "secret-must-not-appear" not in rendered
    assert "token=abc" not in rendered
    assert "evil" not in rendered
    assert '"checks"' not in rendered

    missing = module.render_job_summary(gate_status="FAIL", receipt=None, receipt_path="")
    assert "| Status | `FAIL` |" in missing
    assert "| Checks | unavailable |" in missing
    assert "| Receipt | `unavailable` |" in missing

    process = subprocess.run(
        [sys.executable, "-I", str(summary_path), "--status", "PASS", "--receipt", str(export)],
        capture_output=True, text=True, timeout=10, check=False,
    )
    assert process.returncode == 0
    assert process.stdout == rendered

    unsafe = module.render_job_summary(
        gate_status="unexpected",
        receipt={
            "status": "weird",
            "kind": "nope",
            "reason_code": "X" * 200,
            "checks": [{
                "name": "lint\n<script>alert(1)</script>| `argv` /private/path",
                "status": "unexpected",
                "stdout": "leak",
            }],
        },
        receipt_path="/tmp/safe",
    )
    assert "| Status | `unavailable` |" in unsafe
    assert "leak" not in unsafe
    assert "\n<script>" not in unsafe
    assert "<script>" not in unsafe or "\\<" in unsafe


@pytest.mark.parametrize("case", ["pass", "fail"])
def test_pinned_source_action_receipt_feeds_job_summary(
    tmp_path: Path, case: str,
) -> None:
    repo = tmp_path / "consumer"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / ".hermes").mkdir()
    code = "import sys; sys.exit(1)" if case == "fail" else "pass"
    command = json.dumps([sys.executable, "-c", code])
    (repo / ".hermes/gate.toml").write_text(
        f'[[fast]]\nname="check"\nargv={command}\n'
        f'[[full]]\nname="check"\nargv={command}\n'
    )
    output = tmp_path / "outputs"
    env = dict(
        os.environ,
        RUNNER_TEMP=str(tmp_path),
        GITHUB_OUTPUT=str(output),
        KWIK_GATE_DIRECTORY=str(repo),
        KWIK_GATE_BASE="",
        KWIK_GATE_MODE="full",
    )
    env.pop("HERMES_GATE_BASE", None)
    process = subprocess.run(
        [sys.executable, "-I", str(SCRIPT)], cwd=repo, env=env,
        capture_output=True, text=True, timeout=30, check=False,
    )
    result = json.loads(process.stdout)
    expected = "PASS" if case == "pass" else "FAIL"
    assert result["status"] == expected
    export = Path(result["export_path"])
    summary_path = ROOT / ".github/actions/kwik-e-gate/ci_summary.py"
    summary = subprocess.run(
        [sys.executable, "-I", str(summary_path), "--status", expected, "--receipt", str(export)],
        capture_output=True, text=True, timeout=10, check=False,
    )
    assert summary.returncode == 0
    body = summary.stdout
    assert f"| Status | `{expected}` |" in body
    assert "| Mode / kind | `full` / `full` |" in body
    assert "- check:" in body
    assert str(export) in body
    # No raw command payload from the receipt body.
    assert '"argv"' not in body
    assert "sys.exit" not in body
