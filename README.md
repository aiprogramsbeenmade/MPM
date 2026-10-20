# MPM — Minimal Portable Mapping

<p align="center">
  <img src="assets/logo.png" alt="MPM Logo" width="150">
</p>

> **Il "CSV 2.0":** un formato tabellare semplice come CSV, ma tipizzato, comprimibile e retrocompatibile.

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square&logo=opensourceinitiative&logoColor=white)
![License: CC BY 4.0](https://img.shields.io/badge/License-CC%20BY%204.0-lightgrey.svg?style=flat-square&logo=creativecommons&logoColor=white)
![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg?style=flat-square&logo=python&logoColor=white)
![Tests](https://img.shields.io/badge/tests-92%20passed-brightgreen.svg?style=flat-square&logo=pytest&logoColor=white)
![Version](https://img.shields.io/badge/version-0.1.0-orange.svg?style=flat-square&logo=semver&logoColor=white)
![Status](https://img.shields.io/badge/status-prototype-yellow.svg?style=flat-square&logo=statuspage&logoColor=white)

---



**MPM** è un formato per l'archiviazione e lo scambio di dati tabellari. È progettato per risolvere i problemi di CSV senza la complessità di Parquet:



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


| Comando            | Descrizione                                              |
|:-------------------|:---------------------------------------------------------|
| `mpm convert`      | Converte un CSV in MPM (con schema inferito o esplicito) |
| `mpm to-csv`       | Converte un MPM in CSV                                   |
| `mpm infer`        | Genera uno schema JSON da un CSV                         |
| `mpm compress`     | Comprime un MPM in MPMZ                                  |
| `mpm decompress`   | Decomprime un MPMZ in MPM                                |
| `mpm info`         | Mostra metadati e schema di un file                      |
| `mpm validate`     | Valida i dati contro lo schema                           |


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



Un file `.mpmz` è lo stesso contenuto compresso con **Zstandard** a blocchi.



> La specifica completa è disponibile in `SPEC.md`.



---



## Interoperabilità



Un file `.mpm` non compresso è un CSV valido con righe di commento in testa. Questo significa che può essere letto da qualsiasi tool che supporti i commenti nei CSV.



### pandas

```python

import pandas as pd

df = pd.read_csv("dati.mpm", comment="#")

```

> **Nota:** Il parametro `comment="#"` è obbligatorio: senza, pandas tenta di interpretare le righe `#` come dati e fallisce (o produce risultati errati).



### R

```r

df <- read.csv("dati.mpm", comment.char = "#")

```



### Excel / LibreOffice Calc

Excel e LibreOffice non supportano i commenti nei CSV. Per aprire un file `.mpm` in un foglio di calcolo, convertilo prima in CSV puro:

```bash

mpm to-csv dati.mpm dati.csv

```

Poi apri `dati.csv` con Excel o LibreOffice.



### csvkit / mlr / altri tool CLI

La maggior parte dei tool CLI per CSV non supporta i commenti. Per usarli, converti prima il file:

```bash

mpm to-csv dati.mpm dati.csv

csvstat dati.csv

```



### Altri tool

Qualsiasi tool che supporti il parametro `comment` (o equivalente) può leggere un file `.mpm` direttamente. Per i tool che non lo supportano, `mpm to-csv` è la soluzione.



---



## Test



```bash

python3 -m pytest tests -v

```



La suite include **92 test**: unitari, di integrazione e di conformità.



---



## Conformità



La directory `conformance/` contiene i file di test che ogni implementazione deve superare per essere dichiarata conforme. Per maggiori dettagli, vedi la *sezione 9* di `SPEC.md`.



---



## Licenza



* **Specifica:** CC BY 4.0

* **Codice:** MIT