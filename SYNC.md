# SYNC.md

## 1. Defects Found

Each regression test below was written to isolate the stated defect: it reproduces the failure on the original adapter and passes after the corresponding fix.

### MAIA-812 — Records skipped at page boundaries

**Cause:** `pull()` used a timestamp-only cursor while the ERP returns only records where `updated_at > since`. Because timestamps have second-level resolution, a page could end in the middle of several records sharing the same timestamp. In the supplied scenario, `EXT-0049` and `EXT-0050` both had `2026-08-01 00:00:58`; after the first page ended on `EXT-0049`, the next request skipped `EXT-0050`.

**Test:** `test_pull_does_not_lose_record_when_page_boundary_shares_timestamp`

**Fix:** Pulls overlap the previous cursor by one second and deduplicate `(external_id, version)` pairs.

**Invariant:** Remote changes reachable through the API must not be lost because of pagination boundaries.

---

### MAIA-830 — Duplicate writes after a timeout

**Cause:** The ERP can commit a write and then return a 504. The original adapter retried with a new idempotency key on each attempt, so the ERP treated retries as new writes.

**Test:** `test_push_retry_after_timeout_does_not_duplicate_remote_write`

**Fix:** Each logical local mutation now has a stable `mutation_id`, and retries reuse the same idempotency key.

**Invariant:** Retrying one logical mutation must produce at most one remote effect.

---

### MAIA-844 — Newer ERP edit overwritten by stale local data

**Cause:** When the ERP returned a version conflict, the adapter fetched the newest version and then retried the stale local payload using that version. This bypassed optimistic concurrency protection.

**Test:** `test_push_does_not_overwrite_newer_remote_edit_after_conflict`

**Fix:** A divergent conflict is no longer automatically retried. The local mutation remains dirty for later reconciliation.

**Invariant:** A local edit must not silently overwrite a newer remote edit that it was not based on.

---

### Latent — Separate edits could share an idempotency key

**Condition:** A later logical edit produces the same payload as an earlier edit.

**Cause:** A payload-derived idempotency key cannot distinguish two separate operations with identical content.

**Test:** `test_separate_identical_local_edits_use_distinct_idempotency_operations`

**Fix:** `LocalStore.mark_dirty()` advances a mutation identity for each new local edit.

**Invariant:** Retries share an operation identity; separate logical edits do not.

---

### Latent — Local and ERP timestamps were compared in different timezones

**Condition:** A dirty local edit and remote edit occur close enough that ordering matters.

**Cause:** Local timestamps are UTC, while ERP timestamps are `+08:00` server-local values without an offset. Comparing them directly could choose the wrong winner.

**Test:** `test_pull_compares_remote_local_timestamp_in_same_timezone`

**Fix:** ERP timestamps are normalized to UTC before storage or comparison.

**Invariant:** Timestamp ordering must compare values on the same timeline.

---

### Latent — New local edits kept an old timestamp

**Condition:** A previously pulled record is later edited locally.

**Cause:** Marking a record dirty changed its payload but did not record when the local edit occurred.

**Test:** `test_mark_dirty_records_time_of_new_local_edit`

**Fix:** `mark_dirty()` now records the new local edit time and advances the mutation ID.

**Invariant:** A dirty record's timestamp must represent the local mutation being synchronized.

---

### Latent — Crash after an existing-record write commits

**Condition:** The ERP commits a write, the process dies before local acknowledgement is saved, and the idempotency window expires.

**Test:** `test_push_recovers_after_crash_when_idempotency_window_expired`

**Fix:** On version conflict, if the current ERP payload already equals the intended local payload, the adapter reconciles local state without another write. A different payload remains a genuine conflict.

**Invariant:** An already-committed mutation must not be duplicated after restart.

---

### Latent — Crash after a new-record create commits

**Condition:** A create commits remotely, the process dies before saving the returned version, and the idempotency window expires.

**Test:** `test_push_recovers_new_record_after_crash_when_idempotency_window_expired`

**Fix:** For a dirty record with `remote_version=None`, the adapter checks whether the intended record already exists remotely before retrying the create.

**Invariant:** One logical create must produce at most one remote effect.

---

### Latent — New local create could overwrite an existing ERP record

**Condition:** A locally new record uses an external ID that already exists in the ERP with different data.

**Test:** `test_push_new_record_does_not_overwrite_existing_remote_record`

**Fix:** Before creating a record with `remote_version=None`, the adapter checks whether the external ID already exists. Matching payloads are reconciled; different payloads are treated as a conflict and are not overwritten.

**Invariant:** A local create must not silently overwrite an independently existing ERP record.

---

## 2. Vendor Contract I Would Ask For

In priority order:

1. **Stable pagination cursor or continuation token.** A timestamp-only cursor cannot safely paginate an arbitrarily large group of records sharing one second. A composite `(updated_at, external_id)` cursor or opaque continuation token would solve this properly.

2. **Longer-lived or queryable idempotency operations.** The current 60-second window is too short for crash recovery. Ideally the ERP would allow the result of an operation to be queried by its idempotency key.

3. **Explicit timezone offsets.** ERP timestamps should be ISO-8601 values such as `2026-08-01T08:00:00+08:00` or UTC.

4. **Richer conflict responses.** Returning the current version and change details would make reconciliation safer.

5. **Transactional or resumable batch semantics.** Partial batch success should be explicitly represented per record.

While those contracts are unavailable, the adapter uses cursor overlap and deduplication, per-mutation idempotency, UTC normalization, payload reconciliation after ambiguous writes, and conservative conflict handling.

The remaining pagination limitation is important: overlap handles the supplied same-second boundary case, but if more than `page_size` records share one timestamp, the current ERP API provides no guaranteed way to advance through that tie group.

---

## 3. Crash Safety

A write can commit remotely before the local process records the acknowledgement.

For existing records, a restarted worker may retry with an old `remote_version`. If the ERP already contains exactly the intended payload, the adapter reconciles local metadata instead of writing again. If the payload differs, it remains a real conflict.

For new records, where `remote_version=None`, the adapter first checks whether the external ID already exists. If the payload matches, it reconciles the existing remote record. If the payload differs, it preserves the conflict instead of overwriting the ERP record.

On the pull side, records are applied before the cursor is advanced. Replaying a partially processed page after a crash is therefore safer than advancing the cursor first and permanently losing unapplied records.

In a real Postgres implementation, I would also persist local record changes and cursor advancement transactionally where possible.

---

## 4. What Breaks at Scale

This runs every five minutes across 500 tenants. The main risks are:

* **ERP request volume and retry amplification:** timeouts increase retry traffic and can worsen an already degraded ERP.
* **Schedule overlap:** if a tenant takes longer than five minutes, multiple syncs for the same tenant may run concurrently. I would enforce one active sync per tenant.
* **Dirty-record backlog:** unresolved conflicts or ERP outages can accumulate pending mutations.
* **Pull lag and cursor stagnation:** a worker can still be running while a tenant stops making synchronization progress.
* **Timestamp tie density:** higher write volume increases the chance that many changes share one second, stressing the vendor's timestamp-only pagination contract.
* **Tenant starvation:** one large or unhealthy tenant should not consume all worker capacity.

I would monitor ERP latency and timeout rate, retry attempts per mutation, sync duration, dirty-record count and age, unresolved conflict count and age, cursor advancement, pull freshness, full-page frequency at the same timestamp, and missed five-minute tenant runs.

The key operational signal is not simply whether the worker process is alive, but whether each tenant's data is continuing to make forward progress.
