"""Test unitari per il modulo mpm.format."""

import json

import pytest

from mpm.format import (
    MPMEncodingError,
    MPMError,
    MPMFile,
    MPMHeader,
    MPMHeaderError,
    MPMSchemaError,
    MPMVersionError,
    _decode_mpm_value,
    _encode_mpm_value,
    parse_header,
    read_mpm,
    serialize_header,
    write_mpm,
)


VALID_MPM = """\
# MPM v0.1
# @meta: {"delimiter":",","encoding":"utf-8","compression":"none"}
# @schema: [{"name":"id","type":"int"},{"name":"nome","type":"str"}]
id,nome
1,Mario
2,Luigi
"""


def _make_header(**overrides) -> MPMHeader:
    meta = {"delimiter": ",", "encoding": "utf-8", "compression": "none"}
    schema = [{"name": "id", "type": "int"}, {"name": "nome", "type": "str"}]
    meta.update(overrides.pop("meta", {}))
    schema = overrides.pop("schema", schema)
    return MPMHeader(
        version=overrides.pop("version", "0.1"),
        meta=meta,
        schema=schema,
        **overrides,
    )


class TestParseHeader:
    def test_valid_header(self):
        lines = VALID_MPM.splitlines()
        header, body_start = parse_header(lines)
        assert header.version == "0.1"
        assert header.meta["delimiter"] == ","
        assert header.schema[0]["name"] == "id"
        assert lines[body_start] == "id,nome"

    def test_missing_header(self):
        with pytest.raises(MPMHeaderError):
            parse_header(["id,nome", "1,Mario"])

    def test_bad_version_line(self):
        with pytest.raises(MPMHeaderError):
            parse_header(["# MPN v0.1"])

    def test_unsupported_version(self):
        lines = ["# MPM v9.9", "# @meta: {}", "# @schema: []"]
        with pytest.raises(MPMVersionError):
            parse_header(lines)

    def test_meta_not_json(self):
        lines = [
            "# MPM v0.1",
            "# @meta: {not json}",
            "# @schema: [{\"name\":\"a\",\"type\":\"int\"}]",
        ]
        with pytest.raises(MPMHeaderError):
            parse_header(lines)

    def test_meta_missing_field(self):
        lines = [
            "# MPM v0.1",
            '# @meta: {"delimiter":","}',
            '# @schema: [{"name":"a","type":"int"}]',
        ]
        with pytest.raises(MPMHeaderError):
            parse_header(lines)

    def test_schema_not_array(self):
        lines = [
            "# MPM v0.1",
            '# @meta: {"delimiter":",","encoding":"utf-8","compression":"none"}',
            '# @schema: {"name":"a"}',
        ]
        with pytest.raises(MPMHeaderError):
            parse_header(lines)

    def test_extension_parsed(self):
        lines = [
            "# MPM v0.1",
            '# @meta: {"delimiter":",","encoding":"utf-8","compression":"none"}',
            '# @schema: [{"name":"a","type":"int"}]',
            '# @custom: {"note":"ciao"}',
            "a",
            "1",
        ]
        header, body_start = parse_header(lines)
        assert header.extensions["custom"] == {"note": "ciao"}
        assert lines[body_start] == "a"


class TestSerializeHeader:
    def test_roundtrip(self):
        header = _make_header()
        lines = serialize_header(header)
        header2, _ = parse_header(lines)
        assert header2.version == header.version
        assert header2.meta == header.meta
        assert header2.schema == header.schema

