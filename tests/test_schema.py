"""Test unitari per il modulo mpm.schema."""

import pytest

from mpm.format import MPMFile, MPMHeader
from mpm.schema import (
    MPMSchemaInferenceError,
    infer_schema_from_csv,
    infer_schema_from_rows,
    validate_schema,
)


def _make_mpm(schema, rows) -> MPMFile:
    header = MPMHeader(
        version="0.1",
        meta={"delimiter": ",", "encoding": "utf-8", "compression": "none"},
        schema=schema,
    )
    return MPMFile(header=header, rows=rows)


class TestInferSchema:
    def test_all_int(self):
        schema = infer_schema_from_rows(["a"], [["1"], ["2"], ["3"]])
        assert schema[0]["type"] == "int"
        assert schema[0]["nullable"] is False

    def test_all_float(self):
        schema = infer_schema_from_rows(["a"], [["1.5"], ["2.0"], ["-3.14"]])
        assert schema[0]["type"] == "float"

    def test_mixed_int_float(self):
        schema = infer_schema_from_rows(["a"], [["1"], ["2.5"], ["3"]])
        assert schema[0]["type"] == "float"

    def test_all_str(self):
        schema = infer_schema_from_rows(["a"], [["ciao"], ["mondo"]])
        assert schema[0]["type"] == "str"

    def test_all_date(self):
        schema = infer_schema_from_rows(["a"], [["2024-01-15"], ["2024-02-20"]])
        assert schema[0]["type"] == "date"
        assert schema[0]["format"] == "YYYY-MM-DD"

    def test_all_datetime(self):
        schema = infer_schema_from_rows(
            ["a"], [["2024-01-15T14:30:00"], ["2024-02-20T09:00:00"]]
        )
        assert schema[0]["type"] == "datetime"
        assert schema[0]["format"] == "YYYY-MM-DDTHH:MM:SS"

    def test_all_bool(self):
        schema = infer_schema_from_rows(["a"], [["true"], ["FALSE"], ["True"]])
        assert schema[0]["type"] == "bool"

    def test_nullable(self):
        schema = infer_schema_from_rows(["a"], [["1"], [""], ["3"]])
        assert schema[0]["nullable"] is True
        assert schema[0]["type"] == "int"

    def test_empty_column(self):
        schema = infer_schema_from_rows(["a"], [[""], [""]])
        assert schema[0]["type"] == "str"
        assert schema[0]["nullable"] is True

    def test_multiple_columns(self):
        schema = infer_schema_from_rows(
            ["id", "nome", "data"],
            [["1", "Mario", "2024-01-15"], ["2", "Luigi", "2024-02-20"]],
        )
        assert [c["name"] for c in schema] == ["id", "nome", "data"]
        assert [c["type"] for c in schema] == ["int", "str", "date"]

    def test_empty_header(self):
        with pytest.raises(MPMSchemaInferenceError):
            infer_schema_from_rows([], [])

    def test_wrong_column_count(self):
        with pytest.raises(MPMSchemaInferenceError):
            infer_schema_from_rows(["a", "b"], [["1"]])

    def test_from_csv(self, tmp_path):
        p = tmp_path / "test.csv"
        p.write_text("id,nome\n1,Mario\n2,Luigi\n", encoding="utf-8")
        schema = infer_schema_from_csv(p)
        assert schema[0]["type"] == "int"
        assert schema[1]["type"] == "str"

    def test_from_csv_custom_delimiter(self, tmp_path):
        p = tmp_path / "test.csv"
        p.write_text("id;nome\n1;Mario\n", encoding="utf-8")
        schema = infer_schema_from_csv(p, delimiter=";")
        assert schema[0]["type"] == "int"

    def test_from_csv_empty(self, tmp_path):
        p = tmp_path / "empty.csv"
        p.write_text("", encoding="utf-8")
        with pytest.raises(MPMSchemaInferenceError):
            infer_schema_from_csv(p)


class TestValidateSchema:
    def test_valid_data(self):
        mpm = _make_mpm(
            [{"name": "id", "type": "int", "nullable": False}],
            [["1"], ["2"], ["3"]],
        )
        assert validate_schema(mpm) == []

    def test_invalid_int(self):
        mpm = _make_mpm(
            [{"name": "id", "type": "int", "nullable": False}],
            [["1"], ["abc"]],
        )
        anomalies = validate_schema(mpm)
        assert len(anomalies) == 1
        assert anomalies[0]["row"] == 2
        assert anomalies[0]["column"] == "id"

    def test_empty_non_nullable(self):
        mpm = _make_mpm(
            [{"name": "id", "type": "int", "nullable": False}],
            [["1"], [""]],
        )
        anomalies = validate_schema(mpm)
        assert len(anomalies) == 1
        assert "non nullable" in anomalies[0]["message"]

    def test_empty_nullable_ok(self):
        mpm = _make_mpm(
            [{"name": "id", "type": "int", "nullable": True}],
            [["1"], [""]],
        )
        assert validate_schema(mpm) == []

    def test_invalid_date(self):
        mpm = _make_mpm(
            [{"name": "d", "type": "date"}],
            [["2024-13-45"]],  # mese e giorno invalidi
        )
        anomalies = validate_schema(mpm)
        assert len(anomalies) == 1

    def test_valid_bool(self):
        mpm = _make_mpm(
            [{"name": "b", "type": "bool"}],
            [["true"], ["FALSE"], ["True"]],
        )
        assert validate_schema(mpm) == []

    def test_str_always_valid(self):
        mpm = _make_mpm(
            [{"name": "s", "type": "str"}],
            [["qualsiasi cosa"], ["123"], ["!@#"]],
        )
        assert validate_schema(mpm) == []

    def test_unknown_type_tolerated(self):
        mpm = _make_mpm(
            [{"name": "x", "type": "unknown"}],
            [["qualsiasi"]],
        )
        # Tipo sconosciuto: accettato per tolleranza.
        assert validate_schema(mpm) == []