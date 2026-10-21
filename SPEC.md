
# MPM — Minimal Portable Mapping

**Specifica del Formato, Versione 0.2**

- **Stato:** Bozza (Draft)
- **Data:** 2026-10-20
- **Autore:** Matteo Proietti Micozzi
- **Licenza della specifica:** Creative Commons Attribution 4.0 International (CC BY 4.0). Il testo legale integrale è in `LICENSE-SPEC`.
- **Licenza del codice di riferimento:** MIT. Il testo legale integrale è in `LICENSE`.
- **Brevetti e marchi:** La licenza CC BY 4.0 non concede diritti brevettuali o sui marchi.

---

## 1. Introduzione

**MPM (Minimal Portable Mapping)** è un formato per l'archiviazione e lo scambio di dati tabellari. È progettato per essere:

- **Semplice come CSV:** testuale, leggibile, parsabile senza librerie specializzate.
- **Efficiente come i formati moderni:** tipizzato, comprimibile, con metadati espliciti.
- **Interoperabile con CSV:** il corpo di un file MPM non compresso è un CSV valido secondo RFC 4180. L'header MPM e la semantica dei valori v0.2 richiedono un preprocessamento (es. `comment="#"`) o una conversione esplicita (`mpm to-csv`).

MPM non sostituisce Parquet o Arrow per l'analisi di grandi volumi di dati. Il suo obiettivo è essere il **"CSV 2.0"**: un formato che chiunque può leggere e scrivere, ma che non spreca spazio e non perde informazione sui tipi.

---

## 2. Terminologia

| Termine | Significato |
|---|---|
| **File MPM** | File con estensione `.mpm`, contenente header MPM e corpo CSV. |
| **File MPMZ** | File con estensione `.mpmz`, contenente un file MPM compresso. |
| **Header MPM** | Le righe che iniziano con `#` all'inizio del file. |
| **Corpo CSV** | La parte del file che segue l'header MPM, in formato CSV. |
| **Schema** | La descrizione delle colonne del file, contenuta nell'header. |
| **Blocco** | Un insieme contiguo di righe CSV, unità di compressione in MPMZ. |
| **Implementazione conforme** | Un software che rispetta tutti i requisiti di questa specifica. |

Le parole chiave **DEVE**, **NON DEVE**, **DOVREBBE**, **NON DOVREBBE**, **PUÒ** sono da interpretarsi secondo la **RFC 2119**.

---

## 3. Struttura del File `.mpm`

Un file `.mpm` è composto da due sezioni, con encoding distinti:
 
 1. Header MPM
 2. Corpo CSV

L'**header MPM** (le righe che iniziano con `#`) **DEVE** essere codificato in **UTF-8 senza BOM**.

Il **corpo CSV** **DEVE** essere codificato secondo l'encoding dichiarato in `@meta.encoding`. Il supporto per **UTF-8** è obbligatorio. Altri encoding **POSSONO** essere supportati, ma devono essere dichiarati in `@meta.encoding`.

Un reader **DEVE** rifiutare con un errore chiaro un encoding non supportato o non riconosciuto.

### 3.1 Header MPM

L'header MPM è composto da una o più righe, ognuna delle quali:

- **DEVE** iniziare con il carattere `#` (`U+0023`).
- **DEVE** essere terminata da `\n` (`U+000A`). Il `\r\n` è accettato in lettura ma **NON DEVE** essere prodotto in scrittura.
- **PUÒ** contenere spazi dopo il `#`.

L'header MPM termina alla prima riga che non inizia con `#`. Tale riga è l'inizio del corpo CSV.

### 3.1.1 Riga di versione (obbligatoria)

La prima riga dell'header **DEVE** essere una delle seguenti, in base alla versione del formato.

**Per i file v0.1:**

```text
# MPM v0.1
```

**Per i file v0.2:**

```text
# MPM v0.2
```

Il lettore **DEVE** determinare la versione del formato dalla prima riga dell'header prima di applicare la decodifica dei valori (Sezione 5.3).

Implementazioni conformi **DEVONO** rifiutare file con una versione non supportata, a meno che non sia dichiarata la compatibilità (vedi Sezione 7).

### 3.1.2 Riga di metadati (obbligatoria)

La seconda riga dell'header **DEVE** essere:

```text
# @meta: <oggetto JSON>
```

