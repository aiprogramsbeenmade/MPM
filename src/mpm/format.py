"""Lettura e scrittura di file .mpm (header MPM + corpo CSV)."""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SUPPORTED_VERSION = "0.1"

_EXTENSION_RE = re.compile(r"^#\s*@(?P<key>[A-Za-z0-9_]+)\s*:\s*(?P<value>.+)$")
_VERSION_RE = re.compile(r"^#\s*MPM\s+v(?P<version>\d+\.\d+(?:\.\d+)?)\s*$")


class MPMError(Exception):
    """Errore generico del formato MPM."""


class MPMHeaderError(MPMError):
    """Errore nell'header MPM (riga malformata, ordine errato, ecc.)."""


class MPMSchemaError(MPMError):
    """Errore nello schema (numero di colonne, tipi non validi, ecc.)."""


class MPMVersionError(MPMError):
    """Versione del formato non supportata."""


@dataclass
class MPMHeader:
    """Rappresenta l'header di un file MPM."""

    version: str
    meta: dict[str, Any]
    schema: list[dict[str, Any]]
    extensions: dict[str, Any] = field(default_factory=dict)

    def column_names(self) -> list[str]:
        """Restituisce i nomi delle colonne nello schema."""
        return [col["name"] for col in self.schema]


@dataclass
class MPMFile:
    """Rappresenta un file MPM completo: header + righe del corpo."""

    header: MPMHeader
    rows: list[list[str]] = field(default_factory=list)


def _parse_version_line(line: str) -> str:
    match = _VERSION_RE.match(line)
    if not match:
        raise MPMHeaderError(
            f"Riga di versione non valida: {line!r}. "
            f"Atteso: '# MPM v<versione>'"
        )
    return match.group("version")


def _parse_meta_line(line: str) -> dict[str, Any]:
    prefix = "# @meta:"
    if not line.startswith(prefix):
        raise MPMHeaderError(
            f"Riga di metadati non valida: {line!r}. Atteso: '# @meta: <JSON>'"
        )
    raw = line[len(prefix):].strip()
    try:
        meta = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MPMHeaderError(f"@meta non è JSON valido: {exc}") from exc
    if not isinstance(meta, dict):
        raise MPMHeaderError("@meta deve essere un oggetto JSON")
    for required in ("delimiter", "encoding", "compression"):
        if required not in meta:
            raise MPMHeaderError(f"@meta manca il campo obbligatorio: {required!r}")
    return meta


def _parse_schema_line(line: str) -> list[dict[str, Any]]:
    prefix = "# @schema:"
    if not line.startswith(prefix):
        raise MPMHeaderError(
            f"Riga di schema non valida: {line!r}. Atteso: '# @schema: <JSON>'"
        )
    raw = line[len(prefix):].strip()
    try:
        schema = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MPMHeaderError(f"@schema non è JSON valido: {exc}") from exc
    if not isinstance(schema, list) or not schema:
        raise MPMHeaderError("@schema deve essere un array JSON non vuoto")
    for idx, col in enumerate(schema):
        if not isinstance(col, dict):
            raise MPMSchemaError(f"Colonna {idx}: deve essere un oggetto JSON")
        for required in ("name", "type"):
            if required not in col:
                raise MPMSchemaError(
                    f"Colonna {idx}: manca il campo obbligatorio {required!r}"
                )
    return schema


def parse_header(lines: list[str]) -> tuple[MPMHeader, int]:
    """Parsa le righe di header e restituisce (header, indice prima riga corpo)."""
    if not lines:
        raise MPMHeaderError("File vuoto: manca l'header MPM")

    start = 0
    while start < len(lines) and not lines[start].strip():
        start += 1
    if start >= len(lines):
        raise MPMHeaderError("File vuoto: manca l'header MPM")

    version = _parse_version_line(lines[start])
    if _version_tuple(version) > _version_tuple(SUPPORTED_VERSION):
        raise MPMVersionError(
            f"Versione {version} non supportata (massima: {SUPPORTED_VERSION})"
        )

    if start + 1 >= len(lines):
        raise MPMHeaderError("Manca la riga @meta")
    meta = _parse_meta_line(lines[start + 1])

    if start + 2 >= len(lines):
        raise MPMHeaderError("Manca la riga @schema")
    schema = _parse_schema_line(lines[start + 2])

    extensions: dict[str, Any] = {}
    idx = start + 3
    while idx < len(lines) and lines[idx].startswith("#"):
        match = _EXTENSION_RE.match(lines[idx])
        if match:
            key = match.group("key")
            value_raw = match.group("value").strip()
            try:
                extensions[key] = json.loads(value_raw)
            except json.JSONDecodeError:
                extensions[key] = value_raw
        idx += 1

    header = MPMHeader(
        version=version,
        meta=meta,
        schema=schema,
        extensions=extensions,
    )
    return header, idx