class TestReadVersioning:
    def test_v01_backslashes_preserved(self, tmp_path):
        content = (
            "# MPM v0.1\n"
            '# @meta: {"delimiter":",","encoding":"utf-8","compression":"none"}\n'
            '# @schema: [{"name":"val","type":"str"}]\n'
            "val\n"
            "\\\\N\n"  # nel file: \\N (due backslash e una N)
        )
        p = tmp_path / "v01.mpm"
        p.write_text(content, encoding="utf-8")
        mpm = read_mpm(p)
        assert mpm.rows == [["\\\\N"]]

    def test_v02_null(self, tmp_path):
        content = (
            "# MPM v0.2\n"
            '# @meta: {"delimiter":",","encoding":"utf-8","compression":"none"}\n'
            '# @schema: [{"name":"val","type":"str","nullable":true}]\n'
            "val\n"
            "\\N\n"
        )
        p = tmp_path / "v02.mpm"
        p.write_text(content, encoding="utf-8")
        mpm = read_mpm(p)
        assert mpm.rows == [[None]]

    def test_v02_literal_null_string(self, tmp_path):
        content = (
            "# MPM v0.2\n"
            '# @meta: {"delimiter":",","encoding":"utf-8","compression":"none"}\n'
            '# @schema: [{"name":"val","type":"str"}]\n'
            "val\n"
            "\\\\N\n"
        )
        p = tmp_path / "v02_lit.mpm"
        p.write_text(content, encoding="utf-8")
        mpm = read_mpm(p)
        assert mpm.rows == [["\\N"]]

    def test_v02_empty_and_multiple_backslashes(self, tmp_path):
        content = (
            "# MPM v0.2\n"
            '# @meta: {"delimiter":",","encoding":"utf-8","compression":"none"}\n'
            '# @schema: [{"name":"val","type":"str"}]\n'
            "val\n"
            '""\n'  # stringa vuota (campo quotato)
            "\\\\\\\\\n"  # quattro backslash nel file -> due backslash reali
        )
        p = tmp_path / "v02_back.mpm"
        p.write_text(content, encoding="utf-8")
        mpm = read_mpm(p)
        assert mpm.rows == [[""], ["\\\\"]]

    def test_v02_special_csv_chars(self, tmp_path):
        content = (
            "# MPM v0.2\n"
            '# @meta: {"delimiter":",","encoding":"utf-8","compression":"none"}\n'
            '# @schema: [{"name":"val","type":"str"}]\n'
            "val\n"
            '"a,b"\n'
            '"a""b"\n'
            '"a\nb"\n'
        )
        p = tmp_path / "v02_csv.mpm"
        p.write_text(content, encoding="utf-8")
        mpm = read_mpm(p)
        assert mpm.rows == [["a,b"], ['a"b'], ["a\nb"]]

    def test_v02_header_does_not_escape(self, tmp_path):
        content = (
            "# MPM v0.2\n"
            '# @meta: {"delimiter":",","encoding":"utf-8","compression":"none"}\n'
            '# @schema: [{"name":"col\\\\Nname","type":"str"}]\n'
            "col\\Nname\n"  # nel file: col\Nname (un backslash e una N)
            "value\n"
        )
        p = tmp_path / "v02_header.mpm"
        p.write_text(content, encoding="utf-8")
        mpm = read_mpm(p)
        assert mpm.header.schema[0]["name"] == "col\\Nname"
        assert mpm.rows == [["value"]]

    def test_unknown_version_raises(self, tmp_path):
        content = (
            "# MPM v0.9\n"
            '# @meta: {"delimiter":",","encoding":"utf-8","compression":"none"}\n'
            '# @schema: [{"name":"val","type":"str"}]\n'
            "val\n"
            "x\n"
        )
        p = tmp_path / "v09.mpm"
        p.write_text(content, encoding="utf-8")
        with pytest.raises(MPMVersionError):
            read_mpm(p)

    def test_v02_malformed_escape_raises(self, tmp_path):
        content = (
            "# MPM v0.2\n"
            '# @meta: {"delimiter":",","encoding":"utf-8","compression":"none"}\n'
            '# @schema: [{"name":"val","type":"str"}]\n'
            "val\n"
            "\\x\n"  # escape malformato
        )
        p = tmp_path / "v02_bad.mpm"
        p.write_text(content, encoding="utf-8")
        with pytest.raises(MPMEncodingError):
            read_mpm(p)

