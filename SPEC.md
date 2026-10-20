# MPM — Minimal Portable Mapping

**Specifica del Formato, Versione 0.1**



* **Stato:** Bozza (Draft)

* **Data:** 2026-10-20

* **Autore:** MPM Project

* **Licenza della specifica:** CC BY 4.0

* **Licenza del codice di riferimento:** MIT



---



## 1. Introduzione



**MPM (Minimal Portable Mapping)** è un formato per l'archiviazione e lo scambio di dati tabellari. È progettato per essere:



* **Semplice come CSV:** testuale, leggibile, parsabile senza librerie specializzate.

* **Efficiente come i formati moderni:** tipizzato, comprimibile, con metadati espliciti.

* **Retrocompatibile:** un file MPM non compresso è un CSV valido con righe di commento in testa.



MPM non sostituisce Parquet o Arrow per l'analisi di grandi volumi di dati. Il suo obiettivo è essere il *"CSV 2.0"*: un formato che chiunque può leggere e scrivere, ma che non spreca spazio e non perde informazione sui tipi.



---



## 2. Terminologia



| Termine | Significato |
| :--- | :--- |
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



Un file `.mpm` è un file di testo codificato in UTF-8 (senza BOM) composto da due sezioni:

1. Header MPM

2. Corpo CSV



### 3.1 Header MPM



L'header MPM è composto da una o più righe, ognuna delle quali:

* **DEVE** iniziare con il carattere `#` (`U+0023`).

* **DEVE** essere terminata da `\n` (`U+000A`). Il `\r\n` è accettato in lettura ma **NON DEVE** essere prodotto in scrittura.

* **PUÒ** contenere spazi dopo il `#`.



L'header MPM termina alla prima riga che non inizia con `#`. Tale riga è l'inizio del corpo CSV.



#### 3.1.1 Riga di versione (obbligatoria)

La prima riga dell'header **DEVE** essere:

```text

# MPM v0.1

```

dove `0.1` è la versione del formato. Implementazioni conformi **DEVONO** rifiutare file con una versione maggiore di quella supportata, a meno che non sia dichiarata la compatibilità (vedi *Sezione 7*).



#### 3.1.2 Riga di metadati (obbligatoria)

La seconda riga dell'header **DEVE** essere:

```text

# @meta: <oggetto JSON>

```

L'oggetto JSON **DEVE** essere valido secondo la **RFC 8259** e **DEVE** contenere i campi descritti nella *Sezione 4*.



#### 3.1.3 Riga di schema (obbligatoria)

La terza riga dell'header **DEVE** essere:

```text

# @schema: <array JSON>

```

L'array JSON **DEVE** contenere un oggetto per ogni colonna del corpo CSV, nell'ordine in cui le colonne appaiono. I campi sono descritti nella *Sezione 5*.



#### 3.1.4 Righe di estensione (opzionali)

Righe aggiuntive che iniziano con `# @` seguono la stessa sintassi `<chiave>: <valore JSON>`. Le chiavi non riconosciute **DEVONO** essere ignorate da implementazioni conformi. Questo permette estensioni future senza rompere la compatibilità.



### 3.2 Corpo CSV



Il corpo CSV **DEVE** essere un file CSV valido secondo la **RFC 4180**, con le seguenti precisazioni:

* Il delimitatore **DEVE** essere quello dichiarato in `@meta.delimiter`.

* La prima riga del corpo **DEVE** essere l'header delle colonne (nomi delle colonne).

* Il numero di campi per riga **DEVE** corrispondere al numero di elementi in `@schema`.

* I campi contenenti il delimitatore, il doppio apice, `\n` o `\r` **DEVONO** essere racchiusi tra doppi apici e i doppi apici interni **DEVONO** essere raddoppiati.

* La codifica **DEVE** essere quella dichiarata in `@meta.encoding`.



### 3.3 Esempio Completo



