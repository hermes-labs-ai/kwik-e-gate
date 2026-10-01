#!/usr/bin/env python3
"""Propose a .hermes/gate.toml from cheap repository priors (adaptive kwik v2).

Stdlib only. Filename priors at the repository root; never reads file contents
and never uses the network. ``--dry-run`` (default) prints JSON. ``--write``
creates ``.hermes/gate.toml`` only when absent, unless ``--force`` is set.

v2 adds instruction-surface priors (INTENT.md / SPEC.md / AGENTS.md / skills/)
and optional lintlang + intent-verify proposals. Does not replace ``kwik-gate
init`` and does not run LintLang scan.

Exit status: 0 applied or printed, 2 refused to overwrite, 1 usage or path error.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence


class CalibrateError(ValueError):
    """The repo path cannot be calibrated."""


DEFAULT_EXCLUSIONS = [
    ".git/**",
    ".hermes/hermes_gate_runner.py",
    ".pytest_cache/**",
    ".ruff_cache/**",
    "**/__pycache__/**",
    "vendor/**",
    "node_modules/**",
    "dist/**",
    "build/**",
    "**/*.egg-info/**",
]

LINTLANG_TRIGGER_GLOBS = [
    "**/AGENTS.md",
    "**/CLAUDE.md",
    "**/INTENT.md",
    "**/SPEC.md",
    "**/prompts/**",
    "**/*.prompt",
    ".codex/**",
    ".claude/**",
    "skills/**",
]


def _toml_string(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


def _toml_array(values: Sequence[str]) -> str:
    return "[" + ", ".join(_toml_string(item) for item in values) + "]"


def _within(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root)
    except ValueError:
        return False
    return True


def _version_token(proc: subprocess.CompletedProcess[str]) -> str | None:
    line = ((proc.stdout or proc.stderr or "").splitlines() or [""])[0].strip()
    if not line or len(line) > 120:
        return None
    if any(token in line.lower() for token in ("secret", "token", "password", "key=")):
        return None
    if any(ord(char) < 32 or ord(char) == 127 for char in line):
        return None
    if "/" in line or "\\" in line:
        return None
    return line


def _run_probe(argv: Sequence[str]) -> subprocess.CompletedProcess[str] | None:
    """Run a local version probe. cwd is /tmp so a misbehaving CLI cannot scan the repo."""
    try:
        return subprocess.run(
            list(argv),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            cwd="/tmp",
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def _probe_tool(binary: str, module: str | None = None) -> dict[str, Any]:
    """PATH binary first, then optional ``python -m <module> --version``."""
    which = shutil.which(binary)
    binary_probe = _run_probe([binary, "--version"]) if which else None
    if binary_probe is not None and binary_probe.returncode == 0:
        return {
            "available": True,
            "on_path": True,
            "via": f"{binary} --version",
            "version": _version_token(binary_probe),
        }
    if module is None:
        return {
            "available": False,
            "on_path": which is not None,
            "via": None,
            "version": None,
        }
    module_probe = _run_probe([sys.executable, "-m", module, "--version"])
    if module_probe is None:
        return {"available": False, "on_path": which is not None, "via": None, "version": None}
    combined = f"{module_probe.stderr or ''}\n{module_probe.stdout or ''}"
    if f"No module named {module}" in combined:
        return {"available": False, "on_path": which is not None, "via": None, "version": None}
    if module_probe.returncode == 0 or module in combined.lower():
        return {
            "available": True,
            "on_path": which is not None,
            "via": f"python -m {module}",
            "version": _version_token(module_probe) if module_probe.returncode == 0 else None,
        }
    return {"available": False, "on_path": which is not None, "via": None, "version": None}


def detect_next_command() -> str:
    """Handoff hint. PATH lookup only; nothing is executed."""
    if shutil.which("kwik-gate"):
        return "kwik-gate plan"
    if shutil.which("hermes-gate"):
        return "hermes-gate fast"
    return "install kwik candidate"


def scan_priors(root: Path) -> dict[str, Any]:
    """Cheap filename priors at the repository root. Does not read file contents."""
    python_markers: list[str] = []
    if (root / "pyproject.toml").is_file():
        python_markers.append("pyproject.toml")
    if (root / "setup.py").is_file():
        python_markers.append("setup.py")
    python_markers.extend(
        path.name
        for path in sorted(root.glob("requirements*.txt"))
        if path.is_file()
    )

    package_managers: list[dict[str, str]] = []
    for filename, manager in (
        ("package-lock.json", "npm"),
        ("pnpm-lock.yaml", "pnpm"),
        ("yarn.lock", "yarn"),
    ):
        if (root / filename).is_file():
            package_managers.append({"name": manager, "marker": filename})

    instruction_files: list[str] = []
    for name in ("INTENT.md", "SPEC.md", "AGENTS.md"):
        if (root / name).is_file():
            instruction_files.append(name)
    skills_dir = root / "skills"
    skills_present = skills_dir.is_dir()
    instruction_surface = bool(instruction_files) or skills_present

    intent_spec: str | None = None
    if (root / "INTENT.md").is_file():
        intent_spec = "INTENT.md"
    elif (root / "SPEC.md").is_file():
        intent_spec = "SPEC.md"

    python = bool(python_markers)
    lintlang = _probe_tool("lintlang", module="lintlang")
    intent_verify = _probe_tool("intent-verify", module="intent_verify")

    return {
        "python": python,
        "python_markers": python_markers,
        "package_managers": [item["name"] for item in package_managers],
        "package_manager_markers": [item["marker"] for item in package_managers],
        "gate_toml_exists": (root / ".hermes" / "gate.toml").is_file(),
        "instruction_surface": instruction_surface,
        "instruction_files": instruction_files,
        "skills_dir": skills_present,
        "intent_spec": intent_spec,
        "lintlang": lintlang,
        "intent_verify": intent_verify,
        "tools": {
            "ruff": {"required": python, "on_path": shutil.which("ruff") is not None},
            "pytest": {"required": python, "on_path": shutil.which("pytest") is not None},
            "lintlang": {
                "required": instruction_surface,
                "on_path": lintlang.get("on_path") or lintlang.get("available") is True,
            },
            "intent-verify": {
                "required": intent_spec is not None,
                "on_path": intent_verify.get("on_path") or intent_verify.get("available") is True,
            },
        },
    }


def propose_toml(root: Path, priors: dict[str, Any]) -> str:
    """Schema-aligned Hermes gate profile. Detect-then-propose only."""
    lines = [
        "version = 1",
        "",
        "# Proposed by calibrate v2 (adaptive kwik).",
        "# Detect-then-propose only. Does not install tools, run scans, or contact the network.",
        "# Experimental: does not replace `kwik-gate init` / hermes_gate.init_repo.",
        "[gate]",
        f"name = {_toml_string(root.name or 'repo')}",
        "fast_budget_seconds = 8.0",
        "full_required_local = false",
        "review_required = false",
        'adapter_status = "NOT_CONFIGURED"',
        f"exclusions = {_toml_array(DEFAULT_EXCLUSIONS)}",
        "",
        "[adapter]",
        "enabled = false",
        'name = "native"',
        "argv = []",
        'minimum_version = ""',
        "",
    ]

    managers = priors.get("package_managers") or []
    if managers:
        lines.append("# package manager priors: " + ", ".join(managers))
        lines.append("# JS script checks are not inferred (no package.json content reads).")
        lines.append("")

    instruction_surface = bool(priors.get("instruction_surface"))
    lintlang = priors.get("lintlang") or {}
    lintlang_available = bool(lintlang.get("available"))
    if instruction_surface:
        files = priors.get("instruction_files") or []
        note_bits = list(files)
        if priors.get("skills_dir"):
            note_bits.append("skills/")
        lines.append(
            "# instruction-surface priors: "
            + (", ".join(note_bits) if note_bits else "present")
        )
        lines.append("# requires: lintlang (install separately; engine table below)")
        lines.append("[lintlang]")
        lines.append(f"enabled = {'true' if lintlang_available else 'false'}")
        if not lintlang_available:
            lines.append(
                "# enabled=false because lintlang was not found on PATH / as a module"
            )
        lines.append(
            'argv = ["lintlang", "scan", "--format", "json", "--fail-on", "review", "{files}"]'
        )
        lines.append(f"trigger_globs = {_toml_array(LINTLANG_TRIGGER_GLOBS)}")
        lines.append("timeout_seconds = 4.0")
        lines.append('blocking_threshold = "MEDIUM"')
        lines.append("")
    else:
        lines.append("# No instruction-surface priors; lintlang left disabled.")
        lines.append("[lintlang]")
        lines.append("enabled = false")
        lines.append(
            'argv = ["lintlang", "scan", "--format", "json", "--fail-on", "review", "{files}"]'
        )
        lines.append("trigger_globs = []")
        lines.append("timeout_seconds = 4.0")
        lines.append('blocking_threshold = "MEDIUM"')
        lines.append("")

    lines.extend(
        [
            "[review]",
            'provider = "coderabbit"',
            'argv = ["coderabbit", "review", "--agent"]',
            "timeout_seconds = 180.0",
            'material_severities = ["critical", "major"]',
            'material_categories = ["correctness", "security", "data-loss", "concurrency", "api-contract"]',
            "fallback_argv = []",
            "",
        ]
    )

    if not priors.get("python"):
        lines.append("# No Python priors detected. No ruff or pytest checks proposed.")
        lines.append("")
    else:
        lines.extend(
            [
                "# requires: ruff",
                "[[fast]]",
                'name = "python-ruff"',
                'argv = ["ruff", "check", "{files}"]',
                "timeout_seconds = 3.0",
                'globs = ["**/*.py"]',
                "",
                "# requires: ruff",
                "[[full]]",
                'name = "python-ruff"',
                'argv = ["ruff", "check", "."]',
                "timeout_seconds = 60.0",
                'globs = ["**/*"]',
                "",
                "# requires: pytest",
                "[[full]]",
                'name = "python-test"',
                'argv = ["python3", "-m", "pytest"]',
                "timeout_seconds = 360.0",
                'globs = ["**/*"]',
                "",
            ]
        )

    intent_spec = priors.get("intent_spec")
    if intent_spec:
        lines.extend(
            [
                "# Optional named check — requires: intent-verify (install separately).",
                "# Does not grant acceptance authority; lexical coverage only.",
                "[[full]]",
                'name = "intent-verify"',
                f'argv = ["intent-verify", "check", "--spec", {_toml_string(intent_spec)}]',
                "timeout_seconds = 60.0",
                'globs = ["**/*"]',
                "",
            ]
        )

    if instruction_surface:
        lines.extend(
            [
                "# Optional named check — requires: lintlang (install separately).",
                "# Prefer the [lintlang] engine table above when the binary is installed;",
                "# this argv check is a fallback for operators who want an explicit stage.",
                "[[full]]",
                'name = "lintlang-scan"',
                'argv = ["lintlang", "scan", "--format", "json", "--fail-on", "review", "."]',
                "timeout_seconds = 60.0",
                'globs = ["**/*"]',
                "",
            ]
        )

    return "\n".join(lines)


def _write_atomic(dest: Path, text: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    temporary = dest.parent / f".{dest.name}.calibrate.tmp"
    try:
        temporary.write_text(text, encoding="utf-8")
        os.replace(temporary, dest)
    finally:
        if temporary.exists():
            temporary.unlink()


def _requires_list(priors: dict[str, Any]) -> list[str]:
    requires: list[str] = []
    if priors.get("python"):
        requires.extend(["ruff", "pytest"])
    if priors.get("instruction_surface"):
        requires.append("lintlang")
    if priors.get("intent_spec"):
        requires.append("intent-verify")
    return requires


def calibrate(repo_path: str | Path, *, write: bool = False, force: bool = False) -> dict[str, Any]:
    root = Path(repo_path).expanduser().resolve()
    if not root.is_dir():
        raise CalibrateError(f"repo path is not a directory: {repo_path}")

    dest = root / ".hermes" / "gate.toml"
    if not _within(root, dest):
        raise CalibrateError("refusing to write .hermes/gate.toml outside the repository")

    priors = scan_priors(root)
    proposed = propose_toml(root, priors)
    mode = "write" if write else "dry-run"
    result: dict[str, Any] = {
        "ok": True,
        "mode": mode,
        "repo": str(root),
        "force": bool(force),
        "wrote": False,
        "refused": False,
        "reason": None,
        "priors": priors,
        "requires": _requires_list(priors),
        "proposed_toml": proposed,
        "next_command": detect_next_command(),
        "calibrate_version": 2,
    }

    if not write:
        return result

    if dest.exists() and not dest.is_file():
        raise CalibrateError(f"{dest} exists and is not a file")
    if dest.is_file() and not force:
        result["ok"] = False
        result["refused"] = True
        result["reason"] = "refusing to overwrite .hermes/gate.toml without --force"
        return result

    _write_atomic(dest, proposed)
    result["wrote"] = True
    return result


def _emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, indent=2) + "\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Detect repo priors and propose a schema-aligned .hermes/gate.toml (v2)."
    )
    parser.add_argument("repo_path", help="Path to the repository to calibrate")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Print JSON priors and the proposed toml (default)",
    )
    mode.add_argument(
        "--write",
        action="store_true",
        help="Write .hermes/gate.toml only if it is missing",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="With --write, replace an existing .hermes/gate.toml",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        result = calibrate(args.repo_path, write=args.write, force=args.force)
    except (CalibrateError, OSError) as exc:
        _emit({"ok": False, "wrote": False, "refused": False, "error": str(exc)})
        print(str(exc), file=sys.stderr)
        return 1
    _emit(result)
    if result.get("refused"):
        print(result.get("reason") or "refused", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
