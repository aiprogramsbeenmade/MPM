"""Esegue la suite di conformità di MPM."""

from pathlib import Path

import pytest

from mpm.compress import decompress_mpmz, read_mpmz
from mpm.csv_io import csv_to_mpm, mpm_to_csv
from mpm.format import MPMError, read_mpm

CONFORMANCE = Path(__file__).parent.parent / "conformance"


def _mpm_files(subdir: str) -> list[Path]:
    return sorted((CONFORMANCE / subdir).glob("*.mpm"))


class TestValid:
    @pytest.mark.parametrize("path", _mpm_files("valid"), ids=lambda p: p.name)
    def test_valid_mpm_is_readable(self, path):
        mpm = read_mpm(path)
        assert mpm.header.version == "0.1"
        assert len(mpm.header.schema) > 0


class TestInvalid:
    @pytest.mark.parametrize("path", _mpm_files("invalid"), ids=lambda p: p.name)
    def test_invalid_mpm_is_rejected(self, path):
        with pytest.raises(MPMError):
            read_mpm(path)

    def test_invalid_mpmz_is_rejected(self):
        path = CONFORMANCE / "invalid" / "invalid_004.mpmz"
        with pytest.raises(MPMError):
            read_mpmz(path)


class TestEdgeCases:
    @pytest.mark.parametrize("path", _mpm_files("edge_cases"), ids=lambda p: p.name)
    def test_edge_case_is_readable(self, path):
        mpm = read_mpm(path)
        assert mpm.header.version == "0.1"


class TestRoundtrip:
    def test_csv_to_mpm_to_csv(self, tmp_path):
        csv_in = CONFORMANCE / "roundtrip" / "simple.csv"
        mpm_out = tmp_path / "simple.mpm"
        csv_out = tmp_path / "simple_out.csv"
        csv_to_mpm(csv_in, mpm_out)
        mpm_to_csv(mpm_out, csv_out)
        # Confronta normalizzando il newline finale.
        assert csv_out.read_text(encoding="utf-8").rstrip("\n") == csv_in.read_text(encoding="utf-8").rstrip("\n")

    def test_mpm_to_mpmz_to_mpm(self, tmp_path):
        mpm_in = CONFORMANCE / "roundtrip" / "simple.mpm"
        mpmz_out = tmp_path / "simple.mpmz"
        mpm_out = tmp_path / "simple_out.mpm"
        from mpm.compress import mpm_to_mpmz, mpmz_to_mpm

        mpm_to_mpmz(mpm_in, mpmz_out)
        mpmz_to_mpm(mpmz_out, mpm_out)
        # Il newline finale è una convenzione, non un requisito del formato.
        assert mpm_out.read_text(encoding="utf-8").rstrip("\n") == mpm_in.read_text(encoding="utf-8").rstrip("\n")

    def test_mpm_to_csv_to_mpm(self, tmp_path):
        mpm_in = CONFORMANCE / "roundtrip" / "simple.mpm"
        csv_out = tmp_path / "simple.csv"
        mpm_out = tmp_path / "simple_out.mpm"
        mpm_to_csv(mpm_in, csv_out)
        csv_to_mpm(csv_out, mpm_out)
        # I metadati possono differire (inferenza vs esplicito), ma i dati no.
        mpm1 = read_mpm(mpm_in)
        mpm2 = read_mpm(mpm_out)
        assert mpm2.rows == mpm1.rows