# Changelog

Tutte le modifiche importanti a questo progetto saranno documentate in questo file.

Il formato è basato su [Keep a Changelog](https://keepachangelog.com/it/1.1.0/),
e questo progetto aderisce al [Semantic Versioning](https://semver.org/lang/it/).

## [0.2.0] - 2026-10-21

### Modifiche al formato
- Aggiunto il supporto per il valore `null` tramite il marcatore `\N` (Sezione 5.3).
- Aggiunto l'escaping dei backslash (`\\`) per i valori non nulli.
- Introdotto il campo `original_version` nei contenitori MPMZ per preservare la versione del formato testuale.
- Aggiunto il checksum nativo Zstandard per i blocchi MPMZ (Sezione 6.2.1).
- Introdotti i profili di conformità (MPM Text Reader, MPM Text Writer, MPMZ Reader, MPMZ Writer) nella Sezione 8.
- Chiarita la distinzione tra encoding dell'header (UTF-8) e del corpo (secondo `@meta.encoding`) nella Sezione 3.

### Correzioni di bug
- Corretto `write_mpm` per scrivere l'header in UTF-8 e il corpo con l'encoding dichiarato.
- Corretto `decompress_mpmz` per preservare `original_version` e ricostruire correttamente l'header MPM.
- Corretto il controllo della versione in `write_mpm` per rifiutare versioni non supportate.
- Corretto il controllo su `None` in v0.1 per sollevare `MPMEncodingError`.

### Miglioramenti di sicurezza e robustezza
- Aggiunti limiti di sicurezza per la decompressione MPMZ: dimensione massima del file (256 MiB), header JSON (1 MiB), numero di blocchi (10.000), dimensione totale decompressa (256 MiB).
- Aggiunta la verifica del checksum Zstandard per i blocchi MPMZ.
- Introdotta la scrittura atomica in `write_mpm` per evitare file parziali in caso di errore.

### Miglioramenti documentali
- Aggiornata `SPEC.md` alla versione 0.2.
- Aggiunta la licenza CC BY 4.0 per la specifica (`LICENSE-SPEC`).
- Aggiornata la sezione "Interoperabilità" del README con informazioni accurate sui limiti di compatibilità CSV.
- Aggiunta la nota sull'autore (Matteo Proietti Micozzi).

### Test
- Aggiunti test per null, escaping, versionamento, checksum, sicurezza, encoding e profili di conformità.
- La suite include 198 test, tutti superati.

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