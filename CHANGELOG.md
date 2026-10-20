# Changelog

Tutte le modifiche importanti a questo progetto saranno documentate in questo file.

Il formato è basato su [Keep a Changelog](https://keepachangelog.com/it/1.1.0/),
e questo progetto aderisce al [Semantic Versioning](https://semver.org/lang/it/).

## [0.1.0] - 2026-10-20

### Aggiunto
- Specifica formale del formato MPM v0.1 (`SPEC.md`).
- Implementazione di riferimento in Python (formato `.mpm` e `.mpmz`).
- Compressione Zstandard a blocchi per i file `.mpmz`.
- Inferenza e validazione dello schema (tipi: int, float, str, date, datetime, bool).
- CLI completa con comandi: `convert`, `to-csv`, `infer`, `compress`, `decompress`, `info`, `validate`.
- Suite di conformità con 15 casi di test (validi, invalidi, roundtrip, edge cases).
- 92 test unitari, di integrazione e di conformità.
- Benchmark comparativo (CSV vs MPM vs MPMZ vs Parquet).

### Note
- MPMZ è il 74% più piccolo di CSV su dataset di test realistici.
- I file `.mpm` non compressi sono retrocompatibili con il formato CSV (leggibili con `comment="#"`).