<p align="center">

  <img src="assets/logo.png" alt="MPM Logo" width="150">

</p>



# MPM — Minimal Portable Mapping



> **Il "CSV 2.0":** un formato tabellare semplice come CSV, ma tipizzato, comprimibile e retrocompatibile.



<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square&logo=opensourceinitiative&logoColor=white" alt="License MIT"></a>
  <a href="LICENSE-SPEC"><img src="https://img.shields.io/badge/License-CC%20BY%204.0-lightgrey.svg?style=flat-square&logo=creativecommons&logoColor=white" alt="License CC BY 4.0"></a>
  <img src="https://img.shields.io/badge/python-3.9%2B-blue.svg?style=flat-square&logo=python&logoColor=white" alt="Python Version">
  <img src="https://img.shields.io/badge/tests-198%20passed-brightgreen.svg?style=flat-square&logo=pytest&logoColor=white" alt="Tests">
  <img src="https://img.shields.io/badge/version-0.2.0-orange.svg?style=flat-square&logo=semver&logoColor=white" alt="Version">
  <img src="https://img.shields.io/badge/status-prototype-yellow.svg?style=flat-square&logo=statuspage&logoColor=white" alt="Status">
</p>



---



MPM è un formato per l'archiviazione e lo scambio di dati tabellari. È progettato per risolvere i problemi di CSV senza la complessità di Parquet:



* **Semplice come CSV:** testuale, leggibile, parsabile senza librerie specializzate.

* **Efficiente come i formati moderni:** tipizzato, comprimibile con Zstandard, con metadati espliciti.

* **Retrocompatibile:** un file `.mpm` non compresso è un CSV valido con righe di commento in testa.



---



## Perché MPM?



**CSV** è universale ma inefficiente: non ha tipi, non ha compressione, non ha metadati.  

**Parquet** è potente ma complesso: richiede librerie specializzate e non è leggibile da un editor di testo.



MPM sta nel mezzo:



| Formato | Semplicità | Efficienza | Tipizzazione | Compressione |
| :--- | :---: | :---: | :---: | :---: |
| **CSV** | Alta | Bassa | No | No |
| **Parquet** | Bassa | Alta | Sì | Sì |
| **MPM** | Alta | Media-alta | Sì (hint) | Opzionale |


---



## Installazione



```bash

pip install -e ".[dev]"

```



---



## Uso Rapido



### Genera uno schema da un CSV

```bash

mpm infer dati.csv -o schema.json

```



### Converti un CSV in MPM

```bash

mpm convert dati.csv dati.mpm

```



### Comprimi in MPMZ

```bash

mpm compress dati.mpm dati.mpmz

```



### Mostra informazioni

```bash

mpm info dati.mpmz

```



### Torna a CSV

```bash

mpm to-csv dati.mpmz dati_out.csv

```



---



## Comandi Disponibili



| Comando | Descrizione |
| :--- | :--- |
| `mpm convert` | Converte un CSV in MPM (con schema inferito o esplicito) |
| `mpm to-csv` | Converte un MPM in CSV |
| `mpm infer` | Genera uno schema JSON da un CSV |
| `mpm compress` | Comprime un MPM in MPMZ |
| `mpm decompress` | Decomprime un MPMZ in MPM |
| `mpm info` | Mostra metadati e schema di un file |
| `mpm validate` | Valida i dati contro lo schema |


---



## Formato



Un file `.mpm` è un file di testo con tre righe di header seguite da CSV puro:



```text

# MPM v0.1

# @meta: {"delimiter":",","encoding":"utf-8","compression":"none"}

# @schema: [{"name":"id","type":"int"},{"name":"nome","type":"str"}]

id,nome

1,Mario

2,Luigi

```



### Nota su `null` ed escaping (v0.2)



A partire dalla versione **0.2**, MPM supporta la distinzione tra valore nullo e stringa vuota:

* Il valore nullo è rappresentato dal marcatore `\N` (non quotato).