def _version_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def read_mpm(path: str | Path) -> MPMFile:
    """Legge un file .mpm e restituisce un MPMFile.

    L'header MPM è sempre in UTF-8 (i metadati JSON sono ASCII-compatibili).
    Il corpo viene decodificato con l'encoding dichiarato in @meta.encoding.
    """
    raw = Path(path).read_bytes()

    lines_bytes = raw.split(b"\n")
    header_lines: list[str] = []
    body_start_byte = 0
    for i, line in enumerate(lines_bytes):
        if line.startswith(b"#"):
            try:
                header_lines.append(line.decode("utf-8"))
            except UnicodeDecodeError as exc:
                raise MPMError(
                    f"Riga di header non decodificabile come UTF-8: {line!r}"
                ) from exc
        else:
            body_start_byte = sum(len(l) + 1 for l in lines_bytes[:i])
            break
    else:
        body_start_byte = len(raw)

    header, _ = parse_header(header_lines)

    body_bytes = raw[body_start_byte:]
    encoding = header.meta["encoding"]
    try:
        body_text = body_bytes.decode(encoding)
    except UnicodeDecodeError as exc:
        raise MPMError(
            f"Impossibile decodificare il corpo con encoding "
            f"{encoding!r}: {exc}"
        ) from exc

    delimiter = header.meta["delimiter"]
    reader = csv.reader(io.StringIO(body_text), delimiter=delimiter)
    rows = list(reader)

    if rows:
        body_header = rows[0]
        schema_names = header.column_names()
        if body_header != schema_names:
            raise MPMSchemaError(
                f"Header del corpo {body_header!r} non corrisponde "
                f"allo schema {schema_names!r}"
            )
        data_rows = rows[1:]
    else:
        data_rows = []

    expected = len(header.schema)
    for i, row in enumerate(data_rows, start=1):
        if len(row) != expected:
            raise MPMSchemaError(
                f"Riga dati {i}: {len(row)} campi, attesi {expected}"
            )

    return MPMFile(header=header, rows=data_rows)


def serialize_header(header: MPMHeader) -> list[str]:
    """Serializza un MPMHeader in una lista di righe (senza terminatore)."""
    lines = [f"# MPM v{header.version}"]
    lines.append(
        f"# @meta: {json.dumps(header.meta, ensure_ascii=False, separators=(',', ':'))}"
    )
    lines.append(
        f"# @schema: {json.dumps(header.schema, ensure_ascii=False, separators=(',', ':'))}"
    )
    for key, value in header.extensions.items():
        lines.append(
            f"# @{key}: {json.dumps(value, ensure_ascii=False, separators=(',', ':'))}"
        )
    return lines


def write_mpm(mpm_file: MPMFile, path: str | Path) -> None:
    """Scrive un MPMFile su disco in formato .mpm.

    Costruisce il contenuto in memoria e lo scrive con una singola
    operazione di I/O. Il file viene aperto con newline="" per garantire
    che i terminatori di riga siano esattamente '\\n' su ogni piattaforma.
    """
    header_lines = serialize_header(mpm_file.header)
    delimiter = mpm_file.header.meta["delimiter"]
    encoding = mpm_file.header.meta["encoding"]

    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=delimiter, lineterminator="\n")
    writer.writerow(mpm_file.header.column_names())
    writer.writerows(mpm_file.rows)
    body = buffer.getvalue()

    content = "\n".join(header_lines) + "\n" + body
    with Path(path).open("w", encoding=encoding, newline="") as f:
        f.write(content)