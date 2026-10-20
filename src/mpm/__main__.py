"""CLI per MPM — Minimal Portable Mapping."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from mpm.compress import mpm_to_mpmz, mpmz_to_mpm, read_mpmz, write_mpmz
from mpm.csv_io import csv_to_mpm, mpm_to_csv, read_csv_as_mpm
from mpm.format import MPMError, read_mpm, write_mpm
from mpm.schema import infer_schema_from_csv, validate_schema


def _load_schema(path: str | None) -> list[dict[str, Any]] | None:
    """Carica uno schema da file JSON, se specificato."""
    if path is None:
        return None
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Errore nel caricamento dello schema: {exc}", file=sys.stderr)
        sys.exit(1)
    if isinstance(data, dict) and "schema" in data:
        data = data["schema"]
    if not isinstance(data, list):
        print("Lo schema deve essere un array JSON", file=sys.stderr)
        sys.exit(1)
    return data


def cmd_convert(args: argparse.Namespace) -> int:
    """CSV → MPM."""
    schema = _load_schema(args.schema)
    try:
        csv_to_mpm(
            args.input,
            args.output,
            schema=schema,
            delimiter=args.delimiter,
            encoding=args.encoding,
            sample_size=args.sample_size,
        )
    except (MPMError, OSError) as exc:
        print(f"Errore: {exc}", file=sys.stderr)
        return 1
    print(f"Convertito {args.input} → {args.output}")
    return 0


def cmd_to_csv(args: argparse.Namespace) -> int:
    """MPM → CSV."""
    try:
        mpm_to_csv(args.input, args.output, include_header=not args.no_header)
    except (MPMError, OSError) as exc:
        print(f"Errore: {exc}", file=sys.stderr)
        return 1
    print(f"Convertito {args.input} → {args.output}")
    return 0


def cmd_infer(args: argparse.Namespace) -> int:
    """Genera uno schema JSON da un CSV."""
    try:
        schema = infer_schema_from_csv(
            args.input,
            delimiter=args.delimiter,
            encoding=args.encoding,
            sample_size=args.sample_size,
        )
    except (MPMError, OSError) as exc:
        print(f"Errore: {exc}", file=sys.stderr)
        return 1
    output = json.dumps(schema, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(output + "\n", encoding="utf-8")
        print(f"Schema scritto in {args.output}")
    else:
        print(output)
    return 0


def cmd_compress(args: argparse.Namespace) -> int:
    """MPM → MPMZ."""
    try:
        mpm_to_mpmz(args.input, args.output, block_size=args.block_size)
    except (MPMError, OSError) as exc:
        print(f"Errore: {exc}", file=sys.stderr)
        return 1
    print(f"Compresso {args.input} → {args.output}")
    return 0


def cmd_decompress(args: argparse.Namespace) -> int:
    """MPMZ → MPM."""
    try:
        mpmz_to_mpm(args.input, args.output)
    except (MPMError, OSError) as exc:
        print(f"Errore: {exc}", file=sys.stderr)
        return 1
    print(f"Decompresso {args.input} → {args.output}")
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    """Mostra metadati e schema di un file MPM o MPMZ."""
    path = Path(args.input)
    try:
        if path.suffix == ".mpmz":
            mpm = read_mpmz(path)
            compression = "zstd"
        else:
            mpm = read_mpm(path)
            compression = "none"
    except (MPMError, OSError) as exc:
        print(f"Errore: {exc}", file=sys.stderr)
        return 1
    print(f"File: {path}")
    print(f"Versione: {mpm.header.version}")
    print(f"Compressione: {compression}")
    print(f"Encoding: {mpm.header.meta.get('encoding', 'utf-8')}")
    print(f"Delimitatore: {mpm.header.meta.get('delimiter', ',')!r}")
    print(f"Righe: {len(mpm.rows)}")
    print(f"Colonne: {len(mpm.header.schema)}")
    print("Schema:")
    for col in mpm.header.schema:
        nullable = "nullable" if col.get("nullable", True) else "not null"
        fmt = f" format={col['format']}" if "format" in col else ""
        print(f"  - {col['name']}: {col['type']} ({nullable}){fmt}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    """Valida i dati di un file MPM contro il suo schema."""
    path = Path(args.input)
    try:
        if path.suffix == ".mpmz":
            mpm = read_mpmz(path)
        else:
            mpm = read_mpm(path)
    except (MPMError, OSError) as exc:
        print(f"Errore: {exc}", file=sys.stderr)
        return 1
    anomalies = validate_schema(mpm)
    if not anomalies:
        print(f"Nessuna anomalia trovata in {path}")
        return 0
    print(f"Trovate {len(anomalies)} anomalie in {path}:", file=sys.stderr)
    for a in anomalies:
        print(
            f"  riga {a['row']}, colonna {a['column']!r}: {a['message']}",
            file=sys.stderr,
        )
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mpm",
        description="MPM — Minimal Portable Mapping: un formato CSV 2.0",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("convert", help="Converte un CSV in MPM")
    p.add_argument("input", help="File CSV di input")
    p.add_argument("output", help="File MPM di output")
    p.add_argument("--schema", help="File JSON con lo schema (opzionale)")
    p.add_argument("--delimiter", default=",", help="Delimitatore CSV (default: ,)")
    p.add_argument("--encoding", default="utf-8", help="Encoding (default: utf-8)")
    p.add_argument("--sample-size", type=int, default=1000,
                   help="Righe per l'inferenza (default: 1000)")
    p.set_defaults(func=cmd_convert)

    p = sub.add_parser("to-csv", help="Converte un MPM in CSV")
    p.add_argument("input", help="File MPM di input")
    p.add_argument("output", help="File CSV di output")
    p.add_argument("--no-header", action="store_true",
                   help="Non includere la riga di intestazione")
    p.set_defaults(func=cmd_to_csv)

    p = sub.add_parser("infer", help="Genera uno schema JSON da un CSV")
    p.add_argument("input", help="File CSV di input")
    p.add_argument("-o", "--output", help="File JSON di output (default: stdout)")
    p.add_argument("--delimiter", default=",", help="Delimitatore CSV (default: ,)")
    p.add_argument("--encoding", default="utf-8", help="Encoding (default: utf-8)")
    p.add_argument("--sample-size", type=int, default=1000,
                   help="Righe da analizzare (default: 1000)")
    p.set_defaults(func=cmd_infer)

    p = sub.add_parser("compress", help="Comprime un MPM in MPMZ")
    p.add_argument("input", help="File MPM di input")
    p.add_argument("output", help="File MPMZ di output")
    p.add_argument("--block-size", type=int, default=10000,
                   help="Righe per blocco (default: 10000)")
    p.set_defaults(func=cmd_compress)

    p = sub.add_parser("decompress", help="Decomprime un MPMZ in MPM")
    p.add_argument("input", help="File MPMZ di input")
    p.add_argument("output", help="File MPM di output")
    p.set_defaults(func=cmd_decompress)

    p = sub.add_parser("info", help="Mostra metadati e schema di un file")
    p.add_argument("input", help="File MPM o MPMZ")
    p.set_defaults(func=cmd_info)

    p = sub.add_parser("validate", help="Valida i dati contro lo schema")
    p.add_argument("input", help="File MPM o MPMZ")
    p.set_defaults(func=cmd_validate)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())