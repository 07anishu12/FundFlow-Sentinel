"""FundFlow machine-readable run reporting and provenance tracking.

Provides:
- Deterministic run report generation with unique run ID and timestamps.
- SHA-256 hash and byte size computation for all input and output files.
- Stage-by-stage execution logging with status, duration, warnings, and errors.
- Atomic report writing preserving last-known-good state on disk.
- Quantitative limitation and data sufficiency tracking.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from typing import Any, Optional


def compute_file_sha256(path: Path | str) -> str:
    """Compute the SHA-256 hex digest of a file; returns empty string if missing."""
    p = Path(path)
    if not p.is_file():
        return ""
    h = hashlib.sha256()
    with p.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def count_csv_rows(path: Path | str) -> int:
    """Count data rows in a CSV file (excluding header), safely ignoring empty lines."""
    p = Path(path)
    if not p.is_file():
        return 0
    try:
        count = 0
        with p.open("r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                if i > 0 and line.strip():
                    count += 1
        return count
    except Exception:
        return 0


def get_file_metadata(path: Path | str) -> dict[str, Any]:
    """Inspect a file and return sha256, size_bytes, and row count if CSV."""
    p = Path(path)
    if not p.exists():
        return {"exists": False, "sha256": "", "size_bytes": 0}
    info: dict[str, Any] = {
        "exists": True,
        "path": str(p),
        "sha256": compute_file_sha256(p),
        "size_bytes": p.stat().st_size,
    }
    if p.suffix.lower() == ".csv":
        info["rows"] = count_csv_rows(p)
    return info


def get_git_commit(cwd: Optional[Path] = None) -> str:
    """Query git rev-parse HEAD safely without failing if git is unavailable."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(cwd or Path.cwd()),
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return "unknown"


def atomic_write_text(content: str, target_path: Path | str) -> Path:
    """Write text atomically to a target file via a temporary file."""
    p = Path(target_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, p)
    return p


def atomic_write_json(obj: dict, target_path: Path | str, indent: int = 2) -> Path:
    """Serialize and write a JSON object atomically."""
    serialized = json.dumps(obj, indent=indent, default=str)
    return atomic_write_text(serialized, target_path)


