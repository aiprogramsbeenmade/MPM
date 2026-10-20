"""Conversioni tra CSV e MPM."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

from mpm.format import (
    MPMError,
    MPMFile,
    MPMHeader,
    MPMSchemaError,
    read_mpm,
    write_mpm,
)
from mpm.schema import infer_schema_from_rows


class MPMCsvError(MPMError):
    """Errore durante la conversione CSV ↔ MPM."""


def read_csv_rows(
    path: str | Path,
    delimiter: str = ",",
    encoding: str = "utf-8",
) -> tuple[list[str], list[list[str]]]:
    """Legge un CSV e restituisce (header, righe)."""
    text = Path(path).read_text(encoding=encoding)
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = list(reader)
    if not rows:
        raise MPMCsvError("Il CSV è vuoto")
    header = rows[0]
    if not header:
        raise MPMCsvError("Il CSV non ha colonne")
    data_rows = rows[1:]
    expected = len(header)
    for i, row in enumerate(data_rows, start=1):
        if len(row) != expected:
            raise MPMCsvError(
                f"Riga {i}: {len(row)} campi, attesi {expected}"
            )
    return header, data_rows


def _read_csv_and_infer(
    path: str | Path,
    delimiter: str = ",",
    encoding: str = "utf-8",
    sample_size: int = 1000,
) -> tuple[list[str], list[list[str]], list[dict[str, Any]]]:
    """Legge un CSV e inferisce lo schema in un solo passaggio.

    Restituisce (header, righe, schema).
    """
    from mpm.schema import ColumnStats

    text = Path(path).read_text(encoding=encoding)
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = list(reader)
    if not rows:
        raise MPMCsvError("Il CSV è vuoto")
    header = rows[0]
    if not header:
        raise MPMCsvError("Il CSV non ha colonne")
    data_rows = rows[1:]
    expected = len(header)
    for i, row in enumerate(data_rows, start=1):
        if len(row) != expected:
            raise MPMCsvError(
                f"Riga {i}: {len(row)} campi, attesi {expected}"
            )

    stats = [ColumnStats(name=name) for name in header]
    for row in data_rows[:sample_size]:
        for i, value in enumerate(row):
            stats[i].add(value)

    schema: list[dict[str, Any]] = []
    for col in stats:
        col_type = col.infer_type()
        entry: dict[str, Any] = {
            "name": col.name,
            "type": col_type,
            "nullable": col.infer_nullable(),
        }
        if col_type in ("date", "datetime"):
            entry["format"] = (
                "YYYY-MM-DD" if col_type == "date" else "YYYY-MM-DDTHH:MM:SS"
            )
        schema.append(entry)

    return header, data_rows, schema


def csv_to_mpm(
    input_path: str | Path,
    output_path: str | Path,
    schema: list[dict[str, Any]] | None = None,
    delimiter: str = ",",
    encoding: str = "utf-8",
    sample_size: int = 1000,
) -> None:
    """Converte un file CSV in un file MPM."""
    if schema is None:
        header, rows, schema = _read_csv_and_infer(
            input_path, delimiter=delimiter, encoding=encoding,
            sample_size=sample_size,
        )
    else:
        header, rows = read_csv_rows(
            input_path, delimiter=delimiter, encoding=encoding,
        )
        schema_names = [col["name"] for col in schema]
        if schema_names != header:
            raise MPMSchemaError(
                f"Lo schema {schema_names!r} non corrisponde "
                f"all'header del CSV {header!r}"
            )

    mpm_header = MPMHeader(
        version="0.1",
        meta={
            "delimiter": delimiter,
            "encoding": encoding,
            "compression": "none",
        },
        schema=schema,
    )
    mpm = MPMFile(header=mpm_header, rows=rows)
    write_mpm(mpm, output_path)


def mpm_to_csv(
    input_path: str | Path,
    output_path: str | Path,
    include_header: bool = True,
) -> None:
    """Converte un file MPM in un file CSV.

    Costruisce il contenuto in memoria e lo scrive con una singola
    operazione di I/O. Il file viene aperto con newline="" per garantire
    che i terminatori di riga siano esattamente '\\n' su ogni piattaforma.
    """
    mpm = read_mpm(input_path)
    delimiter = mpm.header.meta["delimiter"]
    encoding = mpm.header.meta["encoding"]

    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=delimiter, lineterminator="\n")
    if include_header:
        writer.writerow(mpm.header.column_names())
    writer.writerows(mpm.rows)

    with Path(output_path).open("w", encoding=encoding, newline="") as f:
        f.write(buffer.getvalue())


def read_csv_as_mpm(
    path: str | Path,
    schema: list[dict[str, Any]] | None = None,
    delimiter: str = ",",
    encoding: str = "utf-8",
    sample_size: int = 1000,
) -> MPMFile:
    """Legge un CSV e restituisce un MPMFile (senza scrivere su disco)."""
    header, rows = read_csv_rows(path, delimiter=delimiter, encoding=encoding)
    if schema is None:
        schema = infer_schema_from_rows(header, rows, sample_size=sample_size)
    else:
        schema_names = [col["name"] for col in schema]
        if schema_names != header:
            raise MPMSchemaError(
                f"Lo schema {schema_names!r} non corrisponde "
                f"all'header del CSV {header!r}"
            )
    mpm_header = MPMHeader(
        version="0.1",
        meta={
            "delimiter": delimiter,
            "encoding": encoding,
            "compression": "none",
        },
        schema=schema,
    )
    return MPMFile(header=mpm_header, rows=rows)