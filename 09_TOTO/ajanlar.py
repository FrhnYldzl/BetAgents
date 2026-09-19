"""
TOTO · AJANLAR — her biri maç başına kendi 1/0/2 olasılığını ve gerekçesini üretir
==================================================================================
Ajanlar BİRBİRİNDEN BAĞIMSIZ bilgi kaynaklarına bakar; Toto Master onları bir
"tahmin pazarında" (pazar.py) yarıştırır — kim geçmişte haklı çıktıysa sesi büyür.

  PİYASA  bahis piyasasının marjı temizlenmiş fiyatı (Pinnacle kapanış / iddaa)
  ELO     takım gücü: kulüplerde lig içi Elo (gol farkı çarpanlı, ev avantajı
          ligden öğrenilir), millilerde Dünya Futbol Elo kuralları (turnuva ağırlığı)
  FORM    son 1 yılın gol verisinden zaman ağırlıklı Poisson hücum/savunma modeli
  H2H     iki takımın aralarındaki maçlar — Elo görüşüne doğru büzülmüş (az veri
          çok konuşmasın diye)

Hiçbiri kalabalık tahmini (q) yapmaz; q ayrı modeldir (kalabalik.py).
"""
from __future__ import annotations

import math
from collections import defaultdict

import numpy as np
import pandas as pd

SONUC_SKOR = np.array([1.0, 0.5, 0.0])          # indeks 0=ev kazandı, 1=beraberlik, 2=deplasman


def _gol_carpani(fark: float) -> float:
    fark = abs(fark)
    if fark <= 1:
        return 1.0
    if fark == 2:
        return 1.5
    return (11.0 + fark) / 8.0


# ── Kulüp Elo ────────────────────────────────────────────────────
ULKE = {"E0": "ENG", "E1": "ENG", "E2": "ENG", "SC0": "SCO", "SC1": "SCO", "D1": "GER", "D2": "GER",
        "I1": "ITA", "I2": "ITA", "SP1": "ESP", "SP2": "ESP", "F1": "FRA", "F2": "FRA"}
def elo_kulup(K: pd.DataFrame, k: float = 20.0, h0: float = 60.0, k_ev: float = 0.8, baslangic: float = 1500.0):
    """Kronolojik tek geçiş. Her satır için MAÇ ÖNCESİ (ev, dep, ev_avantaji) döner.
    Takım ligler arasında gezse de puanı taşınır (küme düşme/çıkma)."""
    r = defaultdict(lambda: baslangic)
    h = defaultdict(lambda: h0)
    n = len(K)
    once = np.zeros((n, 3))
    ev, dep, lig = K["ev"].values, K["dep"].values, K["lig"].values
    ge, gd, son = K["ge"].values, K["gd"].values, K["sonuc"].values
    for i in range(n):
        L = lig[i]
        u = ULKE.get(L, L)
        ka, kb = (u, ev[i]), (u, dep[i])          # aynı ülkenin ligleri tek puan havuzu
        ra, rb, hl = r[ka], r[kb], h[L]
        once[i] = (ra, rb, hl)
        if son[i] != son[i] or np.isnan(ge[i]) or np.isnan(gd[i]):
            continue
        e = 1.0 / (1.0 + 10 ** (-(ra + hl - rb) / 400.0))
        s = SONUC_SKOR[int(son[i])]
        d = k * _gol_carpani(ge[i] - gd[i]) * (s - e)
        r[ka] = ra + d
        r[kb] = rb - d
        h[L] = hl + k_ev * (s - e)
    elo_kulup.son = (dict(r), dict(h))          # son puanlar (canlı hafta ve eşleşmeyen maçlar için)
    return once


# ── Milli Elo (Dünya Futbol Elo kuralları) ───────────────────────
def _k_milli(turnuva: str) -> float:
    t = (turnuva or "").lower()
    if t == "fifa world cup":
        return 60.0
    if t in ("uefa euro", "copa américa", "afc asian cup", "african cup of nations", "gold cup",
             "concacaf championship"):
        return 50.0
    if "qualification" in t or "nations league" in t:
        return 40.0
    if t == "friendly":
        return 20.0
    return 30.0


