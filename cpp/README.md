# MiniDB Journal

The original Python POSIX append-only JSON journal, checksums, transactions, file locks and compaction remain unchanged.

## Embedded C++ companion

`cpp/EmbeddedJournal.h` is an **in-memory, fixed-capacity** key/value revision engine for Arduino Uno/ESP32 algorithm demonstrations. Supports 16 numeric keys, optimistic expected revisions, missing-key detection, explicit reset and latched fault on revision conflicts/capacity overflow.

Run: `cmake -S cpp -B cpp/build && cmake --build cpp/build && ctest --test-dir cpp/build --output-on-failure`. Python regression: `python -m unittest discover -s tests -v`.

**Intentional differences:** This is not a persistent journal, and does not reproduce Python's JSON records, atomic transactions, checksums, disk locking, repair or compaction. Values are signed 32-bit integers only. Uno RAM is limited; ESP32 has more memory but persistence still requires a separate wear-aware storage design. Do not use for financial or safety-critical data without durable storage and recovery verification.