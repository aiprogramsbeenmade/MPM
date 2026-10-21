"""Test unitari per il modulo mpm.compress."""

import json
import struct

import pytest

from mpm.compress import (
    MAGIC,
    MAX_BLOCKS,
    MAX_HEADER_JSON_SIZE,
    MAX_MPMZ_FILE_SIZE,
    MAX_TOTAL_DECOMPRESSED_SIZE,
    MPMZError,
    MPMZHeader,
    VERSION,
    _serialize_mpm_body,
    compress_mpm,
    decompress_mpmz,
    mpm_to_mpmz,
    mpmz_to_mpm,
    read_mpmz,
    write_mpmz,
)

from mpm.format import MPMFile, MPMHeader, MPMVersionError, read_mpm, write_mpm
import zstandard as zstd



def _make_mpm(n_rows: int = 5, version: str = "0.1") -> MPMFile:
    header = MPMHeader(
        version=version,
        meta={"delimiter": ",", "encoding": "utf-8", "compression": "none"},
        schema=[{"name": "id", "type": "int"}, {"name": "nome", "type": "str"}],
    )
    rows = [[str(i), f"nome{i}"] for i in range(n_rows)]
    return MPMFile(header=header, rows=rows)


class TestMpmzVersioning:
    def _make_mpm(self, version: str, rows, schema=None) -> MPMFile:
        schema = schema or [{"name": "val", "type": "str"}]
        header = MPMHeader(
            version=version,
            meta={"delimiter": ",", "encoding": "utf-8", "compression": "none"},
            schema=schema,
        )
        return MPMFile(header=header, rows=rows)

    def test_roundtrip_v01(self):
        mpm = self._make_mpm("0.1", [["hello"], ["world"]])
        data = compress_mpm(mpm)
        mpm2 = decompress_mpmz(data)
        assert mpm2.header.version == "0.1"
        assert mpm2.rows == [["hello"], ["world"]]

    def test_roundtrip_v02(self):
        mpm = self._make_mpm("0.2", [["hello"], [None], ["world"]])
        data = compress_mpm(mpm)
        mpm2 = decompress_mpmz(data)
        assert mpm2.header.version == "0.2"
        assert mpm2.rows == [["hello"], [None], ["world"]]

    def test_roundtrip_with_nulls(self):
        mpm = self._make_mpm("0.2", [[None], ["x"], [None]])
        data = compress_mpm(mpm)
        mpm2 = decompress_mpmz(data)
        assert mpm2.rows == [[None], ["x"], [None]]

    def test_roundtrip_with_escapes(self):
        mpm = self._make_mpm("0.2", [["\\N"], ["a\\b"], ["c\\\\d"]])
        data = compress_mpm(mpm)
        mpm2 = decompress_mpmz(data)
        assert mpm2.rows == [["\\N"], ["a\\b"], ["c\\\\d"]]

    def test_legacy_file_without_version(self):
        mpm = self._make_mpm("0.1", [["hello"]])
        data = compress_mpm(mpm)
        (header_len,) = struct.unpack(">I", data[5:9])
        header_json = data[9:9+header_len]
        header_dict = json.loads(header_json.decode("utf-8"))
        del header_dict["original_version"]
        new_header_json = json.dumps(header_dict, ensure_ascii=False).encode("utf-8")
        new_data = (
            data[:5]
            + struct.pack(">I", len(new_header_json))
            + new_header_json
            + data[9+header_len:]
        )
        mpm2 = decompress_mpmz(new_data)
        assert mpm2.header.version == "0.1"
        assert mpm2.rows == [["hello"]]

    def test_unknown_version_raises(self):
        mpm = self._make_mpm("0.1", [["hello"]])
        data = compress_mpm(mpm)
        (header_len,) = struct.unpack(">I", data[5:9])
        header_json = data[9:9+header_len]
        header_dict = json.loads(header_json.decode("utf-8"))
        header_dict["original_version"] = "0.9"
        new_header_json = json.dumps(header_dict, ensure_ascii=False).encode("utf-8")
        new_data = (
            data[:5]
            + struct.pack(">I", len(new_header_json))
            + new_header_json
            + data[9+header_len:]
        )
        with pytest.raises(MPMVersionError):
            decompress_mpmz(new_data)

    def test_malformed_version_raises(self):
        mpm = self._make_mpm("0.1", [["hello"]])
        data = compress_mpm(mpm)
        (header_len,) = struct.unpack(">I", data[5:9])
        header_json = data[9:9+header_len]
        header_dict = json.loads(header_json.decode("utf-8"))
        header_dict["original_version"] = 123
        new_header_json = json.dumps(header_dict, ensure_ascii=False).encode("utf-8")
        new_data = (
            data[:5]
            + struct.pack(">I", len(new_header_json))
            + new_header_json
            + data[9+header_len:]
        )
        with pytest.raises(MPMZError):
            decompress_mpmz(new_data)