```text

# MPM v0.1

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

| :--- | :--- | :---: | :--- | :---: |

| `delimiter` | stringa (1 carattere) | Sì | Separatore di campo | — |

| `encoding` | stringa | Sì | Codifica del testo | — |

| `compression` | stringa | Sì | `none` per `.mpm`, `zstd` per `.mpmz` | — |

| `compression_block` | intero positivo | No | Righe per blocco (solo se compression diverso da `none`) | `10000` |



Campi aggiuntivi **POSSONO** essere presenti e **DEVONO** essere ignorati se non riconosciuti.



> **Nota:** Il campo `version` è stato rimosso. La versione del formato è dichiarata esclusivamente nella prima riga dell'header (`# MPM v0.1`).



---



## 5. Schema (`@schema`)



L'array JSON in `@schema` **DEVE** contenere un oggetto per colonna. Ogni oggetto **DEVE** avere:



| Campo | Tipo | Obbligatorio | Descrizione |

| :--- | :--- | :---: | :--- |

| `name` | stringa | Sì | Nome della colonna (univoco nel file) |

| `type` | stringa | Sì | Uno tra: `int`, `float`, `str`, `date`, `datetime`, `bool` |

| `nullable` | booleano | No | Se la colonna può contenere valori vuoti (default: `true`) |

| `format` | stringa | No | Formato per date/datetime (es. `YYYY-MM-DD`) |



### 5.1 Tipi e Validazione



I tipi sono hint, non obblighi. Un'implementazione conforme:

* **DEVE** accettare un file anche se un valore non corrisponde al tipo dichiarato.

* **PUÒ** segnalare l'anomalia in un tool di validazione separato.

* **NON DEVE** rifiutare il file per una discrepanza di tipo.



*Questo principio è ispirato alla Postel's Law: sii rigoroso in ciò che produci, tollerante in ciò che accetti.*



### 5.2 Rappresentazione dei Valori



| Tipo | Formato atteso | Esempio |

| :--- | :--- | :--- |

| `int` | Intero decimale, senza separatori | `42`, `-7` |

| `float` | Decimale con punto come separatore | `3.14`, `-0.001` |

| `str` | Qualsiasi stringa UTF-8 | `ciao` |

| `date` | Secondo `format` (default `YYYY-MM-DD`) | `2024-01-15` |

| `datetime` | ISO 8601 (default `YYYY-MM-DDTHH:MM:SS`) | `2024-01-15T14:30:00` |

| `bool` | `true`/`false` (case-insensitive) | `true`, `FALSE` |



---



## 6. Struttura del File `.mpmz`



Un file `.mpmz` è un contenitore binario che incapsula un file `.mpm` compresso. La struttura è:



1. **Magic:** `"MPMZ"` (4 byte ASCII)

2. **Versione:** 1 byte (`0x01`)

3. **Lunghezza header JSON:** 4 byte big-endian

4. **Header JSON** (UTF-8)

5. **N blocchi compressi**



### 6.1 Header JSON



L'header JSON contiene i metadati del file MPM originale, più i campi specifici della compressione:

* `meta`: identico a `@meta` del file MPM, con `compression: "zstd"`

* `schema`: identico a `@schema` del file MPM

* `blocks`: il numero di blocchi compressi

* `original_size`: la dimensione del file MPM non compresso, in byte



### 6.2 Blocchi Compressi



Ogni blocco ha la seguente struttura:

* **Dimensione originale:** 4 byte big-endian

* **Dimensione compressa:** 4 byte big-endian

* **Dati compressi con Zstandard**



**Regole:**

* I blocchi **DEVONO** essere compressi con Zstandard (RFC 8878).

* Ogni blocco **DEVE** contenere al massimo `compression_block` righe CSV.

* L'ultimo blocco **PUÒ** contenere meno righe.

* La concatenazione dei blocchi decompressi **DEVE** produrre esattamente il corpo CSV del file MPM originale (più l'header MPM, che è nell'header JSON).

* La decompressione **DEVE** essere lossless.



### 6.3 Retrocompatibilità



Un file `.mpmz` **NON** è leggibile come CSV. Per ottenere il CSV, è necessario decomprimerlo con un'implementazione conforme. Questo è un compromesso accettato: l'estensione `.mpmz` segnala esplicitamente che serve un tool.



---



## 7. Versionamento



