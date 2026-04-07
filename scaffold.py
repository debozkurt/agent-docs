#!/usr/bin/env python3
"""Scaffold the worked-example agent into a target directory.

Reads worked-example.md (the file next to this script), extracts every fenced
code block whose first line is a path comment (e.g. ``# db.py`` or
``# evals/cases.yaml``), and writes each block's contents to that path under
the target directory. The markdown is the single source of truth — edit it
and re-run this to get the updated files.

Usage:
    python scaffold.py [target_dir]

target_dir defaults to ./todo-agent in the current working directory.

The scaffold creates the directory if it doesn't exist. Existing files are
overwritten — back up local edits before re-running.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "worked-example.md"

# Match the first line of a code block: a comment with a relative file path.
# Accepts: "# foo.py", "# foo/bar.py", "# evals/cases.yaml", etc.
PATH_COMMENT = re.compile(r"^#\s+([\w./-]+\.(?:py|ya?ml))\s*$")

# Fenced code blocks for python or yaml. Captures the body between the fences.
CODE_BLOCK = re.compile(r"```(?:python|yaml|yml)\n(.*?)\n```", re.DOTALL)


def extract_files(markdown: str) -> dict[str, str]:
    """Return {relative_path: file_contents} for every labeled block."""
    files: dict[str, str] = {}
    for match in CODE_BLOCK.finditer(markdown):
        body = match.group(1)
        first_line = body.split("\n", 1)[0]
        m = PATH_COMMENT.match(first_line)
        if not m:
            continue
        path = m.group(1)
        if path in files:
            # The example declares each file in exactly one block. If a second
            # block claims the same path, that's a doc bug — fail loudly.
            print(
                f"ERROR: duplicate code block for '{path}' in {SOURCE.name}",
                file=sys.stderr,
            )
            sys.exit(2)
        files[path] = body
    return files


def main() -> int:
    target_arg = sys.argv[1] if len(sys.argv) > 1 else "todo-agent"
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
    print("  pip install langchain-openai langgraph 'sqlalchemy>=2.0'")
    print("  export OPENAI_API_KEY=sk-...")
    print("  python agent.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