class TestCompressDecompress:
    def test_roundtrip_simple(self):
        mpm = _make_mpm(5)
        data = compress_mpm(mpm)
        mpm2 = decompress_mpmz(data)
        assert mpm2.rows == mpm.rows
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
        header_len = struct.unpack(">I", data[5:9])[0]
        header = json.loads(data[9 : 9 + header_len])
        assert header["blocks"] == 3
        assert header["original_size"] > 0

    def test_compression_is_effective(self):
        mpm = _make_mpm(10_000)
        data = compress_mpm(mpm, block_size=1_000)
        assert len(data) < 10_000 * 10


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


class TestMpmzSecurityLimits:
    def _make_minimal_mpmz(self, **header_overrides) -> bytes:
        header = {
            "meta": {"delimiter": ",", "encoding": "utf-8", "compression": "zstd"},
            "schema": [{"name": "val", "type": "str"}],
            "blocks": 0,
            "original_size": 0,
            "original_version": "0.1",
        }
        header.update(header_overrides)
        header_json = json.dumps(header).encode("utf-8")
        return (
            MAGIC
            + struct.pack(">B", VERSION)
            + struct.pack(">I", len(header_json))
            + header_json
        )

    def test_small_valid_file(self, tmp_path):
        data = self._make_minimal_mpmz()
        p = tmp_path / "small.mpmz"
        p.write_bytes(data)
        mpm = read_mpmz(p)
        assert mpm.rows == []

    def test_legacy_valid_file(self, tmp_path):
        mpm = _make_mpm(5)
        p = tmp_path / "legacy.mpmz"
        write_mpmz(mpm, p)
        mpm2 = read_mpmz(p)
        assert mpm2.rows == mpm.rows

    def test_header_exactly_at_limit(self):
        target_size = MAX_HEADER_JSON_SIZE
        base_header = {
            "meta": {"delimiter": ",", "encoding": "utf-8", "compression": "zstd"},
            "schema": [{"name": "val", "type": "str"}],
            "blocks": 0,
            "original_size": 0,
            "original_version": "0.1",
        }
        base_json = json.dumps(base_header).encode("utf-8")
        padding = target_size - len(base_json)
        assert padding >= 0
        header_json = base_json + b" " * padding
        data = (
            MAGIC
            + struct.pack(">B", VERSION)
            + struct.pack(">I", len(header_json))
            + header_json
        )
        mpm = decompress_mpmz(data)
        assert mpm.rows == []

    def test_header_over_limit(self):
        target_size = MAX_HEADER_JSON_SIZE + 1
        base_header = {
            "meta": {"delimiter": ",", "encoding": "utf-8", "compression": "zstd"},
            "schema": [{"name": "val", "type": "str"}],
            "blocks": 0,
            "original_size": 0,
            "original_version": "0.1",
        }
        base_json = json.dumps(base_header).encode("utf-8")
        padding = target_size - len(base_json)
        header_json = base_json + b" " * padding
        data = (
            MAGIC
            + struct.pack(">B", VERSION)
            + struct.pack(">I", len(header_json))
            + header_json
        )
        with pytest.raises(MPMZError):
            decompress_mpmz(data)

    def test_header_declares_huge_length(self):
        data = (
            MAGIC
            + struct.pack(">B", VERSION)
            + struct.pack(">I", MAX_HEADER_JSON_SIZE + 1)
        )
        with pytest.raises(MPMZError):
            decompress_mpmz(data)

    def test_input_in_memory_over_limit(self):
        data = b"\x00" * (MAX_MPMZ_FILE_SIZE + 1)
        with pytest.raises(MPMZError):
            decompress_mpmz(data)

    def test_file_on_disk_over_limit(self, tmp_path):
        p = tmp_path / "huge.mpmz"
        with p.open("wb") as f:
            f.seek(MAX_MPMZ_FILE_SIZE)
            f.write(b"\x00")
        with pytest.raises(MPMZError):
            read_mpmz(p)

    def test_error_before_decompression(self):
        data = (
            MAGIC
            + struct.pack(">B", VERSION)
            + struct.pack(">I", MAX_HEADER_JSON_SIZE + 1)
            + b"x" * 10
        )
        with pytest.raises(MPMZError):
            decompress_mpmz(data)


