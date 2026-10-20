"""Test di interoperabilità: MPM deve essere leggibile come CSV."""

from pathlib import Path

import pandas as pd

from mpm.csv_io import csv_to_mpm

# Prepara un file MPM di test.
base = Path("benchmarks/data")
csv_path = base / "interop.csv"
mpm_path = base / "interop.mpm"

csv_path.write_text(
    "id,nome,prezzo\n"
    "1,Mario,3.14\n"
    "2,Luigi,2.71\n",
    encoding="utf-8",
)
csv_to_mpm(csv_path, mpm_path)

print("=== Contenuto del file .mpm ===")
print(mpm_path.read_text(encoding="utf-8"))

# Test 1: pandas con comment="#"
print("=== Test 1: pandas con comment='#' ===")
df = pd.read_csv(mpm_path, comment="#")
print(df)
print(f"Shape: {df.shape}")
assert df.shape == (2, 3), f"Atteso (2, 3), ottenuto {df.shape}"
assert list(df.columns) == ["id", "nome", "prezzo"]
assert df["id"].tolist() == [1, 2]
print("✅ pandas: OK")

# Test 2: pandas senza comment (deve fallire o dare risultati strani)
print("\n=== Test 2: pandas senza comment (comportamento atteso: dati sporchi) ===")
try:
    df2 = pd.read_csv(mpm_path)
    print(df2)
    print("⚠️  pandas ha letto il file senza comment: le righe # sono trattate come dati")
except Exception as e:
    print(f"pandas ha fallito: {e}")