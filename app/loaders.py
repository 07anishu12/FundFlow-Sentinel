"""Typed, local-only readers for frozen tables and approved v1 artifact envelopes.

Bundles: data/manifest.json and data/snapshots/manifest.json describe processed/
(flow, market, feature, NAV, scheme tables), outputs/ (remaining tables and
model_results.json), and root quality_report.json / source_metadata.json.
Legacy snapshots/fixtures is flat and synthetic. Explicit bundle selection never
falls back. Auto selection only falls back when the preceding bundle is absent,
not when its data or manifest is invalid. No loader changes or computes metrics.

A manifest's live mode means a locally materialized refresh, not network access
or guaranteed freshness. The 45-day default is presentation policy only. File
mtime is never substituted for generated_at. JSON payload extensions are allowed;
model metrics accept nested finite numbers and string labels, but not booleans.
All artifact validation is structural, not evidence of statistical validity.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Literal, Optional, Tuple

import pandas as pd
from fundflow.contracts import BOOLEAN, COLUMNS, TEXT, validate_table

DATA_ROOT = Path(__file__).resolve().parents[1] / "data"
DEFAULT_DATA_DIR = DATA_ROOT / "snapshots/fixtures"
PROCESSED = {"flows_category_month", "market_month", "feature_matrix", "nav_daily", "scheme_master"}
ARTIFACTS = {"model_results": "outputs/model_results.json", "quality_report": "quality_report.json", "source_metadata": "source_metadata.json"}
Mode = Literal["offline_snapshot", "live", "synthetic", "unknown"]
State = Literal["ok", "missing", "empty", "invalid", "stale"]


@dataclass(frozen=True)
class Metadata:
    mode: Mode = "unknown"
    source: str = "unavailable"
    last_period: str | None = None
    generated_at: str | None = None
    freshness: Literal["fresh", "stale", "unknown"] = "unknown"


@dataclass
class TableResult:
    frame: pd.DataFrame
    message: str = ""
    status: State = "ok"
    metadata: Metadata = field(default_factory=Metadata)


@dataclass
class JsonResult:
    payload: dict | None = None
    message: str = ""
    status: State = "ok"
    metadata: Metadata = field(default_factory=Metadata)


def fixture_directory() -> Path:
    """Compatibility accessor; actual reads must still pass the root guard."""
    return Path(os.environ.get("FUNDFLOW_FIXTURE_DIR", DEFAULT_DATA_DIR))


def _safe_path(root: Path, relative: str | Path) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Path must be relative and cannot traverse parents")
    candidate = (root / path).resolve()
    if not candidate.is_relative_to(root.resolve()):
        raise ValueError("Path escapes the data root")
    return candidate


def _bundle(root: Path, bundle: str | None) -> Path:
    if bundle is not None:
        if bundle not in {"", "snapshots", "snapshots/fixtures"}:
            raise ValueError("Unknown bundle")
        return _safe_path(root, bundle)
    if "FUNDFLOW_FIXTURE_DIR" in os.environ:
        # Environment may select an internal fixture directory, never a trust root.
        selected = Path(os.environ["FUNDFLOW_FIXTURE_DIR"])
        if not selected.is_absolute():
            selected = DATA_ROOT.parent / selected
        if ".." in selected.parts:
            raise ValueError("Traversal is forbidden")
        return _safe_path(root, selected.relative_to(root.resolve()))
    for relative in ("", "snapshots"):
        candidate = _safe_path(root, relative)
        if any((candidate / name).exists() or (candidate / name).is_symlink() for name in ("manifest.json", "processed", "outputs", "quality_report.json", "source_metadata.json")):
            return candidate
    return _safe_path(root, "snapshots/fixtures")


def _utc(value: str) -> datetime:
    if not isinstance(value, str) or "T" not in value:
        raise ValueError("ISO UTC timestamp required")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() != timedelta(0):
        raise ValueError("UTC timestamp required")
    return parsed


def _json(path: Path) -> dict:
    def bad_constant(value):
        raise ValueError(f"Non-finite JSON constant: {value}")
    value = json.loads(path.read_text(), parse_constant=bad_constant)
    if not isinstance(value, dict):
        raise ValueError("JSON object required")
    return value


def _nonempty_text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _metadata(document: dict, *, now: datetime, stale_days: int, mode: Mode) -> Metadata:
    if not _nonempty_text(document.get("source")):
        raise ValueError("Source required")
    generated = document.get("generated_at")
    instant = _utc(generated)
    freshness = "stale" if now - instant > timedelta(days=stale_days) else "fresh"
    return Metadata(mode=mode, source=document["source"], generated_at=generated, freshness=freshness)


def _validate_declared_file(root: Path, directory: Path, relative: str, manifest: dict) -> None:
    """Fail closed when a versioned manifest inventory does not match its table file."""
    files = manifest.get("files")
    if files is None:
        return  # Older test bundles predate file inventories.
    if not isinstance(files, list):
        raise ValueError("Manifest files must be a list")
    matches = [entry for entry in files if isinstance(entry, dict) and entry.get("path") == relative]
    if len(matches) != 1:
        raise ValueError("Declared file inventory entry missing or duplicated")
    entry = matches[0]
    path = _safe_path(root, directory.relative_to(root) / relative)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Declared file is missing or unsafe")
    if entry.get("size_bytes") != path.stat().st_size:
        raise ValueError("Declared file size does not match")
    if not isinstance(entry.get("sha256"), str) or hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
        raise ValueError("Declared file digest does not match")


def _context(root: Path, bundle: str | None, now: datetime | None, stale_days: int):
    root = root.resolve()
    now = now or datetime.now(timezone.utc)
    if now.utcoffset() != timedelta(0) or stale_days < 0:
        raise ValueError("UTC clock and nonnegative freshness threshold required")
    directory = _bundle(root, bundle)
    path = _safe_path(root, directory.relative_to(root) / "manifest.json")
    manifest = _json(path)
    tables = manifest.get("tables")
    if not isinstance(tables, list) or any(not isinstance(n, str) or n not in COLUMNS for n in tables):
        raise ValueError("Manifest tables must name frozen contracts")
    legacy = directory == (root / "snapshots/fixtures").resolve() and "version" not in manifest
    if legacy:
        if manifest.get("synthetic") is not True:
            raise ValueError("Synthetic declaration required")
        metadata = Metadata(mode="synthetic", source="synthetic fixture")
    else:
        mode = manifest.get("mode")
        if type(manifest.get("version")) is not int or manifest["version"] != 1 or mode not in {"offline_snapshot", "live", "synthetic"}:
            raise ValueError("Invalid manifest version or mode")
        artifacts = manifest.get("artifacts")
        if not isinstance(artifacts, list) or any(not isinstance(n, str) or n not in ARTIFACTS for n in artifacts):
            raise ValueError("Invalid artifact declaration")
        metadata = _metadata(manifest, now=now, stale_days=stale_days, mode=mode)
        files = manifest.get("files", [])
        if isinstance(files, list) and any(isinstance(item, dict) and item.get("origin") == "synthetic" for item in files):
            metadata = Metadata("synthetic", metadata.source, metadata.last_period, metadata.generated_at, metadata.freshness)
    return root, directory, manifest, metadata, legacy, now


def _failure(exc: Exception) -> tuple[State, str]:
    if isinstance(exc, FileNotFoundError):
        return "missing", "Dataset unavailable: local file is missing. Data withheld."
    return "invalid", "Dataset unavailable: invalid path, metadata or contents. Data withheld."


def load_table(name: str, *, data_root: Path | None = None, bundle: str | None = None,
               now: datetime | None = None, stale_days: int = 45) -> TableResult:
    """Validate and type a table. IDs/dates remain strings; numbers become numeric.

    data_root is a programmatic dependency-injection seam, not an environment
    override. Empty files are an empty state; header-only files validate normally.
    """
    if name not in COLUMNS:
        raise ValueError(f"Unknown table: {name}")
    empty = pd.DataFrame(columns=COLUMNS[name])
    metadata = Metadata()
    try:
        root, directory, manifest, metadata, legacy, _ = _context(Path(data_root or DATA_ROOT), bundle, now, stale_days)
        if name not in manifest["tables"]:
            return TableResult(empty, "Dataset unavailable: not declared in the manifest. Data withheld.", "missing", metadata)
        relative = f"{name}.csv" if legacy else f"{'processed' if name in PROCESSED else 'outputs'}/{name}.csv"
        if not legacy:
            _validate_declared_file(root, directory, relative, manifest)
        path = _safe_path(root, directory.relative_to(root) / relative)
        try:
            frame = pd.read_csv(path, dtype=str, keep_default_na=False)
        except pd.errors.EmptyDataError:
            return TableResult(empty, "Dataset is empty; no values are displayed.", "empty", metadata)
        validate_table(name, frame)
        for column in frame:
            if column in BOOLEAN:
                frame[column] = frame[column].str.lower().map({"true": True, "false": False}).astype("boolean")
            elif column not in TEXT:
                frame[column] = pd.to_numeric(frame[column].replace("", pd.NA), errors="raise")
        period = next((c for c in ("target_month", "month", "metric_date", "date", "period", "published_at") if c in frame), None)
        last_period = str(frame[period].max()) if period and not frame.empty else None
        metadata = Metadata(metadata.mode, metadata.source, last_period, metadata.generated_at, metadata.freshness)
        status = "empty" if frame.empty else "stale" if metadata.freshness == "stale" else "ok"
        message = "Dataset is empty; no values are displayed." if frame.empty else "Stored data is older than the display freshness threshold." if status == "stale" else ""
        return TableResult(frame, message, status, metadata)
    except (OSError, ValueError, TypeError, AttributeError, OverflowError) as exc:
        status, message = _failure(exc)
        return TableResult(empty, message, status, metadata)


def _validate_metrics(value):
    if isinstance(value, bool) or value is None:
        raise ValueError("Metrics must be finite numbers or string labels")
    if isinstance(value, dict):
        for item in value.values():
            _validate_metrics(item)
    elif isinstance(value, list):
        for item in value:
            _validate_metrics(item)
    elif isinstance(value, (int, float)):
        if not math.isfinite(value):
            raise ValueError("Non-finite metric")
    elif not isinstance(value, str):
        raise ValueError("Invalid metric value")


def load_artifact(name: str, *, data_root: Path | None = None, bundle: str | None = None,
                  now: datetime | None = None, stale_days: int = 45) -> JsonResult:
    """Read an approved envelope; unknown payload fields are preserved, not endorsed."""
    if name not in ARTIFACTS:
        raise ValueError(f"Unknown artifact: {name}")
    metadata = Metadata()
    try:
        root, directory, manifest, metadata, legacy, clock = _context(Path(data_root or DATA_ROOT), bundle, now, stale_days)
        if legacy or name not in manifest.get("artifacts", []):
            return JsonResult(message="Artifact unavailable: not declared in the manifest.", status="missing", metadata=metadata)
        relative = ARTIFACTS[name]
        _validate_declared_file(root, directory, relative, manifest)
        document = _json(_safe_path(root, directory.relative_to(root) / relative))
        if type(document.get("version")) is not int or document["version"] != 1:
            raise ValueError("Invalid artifact version")
        metadata = _metadata(document, now=clock, stale_days=stale_days, mode=metadata.mode)
        payload = document.get("payload")
        if not isinstance(payload, dict):
            raise ValueError("Artifact payload object required")
        if name == "model_results":
            if not isinstance(payload.get("metrics"), dict) or not isinstance(payload.get("limitations"), list) or any(not isinstance(v, str) for v in payload["limitations"]):
                raise ValueError("Invalid results payload")
            _validate_metrics(payload["metrics"])
        elif name == "quality_report":
            if payload.get("status") not in {"pass", "fail", "unknown"} or not isinstance(payload.get("checks"), list) or any(not isinstance(v, dict) for v in payload["checks"]):
                raise ValueError("Invalid quality payload")
        elif not isinstance(payload.get("sources"), list) or any(not isinstance(v, dict) for v in payload["sources"]):
            raise ValueError("Invalid source payload")
        state = "stale" if metadata.freshness == "stale" else "ok"
        return JsonResult(payload, "Stored metadata is older than the display freshness threshold." if state == "stale" else "", state, metadata)
    except (OSError, ValueError, TypeError, AttributeError, OverflowError) as exc:
        status, message = _failure(exc)
        return JsonResult(message=message, status=status, metadata=metadata)


def load_predictions(**kwargs) -> TableResult:
    """Load predictions table."""
    return load_table("predictions", **kwargs)


def load_alerts(**kwargs) -> TableResult:
    """Load alerts table."""
    return load_table("alerts", **kwargs)


def load_flows(**kwargs) -> TableResult:
    """Load category-month flows table."""
    return load_table("flows_category_month", **kwargs)


def load_shortlist(**kwargs) -> TableResult:
    """Load fund research shortlist table."""
    return load_table("shortlist", **kwargs)


def load_sentiment(**kwargs) -> TableResult:
    """Load sentiment aggregates; use load_sentiment_items for article-level evidence."""
    return load_table("sentiment_agg", **kwargs)


def load_sentiment_items(**kwargs) -> TableResult:
    """Load sentiment item-level records."""
    return load_table("sentiment_items", **kwargs)


def load_market(**kwargs) -> TableResult:
    """Load market monthly indicators table."""
    return load_table("market_month", **kwargs)


def load_nav_daily(**kwargs) -> TableResult:
    """Load daily NAV history table."""
    return load_table("nav_daily", **kwargs)


def load_scheme_master(**kwargs) -> TableResult:
    """Load scheme master reference table."""
    return load_table("scheme_master", **kwargs)


def load_feature_matrix(**kwargs) -> TableResult:
    """Load modeling feature matrix table."""
    return load_table("feature_matrix", **kwargs)


def load_model_results(**kwargs) -> JsonResult:
    """Load model_results JSON artifact envelope."""
    return load_artifact("model_results", **kwargs)


def load_quality_metadata(**kwargs) -> JsonResult:
    """Load quality_report JSON artifact envelope."""
    return load_artifact("quality_report", **kwargs)


def load_source_metadata(**kwargs) -> JsonResult:
    """Load source_metadata JSON artifact envelope."""
    return load_artifact("source_metadata", **kwargs)


def get_bundle_fingerprint(data_root: Optional[Path] = None, bundle: Optional[str] = None) -> str:
    """Compute a deterministic fingerprint of the active data bundle.
    
    Tied to manifest SHA-256 and modification timestamp. When a snapshot is refreshed
    or manifest changes, this fingerprint changes, automatically invalidating UI caches.
    """
    root = Path(data_root or DATA_ROOT).resolve()
    try:
        directory = _bundle(root, bundle)
        manifest_p = directory / "manifest.json"
        if not manifest_p.is_file():
            return f"missing:{directory.name}"
        content = manifest_p.read_bytes()
        sha = hashlib.sha256(content).hexdigest()[:16]
        mtime = int(manifest_p.stat().st_mtime)
        return f"{directory.name}:{sha}:{mtime}"
    except Exception as exc:
        return f"err:{type(exc).__name__}"
