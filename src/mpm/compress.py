"""Compressione e decompressione di file .mpmz (Zstandard a blocchi)."""

from __future__ import annotations

import io
import json
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import zstandard as zstd

from mpm.format import (
    MPMError,
    MPMFile,
    MPMHeader,
    MPMSchemaError,
    read_mpm,
    write_mpm,
)

MAGIC = b"MPMZ"
VERSION = 0x01
MAX_DECOMPRESSED_BLOCK = 100 * 1024 * 1024  # 100 MB
DEFAULT_BLOCK_SIZE = 10_000  # righe per blocco


class MPMZError(MPMError):
    """Errore nel formato .mpmz."""


@dataclass
class MPMZHeader:
    """Header JSON di un file .mpmz."""

    meta: dict[str, Any]
    schema: list[dict[str, Any]]
    blocks: int
    original_size: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "meta": self.meta,
            "schema": self.schema,
            "blocks": self.blocks,
            "original_size": self.original_size,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MPMZHeader":
        for required in ("meta", "schema", "blocks", "original_size"):
            if required not in data:
                raise MPMZError(f"Header JSON manca il campo {required!r}")
        if data["blocks"] < 0:
            raise MPMZError("Header JSON: 'blocks' non può essere negativo")
        if data["original_size"] < 0:
            raise MPMZError("Header JSON: 'original_size' non può essere negativo")
        return cls(
            meta=data["meta"],
            schema=data["schema"],
            blocks=data["blocks"],
            original_size=data["original_size"],
        )


@dataclass
class MPMZFile:
    """Rappresenta un file .mpmz in memoria."""

    header: MPMZHeader
    blocks: list[bytes] = field(default_factory=list)


def _serialize_mpm_body(mpm: MPMFile) -> bytes:
    """Serializza il corpo CSV di un MPMFile in bytes (senza header MPM)."""
    import csv

    buffer = io.StringIO()
    delimiter = mpm.header.meta["delimiter"]
    writer = csv.writer(buffer, delimiter=delimiter, lineterminator="\n")
    writer.writerow(mpm.header.column_names())
    for row in mpm.rows:
        writer.writerow(row)
    return buffer.getvalue().encode(mpm.header.meta["encoding"])


def _parse_mpm_body(body: bytes, header: MPMHeader) -> list[list[str]]:
    """Parsa il corpo CSV (bytes) e restituisce le righe dati."""
    import csv

    text = body.decode(header.meta["encoding"])
    reader = csv.reader(io.StringIO(text), delimiter=header.meta["delimiter"])
    rows = list(reader)
    if not rows:
        return []
    body_header = rows[0]
    schema_names = header.column_names()
    if body_header != schema_names:
        raise MPMSchemaError(
            f"Header del corpo {body_header!r} non corrisponde "
            f"allo schema {schema_names!r}"
        )
    return rows[1:]


def _split_into_blocks(data: bytes, block_size: int) -> list[bytes]:
    """Divide il corpo CSV in blocchi di al massimo block_size righe.

    Nota: la divisione avviene sulle righe, non sui byte, per garantire
    che ogni blocco contenga righe CSV complete.
    """
    lines = data.split(b"\n")
    # Rimuove l'ultima riga vuota se il file termina con '\n'.
    if lines and lines[-1] == b"":
        lines = lines[:-1]

    blocks: list[bytes] = []
    for i in range(0, len(lines), block_size):
        chunk = lines[i : i + block_size]
        blocks.append(b"\n".join(chunk) + (b"\n" if chunk else b""))
    return blocks


def compress_mpm(mpm: MPMFile, block_size: int = DEFAULT_BLOCK_SIZE) -> bytes:
    """Comprime un MPMFile in bytes nel formato .mpmz.

    Args:
        mpm: il file MPM da comprimere.
        block_size: numero di righe per blocco (default 10000).

    Returns:
        I bytes del file .mpmz.
    """
    if block_size <= 0:
        raise MPMZError("block_size deve essere positivo")

    body = _serialize_mpm_body(mpm)
    cctx = zstd.ZstdCompressor()
    raw_blocks = _split_into_blocks(body, block_size)
    compressed_blocks = [cctx.compress(raw) for raw in raw_blocks]

    meta = dict(mpm.header.meta)
    meta["compression"] = "zstd"
    meta["compression_block"] = block_size
    header = MPMZHeader(
        meta=meta,
        schema=mpm.header.schema,
        blocks=len(compressed_blocks),
        original_size=len(body),
    )
    header_json = json.dumps(header.to_dict(), ensure_ascii=False).encode("utf-8")

    out = io.BytesIO()
    out.write(MAGIC)
    out.write(struct.pack(">B", VERSION))
    out.write(struct.pack(">I", len(header_json)))
    out.write(header_json)
    for raw, compressed in zip(raw_blocks, compressed_blocks):
        out.write(struct.pack(">I", len(raw)))
        out.write(struct.pack(">I", len(compressed)))
        out.write(compressed)
    return out.getvalue()