def elo_milli(M: pd.DataFrame, baslangic: float = 1500.0, ev_avantaji: float = 100.0):
    r = defaultdict(lambda: baslangic)
    n = len(M)
    once = np.zeros((n, 3))
    ev, dep, ge, gd = M["ev"].values, M["dep"].values, M["ge"].values, M["gd"].values
    son, tur, taraf = M["sonuc"].values, M["turnuva"].values, M["tarafsiz"].values
    for i in range(n):
        ra, rb = r[ev[i]], r[dep[i]]
        hl = 0.0 if taraf[i] else ev_avantaji
        once[i] = (ra, rb, hl)
        if son[i] < 0:
            continue
        e = 1.0 / (1.0 + 10 ** (-(ra + hl - rb) / 400.0))
        s = SONUC_SKOR[int(son[i])]
        d = _k_milli(tur[i]) * _gol_carpani(ge[i] - gd[i]) * (s - e)
        r[ev[i]] = ra + d
        r[dep[i]] = rb - d
    return once, r


# ── Elo farkı → 1/0/2 (sıralı lojit) ─────────────────────────────
def _sig(x):
    return 1.0 / (1.0 + np.exp(-x))


def sirali_lojit_fit(d: np.ndarray, y: np.ndarray, iter_: int = 60):
    """z = b·d; P(dep) = σ(t1 − z), P(ev) = 1 − σ(t2 − z), P(ber) = arası.
    d: Elo farkı/400 (ev avantajı dahil). Newton benzeri basit gradyan inişi."""
    b, t1, t2 = 1.5, -0.6, 0.6
    lr = 0.5
    for _ in range(iter_ * 20):
        z = b * d
        F1, F2 = _sig(t1 - z), _sig(t2 - z)
        p0 = np.clip(1 - F2, 1e-9, 1)          # ev
        p1 = np.clip(F2 - F1, 1e-9, 1)         # beraberlik
        p2 = np.clip(F1, 1e-9, 1)              # deplasman
        f1, f2 = F1 * (1 - F1), F2 * (1 - F2)
        # log-olabilirliğin türevleri
        g_t1 = np.where(y == 2, f1 / p2, np.where(y == 1, -f1 / p1, 0.0))
        g_t2 = np.where(y == 1, f2 / p1, np.where(y == 0, -f2 / p0, 0.0))
        g_z = np.where(y == 0, f2 / p0, np.where(y == 1, (f1 - f2) / p1, -f1 / p2))
        b += lr * np.mean(g_z * d)
        t1 += lr * np.mean(g_t1)
        t2 += lr * np.mean(g_t2)
        if t2 <= t1 + 0.05:
            t2 = t1 + 0.05
    return b, t1, t2


def sirali_lojit_p(d, b, t1, t2) -> np.ndarray:
    z = b * np.asarray(d, float)
    F1, F2 = _sig(t1 - z), _sig(t2 - z)
    p = np.stack([1 - F2, F2 - F1, F1], axis=-1)
    return np.clip(p, 1e-4, 1) / np.clip(p, 1e-4, 1).sum(-1, keepdims=True)


