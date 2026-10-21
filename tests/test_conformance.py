"""Esegue la suite di conformità di MPM."""

from pathlib import Path

import pytest

from mpm.compress import decompress_mpmz, read_mpmz
from mpm.csv_io import csv_to_mpm, mpm_to_csv
from mpm.format import MPMEncodingError, MPMError, MPMVersionError, read_mpm

CONFORMANCE = Path(__file__).parent.parent / "conformance"


def _mpm_files(subdir: str) -> list[Path]:
    return sorted((CONFORMANCE / subdir).glob("*.mpm"))


class TestValid:
    @pytest.mark.parametrize("path", _mpm_files("valid"), ids=lambda p: p.name)
    def test_valid_mpm_is_readable(self, path):
        mpm = read_mpm(path)
        assert mpm.header.version in ("0.1", "0.2")
        assert len(mpm.header.schema) > 0

    def test_v02_null_decoded(self):
        mpm = read_mpm(CONFORMANCE / "valid" / "valid_v02_null.mpm")
        assert mpm.rows == [["1", None]]

    def test_v02_empty_string_distinct(self):
        mpm = read_mpm(CONFORMANCE / "valid" / "valid_v02_empty_string.mpm")
        assert mpm.rows == [["1", ""]]

    def test_v02_literal_null_decoded(self):
        mpm = read_mpm(CONFORMANCE / "valid" / "valid_v02_literal_null.mpm")
        assert mpm.rows == [["1", "\\N"]]

    def test_v02_backslashes_decoded(self):
        mpm = read_mpm(CONFORMANCE / "valid" / "valid_v02_backslashes.mpm")
        assert mpm.rows == [["1", "\\"], ["2", "a\\\\b"]]

    def test_v02_literal_chars(self):
        mpm = read_mpm(CONFORMANCE / "valid" / "valid_v02_literal_chars.mpm")
        assert mpm.rows == [["1", "a\\nb\\tc"]]

    def test_v02_unicode(self):
        mpm = read_mpm(CONFORMANCE / "valid" / "valid_v02_unicode.mpm")
        assert mpm.rows == [["1", "città"], ["2", "🏙️"]]

    def test_v02_special_csv(self):
        mpm = read_mpm(CONFORMANCE / "valid" / "valid_v02_special_csv.mpm")
        assert mpm.rows == [["1", "a,b"], ["2", 'a"b'], ["3", "a\nb"]]

    def test_v01_backslashes_preserved(self):
        mpm = read_mpm(CONFORMANCE / "valid" / "valid_v01_backslashes.mpm")
        assert mpm.rows == [["\\\\N"], ["a\\\\b"]]


class TestInvalid:
    @pytest.mark.parametrize("path", _mpm_files("invalid"), ids=lambda p: p.name)
    def test_invalid_mpm_is_rejected(self, path):
        with pytest.raises(MPMError):
            read_mpm(path)

    def test_invalid_mpmz_is_rejected(self):
        path = CONFORMANCE / "invalid" / "invalid_004.mpmz"
        with pytest.raises(MPMError):
            read_mpmz(path)

    def test_unknown_version_rejected(self):
        path = CONFORMANCE / "invalid" / "invalid_v02_unknown_version.mpm"
        with pytest.raises(MPMVersionError):
            read_mpm(path)

    def test_bad_escape_rejected(self):
        path = CONFORMANCE / "invalid" / "invalid_v02_bad_escape.mpm"
        with pytest.raises(MPMEncodingError):
            read_mpm(path)

    def test_trailing_backslash_rejected(self):
        path = CONFORMANCE / "invalid" / "invalid_v02_trailing_backslash.mpm"
        with pytest.raises(MPMEncodingError):
            read_mpm(path)


class TestEdgeCases:
    @pytest.mark.parametrize("path", _mpm_files("edge_cases"), ids=lambda p: p.name)
    def test_edge_case_is_readable(self, path):
        mpm = read_mpm(path)
        assert mpm.header.version in ("0.1", "0.2")


class TestRoundtrip:
    def test_csv_to_mpm_to_csv(self, tmp_path):
        csv_in = CONFORMANCE / "roundtrip" / "simple.csv"
        mpm_out = tmp_path / "simple.mpm"
        csv_out = tmp_path / "simple_out.csv"
        csv_to_mpm(csv_in, mpm_out)
        mpm_to_csv(mpm_out, csv_out)
        assert (
            csv_out.read_text(encoding="utf-8").rstrip("\n")
            == csv_in.read_text(encoding="utf-8").rstrip("\n")
        )

    def test_mpm_to_mpmz_to_mpm(self, tmp_path):
        mpm_in = CONFORMANCE / "roundtrip" / "simple.mpm"
        mpmz_out = tmp_path / "simple.mpmz"
        mpm_out = tmp_path / "simple_out.mpm"
        from mpm.compress import mpm_to_mpmz, mpmz_to_mpm

        mpm_to_mpmz(mpm_in, mpmz_out)
        mpmz_to_mpm(mpmz_out, mpm_out)
        assert (
            mpm_out.read_text(encoding="utf-8").rstrip("\n")
            == mpm_in.read_text(encoding="utf-8").rstrip("\n")
        )

    def test_mpm_to_csv_to_mpm(self, tmp_path):
        mpm_in = CONFORMANCE / "roundtrip" / "simple.mpm"
        csv_out = tmp_path / "simple.csv"
        mpm_out = tmp_path / "simple_out.mpm"
        mpm_to_csv(mpm_in, csv_out)
        csv_to_mpm(csv_out, mpm_out)
        mpm1 = read_mpm(mpm_in)
        mpm2 = read_mpm(mpm_out)
        assert mpm2.rows == mpm1.rows