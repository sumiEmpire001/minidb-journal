import argparse
import json
from .store import Journal, Corruption, Conflict


def main():
    parser = argparse.ArgumentParser(description="Educational checksummed key-value journal")
    parser.add_argument("--db", default="data.journal")
    commands = parser.add_subparsers(dest="command", required=True)
    put = commands.add_parser("set")
    put.add_argument("key")
    put.add_argument("value", help="JSON value")
    get = commands.add_parser("get")
    get.add_argument("key")
    delete = commands.add_parser("delete")
    delete.add_argument("key")
    for name in ("inspect", "compact", "repair-tail"):
        commands.add_parser(name)
    args = parser.parse_args()
    try:
        journal = Journal(args.db)
        if args.command == "set":
            result = {"revision": journal.set(args.key, json.loads(args.value))}
        elif args.command == "get":
            result = {"value": journal.get(args.key)}
        elif args.command == "delete":
            result = {"revision": journal.delete(args.key)}
        elif args.command == "compact":
            result = journal.compact()
        elif args.command == "repair-tail":
            result = journal.repair_tail()
        else:
            result = journal.snapshot()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, Corruption, Conflict) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
