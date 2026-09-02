#!/usr/bin/env python3
"""Resolve Android ELF dependencies and check imported dynamic symbols."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path


NEEDED_RE = re.compile(r"Shared library: \[([^]]+)\]")
SONAME_RE = re.compile(r"Library soname: \[([^]]+)\]")


class NotElfError(RuntimeError):
    pass


@dataclass(frozen=True)
class ElfInfo:
    elf_class: str
    machine: str
    soname: str | None
    needed: tuple[str, ...]
    defined_symbols: frozenset[str]
    undefined_global: frozenset[str]

    @property
    def architecture(self) -> tuple[str, str]:
        return self.elf_class, self.machine


def run_readelf(readelf: str, options: list[str], path: Path) -> str:
    result = subprocess.run(
        [readelf, *options, str(path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise NotElfError(result.stderr.strip() or f"readelf failed for {path}")
    return result.stdout


def parse_header(output: str) -> tuple[str, str]:
    elf_class = ""
    machine = ""
    for line in output.splitlines():
        key, separator, value = line.partition(":")
        if not separator:
            continue
        if key.strip() == "Class":
            elf_class = value.strip()
        elif key.strip() == "Machine":
            machine = value.strip()
    if not elf_class or not machine:
        raise NotElfError("missing ELF class or machine")
    return elf_class, machine


def symbol_forms(name: str) -> tuple[str, str]:
    exact = name.replace("@@", "@")
    base = exact.split("@", 1)[0]
    return exact, base


def parse_symbols(output: str) -> tuple[frozenset[str], frozenset[str]]:
    defined: set[str] = set()
    undefined_global: set[str] = set()
    for line in output.splitlines():
        fields = line.split()
        if len(fields) < 8 or not fields[0].endswith(":"):
            continue
        bind_index = next(
            (index for index, value in enumerate(fields) if value in {"GLOBAL", "WEAK"}),
            None,
        )
        if bind_index is None or len(fields) <= bind_index + 3:
            continue
        bind = fields[bind_index]
        section = fields[bind_index + 2]
        name = fields[bind_index + 3]
        exact, base = symbol_forms(name)
        if section == "UND":
            if bind == "GLOBAL":
                undefined_global.add(exact)
        else:
            defined.add(exact)
            defined.add(base)
    return frozenset(defined), frozenset(undefined_global)


def load_elf(readelf: str, path: Path) -> ElfInfo:
    elf_class, machine = parse_header(run_readelf(readelf, ["-h"], path))
    dynamic = run_readelf(readelf, ["-d", "--wide"], path)
    symbols = run_readelf(readelf, ["--dyn-syms", "--wide"], path)
    needed = tuple(NEEDED_RE.findall(dynamic))
    soname_match = SONAME_RE.search(dynamic)
    defined, undefined_global = parse_symbols(symbols)
    return ElfInfo(
        elf_class=elf_class,
        machine=machine,
        soname=soname_match.group(1) if soname_match else None,
        needed=needed,
        defined_symbols=defined,
        undefined_global=undefined_global,
    )


def parse_root(value: str) -> tuple[str, Path]:
    label, separator, raw_path = value.partition("=")
    if not separator or not label or not raw_path:
        raise argparse.ArgumentTypeError("roots must use LABEL=PATH")
    path = Path(raw_path).resolve()
    if not path.is_dir():
        raise argparse.ArgumentTypeError(f"root is not a directory: {path}")
    return label, path


def under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def build_name_index(roots: list[tuple[str, Path]]) -> dict[str, list[tuple[str, Path]]]:
    index: dict[str, list[tuple[str, Path]]] = defaultdict(list)
    for label, root in roots:
        for directory, _, filenames in os.walk(root):
            for filename in filenames:
                if ".so" not in filename:
                    continue
                index[filename].append((label, Path(directory, filename).resolve()))
    return index


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--readelf", default="readelf")
    parser.add_argument(
        "--root",
        action="append",
        type=parse_root,
        required=True,
        help="ordered dependency root as LABEL=PATH",
    )
    parser.add_argument("--seed", action="append", type=Path, required=True)
    parser.add_argument(
        "--check-root",
        action="append",
        type=Path,
        default=[],
        help="check strong imports for every closure file below this root",
    )
    args = parser.parse_args()

    roots: list[tuple[str, Path]] = args.root
    seeds = [path.resolve() for path in args.seed]
    check_roots = [path.resolve() for path in args.check_root]
    for seed in seeds:
        if not seed.is_file():
            parser.error(f"seed is not a file: {seed}")

    name_index = build_name_index(roots)
    cache: dict[Path, ElfInfo] = {}

    def info(path: Path) -> ElfInfo:
        if path not in cache:
            cache[path] = load_elf(args.readelf, path)
        return cache[path]

    try:
        seed_architectures = {info(seed).architecture for seed in seeds}
    except NotElfError as exc:
        parser.error(str(exc))
    if len(seed_architectures) != 1:
        parser.error("all seeds must use the same ELF architecture")
    architecture = next(iter(seed_architectures))

    missing_needed: dict[Path, list[str]] = defaultdict(list)
    selected_origin: dict[Path, str] = {seed: "seed" for seed in seeds}
    closure: set[Path] = set()
    queue = deque(seeds)

    while queue:
        consumer = queue.popleft()
        if consumer in closure:
            continue
        closure.add(consumer)
        for library in info(consumer).needed:
            provider = None
            provider_label = ""
            for label, candidate in name_index.get(library, []):
                try:
                    if info(candidate).architecture == architecture:
                        provider = candidate
                        provider_label = label
                        break
                except NotElfError:
                    continue
            if provider is None:
                missing_needed[consumer].append(library)
                continue
            selected_origin.setdefault(provider, provider_label)
            if provider not in closure:
                queue.append(provider)

    provided_symbols: set[str] = set()
    for path in closure:
        provided_symbols.update(info(path).defined_symbols)

    checked = set(seeds)
    for path in closure:
        if any(under(path, root) for root in check_roots):
            checked.add(path)

    unresolved: dict[Path, list[str]] = defaultdict(list)
    version_fallback: dict[Path, list[str]] = defaultdict(list)
    for path in checked:
        for symbol in sorted(info(path).undefined_global):
            exact, base = symbol_forms(symbol)
            if exact in provided_symbols:
                continue
            if base in provided_symbols:
                if "@" in exact:
                    version_fallback[path].append(symbol)
                continue
            if base not in provided_symbols:
                unresolved[path].append(symbol)

    print(f"architecture={architecture[0]} / {architecture[1]}")
    print(f"closure_files={len(closure)}")
    for path in sorted(closure, key=str):
        origin = selected_origin.get(path, "unknown")
        print(f"FILE\t{origin}\t{path}")

    for consumer in sorted(missing_needed, key=str):
        for library in sorted(missing_needed[consumer]):
            print(f"MISSING_NEEDED\t{consumer}\t{library}")
    for consumer in sorted(unresolved, key=str):
        for symbol in unresolved[consumer]:
            print(f"UNRESOLVED_SYMBOL\t{consumer}\t{symbol}")
    for consumer in sorted(version_fallback, key=str):
        for symbol in version_fallback[consumer]:
            print(f"VERSION_FALLBACK\t{consumer}\t{symbol}")

    print(f"missing_needed={sum(map(len, missing_needed.values()))}")
    print(f"unresolved_symbols={sum(map(len, unresolved.values()))}")
    print(f"version_fallbacks={sum(map(len, version_fallback.values()))}")
    return 1 if missing_needed or unresolved else 0


if __name__ == "__main__":
    sys.exit(main())
