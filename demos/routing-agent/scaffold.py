#!/usr/bin/env python3
"""Scaffold the routing-agent worked example into a target directory.

Reads worked-example.md (the file next to this script), extracts every fenced
code block whose first line is a path comment (e.g. ``# graph.py`` or
``# routers/llm.py``), and writes each block's contents to that path under
the target directory. The markdown is the single source of truth — edit it
and re-run this to get the updated files.

Usage:
    python scaffold.py [target_dir]

target_dir defaults to ./routing-agent in the current working directory.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "routing-worked-example.md"

PATH_COMMENT = re.compile(r"^#\s+([\w./-]+\.(?:py|ya?ml))\s*$")
CODE_BLOCK = re.compile(r"```(?:python|yaml|yml)\n(.*?)\n```", re.DOTALL)


def extract_files(markdown: str) -> dict[str, str]:
    files: dict[str, str] = {}
    for match in CODE_BLOCK.finditer(markdown):
        body = match.group(1)
        first_line = body.split("\n", 1)[0]
        m = PATH_COMMENT.match(first_line)
        if not m:
            continue
        path = m.group(1)
        if path in files:
            print(
                f"ERROR: duplicate code block for '{path}' in {SOURCE.name}",
                file=sys.stderr,
            )
            sys.exit(2)
        files[path] = body
    return files


def main() -> int:
    target_arg = sys.argv[1] if len(sys.argv) > 1 else "routing-agent"
    target = Path(target_arg).resolve()

    if not SOURCE.exists():
        print(f"ERROR: cannot find {SOURCE}", file=sys.stderr)
        return 1

    files = extract_files(SOURCE.read_text())
    if not files:
        print(
            f"ERROR: no labeled code blocks found in {SOURCE.name}. "
            f"Each block should start with a '# filename' comment.",
            file=sys.stderr,
        )
        return 1

    target.mkdir(parents=True, exist_ok=True)
    for relpath, body in sorted(files.items()):
        out = target / relpath
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(body + "\n")
        print(f"  wrote {out.relative_to(target.parent)}")

    print(f"\nScaffolded {len(files)} file(s) into {target}/")
    print()
    print("Next steps:")
    print(f"  cd {target}")
    print("  python3 -m venv .venv && source .venv/bin/activate")
    print("  pip install langchain-openai langgraph numpy pyyaml")
    print("  export OPENAI_API_KEY=sk-...")
    print("  python compare.py            # run all four routers side-by-side")
    print("  python agent.py --router llm # interactive REPL")
    return 0


if __name__ == "__main__":
    sys.exit(main())