L'oggetto JSON **DEVE** essere valido secondo la **RFC 8259** e **DEVE** contenere i campi descritti nella Sezione 4.

### 3.1.3 Riga di schema (obbligatoria)

La terza riga dell'header **DEVE** essere:

```text
# @schema: <array JSON>
```

L'array JSON **DEVE** contenere un oggetto per ogni colonna del corpo CSV, nell'ordine in cui le colonne appaiono. I campi sono descritti nella Sezione 5.

### 3.1.4 Righe di estensione (opzionali)

Righe aggiuntive che iniziano con `# @` seguono la stessa sintassi `<chiave>: <valore JSON>`.

Le chiavi non riconosciute **DEVONO** essere ignorate da implementazioni conformi. Questo permette estensioni future senza rompere la compatibilità.

### 3.2 Corpo CSV

Il corpo CSV **DEVE** essere un file CSV valido secondo la **RFC 4180**, con le seguenti precisazioni:

- Il delimitatore **DEVE** essere quello dichiarato in `@meta.delimiter`.
- La prima riga del corpo **DEVE** essere l'header delle colonne (nomi delle colonne).
- Il numero di campi per riga **DEVE** corrispondere al numero di elementi in `@schema`.
- I campi contenenti il delimitatore, il doppio apice, `\n` o `\r` **DEVONO** essere racchiusi tra doppi apici e i doppi apici interni **DEVONO** essere raddoppiati.
- La codifica **DEVE** essere quella dichiarata in `@meta.encoding`. UTF-8 **DEVE** essere supportato. Altri encoding **POSSONO** essere supportati.

### 3.3 Esempio Completo

```text
# MPM v0.2
# @meta: {"delimiter":",","encoding":"utf-8","compression":"none"}
# @schema: [{"name":"id","type":"int","nullable":false},{"name":"nome","type":"str"},{"name":"data","type":"date","format":"YYYY-MM-DD"}]
id,nome,data
1,Mario,2024-01-15
2,Luigi,2024-02-20
3,"Rossi, Anna",2024-03-10
```

---

## 4. Metadati (`@meta`)

L'oggetto JSON in `@meta` **DEVE** contenere i seguenti campi:

| Campo | Tipo | Obbligatorio | Descrizione | Default |
|---|---|:---:|---|:---:|
| `delimiter` | stringa (1 carattere) | Sì | Separatore di campo | — |
| `encoding` | stringa | Sì | Codifica del corpo CSV. UTF-8 è obbligatorio. | — |
| `compression` | stringa | Sì | `none` per `.mpm`, `zstd` per `.mpmz` | — |
| `compression_block` | intero positivo | No | Righe per blocco (solo se compression diverso da `none`) | `10000` |

Campi aggiuntivi **POSSONO** essere presenti e **DEVONO** essere ignorati se non riconosciuti.

> **Nota:** Il campo `version` è stato rimosso. La versione del formato è dichiarata esclusivamente nella prima riga dell'header (`# MPM v0.1` o `# MPM v0.2`).

---

## 5. Schema (`@schema`)

L'array JSON in `@schema` **DEVE** contenere un oggetto per colonna. Ogni oggetto **DEVE** avere:

| Campo | Tipo | Obbligatorio | Descrizione |
|---|---|:---:|---|
| `name` | stringa | Sì | Nome della colonna (univoco nel file) |
| `type` | stringa | Sì | Uno tra: `int`, `float`, `str`, `date`, `datetime`, `bool` |
| `nullable` | booleano | No | Se la colonna può contenere valori vuoti (default: `true`) |
| `format` | stringa | No | Formato per date/datetime (es. `YYYY-MM-DD`) |

### 5.1 Tipi e Validazione

I tipi sono hint, non obblighi. Un'implementazione conforme:

- **DEVE** accettare un file anche se un valore non corrisponde al tipo dichiarato.
- **PUÒ** segnalare l'anomalia in un tool di validazione separato.
- **NON DEVE** rifiutare il file per una discrepanza di tipo.

*Questo principio è ispirato alla Postel's Law: sii rigoroso in ciò che produci, tollerante in ciò che accetti.*

### 5.2 Rappresentazione dei Valori

