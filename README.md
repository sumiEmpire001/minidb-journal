# MiniDB Journal

An educational JSON key-value store with checksummed append-only records, batched transactions, optimistic revisions, explicit interrupted-write repair and atomic compaction. Built for Lord_Sumi's portfolio.

## Run

Python 3.10+ on a **POSIX system** (Linux/macOS). Uses `fcntl` advisory locks; Windows is not supported in this version. No third-party runtime dependencies.

```bash
git clone https://github.com/sumiEmpire001/minidb-journal.git
cd minidb-journal
python -m minidb --db demo.journal set profile '{"name":"Demo","active":true}'
python -m minidb --db demo.journal get profile
python -m minidb --db demo.journal inspect
python -m minidb --db demo.journal compact
python -m unittest discover -s tests -v
```

## Transactions and revisions

```python
from minidb import Journal, Conflict

db = Journal("demo.journal")
revision = db.snapshot()["revision"]
new_revision = db.transaction([
    {"op": "set", "key": "status", "value": "ready"},
    {"op": "set", "key": "count", "value": 2},
], expected_revision=revision)
assert new_revision == revision + 1
```

All operations in a transaction are validated before a single journal record is appended. Cooperating processes serialize writes through a separate lock file. An outdated expected revision raises `Conflict` without writing. Every successful transaction increments the revision, including a deletion of an already-absent key.

Keys are strings of 1..512 characters. Values must be finite JSON values. Each encoded journal record is limited to 2 MiB and each transaction to 1000 operations. A snapshot reads a fresh value tree; mutating it does not change stored data.

## Format and recovery

Each line is a JSON envelope containing a payload and the SHA-256 of its canonical JSON bytes. Ordinary payloads contain a revision and operation list. Compaction writes one snapshot payload retaining the latest revision. Checksums detect accidental damage; they do not authenticate a journal against deliberate modification.

An unterminated last line indicates an interrupted append. Ordinary reads and writes refuse to proceed. After preserving a copy for investigation, explicitly repair the incomplete tail:

```bash
python -m minidb --db demo.journal repair-tail
```

Repair discards only that unterminated final record and retains all complete, valid preceding records. It refuses to skip a complete record with a checksum or sequence error. A partially written transaction is therefore not partially applied. No read silently truncates data.

## Compaction and durability

Compaction replays the current journal, writes and fsyncs a temporary snapshot, replaces the journal atomically, then fsyncs the parent directory. A separate lock file remains stable across replacement. Ordinary append operations flush and fsync before returning. New journals also sync their directory entry.

These mechanisms are educational durability techniques, not a guarantee against every filesystem, hardware or power-loss failure. A process can fail after a record reaches disk but before its caller receives success, so callers must inspect the revision before retrying non-idempotent work.

## Verification

Local checks on 30 October 2026: **15 tests passed**. Fixtures cover restart recovery, Unicode, multi-operation records, invalid transaction rollback, optimistic conflicts, simulated truncated tails, complete corruption rejection, compaction preservation, revision continuity, multiprocess write serialization and invalid/oversized values. Actual host power loss and failing storage hardware were not tested. CI is configured separately for Python 3.10, 3.12 and 3.13.

## Limits

This is not a replacement for SQLite or a production database. Every operation replays the journal: time and memory grow with its history. Compaction requires the entire resulting snapshot to fit in one 2 MiB record; an oversized compaction fails without replacing the old journal. Locks coordinate only processes using this implementation on a local filesystem. There is no encryption, authentication, backup scheduler, secondary index, network protocol or protection from an adversary modifying files outside the lock. Protect the directory and retain the lock file while the store is in use.

MIT license; see [LICENSE](LICENSE).
