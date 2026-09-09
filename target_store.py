from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
import json
import uuid

TARGET_FILE = Path(__file__).resolve().parent / "target_data.json"
_lock = RLock()

STATUSES = {"PENDING_APPROVAL", "APPROVED", "REJECTED"}
LEVELS = {"BRANCH", "RM"}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_targets() -> list[dict]:
    with _lock:
        if not TARGET_FILE.exists():
            return []
        try:
            data = json.loads(TARGET_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
        return data if isinstance(data, list) else []


def save_targets(rows: list[dict]) -> None:
    with _lock:
        tmp = TARGET_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(TARGET_FILE)


def _same_key(row: dict, *, level: str, mode: str, period: str, branch: str, rm: str, metric: str) -> bool:
    return (
        row.get("TargetLevel") == level
        and row.get("PeriodMode") == mode
        and row.get("Period") == period
        and row.get("Branch") == branch
        and (row.get("RM") or "") == (rm or "")
        and row.get("MetricCode") == metric
    )


def next_version(*, level: str, mode: str, period: str, branch: str, rm: str, metric: str) -> int:
    rows = load_targets()
    versions = [int(r.get("Version", 0) or 0) for r in rows if _same_key(r, level=level, mode=mode, period=period, branch=branch, rm=rm, metric=metric)]
    return max(versions, default=0) + 1


def create_target(*, level: str, mode: str, period: str, branch: str, rm: str, metric: str,
                  metric_name: str, value: float, unit: str, effective_from: str, effective_to: str,
                  created_by: str, reason: str, comments: str = "") -> dict:
    if level not in LEVELS:
        raise ValueError("Invalid target level")
    if value <= 0:
        raise ValueError("Target value must be greater than zero")
    if level == "RM" and not rm:
        raise ValueError("RM is required for an RM target")
    if level == "BRANCH":
        rm = ""
    version = next_version(level=level, mode=mode, period=period, branch=branch, rm=rm, metric=metric)
    row = {
        "TargetID": f"TGT-{uuid.uuid4().hex[:10].upper()}",
        "TargetLevel": level,
        "PeriodMode": mode,
        "Period": period,
        "Branch": branch,
        "RM": rm,
        "MetricCode": metric,
        "MetricName": metric_name,
        "TargetValue": float(value),
        "Unit": unit,
        "EffectiveFrom": effective_from,
        "EffectiveTo": effective_to,
        "Version": version,
        "Status": "PENDING_APPROVAL",
        "CreatedBy": created_by,
        "SubmittedAt": _now(),
        "ApprovedBy": "",
        "ApprovalDate": "",
        "RejectedBy": "",
        "RejectionDate": "",
        "Reason": reason.strip() or "Management target",
        "Comments": comments.strip(),
    }
    rows = load_targets()
    rows.append(row)
    save_targets(rows)
    return row


def decide_target(target_id: str, *, decision: str, approver: str) -> dict:
    decision = decision.upper()
    if decision not in {"APPROVED", "REJECTED"}:
        raise ValueError("Invalid target decision")
    rows = load_targets()
    target = None
    for r in rows:
        if r.get("TargetID") == target_id:
            target = r
            break
    if target is None:
        raise ValueError("Target record not found")
    if target.get("Status") != "PENDING_APPROVAL":
        raise ValueError("Only pending targets can be approved or rejected")
    if target.get("CreatedBy") == approver:
        raise PermissionError("Maker-checker control: the maker cannot approve their own target")
    if decision == "APPROVED":
        target["Status"] = "APPROVED"
        target["ApprovedBy"] = approver
        target["ApprovalDate"] = _now()
    else:
        target["Status"] = "REJECTED"
        target["RejectedBy"] = approver
        target["RejectionDate"] = _now()
    save_targets(rows)
    return target


def latest_approved(*, level: str, mode: str, period: str, branch: str, rm: str = "", metric: str) -> dict | None:
    rows = [
        r for r in load_targets()
        if r.get("Status") == "APPROVED"
        and _same_key(r, level=level, mode=mode, period=period, branch=branch, rm=rm, metric=metric)
    ]
    if not rows:
        return None
    rows.sort(key=lambda r: (int(r.get("Version", 0) or 0), str(r.get("ApprovalDate", ""))))
    return rows[-1]


def latest_approved_rm_map(mode: str, period: str, metric: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    rows = [r for r in load_targets() if r.get("Status") == "APPROVED" and r.get("TargetLevel") == "RM" and r.get("PeriodMode") == mode and r.get("Period") == period and r.get("MetricCode") == metric]
    for r in rows:
        rm = r.get("RM") or ""
        old = out.get(rm)
        if old is None or int(r.get("Version", 0) or 0) > int(old.get("Version", 0) or 0):
            out[rm] = r
    return out


def rows_for_scope(*, mode: str, period: str, branch: str | None = None, metric: str | None = None) -> list[dict]:
    rows = [r for r in load_targets() if r.get("PeriodMode") == mode and r.get("Period") == period]
    if branch and branch != "All UAE":
        rows = [r for r in rows if r.get("Branch") == branch]
    if metric:
        rows = [r for r in rows if r.get("MetricCode") == metric]
    return rows