class TestReadWrite:
    def test_read_valid(self, tmp_path):
        p = tmp_path / "test.mpm"
        p.write_text(VALID_MPM, encoding="utf-8")
        mpm = read_mpm(p)
        assert mpm.header.version == "0.1"
        assert mpm.rows == [["1", "Mario"], ["2", "Luigi"]]

    def test_read_missing(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            read_mpm(tmp_path / "nope.mpm")

    def test_schema_mismatch(self, tmp_path):
        content = """\
# MPM v0.1
# @meta: {"delimiter":",","encoding":"utf-8","compression":"none"}
# @schema: [{"name":"a","type":"int"},{"name":"b","type":"int"}]
a
1
"""
        p = tmp_path / "bad.mpm"
        p.write_text(content, encoding="utf-8")
        with pytest.raises(MPMSchemaError):
            read_mpm(p)

    def test_row_wrong_column_count(self, tmp_path):
        content = """\
# MPM v0.1
# @meta: {"delimiter":",","encoding":"utf-8","compression":"none"}
# @schema: [{"name":"a","type":"int"},{"name":"b","type":"int"}]
a,b
1
"""
        p = tmp_path / "bad.mpm"
        p.write_text(content, encoding="utf-8")
        with pytest.raises(MPMSchemaError):
            read_mpm(p)

    def test_write_then_read_roundtrip(self, tmp_path):
        header = _make_header()
        mpm = MPMFile(header=header, rows=[["1", "Mario"], ["2", "Luigi"]])
        p = tmp_path / "out.mpm"
        write_mpm(mpm, p)
        mpm2 = read_mpm(p)
        assert mpm2.rows == mpm.rows
        assert mpm2.header.schema == header.schema

class TestMpmValueEncoding:
    def test_encode_none(self):
        assert _encode_mpm_value(None) == "\\N"

    def test_decode_null(self):
        assert _decode_mpm_value("\\N") is None

    def test_encode_empty(self):
        assert _encode_mpm_value("") == ""

    def test_decode_empty(self):
        assert _decode_mpm_value("") == ""

    def test_encode_backslash(self):
        assert _encode_mpm_value("\\") == "\\\\"
        assert _encode_mpm_value("a\\b") == "a\\\\b"
        assert _encode_mpm_value("\\\\") == "\\\\\\\\"

    def test_decode_backslash(self):
        assert _decode_mpm_value("\\\\") == "\\"
        assert _decode_mpm_value("a\\\\b") == "a\\b"
        assert _decode_mpm_value("\\\\\\\\") == "\\\\"

    def test_encode_literal_null_string(self):
        assert _encode_mpm_value("\\N") == "\\\\N"

    def test_decode_literal_null_string(self):
        assert _decode_mpm_value("\\\\N") == "\\N"

    def test_decode_malformed(self):
        with pytest.raises(MPMEncodingError):
            _decode_mpm_value("\\x")
        with pytest.raises(MPMEncodingError):
            _decode_mpm_value("abc\\")
        with pytest.raises(MPMEncodingError):
            _decode_mpm_value("a\\b")

    def test_encode_unicode(self):
        assert _encode_mpm_value("città 🏙️") == "città 🏙️"
        assert _decode_mpm_value("città 🏙️") == "città 🏙️"

    def test_encode_literal_chars(self):
        assert _encode_mpm_value("a\nb\tc") == "a\nb\tc"
        assert _decode_mpm_value("a\nb\tc") == "a\nb\tc"

    @pytest.mark.parametrize("value", [
        None, "", "ciao", "\\", "\\\\", "\\N", "a\\b", "città 🏙️", "a\nb\tc"
    ])
    def test_roundtrip(self, value):
        encoded = _encode_mpm_value(value)
        decoded = _decode_mpm_value(encoded)
        assert decoded == value
class TestEdgeCases:
    def test_hash_in_body(self, tmp_path):
        content = """\
# MPM v0.1
# @meta: {"delimiter":",","encoding":"utf-8","compression":"none"}
# @schema: [{"name":"tag","type":"str"}]
tag
#ciao
#mondo
"""
        p = tmp_path / "hash.mpm"
        p.write_text(content, encoding="utf-8")
        mpm = read_mpm(p)
        assert mpm.rows == [["#ciao"], ["#mondo"]]

    def test_empty_body(self, tmp_path):
        content = """\
# MPM v0.1
# @meta: {"delimiter":",","encoding":"utf-8","compression":"none"}
# @schema: [{"name":"id","type":"int"}]
id
"""
        p = tmp_path / "empty.mpm"
        p.write_text(content, encoding="utf-8")
        mpm = read_mpm(p)
        assert mpm.rows == []

class TestWriteVersioning:
    def _make_mpm(self, version: str, rows, schema=None) -> MPMFile:
        schema = schema or [{"name": "val", "type": "str"}]
        header = MPMHeader(
            version=version,
            meta={"delimiter": ",", "encoding": "utf-8", "compression": "none"},
            schema=schema,
        )
        return MPMFile(header=header, rows=rows)

    def test_write_new_v02(self, tmp_path):
        mpm = self._make_mpm("0.2", [["hello"]])
        p = tmp_path / "out.mpm"
        write_mpm(mpm, p)
        content = p.read_text(encoding="utf-8")
        assert content.startswith("# MPM v0.2\n")

    def test_write_none_v02(self, tmp_path):
        mpm = self._make_mpm("0.2", [[None]])
        p = tmp_path / "out.mpm"
        write_mpm(mpm, p)
        content = p.read_text(encoding="utf-8")
        assert "val\n\\N\n" in content

    def test_write_empty_string_v02(self, tmp_path):
        mpm = self._make_mpm("0.2", [[""]])
        p = tmp_path / "out.mpm"
        write_mpm(mpm, p)
        mpm2 = read_mpm(p)
        assert mpm2.rows == [[""]]

    def test_write_literal_null_string_v02(self, tmp_path):
        mpm = self._make_mpm("0.2", [["\\N"]])
        p = tmp_path / "out.mpm"
        write_mpm(mpm, p)
        content = p.read_text(encoding="utf-8")
        assert "\\\\N\n" in content
        mpm2 = read_mpm(p)
        assert mpm2.rows == [["\\N"]]

    def test_write_multiple_backslashes_v02(self, tmp_path):
        mpm = self._make_mpm("0.2", [["a\\b\\\\c"]])
        p = tmp_path / "out.mpm"
        write_mpm(mpm, p)
        mpm2 = read_mpm(p)
        assert mpm2.rows == [["a\\b\\\\c"]]

    def test_write_unicode_v02(self, tmp_path):
        mpm = self._make_mpm("0.2", [["città 🏙️"]])
        p = tmp_path / "out.mpm"
        write_mpm(mpm, p)
        mpm2 = read_mpm(p)
        assert mpm2.rows == [["città 🏙️"]]

    def test_write_special_csv_chars_v02(self, tmp_path):
        mpm = self._make_mpm("0.2", [["a,b"], ['a"b'], ["a\nb"]])
        p = tmp_path / "out.mpm"
        write_mpm(mpm, p)
        mpm2 = read_mpm(p)
        assert mpm2.rows == [["a,b"], ['a"b'], ["a\nb"]]

    def test_roundtrip_v02(self, tmp_path):
        mpm = self._make_mpm("0.2", [[None], [""], ["hello"], ["\\N"], ["\\\\"]])
        p = tmp_path / "out.mpm"
        write_mpm(mpm, p)
        mpm2 = read_mpm(p)
        assert mpm2.rows == mpm.rows
        assert mpm2.header.version == "0.2"

    def test_write_preserves_v01(self, tmp_path):
        mpm = self._make_mpm("0.1", [["hello"]])
        p = tmp_path / "out.mpm"
        write_mpm(mpm, p)
        content = p.read_text(encoding="utf-8")
        assert content.startswith("# MPM v0.1\n")

    def test_convert_v01_to_v02(self, tmp_path):
        mpm_v01 = self._make_mpm("0.1", [["hello"], ["world"]])
        # Conversione esplicita: cambio la versione.
        mpm_v01.header.version = "0.2"
        p = tmp_path / "out.mpm"
        write_mpm(mpm_v01, p)
        mpm2 = read_mpm(p)
        assert mpm2.header.version == "0.2"
        assert mpm2.rows == [["hello"], ["world"]]

    def test_write_unknown_version_raises(self, tmp_path):
        mpm = self._make_mpm("0.9", [["hello"]])
        p = tmp_path / "out.mpm"
        with pytest.raises(MPMVersionError):
            write_mpm(mpm, p)

    def test_write_none_v01_raises(self, tmp_path):
        mpm = self._make_mpm("0.1", [[None]])
        p = tmp_path / "out.mpm"
        with pytest.raises(MPMEncodingError):
            write_mpm(mpm, p)