"""Bounded GitHub Actions job summary for the source-pinned core Action.

Presentation only: reads Action status and an optional receipt; never dumps
argv, stdout/stderr, secrets, or the full receipt body.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SOURCE_URL = "https://github.com/hermes-labs-ai/kwik-e-gate"
MAX_CHECKS = 24
ACTION_STATUSES = frozenset({"PASS", "FAIL"})
CHECK_STATUSES = frozenset({
    "PASS", "FAIL", "ERROR", "NOT_APPLICABLE", "NOT_CONFIGURED",
    "pass", "fail", "error", "timeout", "missing", "skipped",
})
KIND_VALUES = frozenset({"fast", "full", "review"})
MODE_VALUES = frozenset({"auto", "fast", "full"})

_UNSAFE = re.compile(r"[\r\n\t]+")


def _bounded_text(value: Any, fallback: str = "unavailable", limit: int = 80) -> str:
    if not isinstance(value, str):
        return fallback
    normalized = _UNSAFE.sub(" ", value).strip()
    return normalized[:limit] if normalized else fallback


def _escape_markdown(value: str) -> str:
    return re.sub(r"([\\`*_{}\[\]()<>#+\-.!|])", r"\\\1", value)


def _allowed(value: Any, allowed: frozenset[str], fallback: str = "unavailable") -> str:
    return value if isinstance(value, str) and value in allowed else fallback


def _check_rows(receipt: dict[str, Any] | None) -> list[dict[str, str]]:
    if not isinstance(receipt, dict):
        return []
    checks = receipt.get("checks")
    if not isinstance(checks, list):
        return []
    rows: list[dict[str, str]] = []
    for check in checks:
        if not isinstance(check, dict):
            continue
        name = _escape_markdown(_bounded_text(check.get("name"), "unnamed check"))
        status = _allowed(check.get("status"), CHECK_STATUSES)
        rows.append({"name": name, "status": status})
    return rows


def _count_text(checks: list[dict[str, str]]) -> str:
    if not checks:
        return "unavailable"
    counts: dict[str, int] = {}
    for check in checks:
        key = check["status"].upper() if check["status"] != "unavailable" else "unavailable"
        counts[key] = counts.get(key, 0) + 1
    return (
        f"{len(checks)} total; "
        f"{counts.get('PASS', 0)} pass; "
        f"{counts.get('FAIL', 0)} fail; "
        f"{counts.get('ERROR', 0)} error; "
        f"{counts.get('NOT_APPLICABLE', 0)} not_applicable; "
        f"{counts.get('unavailable', 0)} unavailable"
    )


def _routing_fields(receipt: dict[str, Any] | None, result_routing: Any = None) -> tuple[str, str]:
    routing = result_routing if isinstance(result_routing, dict) else None
    if routing is None and isinstance(receipt, dict):
        candidate = receipt.get("routing")
        routing = candidate if isinstance(candidate, dict) else None
    if routing is None:
        kind = _allowed(receipt.get("kind") if isinstance(receipt, dict) else None, KIND_VALUES)
        return kind, "unavailable"
    mode = _allowed(routing.get("mode"), MODE_VALUES | KIND_VALUES)
    reason = _bounded_text(routing.get("reason"), "unavailable", limit=120)
    return mode, _escape_markdown(reason)


def render_job_summary(
    *,
    gate_status: str | None = None,
    receipt: dict[str, Any] | None = None,
    receipt_path: str | None = None,
) -> str:
    """Render a concise markdown job summary from Action outputs + receipt."""
    status = _allowed(gate_status, ACTION_STATUSES)
    if status == "unavailable" and isinstance(receipt, dict):
        status = _allowed(receipt.get("status"), ACTION_STATUSES)
    checks = _check_rows(receipt)
    mode, route_reason = _routing_fields(receipt)
    kind = _allowed(receipt.get("kind") if isinstance(receipt, dict) else None, KIND_VALUES)
    # Paths and reason codes sit in backticks; strip control chars only.
    path_text = _bounded_text(receipt_path, "unavailable", limit=200)
    if isinstance(receipt, dict):
        reason_code = _bounded_text(receipt.get("reason_code"), "unavailable", limit=64)
    else:
        reason_code = "unavailable"

    lines = [
        "## Kwik-e-gate",
        "",
        f"[Kwik-e-gate]({SOURCE_URL}) ran the source-pinned core Action for this job.",
        "",
        "| Field | Result |",
        "| --- | --- |",
        f"| Status | `{status}` |",
        f"| Mode / kind | `{mode}` / `{kind}` |",
        f"| Routing | {route_reason} |",
        f"| Checks | {_count_text(checks)} |",
        f"| Reason code | `{reason_code}` |",
        f"| Receipt | `{path_text}` |",
    ]
    if checks:
        lines.extend(["", f"### Checks ({len(checks)})"])
        for check in checks[:MAX_CHECKS]:
            lines.append(f"- {check['name']}: `{check['status']}`")
        omitted = len(checks) - MAX_CHECKS
        if omitted > 0:
            lines.append(f"- {omitted} additional checks omitted")
    lines.append("")
    return "\n".join(lines)


def load_receipt(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", default="")
    parser.add_argument("--receipt", default="")
    args = parser.parse_args(argv)
    receipt = load_receipt(args.receipt or None)
    summary = render_job_summary(
        gate_status=args.status or None,
        receipt=receipt,
        receipt_path=args.receipt or None,
    )
    sys.stdout.write(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
