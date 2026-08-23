"""
BAĞIMSIZ MODEL — gol-tabanlı leak-free Poisson takım gücü (canlı + backtest)
============================================================================
AMAÇ: Sinyallerin `model_prob`'u şu an iddaa oranının vig'siz halidir = piyasanın
KENDİ fiyatı (bağımsız tahmin DEĞİL). Bu modül BAĞIMSIZ bir olasılık üretir:
geçmiş GOL sonuçlarından rolling takım gücü → Poisson → 1X2 / A-Ü / KG.

  gerçek_edge = bağımsız_model_olasılık − piyasa_implied   (anlaşmazlık)
  > 0 → model piyasadan YÜKSEK diyor = potansiyel DEĞER (favori olması şart değil)

Leak-free: bir maçın tahmini SADECE ondan ÖNCEKİ maçların golleriyle yapılır.
Goller ~%100 kapsamlı (tüm ligler) → canlı tüm maçlarda çalışır (xG gibi %30 değil).

Kullanım:
  python independent_model.py            # 6 ana ligde leak-free backtest (dürüstlük)
"""
from __future__ import annotations

import sys
import math
from collections import defaultdict, deque
from pathlib import Path

import numpy as np

# Poisson (scipy'siz — Railway slim runtime'da scipy YOK; scipy importu tüm
# motor ailesini ModuleNotFoundError ile düşürüyordu). numpy ile birebir aynı:
#   pmf(k;λ) = e^-λ λ^k / k!   ·   cdf(k;λ) = Σ_{i<=k} pmf(i)


class _Poisson:
    @staticmethod
    def pmf(k, lam):
        k = np.asarray(k, dtype=float)
        logf = np.cumsum(np.log(np.maximum(np.arange(1, k.max() + 2), 1.0)))
        logfact = np.concatenate(([0.0], logf))[k.astype(int)]
        return np.exp(-lam + k * np.log(lam) - logfact)

    @staticmethod
    def cdf(k, lam):
        ks = np.arange(0, int(k) + 1)
        return float(_Poisson.pmf(ks, lam).sum())


poisson = _Poisson()

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

K = 10            # rolling pencere (son K maç)
MIN_HIST = 6      # her iki takımda en az bu kadar geçmiş maç
SHRINK = 4        # az maçlı takımı lig ortalamasına çekme
HOME_BOOST = 1.10
AWAY_FACTOR = 0.95
MAXG = 8


def _match_probs(lh, la):
    ph = poisson.pmf(np.arange(MAXG + 1), lh)
    pa = poisson.pmf(np.arange(MAXG + 1), la)
    M = np.outer(ph, pa)
    pH = float(np.tril(M, -1).sum())
    pD = float(np.trace(M))
    pA = float(np.triu(M, 1).sum())
    s = pH + pD + pA
    return pH / s, pD / s, pA / s


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


class Ratings:
    """Leak-free rolling gol-gücü deposu. Canlı için: tüm settle maçlardan kur,
    sonra gelecekteki (kickoff>now) maçları tahmin et."""

    def __init__(self, k=K, min_hist=MIN_HIST):
        self.k = k
        self.min_hist = min_hist
        self.gf = defaultdict(lambda: deque(maxlen=k))   # attığı gol
        self.ga = defaultdict(lambda: deque(maxlen=k))   # yediği gol
        self.lsum = defaultdict(float)                   # lig gol toplamı
        self.ln = defaultdict(int)                       # lig (takım×maç) sayısı
        self.gsum = 0.0
        self.gn = 0

    def update(self, league, home, away, hs, as_):
        self.gf[home].append(hs); self.ga[home].append(as_)
        self.gf[away].append(as_); self.ga[away].append(hs)
        self.lsum[league] += hs + as_; self.ln[league] += 2
        self.gsum += hs + as_; self.gn += 2

    def _league_avg(self, league):
        if self.ln.get(league, 0) >= 40:
            return self.lsum[league] / self.ln[league]
        # az veri → global ortalamaya karış
        glob = (self.gsum / self.gn) if self.gn else 1.35
        if self.ln.get(league, 0):
            la = self.lsum[league] / self.ln[league]
            w = self.ln[league] / (self.ln[league] + 40)
            return w * la + (1 - w) * glob
        return glob

    def _shrunk_mean(self, dq, lavg):
        n = len(dq)
        if n == 0:
            return lavg
        m = sum(dq) / n
        w = n / (n + SHRINK)
        return w * m + (1 - w) * lavg

    def predict(self, match_row: dict):
        h = match_row.get("home_team"); a = match_row.get("away_team")
        L = match_row.get("league_code")
        if not h or not a:
            return None
        if len(self.gf[h]) < self.min_hist or len(self.gf[a]) < self.min_hist:
            return None
        lavg = self._league_avg(L)
        if not lavg or lavg <= 0:
            return None
        h_att = self._shrunk_mean(self.gf[h], lavg) / lavg
        a_def = self._shrunk_mean(self.ga[a], lavg) / lavg
        a_att = self._shrunk_mean(self.gf[a], lavg) / lavg
        h_def = self._shrunk_mean(self.ga[h], lavg) / lavg
        lh = _clamp(h_att * a_def * lavg * HOME_BOOST, 0.2, 5.0)
        la = _clamp(a_att * h_def * lavg * AWAY_FACTOR, 0.2, 5.0)
        p1, pX, p2 = _match_probs(lh, la)
        p_over = float(1 - poisson.cdf(2, lh + la))
        p_btts = float((1 - math.exp(-lh)) * (1 - math.exp(-la)))
        return {
            "1": p1, "X": pX, "2": p2,
            "over25": p_over, "under25": 1 - p_over,
            "btts_yes": p_btts, "btts_no": 1 - p_btts,
            "lh": lh, "la": la,
        }


