"""Test unitari per il modulo mpm.format."""

import json

import pytest

from mpm.format import (
    MPMError,
    MPMFile,
    MPMHeader,
    MPMHeaderError,
    MPMSchemaError,
    MPMVersionError,
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