"""Append-only, hash-chained audit trail (JSON Lines).

Each entry stores the SHA-256 of the previous entry, so editing, deleting or
re-ordering any line breaks the chain and `verify()` reports where.
This demonstrates the *idea* behind 21 CFR Part 11 audit-trail expectations
(who / what / when, tamper-evident); it is not a validated Part 11 system.
"""
from __future__ import annotations

import getpass
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

GENESIS = "0" * 64


def _digest(entry: dict) -> str:
    body = {k: v for k, v in entry.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class AuditTrail:
    def __init__(self, path: Path, run_id: str, clock=None):
        self.path, self.run_id = path, run_id
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.prev, self.seq = GENESIS, 0
        try:
            self.user = getpass.getuser()
        except Exception:  # pragma: no cover - containers without a passwd entry
            self.user = "unknown"

    def log(self, action: str, **details) -> None:
        self.seq += 1
        entry = {"seq": self.seq, "run_id": self.run_id,
                 "ts": self.clock().strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "user": self.user, "action": action, "details": details,
                 "prev_hash": self.prev}
        entry["hash"] = _digest(entry)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, sort_keys=True) + "\n")
        self.prev = entry["hash"]


def verify(path: Path) -> tuple[bool, str]:
    prev, n = GENESIS, 0
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        entry = json.loads(line)
        if entry.get("prev_hash") != prev:
            return False, f"line {n}: chain broken (prev_hash mismatch)"
        if _digest(entry) != entry.get("hash"):
            return False, f"line {n}: entry content altered (hash mismatch)"
        if entry.get("seq") != n:
            return False, f"line {n}: sequence gap or reorder"
        prev = entry["hash"]
    return True, f"OK: {n} entries, chain intact"
