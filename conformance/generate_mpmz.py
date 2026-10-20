#!/usr/bin/env python3
"""Genera i file .mpmz di test a partire dai .mpm corrispondenti."""

import subprocess
import sys
from pathlib import Path

CONFORMANCE_DIR = Path(__file__).parent
MPM_FILES = list(CONFORMANCE_DIR.glob("valid/*.mpm")) + list(
    CONFORMANCE_DIR.glob("edge_cases/*.mpm")
)

for mpm_file in MPM_FILES:
    mpmz_file = mpm_file.with_suffix(".mpmz")
    print(f"Generating {mpmz_file}...")
    subprocess.run(
        [sys.executable, "-m", "mpm", "compress", str(mpm_file), str(mpmz_file)],
        check=True,
    )
print(f"Done. Generated {len(MPM_FILES)} .mpmz files.")