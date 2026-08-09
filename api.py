#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SERTAKIS ALTERNÉ — API REST (FastAPI)
Auteurs : Antoine Couet (Architecte1995) & Kimi K3
Licence : MIT

Endpoints :
  GET  /           → racine (info service)
  GET  /health     → santé du service
  POST /chain      → génère une chaîne alternée
  POST /verify     → vérifie une chaîne existante
  POST /stats      → analyse statistique d'une chaîne
"""

import os
from collections import Counter
from typing import List, Dict, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Import du core
# ---------------------------------------------------------------------------
try:
    from sertakis_core import generer_chaine, verifier_chaine
    CORE_AVAILABLE = True
except ImportError:
    CORE_AVAILABLE = False
    generer_chaine = None
    verifier_chaine = None

# ---------------------------------------------------------------------------
# Application FastAPI
# ---------------------------------------------------------------------------
app = FastAPI(
    title="PrimeChain API — Sertakis Alterné Engine",
    version="5.1.1",
    description=(
        "Générateur de chaînes alternées Cunningham↔Sertakis "
        "avec crible orbital et mémoire adaptative EWMA."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# Middleware de garde — accepte X-RapidAPI-Proxy-Secret ET X-RapidAPI-Secret
# ---------------------------------------------------------------------------
PUBLIC_PATHS = {"/", "/health", "/docs", "/redoc", "/openapi.json"}

@app.middleware("http")
async def rapidapi_proxy_guard(request: Request, call_next):
    if request.url.path in PUBLIC_PATHS:
        return await call_next(request)

    rapidapi_secret = os.environ.get("RAPIDAPI_SECRET")

    # Mode dev : pas de secret configuré, tout passe
    if not rapidapi_secret:
        return await call_next(request)

    # Accepte les deux noms de header (proxy production + Studio test)
    proxy_secret = (
        request.headers.get("X-RapidAPI-Proxy-Secret")
        or request.headers.get("X-RapidAPI-Secret")
    )

    if proxy_secret != rapidapi_secret:
        return JSONResponse(
            status_code=403,
            content={"detail": "Forbidden. Access this API through RapidAPI proxy only."},
        )

    return await call_next(request)

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
@app.get("/", tags=["meta"])
def root() -> Dict[str, Any]:
    return {
        "service": "PrimeChain API",
        "version": "5.1.1",
        "authors": "Architecte1995 & Kimi K3",
        "license": "MIT",
        "reference_doi": "10.5281/zenodo.21456976",
        "endpoints": {
            "health": "/health",
            "chain": "POST /chain",
            "verify": "POST /verify",
            "stats": "POST /stats",
            "docs": "/docs",
        },
        "core_loaded": CORE_AVAILABLE,
    }

@app.get("/health", tags=["meta"])
def health() -> Dict[str, str]:
    return {
        "status": "ok",
        "version": "5.1.1",
        "core_loaded": "yes" if CORE_AVAILABLE else "no",
    }

@app.post("/chain", response_model=ChainResponse, tags=["engine"])
def chain_endpoint(req: ChainRequest) -> Dict[str, Any]:
    if not CORE_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Core engine unavailable. sertakis_core.py not found.",
        )
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

@app.post("/verify", response_model=VerifyResponse, tags=["engine"])
def verify_endpoint(req: VerifyRequest) -> Dict[str, Any]:
    if not CORE_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Core engine unavailable. sertakis_core.py not found.",
        )
    if len(req.chaine) != len(req.types) + 1:
        raise HTTPException(
            status_code=400,
            detail="len(chaine) doit être len(types)+1",
        )
    return verifier_chaine(req.chaine, req.types)

@app.post("/stats", tags=["analytics"])
def stats_endpoint(req: StatsRequest) -> Dict[str, Any]:
    if len(req.chaine) != len(req.types) + 1:
        raise HTTPException(
            status_code=400,
            detail="len(chaine) doit être len(types)+1",
        )

    n = len(req.types)
    nC = req.types.count("C")
    bursts, cur = [], 0
    for k in req.types:
        if k == "C":
            cur += 1
        else:
            if cur:
                bursts.append(cur)
            cur = 0
    if cur:
        bursts.append(cur)

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

# ---------------------------------------------------------------------------
# Point d'entrée standalone
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info",
    )