| Tipo | Formato atteso | Esempio |
|---|---|---|
| `int` | Intero decimale, senza separatori | `42`, `-7` |
| `float` | Decimale con punto come separatore | `3.14`, `-0.001` |
| `str` | Qualsiasi stringa UTF-8 | `ciao` |
| `date` | Secondo `format` (default `YYYY-MM-DD`) | `2024-01-15` |
| `datetime` | ISO 8601 (default `YYYY-MM-DDTHH:MM:SS`) | `2024-01-15T14:30:00` |
| `bool` | `true`/`false` (case-insensitive) | `true`, `FALSE` |

### 5.3 Rappresentazione di null ed Escaping (MPM v0.2)

A partire dalla versione **0.2** del formato MPM testuale, i valori `null` e i caratteri di escape sono rappresentati come segue.

### 5.3.1 Il marcatore `null`

Il valore `null` è rappresentato dalla stringa `\N` (backslash seguito da N maiuscola).

Dopo il parsing CSV, se il campo (indipendentemente dal quoting originale) è esattamente `\N`, il valore è `null`. Pertanto, sia `\N` che `"\N"` producono `null`.

Qualsiasi altro valore, inclusa la stringa vuota `""` (campo CSV vuoto), è un valore non nullo.

### 5.3.2 Escaping dei backslash

