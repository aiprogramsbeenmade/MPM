"""Inferenza e validazione dello schema per file MPM."""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from mpm.format import MPMError, MPMFile

# Numero di righe da analizzare per inferire i tipi (default).
DEFAULT_SAMPLE_SIZE = 1000

# Tipi supportati dallo schema MPM.
VALID_TYPES = {"int", "float", "str", "date", "datetime", "bool"}

# Pattern per riconoscere i tipi.
_INT_RE = re.compile(r"^-?\d+$")
_FLOAT_RE = re.compile(r"^-?\d+\.\d+$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
_BOOL_VALUES = {"true", "false"}


class MPMSchemaInferenceError(MPMError):
    """Errore durante l'inferenza dello schema."""


@dataclass
class ColumnStats:
    """Statistiche raccolte su una colonna durante il campionamento."""

    name: str
    total: int = 0
    empty: int = 0
    int_count: int = 0
    float_count: int = 0
    date_count: int = 0
    datetime_count: int = 0
    bool_count: int = 0
    examples: list[str] = None

    def __post_init__(self) -> None:
        if self.examples is None:
            self.examples = []

    def add(self, value: str) -> None:
        self.total += 1
        if value == "":
            self.empty += 1
            return
        # int: isdigit è molto più veloce della regex.
        stripped = value.lstrip("-")
        if stripped.isdigit():
            self.int_count += 1
        elif "." in value and value.replace(".", "", 1).lstrip("-").isdigit():
            self.float_count += 1
        elif value.lower() in _BOOL_VALUES:
            self.bool_count += 1
        elif _DATE_RE.match(value):
            self.date_count += 1
        elif _DATETIME_RE.match(value):
            self.datetime_count += 1
        if len(self.examples) < 5:
            self.examples.append(value)

    def infer_type(self) -> str:
        """Inferisce il tipo della colonna dalle statistiche."""
        non_empty = self.total - self.empty
        if non_empty == 0:
            return "str"  # colonna vuota: tipo di default
        # Se tutti i valori non vuoti sono di un tipo, usa quel tipo.
        if self.int_count == non_empty:
            return "int"
        if self.float_count == non_empty:
            return "float"
        if self.date_count == non_empty:
            return "date"
        if self.datetime_count == non_empty:
            return "datetime"
        if self.bool_count == non_empty:
            return "bool"
        # Mix di tipi: se ci sono solo int e float, promuovi a float.
        if self.int_count + self.float_count == non_empty:
            return "float"
        # Altrimenti, stringa.
        return "str"

    def infer_nullable(self) -> bool:
        """Una colonna è nullable se ha almeno un valore vuoto."""
        return self.empty > 0


def infer_schema_from_csv(
    path: str | Path,
    delimiter: str = ",",
    encoding: str = "utf-8",
    sample_size: int = DEFAULT_SAMPLE_SIZE,
) -> list[dict[str, Any]]:
    """Inferisce lo schema da un file CSV.

    Args:
        path: percorso del file CSV.
        delimiter: separatore di campo.
        encoding: codifica del file.
        sample_size: numero di righe da analizzare (default 1000).

    Returns:
        Una lista di dict, uno per colonna, con campi name, type, nullable.

    Raises:
        MPMSchemaInferenceError: se il CSV è vuoto o malformato.
    """
    if sample_size <= 0:
        raise MPMSchemaInferenceError("sample_size deve essere positivo")

    text = Path(path).read_text(encoding=encoding)
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = list(reader)
    if not rows:
        raise MPMSchemaInferenceError("Il CSV è vuoto")

    header = rows[0]
    if not header:
        raise MPMSchemaInferenceError("Il CSV non ha colonne")

    # Inizializza le statistiche per ogni colonna.
    stats = [ColumnStats(name=name) for name in header]

    # Campiona le righe.
    data_rows = rows[1 : 1 + sample_size]
    for row in data_rows:
        if len(row) != len(header):
            raise MPMSchemaInferenceError(
                f"Riga con {len(row)} campi, attesi {len(header)}: {row!r}"
            )
        for i, value in enumerate(row):
            stats[i].add(value)

    # Costruisci lo schema.
    schema: list[dict[str, Any]] = []
    for col in stats:
        col_type = col.infer_type()
        entry: dict[str, Any] = {
            "name": col.name,
            "type": col_type,
            "nullable": col.infer_nullable(),
        }
        if col_type in ("date", "datetime"):
            entry["format"] = "YYYY-MM-DD" if col_type == "date" else "YYYY-MM-DDTHH:MM:SS"
        schema.append(entry)
    return schema


def validate_schema(mpm: MPMFile) -> list[dict[str, Any]]:
    """Valida i dati di un MPMFile contro il suo schema.

    Restituisce una lista di anomalie (vuota se tutto è ok).
    Ogni anomalia è un dict con: row, column, expected_type, value, message.

    Args:
        mpm: il file MPM da validare.

    Returns:
        Lista di anomalie trovate.
    """
    anomalies: list[dict[str, Any]] = []
    schema = mpm.header.schema
    for row_idx, row in enumerate(mpm.rows, start=1):
        for col_idx, value in enumerate(row):
            col = schema[col_idx]
            expected = col.get("type", "str")
            nullable = col.get("nullable", True)
            if value == "":
                if not nullable:
                    anomalies.append({
                        "row": row_idx,
                        "column": col["name"],
                        "expected_type": expected,
                        "value": value,
                        "message": "Valore vuoto in colonna non nullable",
                    })
                continue
            if not _value_matches_type(value, expected, col.get("format")):
                anomalies.append({
                    "row": row_idx,
                    "column": col["name"],
                    "expected_type": expected,
                    "value": value,
                    "message": f"Valore {value!r} non conforme al tipo {expected}",
                })
    return anomalies


def _value_matches_type(value: str, expected: str, fmt: str | None = None) -> bool:
    """Verifica se un valore corrisponde al tipo dichiarato."""
    if expected == "int":
        return bool(_INT_RE.match(value))
    if expected == "float":
        return bool(_INT_RE.match(value) or _FLOAT_RE.match(value))
    if expected == "date":
        if not _DATE_RE.match(value):
            return False
        try:
            datetime.strptime(value, "%Y-%m-%d")
            return True
        except ValueError:
            return False
    if expected == "datetime":
        if not _DATETIME_RE.match(value):
            return False
        try:
            datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
            return True
        except ValueError:
            return False
    if expected == "bool":
        return value.lower() in _BOOL_VALUES
    if expected == "str":
        return True
    # Tipo sconosciuto: accettiamo tutto (tolleranza).
    return True


def infer_schema_from_rows(
    header: list[str],
    rows: list[list[str]],
    sample_size: int = DEFAULT_SAMPLE_SIZE,
) -> list[dict[str, Any]]:
    """Inferisce lo schema da header e righe già in memoria.

    Utile per i test e per l'uso programmatico.
    """
    if not header:
        raise MPMSchemaInferenceError("Header vuoto")
    stats = [ColumnStats(name=name) for name in header]
    for row in rows[:sample_size]:
        if len(row) != len(header):
            raise MPMSchemaInferenceError(
                f"Riga con {len(row)} campi, attesi {len(header)}"
            )
        for i, value in enumerate(row):
            stats[i].add(value)
    schema: list[dict[str, Any]] = []
    for col in stats:
        col_type = col.infer_type()
        entry: dict[str, Any] = {
            "name": col.name,
            "type": col_type,
            "nullable": col.infer_nullable(),
        }
        if col_type in ("date", "datetime"):
            entry["format"] = "YYYY-MM-DD" if col_type == "date" else "YYYY-MM-DDTHH:MM:SS"
        schema.append(entry)
    return schema