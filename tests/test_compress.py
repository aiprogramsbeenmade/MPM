"""Test unitari per il modulo mpm.compress."""

import json
import struct

import pytest

from mpm.compress import (
    MAGIC,
    MPMZError,
    compress_mpm,
    decompress_mpmz,
    mpm_to_mpmz,
    mpmz_to_mpm,
    read_mpmz,
    write_mpmz,
)
from mpm.format import MPMFile, MPMHeader, read_mpm, write_mpm


def _make_mpm(n_rows: int = 5) -> MPMFile:
    header = MPMHeader(
        version="0.1",
        meta={"delimiter": ",", "encoding": "utf-8", "compression": "none"},
        schema=[{"name": "id", "type": "int"}, {"name": "nome", "type": "str"}],
    )
    rows = [[str(i), f"nome{i}"] for i in range(n_rows)]
    return MPMFile(header=header, rows=rows)


class TestCompressDecompress:
    def test_roundtrip_simple(self):
        mpm = _make_mpm(5)
        data = compress_mpm(mpm)
        mpm2 = decompress_mpmz(data)
        assert mpm2.rows == mpm.rows
        # Il file .mpm ricostruito deve avere compression: "none",
        # perché la compressione è una proprietà del contenitore .mpmz.
        assert mpm2.header.meta["compression"] == "none"
        assert mpm2.header.schema == mpm.header.schema

    def test_roundtrip_empty(self):
        mpm = _make_mpm(0)
        data = compress_mpm(mpm)
        mpm2 = decompress_mpmz(data)
        assert mpm2.rows == []

    def test_roundtrip_large(self):
        mpm = _make_mpm(25_000)
        data = compress_mpm(mpm, block_size=10_000)
        mpm2 = decompress_mpmz(data)
        assert mpm2.rows == mpm.rows

    def test_block_count(self):
        mpm = _make_mpm(25)
        data = compress_mpm(mpm, block_size=10)
        # 25 righe / 10 per blocco = 3 blocchi (10 + 10 + 5)
        # Leggiamo il numero di blocchi dall'header JSON.
        header_len = struct.unpack(">I", data[5:9])[0]
        header = json.loads(data[9 : 9 + header_len])
        assert header["blocks"] == 3
        assert header["original_size"] > 0

    def test_compression_is_effective(self):
        mpm = _make_mpm(10_000)
        data = compress_mpm(mpm, block_size=1_000)
        # Il corpo CSV originale è molto più grande dei dati compressi.
        # Verifichiamo che la compressione abbia ridotto le dimensioni.
        assert len(data) < 10_000 * 10  # stima grossolana ma efficace


class TestMpmzErrors:
    def test_too_short(self):
        with pytest.raises(MPMZError):
            decompress_mpmz(b"MPM")

    def test_bad_magic(self):
        with pytest.raises(MPMZError):
            decompress_mpmz(b"XXXX" + b"\x00" * 10)

    def test_bad_version(self):
        with pytest.raises(MPMZError):
            decompress_mpmz(b"MPMZ" + b"\x99" + b"\x00" * 10)

    def test_truncated_header(self):
        data = b"MPMZ" + b"\x01" + struct.pack(">I", 100) + b"short"
        with pytest.raises(MPMZError):
            decompress_mpmz(data)

    def test_invalid_header_json(self):
        header_json = b"{not json}"
        data = b"MPMZ" + b"\x01" + struct.pack(">I", len(header_json)) + header_json
        with pytest.raises(MPMZError):
            decompress_mpmz(data)

    def test_negative_blocks(self):
        header = {"meta": {}, "schema": [], "blocks": -1, "original_size": 0}
        header_json = json.dumps(header).encode()
        data = b"MPMZ" + b"\x01" + struct.pack(">I", len(header_json)) + header_json
        with pytest.raises(MPMZError):
            decompress_mpmz(data)


class TestFileIO:
    def test_write_then_read(self, tmp_path):
        mpm = _make_mpm(5)
        p = tmp_path / "test.mpmz"
        write_mpmz(mpm, p)
        mpm2 = read_mpmz(p)
        assert mpm2.rows == mpm.rows

    def test_mpm_to_mpmz_to_mpm(self, tmp_path):
        mpm = _make_mpm(5)
        mpm_path = tmp_path / "test.mpm"
        mpmz_path = tmp_path / "test.mpmz"
        mpm2_path = tmp_path / "test2.mpm"
        write_mpm(mpm, mpm_path)
        mpm_to_mpmz(mpm_path, mpmz_path)
        mpmz_to_mpm(mpmz_path, mpm2_path)
        mpm2 = read_mpm(mpm2_path)
        assert mpm2.rows == mpm.rows
        assert mpm2.header.schema == mpm.header.schema