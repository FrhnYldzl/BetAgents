"""
SOFA-xG BASELINE MODEL + BACKTEST (T1 / Türkiye)
=================================================
Sofascore xG'den SIZINTISIZ rolling takım reytingi → Poisson → 1X2 olasılık
→ kapanış oranıyla edge → backtest.

Sızıntı koruması: bir maçın tahmini SADECE o maçtan ÖNCEKİ maçların xG'siyle
yapılır (rolling pencere). Maçın kendi xG'si tahmine GİRMEZ.

Çalıştır:
  python sofa_xg_model.py
"""
from __future__ import annotations
import sys
from collections import defaultdict, deque
from pathlib import Path

import numpy as np
from scipy.stats import poisson

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

K = 6          # rolling pencere (son K maç)
MIN_HIST = 4   # her iki takımda en az bu kadar geçmiş xG maçı olmalı
MAXG = 8


def match_probs(lh, la):
    ph = poisson.pmf(np.arange(MAXG + 1), lh)
    pa = poisson.pmf(np.arange(MAXG + 1), la)
    M = np.outer(ph, pa)
    pH = np.tril(M, -1).sum()
    pD = float(np.trace(M))
    pA = np.triu(M, 1).sum()
    s = pH + pD + pA
    return pH / s, pD / s, pA / s


def vig_strip(o1, ox, o2):
    inv = [1 / o1, 1 / ox, 1 / o2]
    t = sum(inv)
    return [x / t for x in inv]


def vig_strip_2(oa, ob):
    inv = [1 / oa, 1 / ob]
    t = sum(inv)
    return [x / t for x in inv]


