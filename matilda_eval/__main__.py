"""python -m matilda_eval {run,judge,report,bench} [args]"""

from __future__ import annotations

import sys

COMMANDS = ("run", "judge", "report", "bench")


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in {"-h", "--help"}:
        print("usage: python -m matilda_eval {run,judge,report,bench} [args]")
        raise SystemExit(0 if len(sys.argv) > 1 else 2)
    cmd, rest = sys.argv[1], sys.argv[2:]
    if cmd not in COMMANDS:
        raise SystemExit(f"unknown command {cmd!r}. Expected one of: {', '.join(COMMANDS)}")
    sys.argv = [f"matilda_eval {cmd}", *rest]
    if cmd == "run":
        from matilda_eval.run import main as entry
    elif cmd == "judge":
        from matilda_eval.judge import main as entry
    elif cmd == "report":
        from matilda_eval.report import main as entry
    else:
        from matilda_eval.bench_conn import main as entry
    entry()


if __name__ == "__main__":
    main()