def decompress_mpmz(data: bytes) -> MPMFile:
    """Decomprime i bytes di un file .mpmz in un MPMFile.

    Args:
        data: i bytes del file .mpmz.

    Returns:
        Un MPMFile con header e righe.

    Raises:
        MPMZError: se il file è malformato.
    """
    if len(data) < 9:
        raise MPMZError("File .mpmz troppo corto")
    if data[:4] != MAGIC:
        raise MPMZError(f"Magic number non valido: {data[:4]!r}")
    version = data[4]
    if version != VERSION:
        raise MPMZError(f"Versione .mpmz non supportata: {version}")
    (header_len,) = struct.unpack(">I", data[5:9])
    if len(data) < 9 + header_len:
        raise MPMZError("Header JSON troncato")
    header_json = data[9 : 9 + header_len]
    try:
        header_dict = json.loads(header_json.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MPMZError(f"Header JSON non valido: {exc}") from exc
    header = MPMZHeader.from_dict(header_dict)

    offset = 9 + header_len
    dctx = zstd.ZstdDecompressor()
    body_parts: list[bytes] = []
    for i in range(header.blocks):
        if offset + 8 > len(data):
            raise MPMZError(f"Blocco {i}: header troncato")
        orig_size, comp_size = struct.unpack(">II", data[offset : offset + 8])
        offset += 8
        if orig_size > MAX_DECOMPRESSED_BLOCK:
            raise MPMZError(
                f"Blocco {i}: dimensione originale {orig_size} "
                f"supera il limite di {MAX_DECOMPRESSED_BLOCK} byte"
            )
        if offset + comp_size > len(data):
            raise MPMZError(f"Blocco {i}: dati troncati")
        compressed = data[offset : offset + comp_size]
        offset += comp_size
        try:
            raw = dctx.decompress(compressed, max_output_size=orig_size)
        except zstd.ZstdError as exc:
            raise MPMZError(f"Blocco {i}: errore di decompressione: {exc}") from exc
        if len(raw) != orig_size:
            raise MPMZError(
                f"Blocco {i}: dimensione decompressa {len(raw)} "
                f"diversa da quella dichiarata {orig_size}"
            )
        body_parts.append(raw)

    if offset != len(data):
        raise MPMZError(
            f"Dati extra dopo l'ultimo blocco: {len(data) - offset} byte"
        )

    body = b"".join(body_parts)
    if len(body) != header.original_size:
        raise MPMZError(
            f"Dimensione totale {len(body)} diversa da original_size "
            f"{header.original_size}"
        )

    # Ripristina i metadati originali del file .mpm: la compressione
    # è una proprietà del contenitore .mpmz, non del file .mpm.
    meta = dict(header.meta)
    meta["compression"] = "none"
    meta.pop("compression_block", None)
    mpm_header = MPMHeader(
        version="0.1",
        meta=meta,
        schema=header.schema,
    )
    rows = _parse_mpm_body(body, mpm_header)
    return MPMFile(header=mpm_header, rows=rows)


def read_mpmz(path: str | Path) -> MPMFile:
    """Legge un file .mpmz e restituisce un MPMFile."""
    data = Path(path).read_bytes()
    return decompress_mpmz(data)


def write_mpmz(mpm: MPMFile, path: str | Path, block_size: int = DEFAULT_BLOCK_SIZE) -> None:
    """Scrive un MPMFile in formato .mpmz."""
    data = compress_mpm(mpm, block_size=block_size)
    Path(path).write_bytes(data)


def mpm_to_mpmz(input_path: str | Path, output_path: str | Path, block_size: int = DEFAULT_BLOCK_SIZE) -> None:
    """Converte un file .mpm in .mpmz."""
    mpm = read_mpm(input_path)
    write_mpmz(mpm, output_path, block_size=block_size)


def mpmz_to_mpm(input_path: str | Path, output_path: str | Path) -> None:
    """Converte un file .mpmz in .mpm."""
    mpm = read_mpmz(input_path)
    write_mpm(mpm, output_path)