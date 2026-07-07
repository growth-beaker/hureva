"""The `hureva` command — dispatches to subcommands.

    hureva ci         # notify + gate for a push (what the workflow runs)
    hureva notify     # route notifications only
    hureva gate       # gate only
    hureva new-spec   # create a spec folder + branch

Each subcommand is the `main(argv)` of its module, so `hureva notify …` and
`python -m hureva.notify …` behave identically.
"""

from __future__ import annotations

import sys

from . import ci, gate, new_spec, notify

_SUBCOMMANDS = {
    "ci": ci.main,
    "notify": notify.main,
    "gate": gate.main,
    "new-spec": new_spec.main,
}


def _usage(stream=sys.stdout) -> None:
    print("usage: hureva <command> [options]\n", file=stream)
    print("commands:", file=stream)
    print("  ci        notify + gate for a push (run this in CI)", file=stream)
    print("  notify    route notifications for a push", file=stream)
    print("  gate      gate the specs changed in a push (or one --slug)", file=stream)
    print("  new-spec  create a spec folder + spec/<slug> branch", file=stream)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        _usage()
        return 0

    command, rest = argv[0], argv[1:]
    handler = _SUBCOMMANDS.get(command)
    if handler is None:
        print(f"hureva: unknown command {command!r}\n", file=sys.stderr)
        _usage(sys.stderr)
        return 2
    return handler(rest)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
