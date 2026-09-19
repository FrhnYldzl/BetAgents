"""
TOTO · KALABALIK (q) MODELİ — Türkiye'deki Toto oyuncuları hangi sonucu ne sıklıkla işaretliyor?
================================================================================================
Tek gözlem: her haftanın 15/14/13/12 kazanan kolon sayısı. Kalabalığın kolonlarını
maç maç bağımsız sayıp Poisson-binom ile "tam k doğru" olasılığını hesaplar,
kolon sayısıyla (N = D / (ρ·kolon_bedeli·s)) çarpar, gözlenenle negatif binom
olabilirlikle karşılaştırırız.

    q_i(s) ∝ exp( β_aile·log p_i(s) + α_s + γ_TR·[s Türk büyüğünün galibiyeti] + γ_EU·[s Avrupa devinin galibiyeti] )

  β_aile > 1 → kalabalık favoriye piyasadan FAZLA yığılıyor. β lig AİLESİNE göre ayrı:
               Süper Lig / büyük Avrupa haftasında kalabalık takımları tanır ve favoriye
               yığılır; yaz haftalarında (İsveç, Norveç, Asya) tanımaz, dağınık oynar.
  γ > 0      → popüler takımların galibiyeti ayrıca fazla oynanıyor
  α          → beraberlik/deplasman için ayrı sapma
  log_s      → sezon başına ölçek (kolon bedeli tarihçesindeki belirsizliği emer)

Referans p: kalabalığın gördüğü piyasa fiyatı (varsa), yoksa ajan pazarı fiyatı.
Oranı hiç olmayan maç (ör. TFF 1. Lig) için kalabalık payı sonuç türüne göre sabit (u).

Üretimde yalnız numpy (uygula); kalibrasyon scipy ister (yerelde, `kalibre_et`).
"""
from __future__ import annotations

import json

import numpy as np

from toto_ortak import KADEME_PAY, KOK, RHO, kolon_bedeli

PARAM_DOSYA = KOK / "model_parametre.json"
BETA_GRUP = {"TR-UST": "TR", "TR-ALT": "TR", "EU-BIG": "BIG", "KUPA": "BIG", "EU-ALT": "ALT",
             "DUNYA": "DUNYA", "MILLI": "MILLI"}
GRUPLAR = ("TR", "BIG", "ALT", "DUNYA", "MILLI")
VARSAYILAN = {"beta": {"TR": 1.57, "BIG": 1.57, "ALT": 1.2, "DUNYA": 1.0, "MILLI": 1.3},
              "a0": 0.03, "a2": -0.07, "gTR": 0.30, "gEU": 0.31, "gTRM": 0.5, "u0": -1.09, "u2": -0.97,
              "log_s": {}, "logphi": [-0.24, 0.17, 0.48, 0.82]}


def grup(aile: str | None) -> str:
    return BETA_GRUP.get(aile or "", "ALT")


def parametreler() -> dict:
    try:
        return {**VARSAYILAN, **json.loads(PARAM_DOSYA.read_text(encoding="utf-8"))["kalabalik"]}
    except Exception:
        return dict(VARSAYILAN)


def q_uret(p: np.ndarray, pop_tr: np.ndarray, pop_eu: np.ndarray, th: dict, aile=None) -> np.ndarray:
    """p: (n,3) referans olasılık · pop_*: (n,2) [ev, dep] bayrakları · aile: n lig ailesi → q: (n,3)"""
    p = np.clip(np.asarray(p, float), 1e-4, 1.0)
    n = len(p)
    aile = list(aile) if aile is not None else ["EU-BIG"] * n
    b = np.array([th["beta"][grup(a)] for a in aile], float)[:, None]
    ptr = np.zeros_like(p); ptr[:, 0] = pop_tr[:, 0]; ptr[:, 2] = pop_tr[:, 1]
    peu = np.zeros_like(p); peu[:, 0] = pop_eu[:, 0]; peu[:, 2] = pop_eu[:, 1]
    milli = np.array([grup(a) == "MILLI" for a in aile], float)[:, None]
    g_tr = th["gTR"] * (1 - milli) + th.get("gTRM", th["gTR"]) * milli     # Türkiye milli takımı ayrı
    u = b * np.log(p) + np.array([0.0, th["a0"], th["a2"]]) + g_tr * ptr + th["gEU"] * peu
    u -= u.max(1, keepdims=True)
    q = np.exp(u)
    return q / q.sum(1, keepdims=True)


def q_sabit(th: dict) -> np.ndarray:
    a = np.array([0.0, th["u0"], th["u2"]])
    return np.exp(a) / np.exp(a).sum()


def pb_ust(x: np.ndarray) -> np.ndarray:
    """Poisson-binom: başarı olasılıkları x (15) → P(tam 15, 14, 13, 12)."""
    n = len(x)
    f = np.zeros(n + 1); f[0] = 1.0
    for v in x:
        f[1:] = f[1:] * (1 - v) + f[:-1] * v
        f[0] *= (1 - v)
    return f[[n, n - 1, n - 2, n - 3]]


def sezon_olcek(th: dict, sezon: str | None) -> float:
    ls = th.get("log_s") or {}
    if sezon in ls:
        return float(ls[sezon])
    return float(ls[sorted(ls)[-1]]) if ls else 0.0         # yeni sezon → son bilinen


