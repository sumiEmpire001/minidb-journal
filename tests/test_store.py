import concurrent.futures
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from minidb import Journal, Corruption, Conflict
from minidb.store import packed


def process_write(arguments):
    path, number = arguments
    return Journal(path).set(str(number), number)


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "test.journal"
        self.db = Journal(self.path)

    def test_round_trip_and_restart(self):
        self.db.set("hello", {"unicode": "Café 🌍", "items": [1, None, False]})
        self.assertEqual(Journal(self.path).get("hello"), {"unicode": "Café 🌍", "items": [1, None, False]})
        self.assertEqual(self.db.snapshot()["revision"], 1)

    def test_transaction_is_one_record_with_all_changes(self):
        self.db.transaction([{"op": "set", "key": "one", "value": 1}, {"op": "set", "key": "two", "value": 2}])
        self.assertEqual(self.db.snapshot()["data"], {"one": 1, "two": 2})
        self.assertEqual(self.db.snapshot()["records"], 1)

    def test_invalid_transaction_does_not_partially_apply(self):
        self.db.set("old", 1)
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            self.db.transaction([{"op": "set", "key": "new", "value": 2}, {"op": "set", "key": "bad"}])
        self.assertEqual(self.path.read_bytes(), before)
        self.assertIsNone(self.db.get("new"))

    def test_optimistic_revision_conflict(self):
        self.db.set("a", 1, expected_revision=0)
        with self.assertRaises(Conflict):
            self.db.set("b", 2, expected_revision=0)
        self.assertEqual(self.db.snapshot()["data"], {"a": 1})

    def test_truncated_tail_requires_explicit_repair(self):
        self.db.set("first", 1)
        self.db.set("second", 2)
        self.path.write_bytes(self.path.read_bytes()[:-10])
        with self.assertRaises(Corruption):
            self.db.snapshot()
        report = self.db.repair_tail()
        self.assertTrue(report["repaired"])
        self.assertEqual(report["revision"], 1)
        self.assertEqual(self.db.snapshot()["data"], {"first": 1})
        self.assertEqual(self.db.set("third", 3), 2)

    def test_complete_corruption_is_never_silently_discarded(self):
        self.db.set("one", 1)
        data = self.path.read_bytes().replace(b'"value":1', b'"value":9')
        self.path.write_bytes(data)
        with self.assertRaises(Corruption):
            self.db.snapshot()
        with self.assertRaises(Corruption):
            self.db.repair_tail()
        self.assertEqual(self.path.read_bytes(), data)

    def test_compaction_preserves_values_revision_and_future_writes(self):
        for i in range(20):
            self.db.set("value", i)
        before = self.path.stat().st_size
        report = self.db.compact()
        self.assertLess(report["bytes"], before)
        current = Journal(self.path).snapshot()
        self.assertEqual(current["revision"], 20)
        self.assertEqual(current["records"], 1)
        self.assertEqual(current["data"], {"value": 19})
        self.assertEqual(self.db.set("next", True), 21)

    def test_empty_compaction_and_recovery_are_valid(self):
        self.assertFalse(self.db.repair_tail()["repaired"])
        self.db.compact()
        self.assertEqual(self.db.snapshot()["revision"], 0)
        self.assertEqual(self.db.set("first", 1), 1)

    def test_non_contiguous_revision_is_rejected_even_with_valid_checksum(self):
        self.db.set("a", 1)
        envelope = json.loads(self.path.read_bytes())
        envelope["payload"]["revision"] = 10
        envelope["sha256"] = hashlib.sha256(packed(envelope["payload"])).hexdigest()
        self.path.write_bytes(packed(envelope) + b"\n")
        with self.assertRaises(Corruption):
            self.db.snapshot()

    def test_multiprocess_writes_are_serialized_without_lost_updates(self):
        with concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:
            revisions = list(pool.map(process_write, [(str(self.path), i) for i in range(24)]))
        self.assertEqual(set(revisions), set(range(1, 25)))
        self.assertEqual(self.db.snapshot()["data"], {str(i): i for i in range(24)})

    def test_delete_and_missing_values(self):
        self.db.set("a", None)
        marker = object()
        self.assertIsNone(self.db.get("a", marker))
        self.assertIs(self.db.get("missing", marker), marker)
        self.db.delete("a")
        self.db.delete("absent")
        self.assertEqual(self.db.snapshot()["data"], {})
        self.assertEqual(self.db.snapshot()["revision"], 3)

    def test_large_and_non_json_values_fail_before_append(self):
        self.db.set("a", 1)
        before = self.path.read_bytes()
        for value in ("x" * (2 * 1024 * 1024), float("nan"), float("inf"), object()):
            with self.subTest(value_type=type(value).__name__), self.assertRaises((ValueError, TypeError)):
                self.db.set("bad", value)
        self.assertEqual(self.path.read_bytes(), before)

    def test_invalid_operation_keys_and_revision(self):
        for key in ("", None, 1, "x" * 513):
            with self.assertRaises(ValueError):
                self.db.set(key, 1)
        with self.assertRaises(ValueError):
            self.db.transaction([])
        with self.assertRaises(ValueError):
            self.db.set("a", 1, expected_revision=True)

    def test_compaction_refuses_a_damaged_journal(self):
        self.path.write_bytes(b'{"partial":')
        with self.assertRaises(Corruption):
            self.db.compact()
        self.assertEqual(self.path.read_bytes(), b'{"partial":')

    def test_snapshots_do_not_expose_live_mutable_state(self):
        self.db.set("value", [1, 2])
        snapshot = self.db.snapshot()
        snapshot["data"]["value"].append(3)
        self.assertEqual(self.db.get("value"), [1, 2])


if __name__ == "__main__":
    unittest.main()
