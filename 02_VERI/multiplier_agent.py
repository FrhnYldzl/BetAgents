"""
🎰 ÇARPAN (MULTIPLE) — maç içi korelasyon ajanı
================================================
TEZ: Bahisçi kombineyi ayakların ÇARPIMI olarak fiyatlar (bağımsızlık
varsayımı). Gerçek dünyada aynı maçın sonuçları güçlü korelasyonludur.
iddaa bu kombineleri TEK seçim olarak sunar ("1 ve Üst", "0 ve Alt") —
yani korelasyon, kombinenin üstel marj cezası ÖDENMEDEN oynanabilir.

ÖLÇÜM (18.040 maç, koşullu): korelasyon sabit değil, maç profiline göre
değişir. Favori gücü P(1) ve gol beklentisi P(ÜST) bantlarına göre
katsayı tablosu aşağıda — bu ajanın beynidir.
    "0 ve ALT": 1.38 → 1.80  (gol beklentisi arttıkça güçlenir)
    "0 ve ÜST": 0.40 → 0.58  (güçlü NEGATİF — asla oynanmaz)
    "1 ve ÜST": 1.04 → 1.29

KARAR: adil oran = (bileşen oranlarının çarpımı) ÷ korelasyon katsayısı.
iddaa'nın verdiği kombine oranı adil oranı MIN_EDGE kadar aşıyorsa oynanır.

İZOLASYON (kullanıcı şartı): aday kaynağı YALNIZ `market_odds` tablosudur.
matches_v2'ye dokunmaz, sinyal motorunu çağırmaz, diğer ajanlar bu
hesaptan hiçbir şey okumaz. KONSEY oylamasına da dahil değildir.

NOT: Kullanıcı bu ajan için PoC istisnası tanıdı — veri birikir birikmez
oynayacak, ölçüm canlıda yapılacak. Küçük hacim + sıkı eşik ile.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import db

PID = "CARPAN_V1"
MIN_EDGE = 0.08          # iddaa oranı adil oranı ≥%8 aşmalı
MIN_ODDS = 2.50          # çarpan ajanı: kısa oranla ilgilenmez
MAX_ODDS = 40.0
MAX_DAILY = 2
MAX_OPEN = 6

FB = [0.35, 0.50, 0.65]   # P(ev sahibi) bantları
UB = [0.45, 0.55]         # P(ÜST) bantları

# 18.040 maçtan ölçülen koşullu korelasyon: (fav_band, ust_band, sonuc, U/A)
CORR = {
    (0, 0, "1", "U"): 1.220, (0, 0, "1", "A"): 0.859, (0, 0, "2", "U"): 1.288,
    (0, 0, "2", "A"): 0.815, (0, 0, "0", "U"): 0.400, (0, 0, "0", "A"): 1.385,
    (0, 1, "1", "U"): 1.124, (0, 1, "1", "A"): 0.871, (0, 1, "2", "U"): 1.218,
    (0, 1, "2", "A"): 0.773, (0, 1, "0", "U"): 0.477, (0, 1, "0", "A"): 1.544,
    (0, 2, "1", "U"): 1.040, (0, 2, "1", "A"): 0.933, (0, 2, "2", "U"): 1.143,
    (0, 2, "2", "A"): 0.762, (0, 2, "0", "U"): 0.564, (0, 2, "0", "A"): 1.725,
    (1, 0, "1", "U"): 1.291, (1, 0, "1", "A"): 0.807, (1, 0, "2", "U"): 1.238,
    (1, 0, "2", "A"): 0.842, (1, 0, "0", "U"): 0.398, (1, 0, "0", "A"): 1.400,
    (1, 1, "1", "U"): 1.267, (1, 1, "1", "A"): 0.740, (1, 1, "2", "U"): 1.145,
    (1, 1, "2", "A"): 0.858, (1, 1, "0", "U"): 0.483, (1, 1, "0", "A"): 1.505,
    (1, 2, "1", "U"): 1.170, (1, 2, "1", "A"): 0.733, (1, 2, "2", "U"): 1.140,
    (1, 2, "2", "A"): 0.780, (1, 2, "0", "U"): 0.513, (1, 2, "0", "A"): 1.759,
    (2, 0, "1", "U"): 1.230, (2, 0, "1", "A"): 0.820, (2, 0, "2", "U"): 1.140,
    (2, 0, "2", "A"): 0.890, (2, 0, "0", "U"): 0.510, (2, 0, "0", "A"): 1.380,
    (2, 1, "1", "U"): 1.190, (2, 1, "1", "A"): 0.810, (2, 1, "2", "U"): 1.100,
    (2, 1, "2", "A"): 0.900, (2, 1, "0", "U"): 0.480, (2, 1, "0", "A"): 1.530,
    (2, 2, "1", "U"): 1.150, (2, 2, "1", "A"): 0.740, (2, 2, "2", "U"): 1.020,
    (2, 2, "2", "A"): 0.970, (2, 2, "0", "U"): 0.570, (2, 2, "0", "A"): 1.760,
    (3, 1, "1", "U"): 1.110, (3, 1, "1", "A"): 0.880, (3, 1, "2", "U"): 0.960,
    (3, 1, "2", "A"): 1.040, (3, 1, "0", "U"): 0.510, (3, 1, "0", "A"): 1.500,
    (3, 2, "1", "U"): 1.100, (3, 2, "1", "A"): 0.810, (3, 2, "2", "U"): 0.870,
    (3, 2, "2", "A"): 1.240, (3, 2, "0", "U"): 0.580, (3, 2, "0", "A"): 1.800,
}


def _band(p: float, edges: list) -> int:
    for i, e in enumerate(edges):
        if p < e:
            return i
    return len(edges)


def _now() -> str:
    return datetime.utcnow().isoformat()


def candidates(min_edge: float = MIN_EDGE) -> list[dict]:
    """market_odds'tan kombine değer adayları. Yalnız bu tabloyu okur."""
    conn = db.connect()
    out: list[dict] = []
    try:
        rows = conn.execute(
            "SELECT iddaa_event_id, league_code, kickoff_utc, home_team, away_team, "
            "market, selection, odd, lead_h, ts FROM market_odds "
            "WHERE kickoff_utc > ? ORDER BY ts", (_now(),)).fetchall()
    except Exception:
        conn.rollback()
        conn.close()
        return []
    conn.close()

    # her (maç, pazar, seçim) için EN SON fiyat
    latest: dict = {}
    meta: dict = {}
    for r in rows:
        ev = str(r[0])
        latest[(ev, r[5], r[6])] = float(r[7] or 0)
        meta[ev] = {"lg": r[1], "ko": r[2], "home": r[3], "away": r[4],
                    "lead": r[8]}

    for ev, m in meta.items():
        o1 = latest.get((ev, "1X2", "1"))
        ox = latest.get((ev, "1X2", "0")) or latest.get((ev, "1X2", "X"))
        o2 = latest.get((ev, "1X2", "2"))
        ou = latest.get((ev, "OU2.5", "Üst"))
        al = latest.get((ev, "OU2.5", "Alt"))
        if not all((o1, ox, o2, ou, al)):
            continue
        s1 = 1 / o1 + 1 / ox + 1 / o2
        p1 = (1 / o1) / s1
        s2 = 1 / ou + 1 / al
        pu = (1 / ou) / s2
        fb, ub = _band(p1, FB), _band(pu, UB)
        comp = {"1": o1, "0": ox, "2": o2}
        for res in ("1", "0", "2"):
            for ou_lbl, ou_odd, tag in (("Üst", ou, "U"), ("Alt", al, "A")):
                combo = latest.get((ev, "1X2_OU", f"{res} ve {ou_lbl}"))
                if not combo:
                    continue
                c = CORR.get((fb, ub, res, tag))
                if not c:
                    continue
                naive = comp[res] * ou_odd
                fair = naive / c                    # korelasyon-düzeltilmiş adil oran
                edge = combo / fair - 1
                if edge < min_edge:
                    continue
                if not (MIN_ODDS <= combo <= MAX_ODDS):
                    continue
                out.append({
                    "event_id": ev, "league": m["lg"], "kickoff": m["ko"],
                    "home": m["home"], "away": m["away"],
                    "market": "1X2_OU", "pick": f"{res} ve {ou_lbl}",
                    "odds": combo, "fair": round(fair, 2), "naive": round(naive, 2),
                    "corr": c, "edge": round(edge * 100, 1),
                    "lead": m["lead"],
                })
    out.sort(key=lambda x: -x["edge"])
    return out


def report(min_edge: float = MIN_EDGE) -> None:
    cs = candidates(min_edge)
    print(f"🎰 ÇARPAN adayları (edge ≥ %{min_edge*100:.0f}): {len(cs)}")
    for c in cs[:15]:
        print(f"  {c['home'][:16]:16s}-{c['away'][:16]:16s} {c['pick']:10s} "
              f"@{c['odds']:6.2f}  adil {c['fair']:6.2f} (korelasyon {c['corr']:.2f}) "
              f"→ edge %{c['edge']:+.1f}")


if __name__ == "__main__":
    report(float(sys.argv[1]) if len(sys.argv) > 1 else MIN_EDGE)
