#!/usr/bin/env python3
"""Print the package names recorded in a lockfile, one per line.

Supports bun.lock, yarn.lock (v1 classic and berry), pnpm-lock.yaml, Cargo.lock
and uv.lock. Parses text only. Never installs, never resolves, never reaches the
network, so it is safe to run against an untrusted lockfile.

  lockfile_packages.py <lockfile>                list every package name
  lockfile_packages.py <base_lock> <head_lock>   list names present only in head
"""

import re
import sys
from pathlib import Path

# yarn and pnpm descriptors can carry a protocol ("pkg@npm:...", "pkg@patch:...")
# or a peer suffix ("pkg@1.2.3(peer@4.5.6)"). Both defeat a naive rsplit on "@".
_PROTOCOL = re.compile(
    r"@(?:npm|patch|workspace|file|link|portal|git|git\+ssh|git\+https"
    r"|https?|ssh|exec|virtual|alias):"
)


def split_name(spec):
    """'@scope/pkg@1.2.3' -> '@scope/pkg';  'pkg@npm:@other/pkg@^1' -> 'pkg'."""
    spec = spec.split("(", 1)[0]
    proto = _PROTOCOL.search(spec)
    if proto and proto.start() > 0:
        return spec[: proto.start()]
    at = spec.rfind("@")
    return spec[:at] if at > 0 else spec


def bun(text):
    """bun.lock: "packages": { "<key>": ["<name>@<version>", <registry>, ...] }

    The name comes from the array's first element, not the key: bun records a
    hoisted duplicate under a compound key such as "anchor-bankrun/@coral-xyz/anchor".

    The match is deliberately not anchored to line start. bun.lock is JSONC, so
    whitespace is not significant to bun itself and a hand-edited file may legally
    place two entries on one line, which an anchored pattern would skip. An entry
    only counts when the first element carries a version or protocol suffix for
    split_name to strip, which rejects the format's other bracketed keys
    ("os": ["linux"], "cpu": ["x64"]).
    """
    names = set()
    for m in re.finditer(r'"[^"]+":\s*\[\s*"([^"]+)"', text):
        first = m.group(1)
        name = split_name(first)
        if name != first:
            names.add(name)
    return names


def yarn(text):
    names = set()
    if "__metadata:" in text:  # berry, v2 and later
        for m in re.finditer(r'^\s+resolution:\s*"([^"]+)"', text, re.M):
            names.add(split_name(m.group(1)))
    else:  # v1 classic: comma separated descriptor headers ending in ":"
        for line in text.splitlines():
            if not line or line[0].isspace() or line.startswith("#"):
                continue
            line = line.rstrip()
            if not line.endswith(":"):
                continue
            for spec in line[:-1].split(", "):
                spec = spec.strip().strip('"')
                if spec:
                    names.add(split_name(spec))
    return names


def pnpm(text):
    names = set()
    # v9 packages:/snapshots: entries, e.g. "  '@scope/pkg@1.2.3':" or "  pkg@1.2.3:"
    for m in re.finditer(r"^  '?([^'\s:][^'\s]*)'?:\s*$", text, re.M):
        spec = m.group(1)
        if spec.startswith("/"):
            continue  # legacy "/pkg/1.2.3:" form, handled below
        if "@" in spec.lstrip("@"):
            names.add(split_name(spec))
    # v5 and v6 style, e.g. "  /@scope/pkg/1.2.3:" or "  /pkg/1.2.3:"
    for m in re.finditer(r"^  /((?:@[^/\s]+/)?[^/\s]+)/\d", text, re.M):
        names.add(m.group(1))
    return {n for n in names if n}


def cargo(text):
    """Cargo.lock and uv.lock both record one `name = "..."` per [[package]]."""
    return set(re.findall(r'^name = "([^"]+)"$', text, re.M))


PARSERS = {
    "bun.lock": bun,
    "yarn.lock": yarn,
    "pnpm-lock.yaml": pnpm,
    "Cargo.lock": cargo,
    "uv.lock": cargo,
}

SUPPORTED = ", ".join(sorted(PARSERS))


def extract(path):
    p = Path(path)
    parser = PARSERS.get(p.name)
    if parser is None:
        sys.exit(f"unsupported lockfile: {p.name} (supported: {SUPPORTED})")
    if not p.exists():  # added by this PR, so everything in it is new
        return set()
    return parser(p.read_text(encoding="utf-8", errors="replace"))


if __name__ == "__main__":
    if len(sys.argv) == 2:
        for n in sorted(extract(sys.argv[1])):
            print(n)
    elif len(sys.argv) == 3:
        for n in sorted(extract(sys.argv[2]) - extract(sys.argv[1])):
            print(n)
    else:
        sys.exit(__doc__)
