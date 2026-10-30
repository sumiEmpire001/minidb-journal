"""Educational JSON key-value store with checksummed, fsynced journal records.

POSIX only: a separate advisory lock file serializes cooperating processes.
"""
import fcntl
import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

MAX_RECORD = 2 * 1024 * 1024


class Corruption(RuntimeError):
    pass


class Conflict(RuntimeError):
    pass


def packed(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")


def no_constant(value):
    raise ValueError("Non-finite JSON constant " + value)


class Journal:
    def __init__(self, path="data.journal"):
        self.path = Path(path)
        self.lock_path = self.path.with_name(self.path.name + ".lock")
        if not self.path.parent.is_dir():
            raise ValueError("Journal parent directory must exist")

    @contextmanager
    def _locked(self):
        with self.lock_path.open("a+b") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    @staticmethod
    def _validate_ops(ops):
        if not isinstance(ops, list) or not 1 <= len(ops) <= 1000:
            raise ValueError("A transaction requires 1..1000 operations")
        for op in ops:
            if not isinstance(op, dict) or op.get("op") not in ("set", "delete"):
                raise ValueError("Unknown operation")
            if not isinstance(op.get("key"), str) or not op["key"] or len(op["key"]) > 512:
                raise ValueError("Keys must be strings of 1..512 characters")
            fields = {"op", "key", "value"} if op["op"] == "set" else {"op", "key"}
            if set(op) != fields:
                raise ValueError("Incorrect operation fields")
        packed(ops)  # Reject unserializable values and NaN before writing.

    @staticmethod
    def _apply(state, ops):
        for op in ops:
            if op["op"] == "set":
                state[op["key"]] = op["value"]
            else:
                state.pop(op["key"], None)

    def _load(self, allow_tail=False):
        state, revision, records, valid_bytes = {}, 0, 0, 0
        if not self.path.exists():
            return state, revision, records, valid_bytes, False
        with self.path.open("rb") as file:
            while True:
                line = file.readline(MAX_RECORD + 1)
                if not line:
                    break
                if len(line) > MAX_RECORD:
                    raise Corruption("Journal record exceeds size limit")
                if not line.endswith(b"\n"):
                    if allow_tail:
                        return state, revision, records, valid_bytes, True
                    raise Corruption("Truncated final record; explicit repair is required")
                try:
                    envelope = json.loads(line, parse_constant=no_constant)
                    if set(envelope) != {"payload", "sha256"}:
                        raise ValueError("Invalid envelope")
                    payload = envelope["payload"]
                    if hashlib.sha256(packed(payload)).hexdigest() != envelope["sha256"]:
                        raise ValueError("Checksum mismatch")
                    seq = payload["revision"]
                    if type(seq) is not int:
                        raise ValueError("Invalid revision")
                    if "snapshot" in payload:
                        if records != 0 or seq < 0 or set(payload) != {"revision", "snapshot"} or not isinstance(payload["snapshot"], dict):
                            raise ValueError("Invalid snapshot")
                        state = payload["snapshot"]
                    else:
                        if seq != revision + 1 or set(payload) != {"revision", "ops"}:
                            raise ValueError("Non-contiguous journal revision")
                        self._validate_ops(payload["ops"])
                        self._apply(state, payload["ops"])
                    revision, records, valid_bytes = seq, records + 1, valid_bytes + len(line)
                except (ValueError, KeyError, TypeError, UnicodeError) as exc:
                    raise Corruption(f"Invalid journal record at byte {valid_bytes}: {exc}") from exc
        return state, revision, records, valid_bytes, False

    @staticmethod
    def _record(payload):
        data = packed({"payload": payload, "sha256": hashlib.sha256(packed(payload)).hexdigest()}) + b"\n"
        if len(data) > MAX_RECORD:
            raise ValueError("Encoded journal record exceeds 2 MiB")
        return data

    def _sync_directory(self):
        descriptor = os.open(self.path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def transaction(self, ops, *, expected_revision=None):
        self._validate_ops(ops)
        if expected_revision is not None and (type(expected_revision) is not int or expected_revision < 0):
            raise ValueError("expected_revision must be a nonnegative integer")
        with self._locked():
            _, revision, _, _, _ = self._load()
            if expected_revision is not None and expected_revision != revision:
                raise Conflict(f"Expected revision {expected_revision}, found {revision}")
            data = self._record({"revision": revision + 1, "ops": ops})
            new_file = not self.path.exists()
            with self.path.open("ab") as file:
                file.write(data)
                file.flush()
                os.fsync(file.fileno())
            if new_file:
                self._sync_directory()
            return revision + 1

    def set(self, key, value, **options):
        return self.transaction([{"op": "set", "key": key, "value": value}], **options)

    def delete(self, key, **options):
        return self.transaction([{"op": "delete", "key": key}], **options)

    def snapshot(self):
        with self._locked():
            state, revision, records, size, _ = self._load()
            return {"revision": revision, "records": records, "bytes": size, "data": state}

    def get(self, key, default=None):
        return self.snapshot()["data"].get(key, default)

    def repair_tail(self):
        """Discard only an unterminated final record; never skip complete corruption."""
        with self._locked():
            _, revision, _, valid_bytes, damaged = self._load(allow_tail=True)
            if damaged:
                with self.path.open("r+b") as file:
                    file.truncate(valid_bytes)
                    file.flush()
                    os.fsync(file.fileno())
            return {"repaired": damaged, "revision": revision, "retained_bytes": valid_bytes}

    def compact(self):
        with self._locked():
            state, revision, _, _, _ = self._load()
            data = self._record({"revision": revision, "snapshot": state})
            descriptor, temporary = tempfile.mkstemp(prefix=self.path.name + ".compact-", dir=self.path.parent)
            try:
                with os.fdopen(descriptor, "wb") as file:
                    file.write(data)
                    file.flush()
                    os.fsync(file.fileno())
                os.replace(temporary, self.path)
                self._sync_directory()
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            return {"revision": revision, "bytes": len(data)}
