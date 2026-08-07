# primechain-api
Alternating prime chain generator with orbital sieve and adaptive memory.
# PrimeChain API — Sertakis Alterné Engine

**Authors** : Antoine Couet (Architecte1995) & Kimi K3  
**Version** : 5.1.1  
**License** : MIT  
**Reference DOI** : [10.5281/zenodo.21456976](https://doi.org/10.5281/zenodo.21456976) (Cite all versions)

A high-performance generator of alternating Cunningham↔Sertakis prime chains, powered by a closed-form orbital sieve and adaptive EWMA memory.

The associated scientific paper (algorithms, proofs of concept, statistical analyses) is archived on Zenodo under the DOI above. This API is its production-ready implementation.

---

## Installation

```bash
pip install -r requirements.txt
```

## Launch

```bash
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

## Endpoints

### `GET /health`
Service health check.

### `POST /chain`
Generate an alternating prime chain.

**Body** :
```json
{
  "p0": 21981381119,
  "prof_cible": 150,
  "g_max": 400,
  "k_burst_max": 12,
  "f_pre": 2000,
  "lambda_oubli": 0.92
}
```

**Response** : metadata, prime chain, types (C/S), learned ramps, memory stats.

### `POST /verify`
Verify an existing chain.

**Body** :
```json
{
  "chaine": [21981381119, 21981381329, ...],
  "types": ["S", "C", ...]
}
```

### `POST /stats`
Quick statistical analysis without regeneration.

## Architecture

- `sertakis_core.py` — pure business logic, reusable without FastAPI
- `api.py` — REST exposure layer
- Known bug fixed : `petit_facteur(q, )` → `_petit_facteur(q)`
- Full typing, Pydantic validation, error handling