Ogni backslash (`\`) presente in un valore non nullo **DEVE** essere codificato come `\\` (doppio backslash) prima della scrittura.

Pertanto:

- La stringa letterale `\N` è codificata come `\\N`.
- La stringa letterale `\` è codificata come `\\`.
- La stringa letterale `\\` è codificata come `\\\\`.

### 5.3.3 Decodifica

Dopo il parsing CSV, il decoder **DEVE** applicare le seguenti regole, in una singola passata:

1. Se il campo (dopo il parsing CSV) è esattamente `\N`, il valore è `null`.
2. Se il campo contiene la sequenza `\\`, questa viene sostituita con un singolo backslash (`\`). La sostituzione **NON DEVE** essere ricorsiva.
3. Un backslash isolato o seguito da un carattere diverso da `\` (eccetto il caso esatto `\N`) costituisce un errore di codifica.

### 5.3.4 Ordine delle operazioni

- **Scrittura:** il writer applica prima l'escaping MPM (sostituzione di `\` con `\\`, e `null` con `\N`), poi il quoting CSV (secondo RFC 4180).
- **Lettura:** il reader applica prima il parsing CSV (secondo RFC 4180), poi la decodifica MPM (secondo Sezione 5.3.3).

### 5.3.5 Gestione degli errori

Un valore che viola le regole della Sezione 5.3.3 è un errore di codifica. Il file è considerato non conforme.

La conformità della codifica è distinta dalla validazione dei tipi: un file può essere conforme alla codifica ma contenere valori che non rispettano lo schema dichiarato.

In tal caso, il file è conforme, ma il tool di validazione (`mpm validate`) segnalerà le anomalie di tipo.

### 5.3.6 Distinzione tra `null` e stringa vuota

Il valore `null` è distinto dalla stringa vuota per qualsiasi tipo di colonna. La stringa vuota è un valore non nullo di tipo `str` (o un valore vuoto per altri tipi, se `nullable` è `true`).

Un valore `null` in una colonna con `nullable: false` è un errore di validazione dello schema, non un errore di decodifica.

Il file resta conforme alla codifica, ma il tool di validazione (`mpm validate`) segnalerà l'anomalia.

---

## 6. Struttura del File `.mpmz`

Un file `.mpmz` è un contenitore binario che incapsula un file `.mpm` compresso.

La struttura è:

1. **Magic:** `"MPMZ"` (4 byte ASCII)
2. **Versione:** 1 byte (`0x01`)
3. **Lunghezza header JSON:** 4 byte big-endian
4. **Header JSON** (UTF-8)
5. **N blocchi compressi**

### 6.1 Header JSON

L'header JSON contiene i metadati del file MPM originale, più i campi specifici della compressione:

- `meta`: identico a `@meta` del file MPM, con `compression: "zstd"`.
- `schema`: identico a `@schema` del file MPM.
- `blocks`: il numero di blocchi compressi.
- `original_size`: la dimensione del file MPM non compresso, in byte.
- `original_version`: la versione del formato testuale MPM (es. `"0.1"` o `"0.2"`).

I writer MPMZ **DEVONO** emettere `original_version` nei nuovi file. I reader MPMZ **DEVONO** interpretare l'assenza di `original_version` come `"0.1"`, per garantire la retrocompatibilità con i contenitori legacy.

La versione del contenitore MPMZ (byte di versione `0x01`) è indipendente dalla versione testuale MPM (`original_version`).

Un file `.mpmz` con versione del contenitore `0x01` può contenere un file `.mpm` di versione 0.1 o 0.2.

### 6.2 Blocchi Compressi

Ogni blocco ha la seguente struttura:

- **Dimensione originale:** 4 byte big-endian
- **Dimensione compressa:** 4 byte big-endian
- **Dati compressi con Zstandard**

**Regole:**

- I blocchi **DEVONO** essere compressi con Zstandard (RFC 8878).
- Ogni blocco **DEVE** contenere al massimo `compression_block` righe CSV.
- L'ultimo blocco **PUÒ** contenere meno righe.
- La concatenazione dei blocchi decompressi **DEVE** produrre esattamente il corpo CSV del file MPM originale (più l'header MPM, che è nell'header JSON).
- La decompressione **DEVE** essere lossless.

### 6.2.1 Checksum Zstandard

- I writer MPMZ **DOVREBBERO** abilitare il checksum nativo Zstandard nei nuovi frame.
- I reader MPMZ **DEVONO** accettare frame Zstandard validi con o senza checksum.
- Quando un checksum è presente, il reader **DEVE** verificarlo.
- Un frame con checksum non valido **DEVE** essere rifiutato.

Il checksum Zstandard protegge dall'alterazione accidentale dei dati durante la trasmissione o l'archiviazione.

**Non** fornisce autenticazione o integrità crittografica: non protegge da attacchi intenzionali.

L'abilitazione del checksum **NON** richiede una nuova versione del contenitore MPMZ (il byte di versione rimane `0x01`).

I file legacy senza checksum restano validi e leggibili.

### 6.3 Retrocompatibilità

Un file `.mpmz` **NON** è leggibile come CSV. Per ottenere il CSV, è necessario decomprimerlo con un'implementazione conforme.

Questo è un compromesso accettato: l'estensione `.mpmz` segnala esplicitamente che serve un tool.

---

## 7. Versionamento

Il formato MPM segue il **Semantic Versioning (SemVer)** con le seguenti regole:

- **Patch** (es. `0.1.1`): correzioni di errori nella specifica, nessun cambiamento al formato.
- **Minor** (es. `0.2.0`): aggiunta di campi opzionali o estensioni retrocompatibili. Un file 0.1 **DEVE** essere leggibile da un'implementazione 0.2.
- **Major** (es. `1.0.0`): cambiamenti che rompono la compatibilità. Un file 1.0 **NON DEVE** essere letto da un'implementazione 0.x senza conversione esplicita.

Un'implementazione conforme **DEVE** dichiarare la versione massima supportata.
Gli obblighi di retrocompatibilità in lettura si applicano ai profili **Reader** (MPM Text Reader e MPMZ Reader), non ai profili **Writer** (MPM Text Writer e MPMZ Writer). Un Writer può generare file in una versione supportata senza essere obbligato a implementare la lettura di versioni precedenti.
Se incontra un file con versione maggiore, **DEVE** rifiutarlo con un messaggio chiaro, a meno che non sia in modalità tollerante (es. `--allow-newer`).

---

## 8. Requisiti per le Implementazioni Conformi

MPM definisce quattro profili di conformità indipendenti e combinabili. Un'implementazione può dichiarare conformità a uno o più profili, in base alle funzionalità che supporta.

### 8.1 Profili di conformità

**MPM Text Reader**
- Legge file `.mpm` delle versioni dichiarate come supportate.
- Interpreta header, metadati, schema e corpo CSV.
- Applica la decodifica appropriata alla versione (es. escaping per v0.2).
- Rifiuta codifiche malformate e versioni non supportate.
- Supporta UTF-8 per il corpo. Altri encoding possono essere supportati, ma devono essere dichiarati.
- Ignora le estensioni sconosciute secondo la specifica (Sezione 3.1.4).

**MPM Text Writer**
- Genera file `.mpm` conformi alle versioni dichiarate.
- Produce header, metadati, schema e corpo CSV validi.
- Applica correttamente escaping e quoting.
- Non deve implementare un reader.

**MPMZ Reader**
- Legge contenitori `.mpmz` supportati.
- Verifica la struttura del contenitore e i frame Zstandard.
- Verifica i checksum quando presenti.
- Applica controlli di sicurezza e ricostruisce il contenuto MPM.
- Ricostruisce correttamente il contenuto testuale per le versioni MPM dichiarate come supportate.
- Non è obbligato a esporre un'interfaccia separata di lettura `.mpm`.
- La versione del contenitore MPMZ (byte `0x01`) è indipendente dalla versione testuale MPM (`original_version`).

**MPMZ Writer**
- Genera contenitori `.mpmz` validi.
- Scrive `original_version` secondo la specifica.
- Rispetta le regole di compressione e struttura dei blocchi.
- DOVREBBE abilitare il checksum Zstandard, senza renderlo obbligatorio.
- Il contenuto testuale all'interno del contenitore **DEVE** rispettare le regole della versione MPM dichiarata in `original_version`.
- Non deve implementare un reader.

### 8.2 Dichiarazione di conformità

Un'implementazione che dichiara conformità **DEVE** indicare:
- Profili supportati.
- Versioni testuali MPM supportate.
- Eventuale supporto del contenitore MPMZ.
- Limitazioni documentate e limiti di risorse rilevanti.

La conformità a un profilo non implica conformità agli altri.
Gli obblighi di retrocompatibilità in lettura previsti dalla *Sezione 7* si applicano ai profili Reader. Un'implementazione che dichiara conformità a **MPM Text Reader** o **MPMZ Reader** per la versione `0.2` **DEVE** essere in grado di leggere i file `0.1`. I profili Writer non sono soggetti a questo obbligo.

### 8.3 Conversione CSV

La conversione tra MPM e CSV è una funzionalità opzionale. Non è obbligatoria per ottenere la conformità ai profili Reader o Writer.

La conversione MPM → CSV può perdere la distinzione tra `null` e stringa vuota, a seconda del valore scelto per `null_value`. Non si deve promettere una conversione lossless quando esistono collisioni.

---

## 9. Suite di Conformità

La suite di conformità è un insieme di file di test che ogni implementazione **DEVE** superare, limitatamente ai profili e alle versioni dichiarate.

### 9.1 Organizzazione dei test

- Ogni implementazione **DEVE** superare i test applicabili ai profili e alle versioni dichiarate.
- Un'implementazione NON È TENUTA a superare i test relativi a profili non dichiarati.
- Le fixture esistenti rimangono nella struttura attuale (`conformance/valid/`, `conformance/invalid/`, `conformance/roundtrip/`, `conformance/edge_cases/`).
- L'associazione tra fixture e profili sarà resa esplicita in un successivo task.
- I test **DEVONO** avere risultati attesi verificabili indipendentemente dall'implementazione Python.

### 9.2 Struttura delle directory

* `conformance/valid/` per i file `.mpm` validi (committati)
* `conformance/invalid/` per i file non validi (committati)
* `conformance/roundtrip/` per le coppie input/output delle conversioni lossless
* `conformance/edge_cases/` per i casi limite (committati)
* `conformance/expected/` per gli output attesi
* `conformance/generate_mpmz.py` per lo script che genera i `.mpmz` dai `.mpm`

> **Regola:** I file `.mpmz` non sono committati. Sono generati al volo dallo script `generate_mpmz.py` a partire dai `.mpm` corrispondenti.

### 9.3 Esempi di casi di test

La tabella seguente è illustrativa. L'elenco completo e aggiornato dei file di test è nella directory `conformance/`. In caso di discrepanza, la directory `conformance/` è la fonte autorevole.

| ID | Categoria | Descrizione |
| :--- | :--- | :--- |
| `valid_001` | `valid` | File MPM minimo con una colonna `str` |
| `valid_002` | `valid` | File MPM con tutti i tipi supportati |
| `valid_003` | `valid` | File MPM multi-blocco (per testare `.mpmz` con 3 blocchi) |
| `valid_004` | `valid` | File MPM con riga di estensione non riconosciuta |
| `invalid_001` | `invalid` | Header MPM mancante |
| `invalid_002` | `invalid` | `@meta` non è JSON valido |
| `invalid_003` | `invalid` | Numero di colonne nello schema diverso dal corpo |
| `invalid_004` | `invalid` | Magic number errato in `.mpmz` |
| `roundtrip_001` | `roundtrip` | CSV in MPM in CSV (identico all'originale) |
| `roundtrip_002` | `roundtrip` | MPM in MPMZ in MPM (identico all'originale) |
| `roundtrip_003` | `roundtrip` | MPM in CSV in MPM (identico all'originale) |
| `edge_001` | `edge_cases` | Campo contenente `#` all'inizio |
| `edge_002` | `edge_cases` | Campo contenente `\n` e doppio apice |
| `edge_003` | `edge_cases` | File vuoto (solo header, nessuna riga) |
| `edge_004` | `edge_cases` | Encoding `latin-1` |

La suite **DEVE** essere pubblica e versionata insieme alla specifica.

### Esempi di casi di test

| ID | Categoria | Descrizione |
|---|---|---|
| `valid_001` | `valid` | File MPM minimo con una colonna `str` |
| `valid_002` | `valid` | File MPM con tutti i tipi supportati |
| `valid_003` | `valid` | File MPM multi-blocco (per testare `.mpmz` con 3 blocchi) |
| `valid_004` | `valid` | File MPM con riga di estensione non riconosciuta |
| `invalid_001` | `invalid` | Header MPM mancante |
| `invalid_002` | `invalid` | `@meta` non è JSON valido |
| `invalid_003` | `invalid` | Numero di colonne nello schema diverso dal corpo |
| `invalid_004` | `invalid` | Magic number errato in `.mpmz` |
| `roundtrip_001` | `roundtrip` | CSV in MPM in CSV (identico all'originale) |
| `roundtrip_002` | `roundtrip` | MPM in MPMZ in MPM (identico all'originale) |
| `roundtrip_003` | `roundtrip` | MPM in CSV in MPM (identico all'originale) |
| `edge_001` | `edge_cases` | Campo contenente `#` all'inizio |
| `edge_002` | `edge_cases` | Campo contenente `\n` e doppio apice |
| `edge_003` | `edge_cases` | File vuoto (solo header, nessuna riga) |
| `edge_004` | `edge_cases` | Encoding `latin-1` |

La suite **DEVE** essere pubblica e versionata insieme alla specifica.

---

## 10. Sicurezza e Robustezza

Le implementazioni conformi **DEVONO**:

- Rifiutare file `.mpmz` con `original_size` o `blocks` incoerenti (es. `blocks` negativo, dimensioni che non tornano).
- Limitare la dimensione massima di un blocco decompresso a un valore configurabile per prevenire attacchi di decompressione (zip bomb). Il valore specifico è una scelta dell'implementazione (la reference implementation usa 100 MB).
- Non eseguire codice contenuto nei metadati (i JSON sono dati, non codice).
- Gestire correttamente input malformati senza crash (*fuzzing* raccomandato).

**Nota sui limiti di sicurezza:** i limiti specifici utilizzati dalla reference implementation (es. dimensione massima del file `.mpmz`, dimensione massima dell'header JSON, numero massimo di blocchi, dimensione massima totale decompressa) sono scelte locali per proteggere l'ambiente di esecuzione.

Non sono vincoli normativi del formato.

Altre implementazioni **POSSONO** adottare limiti diversi, purché documentino il comportamento in caso di superamento.

---

## 11. Estensioni Future (Non Normative)

Questa sezione elenca idee per versioni future, non parte della v0.2:

- **Compressione colonnare opzionale:** un flag in `@meta` che indica che il corpo è organizzato per colonne, non per righe.
- **Indice dei blocchi:** un blocco opzionale in testa a `.mpmz` con offset per *random access* veloce.
- **Crittografia opzionale:** un wrapper per file cifrati, con metadati separati.
- **Tipi aggiuntivi:** `uuid`, `decimal`, `json`, `array`.

---

## 12. Riferimenti

- **RFC 2119** — *Keywords for use in RFCs to Indicate Requirement Levels*
- **RFC 4180** — *Common Format and MIME Type for Comma-Separated Values (CSV) Files*
- **RFC 8259** — *The JavaScript Object Notation (JSON) Data Interchange Format*
- **RFC 8878** — *Zstandard Compression and the 'application/zstd' Media Type*
- **SemVer 2.0.0** — *Semantic Versioning*
