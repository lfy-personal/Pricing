from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List


@dataclass
class RunPaths:
    run_id: str
    base_dir: Path

    @property
    def discovered_urls(self) -> Path:
        return self.base_dir / "discovered_urls.json"

    @property
    def observations(self) -> Path:
        return self.base_dir / "observations.csv"

    @property
    def errors(self) -> Path:
        return self.base_dir / "errors.csv"

    @property
    def progress(self) -> Path:
        return self.base_dir / "progress.json"

    @property
    def output_partial(self) -> Path:
        return self.base_dir / "output_partial.xlsx"

    @property
    def output_final(self) -> Path:
        return self.base_dir / "us_discount_policy.xlsx"

    @property
    def run_log(self) -> Path:
        return self.base_dir / "run.log"


def ensure_run_dir(run_id: str, root: str = "runs") -> RunPaths:
    base = Path(root) / run_id
    base.mkdir(parents=True, exist_ok=True)
    return RunPaths(run_id=run_id, base_dir=base)


def load_progress(paths: RunPaths) -> Dict[str, Any] | None:
    if not paths.progress.exists():
        return None
    return json.loads(paths.progress.read_text())


def save_progress(paths: RunPaths, payload: Dict[str, Any]) -> None:
    payload["updated_at"] = datetime.utcnow().isoformat()
    paths.progress.write_text(json.dumps(payload, indent=2))


def load_discovered_urls(paths: RunPaths) -> Dict[str, List[str]]:
    if not paths.discovered_urls.exists():
        return {}
    return json.loads(paths.discovered_urls.read_text())


def save_discovered_urls(paths: RunPaths, data: Dict[str, List[str]]) -> None:
    paths.discovered_urls.write_text(json.dumps(data, indent=2))


def _append_csv_row(path: Path, header: Iterable[str], row: Dict[str, Any]) -> None:
    file_exists = path.exists()
    with path.open("a", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(header))
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def append_observation(paths: RunPaths, row: Dict[str, Any]) -> None:
    header = [
        "brand",
        "gender",
        "category",
        "competitor",
        "url",
        "current_price",
        "was_price",
        "discount_pct",
        "timestamp",
    ]
    _append_csv_row(paths.observations, header, row)


def append_error(paths: RunPaths, row: Dict[str, Any]) -> None:
    header = ["timestamp", "context", "error"]
    _append_csv_row(paths.errors, header, row)


def ensure_run_log(paths: RunPaths) -> None:
    if not paths.run_log.exists():
        paths.run_log.write_text("LFY US Discount Researcher run log\n")


def write_log(paths: RunPaths, message: str) -> None:
    ensure_run_log(paths)
    timestamp = datetime.utcnow().isoformat()
    with paths.run_log.open("a") as handle:
        handle.write(f"[{timestamp}] {message}\n")