def kolon_sayisi(D: float, tarih: str, th: dict, sezon: str | None = None) -> float:
    return D / (RHO * kolon_bedeli(tarih) * np.exp(sezon_olcek(th, sezon)))


# ── Kalibrasyon (yalnız yerel — scipy) ────────────────────────────
def hafta_ozeti(hafta_satirlari, p_sutun: str = "p_ref") -> dict | None:
    """Bir haftanın maç satırları (veri seti) → kalibrasyon girdisi."""
    ps, tr, eu, oc, unc, ai = [], [], [], [], [], []
    for r in hafta_satirlari:
        if r["sonuc"] is None or r["sonuc"] != r["sonuc"]:
            return None
        p = r.get(p_sutun)
        if p is not None and not r["noter"]:
            ps.append(p); tr.append(r["pop_tr"]); eu.append(r["pop_eu"]); oc.append(int(r["sonuc"]))
            ai.append(r.get("aile"))
        else:
            unc.append(int(r["sonuc"]))
    return {"p": np.array(ps, float).reshape(-1, 3), "tr": np.array(tr, float).reshape(-1, 2),
            "eu": np.array(eu, float).reshape(-1, 2), "oc": np.array(oc, int), "unc": np.array(unc, int),
            "aile": ai, "sezon": (hafta_satirlari[0].get("sezon") if hafta_satirlari else None)}


def beklenen(ozet: dict, D: float, tarih: str, th: dict) -> np.ndarray:
    """Gerçekleşen sonuç verildiğinde beklenen kazanan sayıları (N15, N14, N13, N12)."""
    x = []
    if len(ozet["oc"]):
        q = q_uret(ozet["p"], ozet["tr"], ozet["eu"], th, ozet.get("aile"))
        x.append(q[np.arange(len(ozet["oc"])), ozet["oc"]])
    if len(ozet["unc"]):
        x.append(q_sabit(th)[ozet["unc"]])
    x = np.concatenate(x)
    return kolon_sayisi(D, tarih, th, ozet.get("sezon")) * pb_ust(x)


_SABIT_AD = ["a0", "a2", "gTR", "gEU", "gTRM", "u0", "u2", "lp15", "lp14", "lp13", "lp12"]


def _adlar(sezonlar) -> list[str]:
    return [f"beta_{g}" for g in GRUPLAR] + _SABIT_AD + [f"ls_{s}" for s in sezonlar]


def _th(v, sezonlar) -> dict:
    d = dict(zip(_adlar(sezonlar), v))
    th = {"beta": {g: float(d[f"beta_{g}"]) for g in GRUPLAR},
          "log_s": {s: float(d[f"ls_{s}"]) for s in sezonlar},
          "logphi": [float(d["lp15"]), float(d["lp14"]), float(d["lp13"]), float(d["lp12"])]}
    th.update({a: float(d[a]) for a in ("a0", "a2", "gTR", "gEU", "gTRM", "u0", "u2")})
    return th


def nll(v, veri, sezonlar) -> float:
    from scipy.special import gammaln
    th = _th(v, sezonlar)
    phi = np.exp(np.array(th["logphi"]))
    t = 0.0
    for ozet, y, D, tarih in veri:
        m = np.maximum(beklenen(ozet, D, tarih, th), 1e-12)
        t += np.sum(gammaln(y + phi) - gammaln(phi) - gammaln(y + 1) + phi * np.log(phi / (phi + m))
                    + y * np.log(m / (phi + m)))
    return -t


def kalibre_et(veri, baslangic: dict | None = None, sabit: dict | None = None) -> tuple[dict, float]:
    """veri: [(ozet, y(4), D, kapanis_iso)] → (parametreler, NLL).
    Verisi olmayan β grubu sabit kalır (başlangıç değerinde)."""
    from scipy.optimize import minimize
    b = {**VARSAYILAN, **(baslangic or {})}
    sezonlar = sorted({oz.get("sezon") for oz, _, _, _ in veri if oz.get("sezon")})
    ad = _adlar(sezonlar)
    ls0 = b.get("log_s") or {}
    x0 = np.array([b["beta"][g] for g in GRUPLAR] + [b["a0"], b["a2"], b["gTR"], b["gEU"], b.get("gTRM", 0.5),
                                                     b["u0"], b["u2"], *b["logphi"]]
                  + [ls0.get(s, 0.0) for s in sezonlar], float)
    gorulen = {grup(a) for oz, _, _, _ in veri for a in (oz.get("aile") or [])}
    sabit = dict(sabit or {})
    for g in GRUPLAR:
        if g not in gorulen:
            sabit.setdefault(f"beta_{g}", b["beta"][g])
    serbest = [i for i, a in enumerate(ad) if a not in sabit]
    for a, v in sabit.items():
        if a in ad:
            x0[ad.index(a)] = v

    def f(z):
        x = x0.copy(); x[serbest] = z
        return nll(x, veri, sezonlar)
    r = minimize(f, x0[serbest], method="L-BFGS-B")
    x = x0.copy(); x[serbest] = r.x
    return _th(x, sezonlar), float(r.fun)
