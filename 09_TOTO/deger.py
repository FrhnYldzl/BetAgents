"""
TOTO · DEĞER MOTORU — sistem kuponunun beklenen getirisi ve kupon kurucu
========================================================================
Sistem kuponu: her maç için işaretlenen sonuç kümesi S_i (1, 2 ya da 3 işaret);
kolonlar kartezyen çarpım, kolon sayısı Π|S_i| (≤ 2.500, oyun planı m.8/4).

Bir sonuç vektörü o gerçekleşince:
  bizim tam-k doğru kolon sayımız  n_k = [k ≤ A]·Π_{kaçan} |S_i| · e_{A−k}({|S_i|−1 : tutan})
      (A = işaretlerimiz arasında doğru sonucun bulunduğu maç sayısı)
  kalabalığın tam-k kazananı        X_k ~ Poisson(λ_k),  λ_k = N·PB_k(q(o))
      PB_15 = Π x_i,  PB_14 = PB_15·e1(r),  PB_13 = PB_15·e2(r),  PB_12 = PB_15·e3(r),
      x_i = q_i(o_i),  r_i = (1 − x_i)/x_i   (simetrik fonksiyonlar → O(15), DP yok)
  bizim ödememiz                    Σ_k havuz_k · E[n_k / (n_k + X_k)]
      (m.10/3: kolon yalnız en üst derecesinden alır; kendi kolonlarımız da
       aynı derecede birbirini seyreltir → n_k paydada)

Beklenen değer önem örneklemesiyle (sonuçlar S'ye doğru eğilmiş dağılımdan
çekilir, ağırlıkla düzeltilir) — 15'li gibi nadir olaylar da yeterince görülür.
15. derece katkısı ayrıca TAM hesaplanır (S içindeki her sonuç tek tek).

Profiller:
  FAVORİ      P(15)'i en çok yapan sistem (klasik yaklaşım — karşılaştırma için)
  15_AVCISI   15 isabetinin BEKLENEN DEĞERİNİ en çok yapan sistem: hem olası hem
              kalabalığın az oynadığı 15'ler ("değerli 15")
  DENGELİ     dört derecenin toplam beklenen getirisini en çok yapan sistem
"""
from __future__ import annotations

import itertools
import math

import numpy as np

from toto_ortak import MAX_KOLON

KADEMELER = (15, 14, 13, 12)


# ── yardımcılar ───────────────────────────────────────────────────
def boyut(S) -> int:
    return int(np.prod([len(s) for s in S]))


def kolonlar(S) -> np.ndarray:
    return np.array(list(itertools.product(*S)), dtype=np.int8)


def _e123(v: np.ndarray, maske: np.ndarray | None = None):
    """Son eksen boyunca elemanter simetrik fonksiyonlar e1, e2, e3 (maskeli)."""
    if maske is not None:
        v = np.where(maske, v, 0.0)
    s1 = v.sum(-1); s2 = (v * v).sum(-1); s3 = (v * v * v).sum(-1)
    e1 = s1
    e2 = (s1 * s1 - s2) / 2.0
    e3 = (s1 ** 3 - 3 * s1 * s2 + 2 * s3) / 6.0
    return e1, np.maximum(e2, 0.0), np.maximum(e3, 0.0)


def _pay_bekleneni(n: np.ndarray, lam: np.ndarray) -> np.ndarray:
    """E[n/(n+X)], X~Poisson(λ). n=1 için kesin; n≥2 için n/(n+λ) (Jensen payı küçük)."""
    lam = np.maximum(lam, 0.0)
    tek = np.where(lam < 1e-9, 1.0 - lam / 2.0, -np.expm1(-lam) / np.maximum(lam, 1e-300))
    cok = n / np.maximum(n + lam, 1e-300)
    return np.where(n <= 0, 0.0, np.where(n == 1, tek, cok))


# ── 15. derece: TAM hesap ─────────────────────────────────────────
def v15(S, P, Q, N, havuz15) -> tuple[float, float, float]:
    """(beklenen 15 getirisi TL, P(15), 15 gelirse beklenen ikramiye TL)"""
    C = kolonlar(S)
    idx = np.arange(15)
    pc = np.prod(P[idx, C], axis=1)
    lam = N * np.prod(Q[idx, C], axis=1)
    f = _pay_bekleneni(np.ones_like(lam), lam)
    ev = float(np.sum(pc * f) * havuz15)
    p15 = float(pc.sum())
    return ev, p15, (ev / p15 if p15 > 0 else 0.0)


# ── 14. derece: TAM hesap ─────────────────────────────────────────
def _lam14(Cidx, Q, N):
    idx = np.arange(15)
    x = np.clip(Q[idx, Cidx], 1e-12, 1)
    r = (1.0 - x) / x
    return N * np.prod(x, axis=1) * r.sum(1)


