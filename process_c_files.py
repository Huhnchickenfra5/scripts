#!/usr/bin/env python3
"""
Process C/H files: remove comments and reverse module-name prefixes.

Usage: python3 process_c_files.py <input_folder> [output_folder]

- Removes // and /* */ comments (respects string and char literals)
- Renames identifiers: first token before '_' is reversed
    uart_init  ->  trau_init
    spi_transfer  ->  ips_transfer
    GPIO_SET_PIN  ->  OIPG_SET_PIN
- Writes results to output folder (default: ./output), preserving directory tree
"""

import os
import sys
import re
from pathlib import Path


# ---------------------------------------------------------------------------
# 1. Comment removal (state-machine approach)
# ---------------------------------------------------------------------------

def remove_comments(source: str) -> str:
    """
    Strip // and /* */ comments from C source.

    Preserves the contents of double-quoted string literals and single-quoted
    character literals so that sequences like  "http://example.com"  or
    '/'  are never misinterpreted as comment openers.

    Newlines that fall inside a multi-line comment are kept so that line
    numbers in the output still roughly correspond to the original.
    """
    out: list[str] = []
    i = 0
    n = len(source)

    while i < n:
        c = source[i]

        # --- double-quoted string literal -----------------------------------
        if c == '"':
            out.append(c)
            i += 1
            while i < n and source[i] != '"':
                if source[i] == '\\' and i + 1 < n:
                    out.append(source[i])
                    out.append(source[i + 1])
                    i += 2
                else:
                    out.append(source[i])
                    i += 1
            if i < n:                       # closing quote
                out.append(source[i])
                i += 1

        # --- single-quoted character literal --------------------------------
        elif c == "'":
            out.append(c)
            i += 1
            while i < n and source[i] != "'":
                if source[i] == '\\' and i + 1 < n:
                    out.append(source[i])
                    out.append(source[i + 1])
                    i += 2
                else:
                    out.append(source[i])
                    i += 1
            if i < n:
                out.append(source[i])
                i += 1

        # --- single-line comment  // ----------------------------------------
        elif c == '/' and i + 1 < n and source[i + 1] == '/':
            i += 2
            while i < n and source[i] != '\n':
                i += 1
            # the '\n' itself is NOT consumed — it stays in the output

        # --- multi-line comment  /* … */ ------------------------------------
        elif c == '/' and i + 1 < n and source[i + 1] == '*':
            i += 2
            while i < n:
                if source[i] == '*' and i + 1 < n and source[i + 1] == '/':
                    i += 2
                    break
                if source[i] == '\n':       # preserve newlines for alignment
                    out.append('\n')
                i += 1

        # --- ordinary character ---------------------------------------------
        else:
            out.append(c)
            i += 1

    return ''.join(out)


# ---------------------------------------------------------------------------
# 2. Identifier renaming
# ---------------------------------------------------------------------------

_IDENT_RE = re.compile(r'\b([a-zA-Z][a-zA-Z0-9]*)(_[a-zA-Z0-9_]+)\b')

# #include lines must not be touched (header paths contain underscores)
_INCLUDE_RE = re.compile(r'^\s*#\s*include\b')


def _reverse_prefix(m: re.Match) -> str:
    """
    Callback for re.sub — reverses the first token (the part before the
    first underscore) of a matched identifier.

    Safety: if reversing would produce a prefix that starts with a digit
    (e.g. uint8_t -> 8tniu_t) the identifier is left unchanged, because
    that would create an illegal C token.
    """
    prefix = m.group(1)
    rest   = m.group(2)          # includes the leading '_'

    rev = prefix[::-1]

    # A C identifier cannot start with a digit
    if rev[0].isdigit():
        return m.group(0)        # leave unchanged

    return rev + rest


def rename_identifiers(source: str) -> str:
    """
    Walk every line of *source* and reverse the module-name prefix of each
    identifier that contains at least one underscore.

    Lines that are ``#include`` directives are passed through untouched so
    that header paths are never corrupted.

    Identifiers that start with an underscore (reserved / compiler names
    like ``__attribute__``, ``_Bool``) are never matched by the regex and
    are therefore left alone.
    """
    lines = source.split('\n')
    result: list[str] = []

    for line in lines:
        if _INCLUDE_RE.match(line):
            result.append(line)
        else:
            result.append(_IDENT_RE.sub(_reverse_prefix, line))

    return '\n'.join(result)


# ---------------------------------------------------------------------------
# 3. File / directory walking
# ---------------------------------------------------------------------------

_C_EXTENSIONS = {'.c', '.h'}


def process_file(in_path: str, out_path: str) -> None:
    """Read one C/H file, strip comments, rename identifiers, write output."""
    with open(in_path, 'r', encoding='utf-8', errors='replace') as fh:
        source = fh.read()

    source = remove_comments(source)
    source = rename_identifiers(source)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as fh:
        fh.write(source)


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <input_folder> [output_folder]")
        sys.exit(1)

    in_dir  = Path(sys.argv[1]).resolve()
    out_dir = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else Path('output').resolve()

    if not in_dir.is_dir():
        print(f"Error: '{in_dir}' is not a directory")
        sys.exit(1)

    files = sorted(
        p for p in in_dir.rglob('*')
        if p.is_file() and p.suffix.lower() in _C_EXTENSIONS
    )

    if not files:
        print(f"No .c or .h files found under '{in_dir}'")
        sys.exit(0)

    print(f"Found {len(files)} file(s) to process")
    print(f"Output: {out_dir}\n")

    for fpath in files:
        rel = fpath.relative_to(in_dir)
        dest = out_dir / rel
        print(f"  {rel}")
        process_file(str(fpath), str(dest))

    print(f"\nDone — {len(files)} file(s) written to {out_dir}")


if __name__ == '__main__':
    main()