Il formato MPM segue il **Semantic Versioning (SemVer)** con le seguenti regole:



* **Patch** (es. `0.1.1`): correzioni di errori nella specifica, nessun cambiamento al formato.

* **Minor** (es. `0.2.0`): aggiunta di campi opzionali o estensioni retrocompatibili. Un file `0.1` **DEVE** essere leggibile da un'implementazione `0.2`.

* **Major** (es. `1.0.0`): cambiamenti che rompono la compatibilità. Un file `1.0` **NON DEVE** essere letto da un'implementazione `0.x` senza conversione esplicita.



Un'implementazione conforme **DEVE** dichiarare la versione massima supportata. Se incontra un file con versione maggiore, **DEVE** rifiutarlo con un messaggio chiaro, a meno che non sia in modalità tollerante (es. `--allow-newer`).



---



## 8. Requisiti per le Implementazioni Conformi



Un'implementazione conforme **DEVE**:

1. Leggere correttamente file `.mpm` validi secondo la *Sezione 3*.

2. Leggere correttamente file `.mpmz` validi secondo la *Sezione 6*.

3. Convertire `.mpm` e `.mpmz` senza perdita di dati.

4. Convertire `.mpm` e CSV (rimuovendo o aggiungendo l'header MPM).

5. Rifiutare file con header MPM malformato, con un messaggio di errore che indichi la riga problematica.

6. Ignorare le righe di estensione non riconosciute (*Sezione 3.1.4*).

7. Superare la suite di conformità (vedi *Sezione 9*).



Un'implementazione conforme **PUÒ**:

* Offrire un tool di inferenza dello schema (`mpm infer`) che genera uno schema da revisionare.

* Offrire un tool di validazione (`mpm validate`) che segnala discrepanze di tipo.

* Supportare formati di compressione aggiuntivi (es. `gzip`) come estensione.



---



## 9. Suite di Conformità



La suite di conformità è un insieme di file di test che ogni implementazione **DEVE** superare. I file sono organizzati in:



* `conformance/valid/` per i file `.mpm` validi (committati)

* `conformance/invalid/` per i file non validi (committati)

* `conformance/roundtrip/` per le coppie input/output delle conversioni lossless

* `conformance/edge_cases/` per i casi limite (committati)

* `conformance/expected/` per gli output attesi

* `conformance/generate_mpmz.py` per lo script che genera i `.mpmz` dai `.mpm`



> **Regola:** I file `.mpmz` non sono committati. Sono generati al volo dallo script `generate_mpmz.py` a partire dai `.mpm` corrispondenti.



### Esempi di casi di test



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



---



## 10. Sicurezza e Robustezza



Le implementazioni conformi **DEVONO**:

* Rifiutare file `.mpmz` con `original_size` o `blocks` incoerenti (es. `blocks` negativo, dimensioni che non tornano).

* Limitare la dimensione massima di un blocco decompresso a un valore configurabile (default: 100 MB) per prevenire attacchi di decompressione (zip bomb).

* Non eseguire codice contenuto nei metadati (i JSON sono dati, non codice).

* Gestire correttamente input malformati senza crash (*fuzzing* raccomandato).



---



## 11. Estensioni Future (Non Normative)



Questa sezione elenca idee per versioni future, non parte della v0.1:

* **Compressione colonnare opzionale:** un flag in `@meta` che indica che il corpo è organizzato per colonne, non per righe.

* **Indice dei blocchi:** un blocco opzionale in testa a `.mpmz` con offset per *random access* veloce.

* **Crittografia opzionale:** un wrapper per file cifrati, con metadati separati.

* **Tipi aggiuntivi:** `uuid`, `decimal`, `json`, `array`.



---



## 12. Riferimenti



* **RFC 2119** — *Keywords for use in RFCs to Indicate Requirement Levels*

* **RFC 4180** — *Common Format and MIME Type for Comma-Separated Values (CSV) Files*

* **RFC 8259** — *The JavaScript Object Notation (JSON) Data Interchange Format*

* **RFC 8878** — *Zstandard Compression and the 'application/zstd' Media Type*

* **SemVer 2.0.0** — *Semantic Versioning*