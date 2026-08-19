import unittest
from unittest.mock import patch

from fake_erp import FakeErp, Record
from sync_adapter import (
    LocalRecord,
    LocalStore,
    erp_timestamp_to_utc,
    idempotency_key,
    pull,
    push,
)

class SyncAdapterTests(unittest.TestCase):

    def test_pull_does_not_lose_record_when_page_boundary_shares_timestamp(self):
        erp = FakeErp(seed=11, timeout_rate=0)
        erp.seed_records(60)
        store = LocalStore()

        pull(erp, store, page_size=50)

        self.assertIn("EXT-0050", store.records)
        self.assertEqual(len(store.records), 60)

    def test_push_retry_after_timeout_does_not_duplicate_remote_write(self):
        erp = FakeErp(seed=1, timeout_rate=1.0)

        store = LocalStore()
        store.upsert(LocalRecord(
            external_id="EXT-NEW",
            payload={"name": "new item", "price": 999.0, "uom": "Nos"},
            remote_version=None,
            updated_at_utc="2026-08-01 00:00:00",
            dirty=True,
        ))

        push(erp, store, max_attempts=3)

        writes = [
            entry for entry in erp.write_log
            if entry[0] == "EXT-NEW"
        ]

        self.assertEqual(len(writes), 1)

    def test_push_does_not_overwrite_newer_remote_edit_after_conflict(self):
        erp = FakeErp(seed=1, timeout_rate=0)
        erp.seed_records(1)

        original = erp.get("EXT-0000")

        store = LocalStore()
        store.upsert(LocalRecord(
            external_id="EXT-0000",
            payload=dict(original.payload, price=999.0),
            remote_version=original.version,
            updated_at_utc=original.updated_at,
            dirty=True,
        ))

        # ERP user edits the same record after our local copy was based on v1.
        erp.tick(120)
        erp.write(
            "EXT-0000",
            {"name": "item 0", "price": 55.5, "uom": "Box"},
            base_version=original.version,
        )

        push(erp, store)

        remote = erp.get("EXT-0000")

        self.assertEqual(remote.payload["price"], 55.5)
        self.assertEqual(remote.payload["uom"], "Box")

    def test_separate_identical_local_edits_use_distinct_idempotency_operations(self):
        erp = FakeErp(seed=1, timeout_rate=0)
        erp.seed_records(1)

        remote = erp.get("EXT-0000")

        store = LocalStore()
        store.upsert(LocalRecord(
            external_id="EXT-0000",
            payload=dict(remote.payload, price=999.0),
            remote_version=remote.version,
            updated_at_utc=remote.updated_at,
            dirty=True,
            mutation_id=1,
        ))

        # First logical edit: -> 999
        push(erp, store)

        # Second logical edit: -> 500
        store.mark_dirty(
            "EXT-0000",
            dict(store.records["EXT-0000"].payload, price=500.0),
        )
        push(erp, store)

        # Third logical edit: -> 999 again.
        # This is a NEW operation, not a retry of the first one.
        store.mark_dirty(
            "EXT-0000",
            dict(store.records["EXT-0000"].payload, price=999.0),
        )
        push(erp, store)

        remote = erp.get("EXT-0000")

        self.assertEqual(remote.payload["price"], 999.0)
        self.assertEqual(remote.version, 4)

    def test_pull_compares_remote_local_timestamp_in_same_timezone(self):
        erp = FakeErp(seed=1, timeout_rate=0)

        # ERP timestamp is server-local +08:00.
        # 08:00 ERP local == 00:00 UTC.
        erp.records["EXT-TZ"] = Record(
            external_id="EXT-TZ",
            payload={"name": "remote old value", "price": 10.0, "uom": "Nos"},
            version=2,
            updated_at="2026-08-01 08:00:00",
        )

        store = LocalStore()
        store.upsert(LocalRecord(
            external_id="EXT-TZ",
            payload={"name": "local newer value", "price": 999.0, "uom": "Nos"},
            remote_version=1,
            updated_at_utc="2026-08-01 00:30:00",
            dirty=True,
            mutation_id=1,
        ))

        pull(erp, store)

        local = store.records["EXT-TZ"]

        self.assertEqual(local.payload["price"], 999.0)
        self.assertTrue(local.dirty)

    def test_push_recovers_after_crash_when_idempotency_window_expired(self):
        erp = FakeErp(seed=1, timeout_rate=0)
        erp.seed_records(1)

        original = erp.get("EXT-0000")

        store = LocalStore()
        store.upsert(LocalRecord(
            external_id="EXT-0000",
            payload=dict(original.payload, price=999.0),
            remote_version=original.version,
            updated_at_utc=erp_timestamp_to_utc(original.updated_at),
            dirty=True,
            mutation_id=1,
        ))

        rec = store.records["EXT-0000"]
        key = idempotency_key(rec.external_id, rec.mutation_id)

        # The ERP commits our mutation...
        erp.write(
            rec.external_id,
            rec.payload,
            base_version=rec.remote_version,
            idempotency_key=key,
        )

        # ...but our process crashes before marking the local row clean.
        # Simulate the vendor's 60-second idempotency window expiring.
        erp._idem.clear()

        push(erp, store)

        remote = erp.get("EXT-0000")
        local = store.records["EXT-0000"]

        writes = [
            entry for entry in erp.write_log
            if entry[0] == "EXT-0000"
            and entry[2].get("price") == 999.0
        ]

        self.assertEqual(len(writes), 1)
        self.assertEqual(local.remote_version, remote.version)
        self.assertFalse(local.dirty)

    def test_mark_dirty_records_time_of_new_local_edit(self):
        store = LocalStore()

        store.upsert(LocalRecord(
            external_id="EXT-LOCAL",
            payload={"name": "item", "price": 10.0, "uom": "Nos"},
            remote_version=1,
            updated_at_utc="2026-08-01 00:00:00",
            dirty=False,
            mutation_id=0,
        ))

        with patch("sync_adapter.now_utc", return_value="2026-08-01 00:30:00"):
            store.mark_dirty(
                "EXT-LOCAL",
                {"name": "item", "price": 999.0, "uom": "Nos"},
            )

        rec = store.records["EXT-LOCAL"]

        self.assertEqual(rec.updated_at_utc, "2026-08-01 00:30:00")
        self.assertTrue(rec.dirty)
        self.assertEqual(rec.mutation_id, 1)

    def test_push_recovers_new_record_after_crash_when_idempotency_window_expired(self):
        erp = FakeErp(seed=1, timeout_rate=0)

        store = LocalStore()
        store.upsert(LocalRecord(
            external_id="EXT-NEW",
            payload={"name": "new item", "price": 999.0, "uom": "Nos"},
            remote_version=None,
            updated_at_utc="2026-08-01 00:00:00",
            dirty=True,
            mutation_id=1,
        ))

        rec = store.records["EXT-NEW"]
        key = idempotency_key(rec.external_id, rec.mutation_id)

        # ERP commits the create, but our process dies before local acknowledgement.
        erp.write(
            rec.external_id,
            rec.payload,
            base_version=None,
            idempotency_key=key,
        )

        # Simulate the documented idempotency window having expired.
        erp._idem.clear()

        push(erp, store)

        writes = [
            entry for entry in erp.write_log
            if entry[0] == "EXT-NEW"
        ]

        self.assertEqual(len(writes), 1)
        self.assertEqual(store.records["EXT-NEW"].remote_version, 1)
        self.assertFalse(store.records["EXT-NEW"].dirty)

    def test_push_new_record_does_not_overwrite_existing_remote_record(self):
        erp = FakeErp(seed=1, timeout_rate=0)

        erp.write(
            "EXT-NEW",
            {"name": "ERP item", "price": 50.0, "uom": "Box"},
            base_version=None,
        )

        store = LocalStore()
        store.upsert(LocalRecord(
            external_id="EXT-NEW",
            payload={"name": "local item", "price": 999.0, "uom": "Nos"},
            remote_version=None,
            updated_at_utc="2026-08-01 00:00:00",
            dirty=True,
            mutation_id=1,
        ))

        push(erp, store)

        remote = erp.get("EXT-NEW")

        self.assertEqual(remote.payload["price"], 50.0)
        self.assertEqual(remote.payload["uom"], "Box")
        self.assertTrue(store.records["EXT-NEW"].dirty)

if __name__ == "__main__":
    unittest.main()