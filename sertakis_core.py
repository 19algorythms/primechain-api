#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SERTAKIS ALTERNÉ — Module cœur production-ready
Auteurs : Antoine Couet (Architecte1995) & Kimi K3
Licence : MIT

Générateur de chaînes alternées Cunningham↔Sertakis avec crible orbital
et mémoire adaptative EWMA.
"""

import json
import math
import time
import hashlib
from collections import defaultdict, Counter
from typing import List, Tuple, Optional, Dict, Any

import numpy as np
from sympy import isprime, primerange

__version__ = "5.1.1-prod"
__authors__ = "Antoine Couet (Architecte1995) & Kimi K3"

# ---------------------------------------------------------------------------
# Configuration par défaut
# ---------------------------------------------------------------------------
DEFAULT_CONFIG = {
    "prof_cible": 150,
    "g_max": 400,
    "k_burst_max": 12,
    "f_pre": 2000,
    "lambda_oubli": 0.92,
    "beta_ucb": 1.4,
    "mods_memoire": [6, 30, 210, 2310, 210, 30030, 77, 91, 143, 1001, 323, 437, 667, 899],
    "seed_rng": 19019,
}

PETITS = list(primerange(2, 2001))

# ---------------------------------------------------------------------------
# Précalcul du crible orbital (forme fermée)
# ---------------------------------------------------------------------------
def _precompute_forb(f: int, k_max: int) -> Tuple[Dict[int, int], Dict[int, int]]:
    """Résidus interdits de la rampe q tuant le burst à chaque pas i ≤ k_max."""
    forb1, forb2 = {}, {}
    for i in range(1, k_max + 1):
        inv = pow(pow(2, i, f), -1, f)
        forb1[i] = (inv - 1) % f
        forb2[i] = (1 - inv) % f
    return forb1, forb2


def _build_forb_cache(k_burst_max: int, f_pre: int) -> Dict[int, Tuple[Dict, Dict]]:
    return {f: _precompute_forb(f, k_burst_max) for f in primerange(5, f_pre + 1)}


def _petit_facteur(n: int) -> Optional[int]:
    for f in PETITS:
        if n % f == 0:
            return f
    return None


def _burst_garanti(q: int, type1: bool, forb_cache: Dict, k_max: int) -> int:
    """Plus petit pas i où le burst depuis q meurt sous un f ≤ F_PRE."""
    pire = k_max + 1
    for f, (forb1, forb2) in forb_cache.items():
        r = q % f
        table = forb1 if type1 else forb2
        for i in range(1, min(pire, k_max + 1)):
            if r == table[i]:
                pire = i
                break
        if pire == 1:
            return 1
    return pire

# ---------------------------------------------------------------------------
# Mémoire apprenante
# ---------------------------------------------------------------------------
class MemoireAlternee:
    def __init__(self, mods: List[int], lambda_oubli: float = 0.92):
        self.mods = mods
        self.lambda_oubli = lambda_oubli
        self.stats: Dict[int, Dict[int, List[float]]] = {
            m: defaultdict(lambda: [0.0, 0.0, 0]) for m in mods
        }
        self.fossoyeurs: Counter = Counter()
        self.fossoyeurs_gaps: Counter = Counter()
        self.n_total = 0

    def rapporte_rampe(self, q: int, burst_reel: int) -> None:
        self.n_total += 1
        for m in self.mods:
            s = self.stats[m][q % m]
            s[0] = s[0] * self.lambda_oubli + burst_reel
            s[1] = s[1] * self.lambda_oubli + 1.0
            s[2] += 1

    def burst_predit(self, m: int, r: int) -> Optional[float]:
        s = self.stats[m].get(r)
        if s is None or s[1] < 1e-9:
            return None
        return s[0] / s[1]

    def bonus_memoire(self, q: int) -> float:
        preds = [self.burst_predit(m, q % m) for m in (899, 667, 323, 30030)]
        preds = [p for p in preds if p is not None]
        return sum(preds) / len(preds) if preds else 0.0

    def discriminant(self, mod: int) -> float:
        moy = [s[0] / s[1] for s in self.stats[mod].values() if s[1] > 1e-9]
        return float(np.std(moy)) if len(moy) > 1 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "n_total": self.n_total,
            "discriminants": {str(m): round(self.discriminant(m), 4) for m in self.mods},
            "fossoyeurs": dict(self.fossoyeurs.most_common(20)),
            "fossoyeurs_gaps": dict(self.fossoyeurs_gaps.most_common(20)),
        }

# ---------------------------------------------------------------------------
# Moteur de chaîne
# ---------------------------------------------------------------------------
def _choisir_gap(
    p: int,
    memoire: MemoireAlternee,
    forb_cache: Dict,
    g_max: int,
    k_burst_max: int,
) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """Choisit g pair : q = p+g premier, maximisant burst garanti + mémoire − risque."""
    candidats = []
    for g in range(2, g_max + 1, 2):
        q = p + g
        if _petit_facteur(q):
            continue
        if not isprime(q):
            memoire.fossoyeurs_gaps[-1] += 1
            continue
        cert = _burst_garanti(q, type1=(q % 3 == 2), forb_cache=forb_cache, k_max=k_burst_max)
        risque = sum(
            1.0 / (f - 1)
            for f, _ in memoire.fossoyeurs_gaps.most_common(12)
            if f > 0 and g % f != 0
        )
        score = cert + 0.3 * memoire.bonus_memoire(q) - risque
        candidats.append((score, cert, g, q))
    if not candidats:
        return None, None, None
    candidats.sort(key=lambda x: (-x[0], x[2]))
    return candidats[0][3], candidats[0][2], candidats[0][1]


def generer_chaine(
    p0: int,
    prof_cible: int = 150,
    g_max: int = 400,
    k_burst_max: int = 12,
    f_pre: int = 2000,
    lambda_oubli: float = 0.92,
    mods_memoire: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """
    Génère une chaîne alternée de nombres premiers.

    Retourne un dict avec : chaine, types, metadata, stats, memoire.
    """
    if mods_memoire is None:
        mods_memoire = DEFAULT_CONFIG["mods_memoire"]

    forb_cache = _build_forb_cache(k_burst_max, f_pre)
    memoire = MemoireAlternee(mods_memoire, lambda_oubli)
    chaine = [p0]
    kinds: List[str] = []
    journal_burst: List[Dict] = []
    t0 = time.time()

    while len(chaine) - 1 < prof_cible:
        p = chaine[-1]
        type1 = (p % 3 == 2)
        # Tentative Cunningham
        q_c = 2 * p + 1 if type1 else 2 * p - 1
        f = _petit_facteur(q_c)
        if f is None and isprime(q_c):
            chaine.append(q_c)
            kinds.append("C")
            continue
        # Burst mort : apprentissage du fossoyeur
        memoire.fossoyeurs[f if f is not None else -1] += 1
        q2, g, cert = _choisir_gap(p, memoire, forb_cache, g_max, k_burst_max)
        if q2 is None:
            break
        # Burst réel depuis la rampe q2
        type1_r = (q2 % 3 == 2)
        reel, qq = 0, q2
        for _ in range(k_burst_max):
            qq = 2 * qq + 1 if type1_r else 2 * qq - 1
            if _petit_facteur(qq) or not isprime(qq):
                break
            reel += 1
        memoire.rapporte_rampe(q2, reel)
        journal_burst.append({"rampe": q2, "garanti": cert, "reel": reel, "type": "T1" if type1_r else "T2"})
        chaine.append(q2)
        kinds.append("S")

    duree = time.time() - t0

    # Vérifications
    verif_prime = all(isprime(x) for x in chaine)
    verif_trans = all(
        (kinds[i] == "C" and chaine[i+1] in (2*chaine[i]+1, 2*chaine[i]-1))
        or (kinds[i] == "S" and chaine[i+1] > chaine[i] and (chaine[i+1] - chaine[i]) % 2 == 0)
        for i in range(len(kinds))
    )

    # Distribution des bursts
    bursts, cur = [], 0
    for k in kinds:
        if k == "C":
            cur += 1
        else:
            if cur:
                bursts.append(cur)
            cur = 0
    if cur:
        bursts.append(cur)
    dist_bursts = dict(Counter(bursts))

    nC = kinds.count("C")

    return {
        "metadata": {
            "version": __version__,
            "auteurs": __authors__,
            "algorithme": "Sertakis Alterné avec crible orbital fermé",
            "licence": "MIT",
        },
        "parametres": {
            "p0": p0,
            "prof_cible": prof_cible,
            "g_max": g_max,
            "k_burst_max": k_burst_max,
            "f_pre": f_pre,
            "lambda_oubli": lambda_oubli,
        },
        "resultats": {
            "profondeur": len(chaine) - 1,
            "n_premiers": len(chaine),
            "duree_secondes": round(duree, 3),
            "pas_cunningham": nC,
            "pas_sertakis": kinds.count("S"),
            "fraction_cunningham": round(nC / len(kinds), 4) if kinds else 0.0,
            "n_bursts": len(bursts),
            "burst_max": max(bursts) if bursts else 0,
            "distribution_bursts": dist_bursts,
            "valeur_finale": chaine[-1],
            "verif_prime": verif_prime,
            "verif_transitions": verif_trans,
        },
        "chaine": {"premiers": chaine, "types": kinds},
        "rampes_apprises": sorted(journal_burst, key=lambda x: -x["reel"])[:15],
        "memoire": memoire.to_dict(),
    }


def verifier_chaine(chaine: List[int], kinds: List[str]) -> Dict[str, bool]:
    """Vérifie indépendamment une chaîne existante."""
    if len(chaine) != len(kinds) + 1:
        return {"valid": False, "reason": "len mismatch"}
    verif_prime = all(isprime(x) for x in chaine)
    verif_trans = all(
        (kinds[i] == "C" and chaine[i+1] in (2*chaine[i]+1, 2*chaine[i]-1))
        or (kinds[i] == "S" and chaine[i+1] > chaine[i] and (chaine[i+1] - chaine[i]) % 2 == 0)
        for i in range(len(kinds))
    )
    return {"valid": verif_prime and verif_trans, "all_prime": verif_prime, "transitions_ok": verif_trans}