def v14(S, P, Q, N, havuz14) -> float:
    """14'lünün beklenen getirisi (TL), tam. İki tür sonuç 14'lü verir:
      o ∈ S (hepsi tuttu)         → bizim 14'lü kolon sayımız Σ(|S_i|−1)
      o tek maçta S dışı (j'de)    → bizim 14'lü kolon sayımız |S_j|"""
    idx = np.arange(15)
    uz = [len(x) for x in S]
    n_ic = sum(u - 1 for u in uz)
    top = 0.0
    if n_ic > 0:
        C = kolonlar(S)
        top += float(np.sum(np.prod(P[idx, C], axis=1) * _pay_bekleneni(np.full(len(C), float(n_ic)), _lam14(C, Q, N))))
    for j in range(15):
        for o in range(3):
            if o in S[j]:
                continue
            T = list(S); T[j] = (o,)
            C = kolonlar(T)
            top += float(np.sum(np.prod(P[idx, C], axis=1) * _pay_bekleneni(np.full(len(C), float(uz[j])), _lam14(C, Q, N))))
    return top * havuz14


# ── 12–13: önem örneklemesi (aday başına eğik öneri, ortak rastgele sayılar) ──
class Degerlendirici:
    def __init__(self, P, Q, N, havuz: dict, M: int = 12000, tohum: int = 7, egim: float = 0.85):
        self.P = np.clip(np.asarray(P, float), 1e-9, 1)
        self.Q = np.clip(np.asarray(Q, float), 1e-12, 1)
        self.N = float(N)
        self.havuz = havuz
        self.M = M
        self.egim = egim
        self.U = np.random.default_rng(tohum).random((M, 15))
        self._onb = {}

    def hazirla(self, S_ref):                   # geriye uyum (kurucu çağırır) — artık gerekmiyor
        return

    def _oneri(self, S):
        g = np.zeros((15, 3))
        for i, s in enumerate(S):
            ic = np.zeros(3, bool); ic[list(s)] = True
            pin, pout = self.P[i][ic].sum(), self.P[i][~ic].sum()
            if pout <= 1e-12 or len(s) == 3:
                g[i] = self.P[i]
            else:
                w = max(self.egim, pin)
                g[i, ic] = w * self.P[i][ic] / pin
                g[i, ~ic] = (1 - w) * self.P[i][~ic] / pout
        return g

    def _mc(self, S):
        g = self._oneri(S)
        cdf = np.cumsum(g, 1)
        O = (self.U[:, :, None] > cdf[None, :, :]).sum(2).clip(0, 2)
        idx = np.arange(15)[None, :]
        w = np.prod(self.P[idx, O] / g[idx, O], axis=1)
        uz = np.array([len(x) for x in S], float)
        icinde = np.zeros((15, 3), bool)
        for i, x in enumerate(S):
            icinde[i, list(x)] = True
        a = icinde[idx, O]
        A = a.sum(1)
        b = np.where(a, uz[None, :] - 1.0, 0.0)
        kacan = np.prod(np.where(a, 1.0, uz[None, :]), axis=1)
        e1b, e2b, e3b = _e123(b)
        eb = (np.ones_like(e1b), e1b, e2b, e3b)
        x = self.Q[idx, O]
        r = (1.0 - x) / x
        pb15 = np.prod(x, axis=1)
        _, e2r, e3r = _e123(r)
        lam = {13: self.N * pb15 * e2r, 12: self.N * pb15 * e3r}
        ev = {}
        for k in (13, 12):
            j = A - k
            nk = np.zeros(self.M)
            for jj in range(4):
                sec = j == jj
                if sec.any():
                    nk[sec] = kacan[sec] * eb[jj][sec]
            ev[k] = float(np.mean(w * self.havuz[k] * _pay_bekleneni(nk, lam[k])))
        return ev, w, A

    def ev(self, S) -> float:
        key = tuple(tuple(x) for x in S)
        if key not in self._onb:
            e13 = self._mc(S)[0]
            self._onb[key] = (v15(S, self.P, self.Q, self.N, self.havuz[15])[0]
                              + v14(S, self.P, self.Q, self.N, self.havuz[14]) + e13[13] + e13[12])
        return self._onb[key]

    def degerle(self, S) -> dict:
        e15, p15, od15 = v15(S, self.P, self.Q, self.N, self.havuz[15])
        e14 = v14(S, self.P, self.Q, self.N, self.havuz[14])
        e1213, w, A = self._mc(S)
        ev_k = {15: e15, 14: e14, 13: e1213[13], 12: e1213[12]}
        return {"ev": float(sum(ev_k.values())), "p15": p15, "odul15": od15,
                "p14p": float(np.mean(w * (A >= 14))), "p13p": float(np.mean(w * (A >= 13))),
                "p12p": float(np.mean(w * (A >= 12))), "ev_k": ev_k}