class TestMpmzSecurityB2:
    def _make_minimal_mpmz(self, **header_overrides) -> bytes:
        header = {
            "meta": {"delimiter": ",", "encoding": "utf-8", "compression": "zstd"},
            "schema": [{"name": "val", "type": "str"}],
            "blocks": 0,
            "original_size": 0,
            "original_version": "0.1",
        }
        header.update(header_overrides)
        header_json = json.dumps(header).encode("utf-8")
        return (
            MAGIC
            + struct.pack(">B", VERSION)
            + struct.pack(">I", len(header_json))
            + header_json
        )

    def test_blocks_exactly_at_limit(self):
        data = self._make_minimal_mpmz(blocks=MAX_BLOCKS)
        # Non ci sono blocchi, ma l'header è accettato; il parser
        # fallirà nel ciclo per mancanza di dati, non per il limite.
        with pytest.raises(MPMZError):
            decompress_mpmz(data)

    def test_blocks_over_limit(self):
        data = self._make_minimal_mpmz(blocks=MAX_BLOCKS + 1)
        with pytest.raises(MPMZError):
            decompress_mpmz(data)

    def test_blocks_negative(self):
        data = self._make_minimal_mpmz(blocks=-1)
        with pytest.raises(MPMZError):
            decompress_mpmz(data)

    def test_blocks_wrong_type(self):
        data = self._make_minimal_mpmz(blocks="not an int")
        with pytest.raises(MPMZError):
            decompress_mpmz(data)

    def test_blocks_bool(self):
        data = self._make_minimal_mpmz(blocks=True)
        with pytest.raises(MPMZError):
            decompress_mpmz(data)

    def test_original_size_exactly_at_limit(self):
        data = self._make_minimal_mpmz(original_size=MAX_TOTAL_DECOMPRESSED_SIZE)
        with pytest.raises(MPMZError):
            # Il parser fallirà nel ciclo per mancanza di blocchi,
            # ma non per il limite.
            decompress_mpmz(data)

    def test_original_size_over_limit(self):
        data = self._make_minimal_mpmz(original_size=MAX_TOTAL_DECOMPRESSED_SIZE + 1)
        with pytest.raises(MPMZError):
            decompress_mpmz(data)

    def test_original_size_negative(self):
        data = self._make_minimal_mpmz(original_size=-1)
        with pytest.raises(MPMZError):
            decompress_mpmz(data)

    def test_original_size_wrong_type(self):
        data = self._make_minimal_mpmz(original_size="not an int")
        with pytest.raises(MPMZError):
            decompress_mpmz(data)

    def test_cumulative_sum_exceeds_limit(self):
        # Header valido, ma i blocchi hanno dimensioni che sommate
        # superano il limite, anche se original_size dichiara un valore inferiore.
        # Usiamo un blocco fittizio con orig_size grande.
        header = {
            "meta": {"delimiter": ",", "encoding": "utf-8", "compression": "zstd"},
            "schema": [{"name": "val", "type": "str"}],
            "blocks": 2,
            "original_size": 1000,
            "original_version": "0.1",
        }
        header_json = json.dumps(header).encode("utf-8")
        # Due blocchi fittizi: orig_size 200 MiB ciascuno.
        # Il primo supera il limite cumulativo.
        block_data = (
            struct.pack(">I", 200 * 1024 * 1024)  # orig_size primo blocco
            + struct.pack(">I", 4)                # comp_size
            + b"\x00" * 4                         # dati fittizi
        )
        data = (
            MAGIC
            + struct.pack(">B", VERSION)
            + struct.pack(">I", len(header_json))
            + header_json
            + block_data
        )
        with pytest.raises(MPMZError):
            decompress_mpmz(data)

    def test_sum_mismatch(self):
        # Header dichiara original_size diverso dalla somma dei blocchi.
        header = {
            "meta": {"delimiter": ",", "encoding": "utf-8", "compression": "zstd"},
            "schema": [{"name": "val", "type": "str"}],
            "blocks": 1,
            "original_size": 100,
            "original_version": "0.1",
        }
        header_json = json.dumps(header).encode("utf-8")
        # Blocco fittizio con orig_size 50 (diverso da 100).
        block_data = (
            struct.pack(">I", 50)
            + struct.pack(">I", 4)
            + b"\x00" * 4
        )
        data = (
            MAGIC
            + struct.pack(">B", VERSION)
            + struct.pack(">I", len(header_json))
            + header_json
            + block_data
        )
        with pytest.raises(MPMZError):
            decompress_mpmz(data)

    def test_error_before_decompressing_block(self):
        # Il secondo blocco supera il limite cumulativo, ma il primo è
        # valido. L'errore deve avvenire prima di decomprimere il secondo.
        header = {
            "meta": {"delimiter": ",", "encoding": "utf-8", "compression": "zstd"},
            "schema": [{"name": "val", "type": "str"}],
            "blocks": 2,
            "original_size": 1000,
            "original_version": "0.1",
        }
        header_json = json.dumps(header).encode("utf-8")
        # Primo blocco: orig_size 1 MiB (sotto il limite cumulativo).
        # Secondo blocco: orig_size 256 MiB + 1 (supera il limite).
        block1 = (
            struct.pack(">I", 1 * 1024 * 1024)
            + struct.pack(">I", 4)
            + b"\x00" * 4
        )
        block2 = (
            struct.pack(">I", MAX_TOTAL_DECOMPRESSED_SIZE + 1)
            + struct.pack(">I", 4)
            + b"\x00" * 4
        )
        data = (
            MAGIC
            + struct.pack(">B", VERSION)
            + struct.pack(">I", len(header_json))
            + header_json
            + block1
            + block2
        )
        with pytest.raises(MPMZError):
            decompress_mpmz(data)

    def test_compatibility_v01_v02(self):
        for version in ("0.1", "0.2"):
            mpm = MPMFile(
                header=MPMHeader(
                    version=version,
                    meta={"delimiter": ",", "encoding": "utf-8", "compression": "none"},
                    schema=[{"name": "val", "type": "str"}],
                ),
                rows=[["x"], ["y"]],
            )
            data = compress_mpm(mpm)
            mpm2 = decompress_mpmz(data)
            assert mpm2.header.version == version
            assert mpm2.rows == mpm.rows