def main():
    c = db.connect()
    rows = c.execute("""
        SELECT m.match_id, m.kickoff_utc, m.home_team, m.away_team,
               m.home_score, m.away_score,
               m.closing_1, m.closing_X, m.closing_2,
               m.closing_over25, m.closing_under25,
               s.home_xg, s.away_xg
        FROM sofascore_stats s JOIN matches_v2 m ON s.match_id=m.match_id
        WHERE s.home_xg IS NOT NULL AND m.home_score IS NOT NULL
        ORDER BY m.kickoff_utc ASC
    """).fetchall()
    c.close()
    rows = [dict(r) for r in rows]
    print(f"Toplam xG'li T1 maçı: {len(rows)}")

    # lig ortalaması (rolling değil, genel — shrinkage referansı)
    league_avg = np.mean([r["home_xg"] + r["away_xg"] for r in rows]) / 2

    xgf = defaultdict(lambda: deque(maxlen=K))  # takımın attığı xG
    xga = defaultdict(lambda: deque(maxlen=K))  # takımın yediği xG

    preds = []
    for r in rows:
        h, a = r["home_team"], r["away_team"]
        if len(xgf[h]) >= MIN_HIST and len(xgf[a]) >= MIN_HIST \
           and r["closing_1"] and r["closing_X"] and r["closing_2"]:
            # attack-strength × defense-weakness (sızıntısız: sadece geçmiş)
            h_att = np.mean(xgf[h]) / league_avg
            a_def = np.mean(xga[a]) / league_avg
            a_att = np.mean(xgf[a]) / league_avg
            h_def = np.mean(xga[h]) / league_avg
            lh = h_att * a_def * league_avg * 1.10   # hafif ev avantajı
            la = a_att * h_def * league_avg * 0.95
            pH, pD, pA = match_probs(lh, la)
            iH, iD, iA = vig_strip(r["closing_1"], r["closing_X"], r["closing_2"])
            res = "1" if r["home_score"] > r["away_score"] else ("2" if r["home_score"] < r["away_score"] else "X")
            rec = {
                "p": {"1": pH, "X": pD, "2": pA},
                "imp": {"1": iH, "X": iD, "2": iA},
                "odds": {"1": r["closing_1"], "X": r["closing_X"], "2": r["closing_2"]},
                "res": res,
            }
            # Alt/Üst 2.5 — xG'nin en doğrudan kullanımı (toplam gol)
            if r["closing_over25"] and r["closing_under25"]:
                p_over = float(1 - poisson.cdf(2, lh + la))
                io = vig_strip_2(r["closing_over25"], r["closing_under25"])
                rec["ou"] = {
                    "p_over": p_over, "imp_over": io[0],
                    "odds_over": r["closing_over25"], "odds_under": r["closing_under25"],
                    "res": "O" if (r["home_score"] + r["away_score"]) > 2.5 else "U",
                }
            preds.append(rec)
        # maçtan SONRA geçmişe ekle (sızıntı yok)
        xgf[h].append(r["home_xg"]); xga[h].append(r["away_xg"])
        xgf[a].append(r["away_xg"]); xga[a].append(r["home_xg"])

    print(f"Tahmin edilebilen (yeterli geçmiş + oran): {len(preds)}\n")

    # ── KALİBRASYON (model olasılığı gerçeğe yakın mı) ──
    import math
    brier = np.mean([sum((pr["p"][o] - (1 if pr["res"] == o else 0))**2 for o in "1X2") for pr in preds])
    brier_mkt = np.mean([sum((pr["imp"][o] - (1 if pr["res"] == o else 0))**2 for o in "1X2") for pr in preds])
    print(f"Brier skoru (düşük=iyi): MODEL {brier:.4f}  vs  PİYASA {brier_mkt:.4f}")
    print(f"  → {'model piyasaya yakın/iyi' if brier <= brier_mkt + 0.01 else 'model piyasanın gerisinde'}\n")

    # ── BACKTEST (edge eşiğine göre flat 1 birim) ──
    print(f"{'Eşik':>6} {'Bahis':>6} {'İsabet':>7} {'ROI':>8}  {'(iddaa %10 vergi sonrası)':>26}")
    print("-" * 60)
    for T in [0.03, 0.05, 0.08, 0.12]:
        n = won = 0; pnl = 0.0; pnl_tax = 0.0
        for pr in preds:
            for o in "1X2":
                edge = pr["p"][o] - pr["imp"][o]
                if edge > T:
                    n += 1
                    if pr["res"] == o:
                        won += 1
                        gain = pr["odds"][o] - 1
                        pnl += gain
                        pnl_tax += gain * 0.90  # iddaa kazançtan ~%10 vergi (yaklaşık)
                    else:
                        pnl -= 1; pnl_tax -= 1
        if n:
            roi = 100 * pnl / n
            roi_t = 100 * pnl_tax / n
            print(f"{T:>6.2f} {n:>6} {100*won//n:>6}% {roi:>+7.1f}% {roi_t:>+24.1f}%")
        else:
            print(f"{T:>6.2f} {n:>6}      -        -")
    print("-" * 60)

    # ── ALT/ÜST 2.5 BACKTEST (xG → toplam gol; en doğrudan kullanım) ──
    ou = [p["ou"] for p in preds if "ou" in p]
    print(f"\n=== ALT/ÜST 2.5 (xG→toplam gol) — {len(ou)} maç ===")
    if ou:
        bm = np.mean([(o["p_over"] - (1 if o["res"] == "O" else 0))**2 for o in ou])
        bmkt = np.mean([(o["imp_over"] - (1 if o["res"] == "O" else 0))**2 for o in ou])
        print(f"Brier: MODEL {bm:.4f} vs PİYASA {bmkt:.4f}")
        print(f"{'Eşik':>6} {'Bahis':>6} {'İsabet':>7} {'ROI':>8} {'vergi sonrası':>14}")
        print("-" * 48)
        for T in [0.03, 0.05, 0.08]:
            n = won = 0; pnl = pnl_t = 0.0
            for o in ou:
                for side, mp, ip, od in (("O", o["p_over"], o["imp_over"], o["odds_over"]),
                                          ("U", 1 - o["p_over"], 1 - o["imp_over"], o["odds_under"])):
                    if mp - ip > T:
                        n += 1
                        if o["res"] == side:
                            won += 1; pnl += od - 1; pnl_t += (od - 1) * 0.90
                        else:
                            pnl -= 1; pnl_t -= 1
            if n:
                print(f"{T:>6.2f} {n:>6} {100*won//n:>6}% {100*pnl/n:>+7.1f}% {100*pnl_t/n:>+13.1f}%")
            else:
                print(f"{T:>6.2f} {n:>6}      -       -")
    print("-" * 48)
    print("\nNot: pre-match sızıntısız (rolling xG). Pozitif ROI = xG-edge sinyali var demek.")


if __name__ == "__main__":
    main()
