"""Test di integrazione per la CLI di MPM."""

import io
import json
from contextlib import redirect_stderr, redirect_stdout

import pytest

from mpm.__main__ import main


CSV_SIMPLE = """\
id,nome
1,Mario
2,Luigi
"""


def _run(args, tmp_path):
    """Esegue la CLI e restituisce (returncode, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(args)
    return code, out.getvalue(), err.getvalue()


class TestConvert:
    def test_convert_infer(self, tmp_path):
        csv_p = tmp_path / "in.csv"
        mpm_p = tmp_path / "out.mpm"
        csv_p.write_text(CSV_SIMPLE, encoding="utf-8")
        code, out, err = _run(["convert", str(csv_p), str(mpm_p)], tmp_path)
        assert code == 0
        assert mpm_p.exists()
        assert "Convertito" in out

    def test_convert_with_schema(self, tmp_path):
        csv_p = tmp_path / "in.csv"
        mpm_p = tmp_path / "out.mpm"
        schema_p = tmp_path / "schema.json"
        csv_p.write_text(CSV_SIMPLE, encoding="utf-8")
        schema = [
            {"name": "id", "type": "int", "nullable": False},
            {"name": "nome", "type": "str"},
        ]
        schema_p.write_text(json.dumps(schema), encoding="utf-8")
        code, _, _ = _run(
            ["convert", str(csv_p), str(mpm_p), "--schema", str(schema_p)],
            tmp_path,
        )
        assert code == 0


class TestInfer:
    def test_infer_stdout(self, tmp_path):
        csv_p = tmp_path / "in.csv"
        csv_p.write_text(CSV_SIMPLE, encoding="utf-8")
        code, out, _ = _run(["infer", str(csv_p)], tmp_path)
        assert code == 0
        schema = json.loads(out)
        assert schema[0]["type"] == "int"

    def test_infer_to_file(self, tmp_path):
        csv_p = tmp_path / "in.csv"
        out_p = tmp_path / "schema.json"
        csv_p.write_text(CSV_SIMPLE, encoding="utf-8")
        code, _, _ = _run(["infer", str(csv_p), "-o", str(out_p)], tmp_path)
        assert code == 0
        assert out_p.exists()
        schema = json.loads(out_p.read_text(encoding="utf-8"))
        assert schema[1]["type"] == "str"


class TestCompressDecompress:
    def test_roundtrip(self, tmp_path):
        csv_p = tmp_path / "in.csv"
        mpm_p = tmp_path / "out.mpm"
        mpmz_p = tmp_path / "out.mpmz"
        mpm2_p = tmp_path / "out2.mpm"
        csv_p.write_text(CSV_SIMPLE, encoding="utf-8")
        _run(["convert", str(csv_p), str(mpm_p)], tmp_path)
        code, _, _ = _run(["compress", str(mpm_p), str(mpmz_p)], tmp_path)
        assert code == 0
        code, _, _ = _run(["decompress", str(mpmz_p), str(mpm2_p)], tmp_path)
        assert code == 0
        assert mpm2_p.read_text(encoding="utf-8") == mpm_p.read_text(encoding="utf-8")


class TestInfo:
    def test_info_mpm(self, tmp_path):
        csv_p = tmp_path / "in.csv"
        mpm_p = tmp_path / "out.mpm"
        csv_p.write_text(CSV_SIMPLE, encoding="utf-8")
        _run(["convert", str(csv_p), str(mpm_p)], tmp_path)
        code, out, _ = _run(["info", str(mpm_p)], tmp_path)
        assert code == 0
        assert "Righe: 2" in out
        assert "Colonne: 2" in out
        assert "id: int" in out

    def test_info_mpmz(self, tmp_path):
        csv_p = tmp_path / "in.csv"
        mpm_p = tmp_path / "out.mpm"
        mpmz_p = tmp_path / "out.mpmz"
        csv_p.write_text(CSV_SIMPLE, encoding="utf-8")
        _run(["convert", str(csv_p), str(mpm_p)], tmp_path)
        _run(["compress", str(mpm_p), str(mpmz_p)], tmp_path)
        code, out, _ = _run(["info", str(mpmz_p)], tmp_path)
        assert code == 0
        assert "Righe: 2" in out
        assert "Colonne: 2" in out
        assert "id: int" in out


class TestValidate:
    def test_valid(self, tmp_path):
        csv_p = tmp_path / "in.csv"
        mpm_p = tmp_path / "out.mpm"
        csv_p.write_text(CSV_SIMPLE, encoding="utf-8")
        _run(["convert", str(csv_p), str(mpm_p)], tmp_path)
        code, out, _ = _run(["validate", str(mpm_p)], tmp_path)
        assert code == 0
        assert "Nessuna anomalia" in out

    def test_invalid(self, tmp_path):
        csv_p = tmp_path / "in.csv"
        mpm_p = tmp_path / "out.mpm"
        schema_p = tmp_path / "schema.json"
        csv_p.write_text("id\nabc\n", encoding="utf-8")
        schema = [{"name": "id", "type": "int", "nullable": False}]
        schema_p.write_text(json.dumps(schema), encoding="utf-8")
        _run(
            ["convert", str(csv_p), str(mpm_p), "--schema", str(schema_p)],
            tmp_path,
        )
        code, out, err = _run(["validate", str(mpm_p)], tmp_path)
        assert code == 1
        assert "anomalie" in err


class TestErrors:
    def test_missing_input(self, tmp_path):
        code, _, err = _run(
            ["convert", str(tmp_path / "nope.csv"), str(tmp_path / "out.mpm")],
            tmp_path,
        )
        assert code == 1
        assert "Errore" in err

    def test_no_command(self):
        err = io.StringIO()
        with redirect_stderr(err), pytest.raises(SystemExit):
            main([])