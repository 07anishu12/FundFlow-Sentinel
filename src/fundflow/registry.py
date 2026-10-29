"""Local provenance ledger. No retrieval, credentials, or personal data storage.

Single-writer API: the integrator serializes writes. Replacement is atomic so
readers never observe a partially written CSV; multi-writer locking is not offered.
"""
from __future__ import annotations

import csv
import hashlib
import os
from pathlib import Path
import re
import tempfile
from datetime import datetime
from urllib.parse import urlsplit, unquote
from collections.abc import Iterable, Mapping

REGISTRY_COLUMNS = (
    "source_name", "url", "data_type", "frequency", "retrieved_at",
    "terms_url", "permitted_use", "attribution", "redistribution_status",
    "source_confidence", "sha256", "last_outcome", "status", "checked_on",
)
STATUSES = {"verified", "unverified", "restricted"}
OUTCOMES = {"success", "failed", "blocked", "not_attempted"}


def file_sha256(path: str | Path) -> str:
    """Hash file bytes in bounded memory; timestamps and names do not affect hash."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _public_url(value: str) -> None:
    """Only public credential-free URL locations, never query strings or fragments."""
    parsed = urlsplit(value)
    if (parsed.scheme not in {"https", "http"} or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError("Use a public HTTP(S) URL without credentials, query or fragment")
    # Exact retrieval parameters stay in separately reviewed ingestion metadata.
    if re.search(r"(?i)(api[_-]?key|token|secret|password|authorization)", unquote(parsed.path)):
        raise ValueError("Credential-like URL path rejected")


def validate_record(record: Mapping[str, str]) -> dict[str, str]:
    """Validate strict ledger fields; reject errors rather than save exception text."""
    if set(record) != set(REGISTRY_COLUMNS):
        raise ValueError("Registry columns do not match frozen ledger fields")
    row = dict(record)
    for key, value in row.items():
        if not isinstance(value, str) or len(value) > 2000 or any(ord(c) < 32 for c in value):
            raise ValueError(f"Invalid text in {key}")
        if value.lstrip().startswith(("=", "+", "-", "@")):
            raise ValueError(f"Spreadsheet formula prefix rejected in {key}")
        if re.search(r"(?i)(bearer\s+|(?:api[_-]?key|password|secret|token)\s*[:=]|[\w.+-]+@[\w.-]+\.[a-z]{2,})", value):
            raise ValueError(f"Credential or personal contact text rejected in {key}")
        if key not in {"retrieved_at", "sha256", "terms_url"} and not value.strip():
            raise ValueError(f"Required registry field: {key}")
    _public_url(row["url"])
    if row["terms_url"]:
        _public_url(row["terms_url"])
    if row["status"] not in STATUSES or row["last_outcome"] not in OUTCOMES:
        raise ValueError("Invalid registry status/outcome")
    if row["redistribution_status"] not in {"permitted_with_conditions", "restricted", "unknown"}:
        raise ValueError("Invalid redistribution status")
    if row["source_confidence"] not in {"official", "unofficial", "unknown"}:
        raise ValueError("Invalid source confidence")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["checked_on"]):
        raise ValueError("checked_on must be YYYY-MM-DD")
    datetime.strptime(row["checked_on"], "%Y-%m-%d")
    if row["retrieved_at"]:
        stamp = row["retrieved_at"]
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        if "T" not in stamp or parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
            raise ValueError("retrieved_at must be ISO UTC")
    if row["sha256"] and not re.fullmatch(r"[a-f0-9]{64}", row["sha256"]):
        raise ValueError("sha256 must be lowercase hex")
    if row["last_outcome"] == "success" and not (row["retrieved_at"] and row["sha256"]):
        raise ValueError("Successful retrieval requires timestamp and file hash")
    if row["last_outcome"] != "success" and row["sha256"]:
        raise ValueError("Non-success outcome cannot claim a retrieved file hash")
    if row["status"] == "unverified" and row["redistribution_status"] == "permitted_with_conditions":
        raise ValueError("Unverified source cannot claim redistribution permission")
    if row["status"] != "unverified" and not row["terms_url"]:
        raise ValueError("Verified/restricted status requires terms evidence URL")
    return row


def read_registry(path: str | Path) -> list[dict[str, str]]:
    """Missing ledger is empty; malformed existing ledgers fail loudly."""
    path = Path(path)
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != REGISTRY_COLUMNS:
            raise ValueError("Invalid registry header")
        return [validate_record(row) for row in reader]


def write_registry(path: str | Path, records: Iterable[Mapping[str, str]]) -> None:
    """Validate all rows before atomic replacement, retaining old file on failure."""
    rows = [validate_record(row) for row in records]
    path = Path(path)
    if path.is_symlink():
        raise ValueError("Refusing symlink ledger destination")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", newline="", encoding="utf-8",
                                         dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            writer = csv.DictWriter(stream, fieldnames=REGISTRY_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def append_record(path: str | Path, record: Mapping[str, str]) -> None:
    """Append an immutable attempt under the documented single-writer policy."""
    write_registry(path, [*read_registry(path), validate_record(record)])