def build_current_ratings(conn=None, before_iso=None) -> Ratings:
    """Settle olmuş tüm maçlardan (opsiyonel: before_iso öncesi) rating kur.
    Canlı tahmin için: before_iso=None → tüm geçmiş; upcoming maçlar geleceği
    için leak yok."""
    own = conn is None
    if own:
        conn = db.connect()
    try:
        q = ("SELECT league_code, home_team, away_team, home_score, away_score "
             "FROM matches_v2 WHERE home_score IS NOT NULL AND away_score IS NOT NULL")
        params: tuple = ()
        if before_iso:
            q += " AND kickoff_utc < ?"
            params = (before_iso,)
        q += " ORDER BY kickoff_utc ASC"
        rows = conn.execute(q, params).fetchall()
    finally:
        if own:
            conn.close()
    R = Ratings()
    for r in rows:
        r = dict(r)
        try:
            R.update(r["league_code"], r["home_team"], r["away_team"],
                     int(r["home_score"]), int(r["away_score"]))
        except (TypeError, ValueError):
            continue
    return R


# Sinyal (market,pick) → bağımsız model olasılık anahtarı
PICK_KEY = {
    ("1X2", "1"): "1", ("1X2", "X"): "X", ("1X2", "2"): "2",
    ("KG_VAR", "VAR"): "btts_yes", ("KG_YOK", "YOK"): "btts_no",
    ("UST_25", "UST"): "over25", ("ALT_25", "ALT"): "under25",
}


def model_prob_for(probs: dict, market: str, pick: str):
    if not probs:
        return None
    return probs.get(PICK_KEY.get((market, pick)))


# ============================================================
# BACKTEST — leak-free rolling (dürüstlük: gerçekten sinyal var mı?)
# ============================================================
def backtest():
    BT = ("T1", "E0", "SP1", "D1", "I1", "F1")
    c = db.connect()
    rows = [dict(r) for r in c.execute(
        "SELECT league_code, kickoff_utc, home_team, away_team, home_score, away_score, "
        "closing_1, closing_X, closing_2, closing_over25, closing_under25 "
        "FROM matches_v2 WHERE home_score IS NOT NULL AND closing_1 IS NOT NULL "
        "ORDER BY kickoff_utc ASC").fetchall()]
    c.close()

    R = Ratings()
    preds = []
    for r in rows:
        if r["league_code"] in BT:
            p = R.predict(r)
            if p and r["closing_1"] and r["closing_X"] and r["closing_2"]:
                inv = [1 / r["closing_1"], 1 / r["closing_X"], 1 / r["closing_2"]]
                t = sum(inv); imp = {k: v / t for k, v in zip("1X2", inv)}
                res = ("1" if r["home_score"] > r["away_score"]
                       else "2" if r["home_score"] < r["away_score"] else "X")
                preds.append({"p": p, "imp": imp,
                              "odds": {"1": r["closing_1"], "X": r["closing_X"], "2": r["closing_2"]},
                              "res": res})
        try:
            R.update(r["league_code"], r["home_team"], r["away_team"],
                     int(r["home_score"]), int(r["away_score"]))
        except (TypeError, ValueError):
            pass

    print(f"Leak-free tahmin (6 lig, yeterli geçmiş + oran): {len(preds)}")
    if not preds:
        print("Yeterli veri yok."); return

    brier = np.mean([sum((pr["p"][o] - (1 if pr["res"] == o else 0))**2 for o in "1X2") for pr in preds])
    brier_m = np.mean([sum((pr["imp"][o] - (1 if pr["res"] == o else 0))**2 for o in "1X2") for pr in preds])
    print(f"Brier (düşük=iyi): MODEL {brier:.4f}  vs  PİYASA {brier_m:.4f}  "
          f"→ {'model rekabetçi' if brier <= brier_m + 0.005 else 'model piyasanın gerisinde'}")

    print(f"\n{'Eşik':>6} {'Bahis':>6} {'İsabet':>7} {'ROI':>8} {'vergi sonrası':>14}")
    print("-" * 50)
    for T in (0.03, 0.05, 0.08, 0.12):
        n = won = 0; pnl = pnl_t = 0.0
        for pr in preds:
            for o in "1X2":
                if pr["p"][o] - pr["imp"][o] > T:
                    n += 1
                    if pr["res"] == o:
                        won += 1; g = pr["odds"][o] - 1; pnl += g; pnl_t += g * 0.90
                    else:
                        pnl -= 1; pnl_t -= 1
        if n:
            print(f"{T:>6.2f} {n:>6} {100*won//n:>6}% {100*pnl/n:>+7.1f}% {100*pnl_t/n:>+13.1f}%")
        else:
            print(f"{T:>6.2f} {n:>6}      -        -")
    print("-" * 50)
    print("Pozitif ROI = gol-modeli edge sinyali var. ~0/negatif = beklendiği gibi "
          "kapanış verimli; ama 'edge' artık GERÇEK anlaşmazlık (favori değil) → CLV ölçer.")


if __name__ == "__main__":
    backtest()