* Ogni backslash (`\`) presente nei dati viene codificato come `\\` per evitare ambiguità.



#### Esempio

```text

# MPM v0.2

# @meta: {"delimiter":",","encoding":"utf-8","compression":"none"}

# @schema: [{"name":"id","type":"int","nullable":false},{"name":"nome","type":"str","nullable":true}]

id,nome

1,Mario

2,\N

3,"\\N"

```



> **Nota:** La riga `3,"\\N"` rappresenta la stringa letterale `\N` (non un valore nullo). Per i dettagli completi, vedi la **Sezione 5.3 di SPEC.md**.



Un file `.mpmz` è lo stesso contenuto compresso con **Zstandard** a blocchi.



La specifica completa è disponibile in `SPEC.md`.



---



## Interoperabilità



Un file `.mpm` non compresso è composto da due parti:

1. **Header MPM** (righe che iniziano con `#`), contenente metadati e schema.

2. **Corpo CSV** (secondo RFC 4180), contenente i dati veri e propri.



Il corpo è sintatticamente un CSV valido. Tuttavia, il file completo non è automaticamente interpretabile come una normale tabella CSV da qualsiasi applicazione, per tre motivi:

* **Header MPM:** le righe `#` non sono dati. I tool che non supportano i commenti le leggeranno come dati, producendo risultati errati.

* **Semantica dei valori:** un file MPM v0.2 può contenere `\N` per rappresentare `null` e backslash raddoppiati (`\\`) per rappresentare backslash letterali. Un lettore CSV generico non interpreta automaticamente queste sequenze secondo la specifica MPM.

* **Tipi e metadati:** lo schema dichiara tipi e `nullability` che un lettore CSV generico ignora.



### pandas

`pandas` supporta i commenti con `comment="#"`:

```python

import pandas as pd



df = pd.read_csv("dati.mpm", comment="#")

```

> **Attenzione:** Questa soluzione funziona per i file MPM v0.1 e per i file v0.2 che non contengono `null` o escaping. Se il file v0.2 contiene `\N` o backslash, `pandas` li leggerà come stringhe letterali, non come `null` o backslash. Inoltre, `comment="#"` è una soluzione specifica di `pandas`, non universale.



### Excel / LibreOffice Calc

Excel e LibreOffice non supportano i commenti nei CSV. Il percorso consigliato è convertire prima il file in CSV puro con la CLI MPM:

```bash

mpm to-csv dati.mpm dati.csv

```

Poi apri `dati.csv` con Excel o LibreOffice.



> **Nota:** La conversione MPM → CSV può perdere la distinzione tra `null` e stringa vuota. Di default, `mpm to-csv` esporta i `null` come campi vuoti. Se vuoi preservarli, puoi usare `--null-value "\\N"`, ma questo può creare collisioni con stringhe letterali `\N`.



### Python `csv`, R, `csvkit` e altri tool

* **Python `csv`:** puoi leggere il file saltando le righe che iniziano con `#`, ma devi gestire manualmente l'header e la semantica dei valori (inclusi `null` ed escaping).

* **R:** `read.csv("dati.mpm", comment.char = "#")` funziona per i file v0.1 e per i v0.2 senza `null`/escaping. Per i file v0.2, è consigliata la conversione con `mpm to-csv`.

* **`csvkit` / `mlr`:** la maggior parte dei tool CLI non supporta i commenti. Converti prima il file con `mpm to-csv`.



### Altri tool

Qualsiasi tool che supporti il parametro `comment` (o equivalente) può leggere un file `.mpm` direttamente, con le stesse limitazioni di `pandas`. Per i tool che non lo supportano, `mpm to-csv` è il percorso consigliato.



### Riepilogo



| Tool | Lettura diretta | Note |
| :--- | :---: | :--- |
| **pandas** | Sì, con `comment="#"` | Non interpreta `null`/escaping v0.2 |
| **R** | Sì, con `comment.char="#"` | Stesse limitazioni di `pandas` |
| **Excel / LibreOffice** | No | Usare `mpm to-csv` |
| **csvkit / mlr** | No | Usare `mpm to-csv` |
| **Python csv** | Sì, con filtro manuale | Gestire header e semantica |



---



## Test



```bash

python3 -m pytest tests -v

```



La suite include **198 test**: unitari, di integrazione e di conformità.



---



## Conformità



La directory `conformance/` contiene i file di test che ogni implementazione deve superare per essere dichiarata conforme. Per maggiori dettagli, vedi la **sezione 9 di SPEC.md**.



---



## Licenza



* **Codice:** MIT. Vedi `LICENSE`.

* **Specifica:** Creative Commons Attribution 4.0 International (CC BY 4.0). Vedi `LICENSE-SPEC`.



> La licenza CC BY 4.0 non concede diritti brevettuali o sui marchi. Gli autori non rivendicano brevetti sull'implementazione del formato MPM.