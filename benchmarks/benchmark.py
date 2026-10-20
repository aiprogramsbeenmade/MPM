"""Benchmark affidabile: CSV vs MPM vs MPMZ vs Parquet."""

import gc
import random
import statistics
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from mpm.compress import mpm_to_mpmz, mpmz_to_mpm
from mpm.csv_io import csv_to_mpm, mpm_to_csv

REPEATS = 5
N_ROWS = 500_000


def generate_dataset(path: Path, n_rows: int) -> None:
    """Genera un dataset realistico con un mix di tipi."""
    if path.exists():
        print(f"Dataset già esistente: {path} ({path.stat().st_size:,} byte)")
        return
    print(f"Generazione dataset ({n_rows:,} righe)...")
    random.seed(42)
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write("id,nome,prezzo,data,attivo,categoria\n")
        for i in range(n_rows):
            nome = f"utente_{i % 1000}"
            prezzo = round(random.uniform(1.0, 1000.0), 2)
            data = (date(2024, 1, 1) + timedelta(days=i % 365)).isoformat()
            attivo = random.choice(["true", "false"])
            categoria = random.choice(["A", "B", "C", "D"])
            f.write(f"{i},{nome},{prezzo},{data},{attivo},{categoria}\n")
    print(f"Dataset generato: {path.stat().st_size:,} byte")


def measure(func, *args, repeats: int = REPEATS, **kwargs) -> tuple[float, float, float]:
    """Esegue func `repeats` volte e restituisce (min, mediana, max) in secondi."""
    func(*args, **kwargs)  # riscaldamento

    times: list[float] = []
    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        for _ in range(repeats):
            start = time.perf_counter_ns()
            func(*args, **kwargs)
            elapsed = (time.perf_counter_ns() - start) / 1e9
            times.append(elapsed)
    finally:
        if gc_was_enabled:
            gc.enable()

    return min(times), statistics.median(times), max(times)


def main():
    base = Path("benchmarks/data")
    base.mkdir(parents=True, exist_ok=True)
    csv_path = base / f"dataset_{N_ROWS}.csv"
    mpm_path = base / f"dataset_{N_ROWS}.mpm"
    mpmz_path = base / f"dataset_{N_ROWS}.mpmz"
    mpm_out_path = base / f"dataset_{N_ROWS}_out.mpm"
    csv_out_path = base / f"dataset_{N_ROWS}_out.csv"
    parquet_path = base / f"dataset_{N_ROWS}.parquet"

    generate_dataset(csv_path, N_ROWS)

    print(f"\nBenchmark con {N_ROWS:,} righe, {REPEATS} ripetizioni per misura.")
    print("I tempi sono in secondi: min / mediana / max\n")

    results: dict[str, tuple[float, float, float]] = {}

    print("Misura: CSV → MPM")
    results["CSV → MPM"] = measure(csv_to_mpm, csv_path, mpm_path)

    print("Misura: MPM → MPMZ")
    results["MPM → MPMZ"] = measure(mpm_to_mpmz, mpm_path, mpmz_path)

    print("Misura: MPMZ → MPM")
    results["MPMZ → MPM"] = measure(mpmz_to_mpm, mpmz_path, mpm_out_path)

    print("Misura: MPM → CSV")
    results["MPM → CSV"] = measure(mpm_to_csv, mpm_out_path, csv_out_path)

    print("Misura: CSV → Parquet")
    df = pd.read_csv(csv_path)
    results["CSV → Parquet"] = measure(df.to_parquet, parquet_path)

    sizes = {
        "CSV": csv_path.stat().st_size,
        "MPM": mpm_path.stat().st_size,
        "MPMZ": mpmz_path.stat().st_size,
        "Parquet": parquet_path.stat().st_size,
    }

    print("\n=== Dimensioni ===")
    for name, size in sizes.items():
        print(f"{name:12s} {size:>15,} byte  ({size / 1024 / 1024:.2f} MB)")

    print("\n=== Tempi (min / mediana / max, in secondi) ===")
    for label, (t_min, t_med, t_max) in results.items():
        print(f"{label:16s} {t_min:.3f} / {t_med:.3f} / {t_max:.3f}")

    print("\n=== Risparmio vs CSV ===")
    csv_size = sizes["CSV"]
    for name in ("MPM", "MPMZ", "Parquet"):
        ratio = 100 * (1 - sizes[name] / csv_size)
        print(f"{name:12s} {ratio:>6.1f}% più piccolo")

    original = csv_path.read_text(encoding="utf-8").rstrip("\n")
    reconstructed = csv_out_path.read_text(encoding="utf-8").rstrip("\n")
    if original == reconstructed:
        print("\n✅ Roundtrip CSV → MPM → MPMZ → MPM → CSV: identico")
    else:
        print("\n❌ Roundtrip fallito: i file differiscono")


if __name__ == "__main__":
    main()