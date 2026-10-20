"""Test unitari per il modulo mpm.csv_io."""

import pytest

from mpm.csv_io import (
    MPMCsvError,
    csv_to_mpm,
    mpm_to_csv,
    read_csv_as_mpm,
    read_csv_rows,
)
from mpm.format import MPMSchemaError, read_mpm


CSV_SIMPLE = """\
id,nome
1,Mario
2,Luigi
"""

CSV_WITH_QUOTES = """\
id,testo
1,"a,b"
2,"a""b"
"""


class TestReadCsvRows:
    def test_simple(self, tmp_path):
        p = tmp_path / "test.csv"
        p.write_text(CSV_SIMPLE, encoding="utf-8")
        header, rows = read_csv_rows(p)
        assert header == ["id", "nome"]
        assert rows == [["1", "Mario"], ["2", "Luigi"]]

    def test_empty(self, tmp_path):
        p = tmp_path / "empty.csv"
        p.write_text("", encoding="utf-8")
        with pytest.raises(MPMCsvError):
            read_csv_rows(p)

    def test_wrong_column_count(self, tmp_path):
        p = tmp_path / "bad.csv"
        p.write_text("a,b\n1\n", encoding="utf-8")
        with pytest.raises(MPMCsvError):
            read_csv_rows(p)

    def test_custom_delimiter(self, tmp_path):
        p = tmp_path / "test.csv"
        p.write_text("a;b\n1;2\n", encoding="utf-8")
        header, rows = read_csv_rows(p, delimiter=";")
        assert header == ["a", "b"]
        assert rows == [["1", "2"]]


class TestCsvToMpm:
    def test_inferred_schema(self, tmp_path):
        csv_p = tmp_path / "test.csv"
        mpm_p = tmp_path / "test.mpm"
        csv_p.write_text(CSV_SIMPLE, encoding="utf-8")
        csv_to_mpm(csv_p, mpm_p)
        mpm = read_mpm(mpm_p)
        assert mpm.header.schema[0]["type"] == "int"
        assert mpm.header.schema[1]["type"] == "str"
        assert mpm.rows == [["1", "Mario"], ["2", "Luigi"]]

    def test_explicit_schema(self, tmp_path):
        csv_p = tmp_path / "test.csv"
        mpm_p = tmp_path / "test.mpm"
        csv_p.write_text(CSV_SIMPLE, encoding="utf-8")
        schema = [
            {"name": "id", "type": "int", "nullable": False},
            {"name": "nome", "type": "str", "nullable": False},
        ]
        csv_to_mpm(csv_p, mpm_p, schema=schema)
        mpm = read_mpm(mpm_p)
        assert mpm.header.schema == schema

    def test_schema_mismatch(self, tmp_path):
        csv_p = tmp_path / "test.csv"
        mpm_p = tmp_path / "test.mpm"
        csv_p.write_text(CSV_SIMPLE, encoding="utf-8")
        schema = [{"name": "wrong", "type": "int"}]
        with pytest.raises(MPMSchemaError):
            csv_to_mpm(csv_p, mpm_p, schema=schema)

    def test_with_quotes(self, tmp_path):
        csv_p = tmp_path / "test.csv"
        mpm_p = tmp_path / "test.mpm"
        csv_p.write_text(CSV_WITH_QUOTES, encoding="utf-8")
        csv_to_mpm(csv_p, mpm_p)
        mpm = read_mpm(mpm_p)
        assert mpm.rows == [["1", "a,b"], ["2", 'a"b']]


class TestMpmToCsv:
    def test_simple(self, tmp_path):
        csv_p = tmp_path / "input.csv"
        mpm_p = tmp_path / "test.mpm"
        out_p = tmp_path / "output.csv"
        csv_p.write_text(CSV_SIMPLE, encoding="utf-8")
        csv_to_mpm(csv_p, mpm_p)
        mpm_to_csv(mpm_p, out_p)
        assert out_p.read_text(encoding="utf-8") == CSV_SIMPLE

    def test_without_header(self, tmp_path):
        csv_p = tmp_path / "input.csv"
        mpm_p = tmp_path / "test.mpm"
        out_p = tmp_path / "output.csv"
        csv_p.write_text(CSV_SIMPLE, encoding="utf-8")
        csv_to_mpm(csv_p, mpm_p)
        mpm_to_csv(mpm_p, out_p, include_header=False)
        assert out_p.read_text(encoding="utf-8") == "1,Mario\n2,Luigi\n"

    def test_quotes_roundtrip(self, tmp_path):
        csv_p = tmp_path / "input.csv"
        mpm_p = tmp_path / "test.mpm"
        out_p = tmp_path / "output.csv"
        csv_p.write_text(CSV_WITH_QUOTES, encoding="utf-8")
        csv_to_mpm(csv_p, mpm_p)
        mpm_to_csv(mpm_p, out_p)
        assert out_p.read_text(encoding="utf-8") == CSV_WITH_QUOTES


class TestReadCsvAsMpm:
    def test_inferred(self, tmp_path):
        p = tmp_path / "test.csv"
        p.write_text(CSV_SIMPLE, encoding="utf-8")
        mpm = read_csv_as_mpm(p)
        assert mpm.header.schema[0]["type"] == "int"
        assert mpm.rows == [["1", "Mario"], ["2", "Luigi"]]

    def test_explicit(self, tmp_path):
        p = tmp_path / "test.csv"
        p.write_text(CSV_SIMPLE, encoding="utf-8")
        schema = [
            {"name": "id", "type": "str"},
            {"name": "nome", "type": "str"},
        ]
        mpm = read_csv_as_mpm(p, schema=schema)
        assert mpm.header.schema == schema

    def test_schema_mismatch(self, tmp_path):
        p = tmp_path / "test.csv"
        p.write_text(CSV_SIMPLE, encoding="utf-8")
        with pytest.raises(MPMSchemaError):
            read_csv_as_mpm(p, schema=[{"name": "wrong", "type": "int"}])