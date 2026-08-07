#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SERTAKIS ALTERNÉ — API REST (FastAPI)
Auteurs : Antoine Couet (Architecte1995) & Kimi K3
Licence : MIT

Endpoints :
  POST /chain      → génère une chaîne alternée
  POST /verify     → vérifie une chaîne existante
  POST /stats      → analyse statistique d'une chaîne
  GET  /health     → santé du service
"""

from collections import Counter
from typing import List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from sertakis_core import generer_chaine, verifier_chaine

app = FastAPI(
    title="Sertakis Alterné API",
    version="5.1.1",
    description="Générateur de chaînes alternées Cunningham↔Sertakis avec crible orbital",
)

# ---------------------------------------------------------------------------
# Modèles Pydantic
# ---------------------------------------------------------------------------
class ChainRequest(BaseModel):
    p0: int = Field(..., gt=1, description="Nombre premier de départ")
    prof_cible: int = Field(150, ge=1, le=500, description="Profondeur visée")
    g_max: int = Field(400, ge=2, le=2000, description="Gap Sertakis maximal")
    k_burst_max: int = Field(12, ge=1, le=50, description="Profondeur de burst évaluée")
    f_pre: int = Field(2000, ge=100, le=10000, description="Fossoyeurs couverts")
    lambda_oubli: float = Field(0.92, ge=0.0, le=1.0)

class ChainResponse(BaseModel):
    metadata: dict
    parametres: dict
    resultats: dict
    chaine: dict
    rampes_apprises: list
    memoire: dict

class VerifyRequest(BaseModel):
    chaine: List[int]
    types: List[str]

class VerifyResponse(BaseModel):
    valid: bool
    all_prime: bool
    transitions_ok: bool

class StatsRequest(BaseModel):
    chaine: List[int]
    types: List[str]

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok", "version": "5.1.1"}

@app.post("/chain", response_model=ChainResponse)
def chain_endpoint(req: ChainRequest):
    try:
        result = generer_chaine(
            p0=req.p0,
            prof_cible=req.prof_cible,
            g_max=req.g_max,
            k_burst_max=req.k_burst_max,
            f_pre=req.f_pre,
            lambda_oubli=req.lambda_oubli,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/verify", response_model=VerifyResponse)
def verify_endpoint(req: VerifyRequest):
    if len(req.chaine) != len(req.types) + 1:
        raise HTTPException(status_code=400, detail="len(chaine) doit être len(types)+1")
    return verifier_chaine(req.chaine, req.types)

@app.post("/stats")
def stats_endpoint(req: StatsRequest):
    """Analyse statistique rapide d'une chaîne existante."""
    if len(req.chaine) != len(req.types) + 1:
        raise HTTPException(status_code=400, detail="len(chaine) doit être len(types)+1")

    n = len(req.types)
    nC = req.types.count("C")
    bursts, cur = [], 0
    for k in req.types:
        if k == "C":
            cur += 1
        else:
            if cur: bursts.append(cur)
            cur = 0
    if cur: bursts.append(cur)

    return {
        "profondeur": n,
        "pas_cunningham": nC,
        "pas_sertakis": n - nC,
        "fraction_cunningham": round(nC / n, 4) if n else 0.0,
        "n_bursts": len(bursts),
        "burst_max": max(bursts) if bursts else 0,
        "distribution_bursts": dict(Counter(bursts)),
        "valeur_finale": req.chaine[-1],
    }