# ── FORM: zaman ağırlıklı Poisson hücum/savunma ───────────────────
def form_poisson(gecmis: pd.DataFrame, tarih: pd.Timestamp, yari_omur_gun: float = 120.0,
                 iterasyon: int = 25) -> dict | None:
    """gecmis: aynı ligin tarih öncesi maçları (ev, dep, ge, gd, tarih).
    Dönen: {'hucum':{}, 'savunma':{}, 'ev':çarpan, 'ort':lig gol ort.}"""
    g = gecmis[(gecmis["tarih"] < tarih) & (gecmis["tarih"] >= tarih - pd.Timedelta(days=400))]
    g = g[g["ge"].notna() & g["gd"].notna()]
    if len(g) < 60:
        return None
    w = 0.5 ** ((tarih - g["tarih"]).dt.days.values / yari_omur_gun)
    ev, dep = g["ev"].values, g["dep"].values
    ge, gd = g["ge"].values.astype(float), g["gd"].values.astype(float)
    takimlar = sorted(set(ev) | set(dep))
    ix = {t: i for i, t in enumerate(takimlar)}
    ei = np.array([ix[t] for t in ev]); di = np.array([ix[t] for t in dep])
    n = len(takimlar)
    A = np.ones(n); Dv = np.ones(n)
    mu = (np.sum(w * (ge + gd)) / np.sum(w)) / 2.0
    ev_c = max(np.sum(w * ge) / max(np.sum(w * gd), 1e-9), 0.8) ** 0.5
    for _ in range(iterasyon):
        # beklenen: ev gol = mu·ev_c·A[e]·D[d]; dep gol = mu/ev_c·A[d]·D[e]
        payA = np.bincount(ei, w * ge, n) + np.bincount(di, w * gd, n)
        paydaA = np.bincount(ei, w * mu * ev_c * Dv[di], n) + np.bincount(di, w * mu / ev_c * Dv[ei], n)
        A = (payA + 2.0) / (paydaA + 2.0)                    # hafif önsel (1,0'a çekiş)
        payD = np.bincount(di, w * ge, n) + np.bincount(ei, w * gd, n)
        paydaD = np.bincount(di, w * mu * ev_c * A[ei], n) + np.bincount(ei, w * mu / ev_c * A[di], n)
        Dv = (payD + 2.0) / (paydaD + 2.0)
        A /= np.exp(np.mean(np.log(A))); Dv /= np.exp(np.mean(np.log(Dv)))
        tah_ev = np.sum(w * mu * ev_c * A[ei] * Dv[di]); tah_dep = np.sum(w * mu / ev_c * A[di] * Dv[ei])
        ev_c *= (np.sum(w * ge) / tah_ev * tah_dep / max(np.sum(w * gd), 1e-9)) ** 0.25
    return {"hucum": dict(zip(takimlar, A)), "savunma": dict(zip(takimlar, Dv)), "ev": ev_c, "ort": mu,
            "n": len(g)}


def poisson_1x2(lam: float, mu: float, rho: float = -0.05, maks: int = 10) -> np.ndarray:
    """Dixon-Coles düşük skor düzeltmeli bağımsız Poisson → (ev, beraberlik, dep)."""
    i = np.arange(maks + 1)
    pa = np.exp(-lam) * lam ** i / np.array([math.factorial(k) for k in i])
    pb = np.exp(-mu) * mu ** i / np.array([math.factorial(k) for k in i])
    M = np.outer(pa, pb)
    M[0, 0] *= 1 - lam * mu * rho
    M[0, 1] *= 1 + lam * rho
    M[1, 0] *= 1 + mu * rho
    M[1, 1] *= 1 - rho
    M /= M.sum()
    return np.array([np.tril(M, -1).sum(), np.trace(M), np.triu(M, 1).sum()])


def form_p(model: dict, ev: str, dep: str) -> np.ndarray | None:
    if model is None or ev not in model["hucum"] or dep not in model["hucum"]:
        return None
    lam = model["ort"] * model["ev"] * model["hucum"][ev] * model["savunma"][dep]
    mu = model["ort"] / model["ev"] * model["hucum"][dep] * model["savunma"][ev]
    return poisson_1x2(lam, mu)


# ── H2H: aralarındaki maçlar, Elo görüşüne büzülmüş ───────────────
def h2h_p(gecmis: pd.DataFrame, ev: str, dep: str, tarih, onsel: np.ndarray, kappa: float = 8.0,
          yil: int = 8) -> tuple[np.ndarray, int]:
    g = gecmis[(gecmis["tarih"] < tarih) & (gecmis["tarih"] >= pd.Timestamp(tarih) - pd.Timedelta(days=365 * yil))]
    a = g[(g["ev"] == ev) & (g["dep"] == dep)]
    b = g[(g["ev"] == dep) & (g["dep"] == ev)]
    say = np.zeros(3)
    for s in a["sonuc"].values:
        if s == s and s >= 0:
            say[int(s)] += 1.0
    for s in b["sonuc"].values:                      # ters sahada: ev/dep yer değiştirir, ev avantajı yok sayılır
        if s == s and s >= 0:
            say[2 - int(s)] += 0.7
    n = say.sum()
    return (say + kappa * onsel) / (n + kappa), int(len(a) + len(b))
