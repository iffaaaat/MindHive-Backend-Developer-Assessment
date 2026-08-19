#!/usr/bin/env python3
"""Two-way sync between our local item store and the ERP in fake_erp.py.

This code is in production. It mostly works. Ops have raised three tickets:

  MAIA-812  "some items never appear on our side until someone edits them"
  MAIA-830  "price history shows two updates a second apart, we only made one"
  MAIA-844  "an edit made in the ERP was overwritten by our older value"

Task 5 is about this file. Read the tickets as symptoms, not diagnoses.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from fake_erp import ErpConflict, ErpTimeout, FakeErp


@dataclass
class LocalRecord:
    external_id: str
    payload: dict
    remote_version: int
    updated_at_utc: str          # "YYYY-MM-DD HH:MM:SS", UTC
    dirty: bool = False
    mutation_id: int = 0


@dataclass
class LocalStore:
    """Stands in for our Postgres tables. Committed writes only."""
    records: dict = field(default_factory=dict)
    cursor: str | None = None
    applied_log: list = field(default_factory=list)

    def upsert(self, rec: LocalRecord) -> None:
        self.records[rec.external_id] = rec
        self.applied_log.append((rec.external_id, rec.remote_version))

    def mark_dirty(
        self,
        external_id: str,
        payload: dict,
        updated_at_utc: str | None = None,
    ) -> None:
        rec = self.records[external_id]
        rec.payload = dict(payload)
        rec.dirty = True
        rec.mutation_id += 1
        rec.updated_at_utc = updated_at_utc or now_utc()

    def set_cursor(self, cursor: str) -> None:
        self.cursor = cursor


def now_utc() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())


def idempotency_key(external_id: str, mutation_id: int) -> str:
    blob = json.dumps(
        {
            "id": external_id,
            "mutation_id": mutation_id,
        },
        sort_keys=True,
    )
    return hashlib.sha256(blob.encode()).hexdigest()[:32]

def previous_second(timestamp: str) -> str:
    """Return an ERP wall-clock timestamp minus one second."""
    dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
    return (dt - timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S")

def erp_timestamp_to_utc(timestamp: str) -> str:
    """Convert ERP server-local (+08:00) timestamp to UTC."""
    server_tz = timezone(timedelta(hours=8))

    local_dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
    local_dt = local_dt.replace(tzinfo=server_tz)

    utc_dt = local_dt.astimezone(timezone.utc)
    return utc_dt.strftime("%Y-%m-%d %H:%M:%S")

def pull(erp: FakeErp, store: LocalStore, page_size: int = 50) -> int:
    """Pull remote changes since the stored cursor into the local store."""
    pulled = 0
    seen = set()

    while True:
        since = previous_second(store.cursor) if store.cursor else None
        page = erp.list_changes(since=since, limit=page_size)

        if not page:
            break

        new_records = 0

        for rec in page:
            identity = (rec.external_id, rec.version)

            if identity in seen:
                continue
            seen.add(identity)

            local = store.records.get(rec.external_id)

            # Overlap may return a record already applied in an earlier page/run.
            if local and local.remote_version == rec.version and not local.dirty:
                continue

            remote_updated_at_utc = erp_timestamp_to_utc(rec.updated_at)

            if local and local.dirty and local.updated_at_utc > remote_updated_at_utc:
                continue

            store.upsert(LocalRecord(
                external_id=rec.external_id,
                payload=dict(rec.payload),
                remote_version=rec.version,
                updated_at_utc=remote_updated_at_utc,
                dirty=False,
            ))
            pulled += 1
            new_records += 1

        store.set_cursor(page[-1].updated_at)

        if len(page) < page_size:
            break

        if new_records == 0:
            break

    return pulled

def push(erp: FakeErp, store: LocalStore, max_attempts: int = 3) -> int:
    """Push locally-dirty records to the ERP."""
    pushed = 0
    for rec in list(store.records.values()):
        if not rec.dirty:
            continue
        if rec.remote_version is None:
            current = erp.get(rec.external_id)

            if current:
                # A previous create may already have committed.
                if current.payload == rec.payload:
                    rec.remote_version = current.version
                    rec.updated_at_utc = erp_timestamp_to_utc(current.updated_at)
                    rec.dirty = False
                    store.upsert(rec)
                    pushed += 1

                # If the payload differs, this is a genuine create conflict.
                # Do not overwrite the existing ERP record.
                continue
            
        for attempt in range(max_attempts):
            try:
                remote = erp.write(rec.external_id, rec.payload,
                                   base_version=rec.remote_version,
                                   idempotency_key=idempotency_key(
                                       rec.external_id, rec.mutation_id))
            except ErpTimeout:
                continue                      # transient - try again
            except ErpConflict:
                current = erp.get(rec.external_id)

                # The previous attempt may have committed before we crashed or timed out.
                # If the ERP already contains exactly our intended payload, reconcile
                # locally instead of writing the same mutation again.
                if current and current.payload == rec.payload:
                    remote = current
                else:
                    # Genuine concurrent remote edit: do not silently overwrite it.
                    break
            rec.remote_version = remote.version
            rec.updated_at_utc = erp_timestamp_to_utc(remote.updated_at)
            rec.dirty = False
            store.upsert(rec)
            pushed += 1
            break
    return pushed


def sync(erp: FakeErp, store: LocalStore) -> dict:
    return {"pulled": pull(erp, store), "pushed": push(erp, store)}
