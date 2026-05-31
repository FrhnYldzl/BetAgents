"""
SELECTIVE EDGE v1.1 — Team Name Fuzzy Matching

iddaa.com, tipster_picks, DC modeli, api-football — her biri farklı takım adı
kullanıyor. Örnek:
    iddaa:        "Fenerbahçe"
    api-football: "Fenerbahce"
    DC model:     "Fenerbahce"
    tipster:      "Fenerbahce"
    Mackolik:     "FB"

Bu modül:
    1. normalize(name)        — lowercase, accent strip, paren temizle, abbr genişlet
    2. similarity(a, b)       — Levenshtein-based ratio
    3. best_team_match(name, candidates) — en iyi eşleşmeyi bul

Hiç external lib yok (rapidfuzz değil) — saf python.
"""
from __future__ import annotations

import re
import unicodedata


# ============================================================
# NORMALIZATION
# ============================================================

# Yaygın iddaa/tipster/DC abbreviations
ABBREV = {
    "fb": "fenerbahce",
    "gs": "galatasaray",
    "bjk": "besiktas",
    "ts": "trabzonspor",
    "man city": "manchester city",
    "man united": "manchester united",
    "man utd": "manchester united",
    "spurs": "tottenham",
    "wolves": "wolverhampton",
    "atl": "atletico",
    "atl. madrid": "atletico madrid",
    "real": "real madrid",
    "bayern": "bayern munich",
    "psg": "paris saint germain",
    "milan": "ac milan",
    "inter": "inter milan",
}

# Suffix patterns to remove
SUFFIX_RE = [
    r"\s+\(.*?\)$",          # "Barcelona (K)" → "Barcelona"
    r"\s+(fc|cf|sc|sk|ac|fk|cd|cs|sv|usl ?\d*)$",
    r"\s+(reserve|reserves|res|ii|b|u\d+)$",
]


def _strip_accents(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalize(name: str | None) -> str:
    """Kanonik form: lowercase, accent-strip, suffix-clean, abbr-expand."""
    if not name:
        return ""
    s = name.strip().lower()
    s = _strip_accents(s)
    # Suffix temizle
    for pat in SUFFIX_RE:
        s = re.sub(pat, "", s, flags=re.IGNORECASE)
    # Multi-space normalize
    s = re.sub(r"\s+", " ", s).strip()
    # Abbreviation expansion (full string match)
    if s in ABBREV:
        s = ABBREV[s]
    return s


# ============================================================
# LEVENSHTEIN
# ============================================================

def levenshtein(a: str, b: str) -> int:
    """Klasik dynamic-programming Levenshtein distance."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    if len(a) > len(b):
        a, b = b, a
    # Now len(a) <= len(b)
    prev = list(range(len(a) + 1))
    for i, cb in enumerate(b, 1):
        cur = [i] + [0] * len(a)
        for j, ca in enumerate(a, 1):
            ins = cur[j - 1] + 1
            dele = prev[j] + 1
            sub = prev[j - 1] + (0 if ca == cb else 1)
            cur[j] = min(ins, dele, sub)
        prev = cur
    return prev[-1]


def similarity(a: str | None, b: str | None) -> float:
    """0-1 similarity score. Normalize'lı."""
    na = normalize(a)
    nb = normalize(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    max_len = max(len(na), len(nb))
    if max_len == 0:
        return 0.0
    # Substring check (kısa isim uzun isim içinde)
    if na in nb or nb in na:
        shorter = min(len(na), len(nb))
        longer = max(len(na), len(nb))
        # 'palace' in 'crystal palace' → 0.85 ratio
        substr_score = 0.6 + 0.4 * (shorter / longer)
    else:
        substr_score = 0
    # Token-set overlap
    a_tokens = set(na.split())
    b_tokens = set(nb.split())
    if a_tokens and b_tokens:
        token_overlap = len(a_tokens & b_tokens) / max(len(a_tokens), len(b_tokens))
    else:
        token_overlap = 0
    # Levenshtein ratio
    d = levenshtein(na, nb)
    lev_ratio = 1.0 - d / max_len
    # En iyisini al
    return max(lev_ratio, token_overlap, substr_score)


# ============================================================
# MATCHING
# ============================================================

def best_team_match(name: str, candidates: list[str],
                    min_score: float = 0.6) -> tuple[str | None, float]:
    """
    En benzer takım adını candidates'tan bul.
    Returns (matched_name, score) or (None, 0.0).
    """
    if not name or not candidates:
        return None, 0.0
    best = None
    best_score = 0.0
    for c in candidates:
        sc = similarity(name, c)
        if sc > best_score:
            best_score = sc
            best = c
    if best_score >= min_score:
        return best, best_score
    return None, best_score


def match_pair(home_a: str, away_a: str,
               home_b: str, away_b: str,
               min_score: float = 0.7) -> bool:
    """İki maç çiftini eşleştir (both teams must match)."""
    s_home = similarity(home_a, home_b)
    s_away = similarity(away_a, away_b)
    return s_home >= min_score and s_away >= min_score


if __name__ == "__main__":
    # Test
    cases = [
        ("Fenerbahçe", "Fenerbahce"),
        ("Manchester City", "Man City"),
        ("Galatasaray", "GS"),
        ("Real Madrid", "Real"),
        ("Barcelona (K)", "Barcelona"),
        ("Borussia Dortmund", "Dortmund"),
        ("Crystal Palace", "Palace"),
        ("AC Milan", "Milan"),
        ("Penarol Uru", "Peñarol"),
    ]
    print("--- SIMILARITY TESTS ---")
    for a, b in cases:
        s = similarity(a, b)
        flag = "OK" if s >= 0.7 else "--"
        print(f"  [{flag}] '{a}' <-> '{b}': {s:.3f}")

    print("\n--- BEST MATCH ---")
    candidates = ["Fenerbahce", "Galatasaray", "Besiktas", "Trabzonspor", "Antalyaspor"]
    for name in ["FB", "Fenerbahçe", "Galatasaray Spor Kulübü", "Beşiktaş"]:
        m, sc = best_team_match(name, candidates)
        print(f"  '{name}' -> '{m}' ({sc:.3f})")