class RunReporter:
    """Stateful orchestrator for generating auditable machine-readable run reports."""

    def __init__(
        self,
        cli_args: Optional[dict[str, Any]] = None,
        run_id: Optional[str] = None,
        base_dir: Optional[Path] = None,
    ):
        now_dt = datetime.now(timezone.utc)
        self.start_dt = now_dt
        self.start_time: str = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        self.end_time: Optional[str] = None
        self.duration_seconds: float = 0.0
        self.run_id: str = run_id or f"run_{now_dt.strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"
        self.base_dir: Path = base_dir or Path.cwd()
        self.git_commit: str = get_git_commit(self.base_dir)
        self.cli_args: dict[str, Any] = cli_args or {}

        self.stages: dict[str, dict[str, Any]] = {}
        self.inputs: dict[str, dict[str, Any]] = {}
        self.outputs: dict[str, dict[str, Any]] = {}
        self.metrics: dict[str, Any] = {}
        self.limitations: list[str] = []
        self.warnings: list[str] = []
        self.errors: list[str] = []
        self.status: str = "running"

    def register_input(self, label: str, path: Path | str) -> None:
        """Register an input file into the report with metadata and hash."""
        self.inputs[label] = get_file_metadata(path)

    def register_output(self, label: str, path: Path | str) -> None:
        """Register an output file into the report with metadata and hash."""
        self.outputs[label] = get_file_metadata(path)

    def start_stage(self, stage_name: str, input_paths: Optional[dict[str, Path | str]] = None) -> None:
        """Mark the beginning of a pipeline execution stage."""
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        stage_inputs = {}
        if input_paths:
            for lbl, p in input_paths.items():
                meta = get_file_metadata(p)
                stage_inputs[lbl] = meta
                self.inputs[lbl] = meta

        self.stages[stage_name] = {
            "status": "running",
            "start_time": now_iso,
            "end_time": None,
            "duration_seconds": None,
            "inputs": stage_inputs,
            "outputs": {},
            "details": {},
            "warnings": [],
            "errors": [],
        }

    def end_stage(
        self,
        stage_name: str,
        status: str = "success",
        output_paths: Optional[dict[str, Path | str]] = None,
        details: Optional[dict[str, Any]] = None,
        warnings: Optional[list[str]] = None,
        errors: Optional[list[str]] = None,
    ) -> None:
        """Mark the completion of a pipeline execution stage."""
        if stage_name not in self.stages:
            self.start_stage(stage_name)

        rec = self.stages[stage_name]
        now_dt = datetime.now(timezone.utc)
        rec["end_time"] = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            st_dt = datetime.fromisoformat(rec["start_time"].replace("Z", "+00:00"))
            rec["duration_seconds"] = round((now_dt - st_dt).total_seconds(), 3)
        except Exception:
            rec["duration_seconds"] = 0.0

        rec["status"] = status

        if output_paths:
            for lbl, p in output_paths.items():
                meta = get_file_metadata(p)
                rec["outputs"][lbl] = meta
                self.outputs[lbl] = meta

        if details:
            rec["details"].update(details)

        if warnings:
            rec["warnings"].extend(warnings)
            self.warnings.extend(warnings)

        if errors:
            rec["errors"].extend(errors)
            self.errors.extend(errors)

    def add_warning(self, message: str) -> None:
        """Add a global pipeline warning."""
        if message not in self.warnings:
            self.warnings.append(message)

    def add_error(self, message: str) -> None:
        """Add a global pipeline error."""
        if message not in self.errors:
            self.errors.append(message)

    def add_limitation(self, limitation: str) -> None:
        """Record an explicit limitation or data insufficiency notice."""
        if limitation not in self.limitations:
            self.limitations.append(limitation)

    def record_metrics(self, new_metrics: dict[str, Any]) -> None:
        """Merge evaluation metrics into the report."""
        self.metrics.update(new_metrics)

    def build_envelope(self, status: Optional[str] = None) -> dict[str, Any]:
        """Finalize and return the machine-readable run report dict."""
        end_dt = datetime.now(timezone.utc)
        self.end_time = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        self.duration_seconds = round((end_dt - self.start_dt).total_seconds(), 3)

        # Determine overall status if not explicitly given
        if status:
            self.status = status
        else:
            has_failed_stages = any(s.get("status") == "failed" for s in self.stages.values())
            has_warning_stages = any(s.get("status") in ("warning", "skipped") for s in self.stages.values())
            if has_failed_stages or self.errors:
                self.status = "failure"
            elif has_warning_stages or self.warnings:
                self.status = "partial_success"
            else:
                self.status = "success"

        # Tally summary
        n_total = len(self.stages)
        n_success = sum(1 for s in self.stages.values() if s.get("status") == "success")
        n_failed = sum(1 for s in self.stages.values() if s.get("status") == "failed")
        n_skipped = sum(1 for s in self.stages.values() if s.get("status") == "skipped")

        return {
            "version": 1,
            "run_id": self.run_id,
            "generated_at": self.end_time,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": self.duration_seconds,
            "status": self.status,
            "git_commit": self.git_commit,
            "environment": {
                "python_version": sys.version.split()[0],
                "platform": platform.platform(),
            },
            "cli_args": self.cli_args,
            "summary": {
                "total_stages": n_total,
                "successful_stages": n_success,
                "failed_stages": n_failed,
                "skipped_stages": n_skipped,
                "warnings_count": len(self.warnings),
                "errors_count": len(self.errors),
            },
            "stages": self.stages,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "metrics": self.metrics,
            "limitations": self.limitations,
            "warnings": self.warnings,
            "errors": self.errors,
        }

    def save(self, output_path: Path | str) -> Path:
        """Finalize and save the run report atomically to JSON."""
        envelope = self.build_envelope()
        return atomic_write_json(envelope, output_path)
