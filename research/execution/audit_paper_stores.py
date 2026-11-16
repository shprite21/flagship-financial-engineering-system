"""Count retained forward records in closed terminal stores; expose aggregate counts only."""

import argparse
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


QUERIES = {
    "paper/paper.sqlite": {
        "deployments": "SELECT count(*) FROM deployments",
        "events": "SELECT count(*) FROM events",
    },
    "flagship/survival/registry.sqlite": {
        "manual_registrations": "SELECT count(*) FROM artifacts WHERE kind='survival_paper'",
        "demo_registrations": """SELECT count(*) FROM artifacts WHERE kind='survival_paper'
                                 AND json_extract(body, '$.request.data_mode')='demo'""",
        "manual_signals": """SELECT count(*) FROM artifacts WHERE kind='survival_paper_event'
                             AND json_extract(body, '$.kind')='signal'""",
        "manual_observations": """SELECT count(*) FROM artifacts WHERE kind='survival_paper_event'
                                  AND json_extract(body, '$.kind')='observation'""",
    },
    "india/manual-journal.sqlite": {"manual_journal_events": "SELECT count(*) FROM events"},
}


def signature(path):
    files = {}
    for suffix in ("", "-wal", "-journal"):
        candidate = Path(str(path) + suffix)
        if candidate.exists():
            stat = candidate.stat()
            files[suffix] = (stat.st_size, stat.st_mtime_ns)
    if any(files.get(suffix, (0, 0))[0] for suffix in ("-wal", "-journal")):
        raise ValueError("Use a cleanly closed or checkpointed copy of the terminal store")
    return files


def inspect(root):
    if not root.is_dir():
        raise ValueError("Data directory was not found")
    counts = {}
    for name, queries in QUERIES.items():
        path = root.resolve() / name
        if not path.is_file():
            counts[name] = None
            continue
        before = signature(path)
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)) as db:
            counts[name] = {field: db.execute(q).fetchone()[0] for field, q in queries.items()}
        if signature(path) != before:
            raise ValueError("Store changed during inspection; retry with a closed copy")
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--terminal-v2-data", required=True, type=Path)
    parser.add_argument("--predecessor-data", type=Path)
    args = parser.parse_args()
    result = {
        "schema": 1,
        "inspected_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scope": "Aggregate counts in closed local terminal stores. A missing database is recorded as null.",
        "broker_account_evidence": "outside scope of local store audit",
        "terminal_v2": inspect(args.terminal_v2_data),
    }
    if args.predecessor_data:
        result["predecessor"] = inspect(args.predecessor_data)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