# ── kupon kurucu ──────────────────────────────────────────────────
def _tek_en_iyi(amac, S0, hazirla=None, en_cok_tur: int = 4):
    """Koordinat yükselişi: her maçta tek işaret, amaç en büyük.
    Örneklemli amaçta her tur sonunda örneklem yeni kupona göre tazelenir;
    tur sayısı sınırlı (örneklem gürültüsü sonsuz döngü yaratmasın)."""
    S = [tuple(s) for s in S0]
    if hazirla:
        hazirla(S)
    v = amac(S)
    for _tur in range(en_cok_tur):
        iy = False
        for i in range(15):
            for o in range(3):
                if (o,) == S[i]:
                    continue
                T = list(S); T[i] = (o,)
                vt = amac(T)
                if vt > v * (1 + 1e-9) + 1e-12:
                    S, v, iy = T, vt, True
        if not iy:
            return S, v
        if hazirla:
            hazirla(S)
            v = amac(S)
    return S, v


def kur(P, Q, N, havuz: dict, butce: int, profil: str = "15_AVCISI", deg: Degerlendirici | None = None):
    """Bütçe (en çok kolon) içinde profile göre sistem kuponu. Dönen: (S, amaç değeri)."""
    P = np.asarray(P, float); Q = np.asarray(Q, float)
    butce = int(min(butce, MAX_KOLON))
    if profil == "FAVORİ":
        return _favori(P, butce), None
    hazirla = None
    if profil == "15_AVCISI":
        amac = lambda S: v15(S, P, Q, N, havuz[15])[0]
    else:
        deg = deg or Degerlendirici(P, Q, N, havuz)
        amac = deg.ev
        hazirla = deg.hazirla
    bas = [(int(np.argmax(P[i])),) for i in range(15)]
    S, v = _tek_en_iyi(amac, bas, hazirla)
    while True:
        if hazirla:
            hazirla(S); v = amac(S)
        en = None
        for i in range(15):
            if len(S[i]) == 3:
                continue
            yeni_boy = boyut(S) // len(S[i]) * (len(S[i]) + 1)
            if yeni_boy > butce:
                continue
            for o in range(3):
                if o in S[i]:
                    continue
                T = list(S); T[i] = tuple(sorted(S[i] + (o,)))
                vt = amac(T)
                oran = (vt - v) / math.log((len(S[i]) + 1) / len(S[i]))
                if en is None or oran > en[0]:
                    en = (oran, T, vt)
        if en is None or en[2] <= v:
            break
        S, v = en[1], en[2]
        for i in range(15):                      # yerel iyileştirme: tek işaretli maçta değiştir
            if len(S[i]) != 1:
                continue
            for o in range(3):
                if (o,) == S[i]:
                    continue
                T = list(S); T[i] = (o,)
                vt = amac(T)
                if vt > v * (1 + 1e-9):
                    S, v = T, vt
    return S, v


def _favori(P, butce: int):
    """P(15) = Π P(S_i) en büyük — (çift, üçlü) sayıları üzerinde tam arama."""
    sirali = np.argsort(-P, axis=1)
    tek = np.log(P[np.arange(15), sirali[:, 0]])
    cift = np.log(P[np.arange(15), sirali[:, 0]] + P[np.arange(15), sirali[:, 1]])
    en, en_S = -np.inf, None
    for u in range(0, 8):
        for c in range(0, 12):
            if 2 ** c * 3 ** u > butce or c + u > 15:
                continue
            # DP yerine: her maç için (üçlü kazancı, çift kazancı) — küçük n'de açgözlü seçim yeterli
            kaz3 = -tek
            kaz2 = cift - tek
            secim = [0] * 15
            kalan = list(range(15))
            for _ in range(u):
                j = max(kalan, key=lambda i: kaz3[i]); secim[j] = 2; kalan.remove(j)
            for _ in range(c):
                j = max(kalan, key=lambda i: kaz2[i]); secim[j] = 1; kalan.remove(j)
            deger = sum(0.0 if secim[i] == 2 else (cift[i] if secim[i] == 1 else tek[i]) for i in range(15))
            if deger > en:
                en = deger
                en_S = [tuple(sorted(sirali[i, :secim[i] + 1].tolist())) for i in range(15)]
    return en_S


def gerceklesen(S, sonuc, n_gercek: dict, havuz_gercek: dict) -> dict:
    """Gerçek sonuç ve açıklanan ikramiyelerle kuponun ödemesi (kendi kolonlarımız eklenmiş)."""
    uz = np.array([len(s) for s in S], float)
    a = np.array([int(sonuc[i]) in S[i] for i in range(15)])
    A = int(a.sum())
    b = np.where(a, uz - 1.0, 0.0)
    kacan = float(np.prod(np.where(a, 1.0, uz)))
    e1, e2, e3 = _e123(b[None, :])
    eb = [1.0, float(e1[0]), float(e2[0]), float(e3[0])]
    odeme, nk = 0.0, {}
    for k in KADEMELER:
        j = A - k
        n = kacan * eb[j] if 0 <= j <= 3 else 0.0
        nk[k] = n
        if n > 0:
            odeme += n * havuz_gercek[k] / ((n_gercek.get(k) or 0) + n)
    return {"dogru_en_cok": A, "n": nk, "odeme": odeme, "kacan_mac": [i + 1 for i in range(15) if not a[i]]}