class TestMpmzChecksum:
    def _make_mpm(self, version="0.2", rows=None):
        schema = [{"name": "val", "type": "str"}]
        header = MPMHeader(
            version=version,
            meta={"delimiter": ",", "encoding": "utf-8", "compression": "none"},
            schema=schema,
        )
        rows = rows or [["x"], ["y"]]
        return MPMFile(header=header, rows=rows)

    def _extract_first_block(self, data: bytes) -> bytes:
        """Estrae il primo blocco compresso (payload) dal file .mpmz."""
        (header_len,) = struct.unpack(">I", data[5:9])
        offset = 9 + header_len
        _orig_size, comp_size = struct.unpack(">II", data[offset : offset + 8])
        offset += 8
        return data[offset : offset + comp_size]

    def test_checksum_present(self):
        mpm = self._make_mpm()
        data = compress_mpm(mpm)
        block = self._extract_first_block(data)
        params = zstd.get_frame_parameters(block)
        assert params.has_checksum is True

    def test_legacy_frame_without_checksum(self):
        # Costruisce un .mpmz con un frame Zstandard senza checksum.
        mpm = self._make_mpm()
        body = _serialize_mpm_body(mpm)
        cctx = zstd.ZstdCompressor(write_checksum=False)
        compressed = cctx.compress(body)
        header = MPMZHeader(
            meta={"delimiter": ",", "encoding": "utf-8", "compression": "zstd"},
            schema=mpm.header.schema,
            blocks=1,
            original_size=len(body),
            original_version="0.2",
        )
        header_json = json.dumps(header.to_dict(), ensure_ascii=False).encode("utf-8")
        data = (
            MAGIC
            + struct.pack(">B", VERSION)
            + struct.pack(">I", len(header_json))
            + header_json
            + struct.pack(">I", len(body))
            + struct.pack(">I", len(compressed))
            + compressed
        )
        mpm2 = decompress_mpmz(data)
        assert mpm2.rows == mpm.rows

    def test_corrupted_checksum_raises(self):
        mpm = self._make_mpm()
        data = bytearray(compress_mpm(mpm))
        (header_len,) = struct.unpack(">I", bytes(data[5:9]))
        offset = 9 + header_len
        _orig_size, comp_size = struct.unpack(">II", bytes(data[offset : offset + 8]))
        offset += 8
        # Il checksum è gli ultimi 4 byte del frame Zstandard.
        checksum_pos = offset + comp_size - 4
        data[checksum_pos] ^= 0xFF  # corrompe un byte del checksum
        with pytest.raises(MPMZError):
            decompress_mpmz(bytes(data))

    def test_roundtrip_v01_with_checksum(self):
        mpm = self._make_mpm("0.1", [["hello"], ["world"]])
        data = compress_mpm(mpm)
        mpm2 = decompress_mpmz(data)
        assert mpm2.header.version == "0.1"
        assert mpm2.rows == [["hello"], ["world"]]

    def test_roundtrip_v02_with_checksum(self):
        mpm = self._make_mpm("0.2", [[None], [""], ["\\N"], ["a\\\\b"]])
        data = compress_mpm(mpm)
        mpm2 = decompress_mpmz(data)
        assert mpm2.header.version == "0.2"
        assert mpm2.rows == [[None], [""], ["\\N"], ["a\\\\b"]]

    def test_cli_roundtrip_still_works(self, tmp_path):
        # Verifica che il roundtrip CLI (convert → compress → decompress)
        # funzioni ancora con il checksum abilitato.
        csv_p = tmp_path / "in.csv"
        mpm_p = tmp_path / "out.mpm"
        mpmz_p = tmp_path / "out.mpmz"
        mpm2_p = tmp_path / "out2.mpm"
        csv_p.write_text("id,nome\n1,Mario\n2,Luigi\n", encoding="utf-8")
        from mpm.csv_io import csv_to_mpm, mpm_to_csv
        from mpm.compress import mpm_to_mpmz, mpmz_to_mpm
        csv_to_mpm(csv_p, mpm_p)
        mpm_to_mpmz(mpm_p, mpmz_p)
        mpmz_to_mpm(mpmz_p, mpm2_p)
        assert (
            mpm2_p.read_text(encoding="utf-8").rstrip("\n")
            == mpm_p.read_text(encoding="utf-8").rstrip("\n")
        )