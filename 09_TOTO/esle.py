"""
TOTO · EŞLEME — Toto maçını kaynak satırına bağlar
===================================================
Kulüp maçı → football-data (lig kodu Toto turnuvasından; bilinmiyorsa tüm ligler)
Milli maç  → uluslararası sonuçlar (Türkçe ad → İngilizce, MILLI_EN)

Benzerlik: kaynak adının jetonlarının karşı adda ne kadarının bulunduğu
(kısa adın kapsanması). "Tümosan Konyaspor" ↔ "Konyaspor" = 1,0;
"Manchester City" ↔ "Man United" = 0,5. Ev/deplasman çifti birlikte
puanlanır; tarih penceresi ±2 gün (Toto yerel saat, kaynak İngiltere/yerel).
Tarafsız sahada (Dünya Kupası vb.) kaynak ev/dep sırası farklı olabilir →
ters çift de denenir, eşleşirse sonuç ve olasılık aynalanır.
"""
from __future__ import annotations

import difflib
from collections import defaultdict
from functools import lru_cache

import numpy as np
import pandas as pd

from toto_ortak import ESDEGER, GENEL, MILLI_EN, norm, turnuva

_GENEL = set(GENEL) - {"real", "united", "city", "sporting"}


@lru_cache(maxsize=20000)
def jetonlar(ad: str) -> tuple[str, ...]:
    n = norm(ad)
    ek = []
    for a, b in ESDEGER.items():
        if a in n:
            ek.append(b)
    n = " ".join([n] + ek)
    return tuple(t for t in n.split() if t not in _GENEL and len(t) >= 2)


@lru_cache(maxsize=200000)
def _tsim(a: str, b: str) -> float:
    if a == b:
        return 1.0
    if min(len(a), len(b)) >= 3 and (a.startswith(b) or b.startswith(a)):
        return 0.9
    if len(a) == 2 or len(b) == 2:           # "sp" ↔ "sporting" gibi kısaltmalar
        return 0.85 if (a.startswith(b) or b.startswith(a)) else 0.0
    r = difflib.SequenceMatcher(None, a, b).ratio()
    return r if r >= 0.72 else 0.0


def benzer(toto_ad: str, kaynak_ad: str) -> float:
    ta, kb = jetonlar(toto_ad), jetonlar(kaynak_ad)
    if not ta or not kb:
        return 0.0
    kapsam_k = np.mean([max(_tsim(x, y) for y in ta) for x in kb])     # kaynak jetonları Toto adında
    kapsam_t = np.mean([max(_tsim(x, y) for y in kb) for x in ta])     # tersi (sponsorlu Toto adı cezalı)
    return float(max(kapsam_k, 0.6 * kapsam_k + 0.4 * kapsam_t))


def _gun(t) -> pd.Timestamp:
    return pd.Timestamp(str(t)[:10])


class Eslestirici:
    def __init__(self, kulup: pd.DataFrame, milli: pd.DataFrame):
        self.k_lig = defaultdict(list)          # lig → [(gün, idx)]
        for i, (lig, t) in enumerate(zip(kulup["lig"].values, kulup["tarih"].values)):
            self.k_lig[lig].append(i)
        self.kulup = kulup
        self.k_tarih = kulup["tarih"].values.astype("datetime64[D]")
        self.k_ev = kulup["ev"].values
        self.k_dep = kulup["dep"].values
        self.k_lig_arr = kulup["lig"].values
        self.milli = milli
        self.m_tarih = milli["tarih"].values.astype("datetime64[D]")
        self.m_ev = milli["ev"].values
        self.m_dep = milli["dep"].values
        self._lig_idx = {lig: np.array(v) for lig, v in self.k_lig.items()}

    def _aday(self, idx: np.ndarray, tarihler: np.ndarray, gun: np.datetime64, pencere: int) -> np.ndarray:
        if idx is None:
            m = np.abs((tarihler - gun).astype(int)) <= pencere
            return np.nonzero(m)[0]
        t = tarihler[idx]
        return idx[np.abs((t - gun).astype(int)) <= pencere]

    def kulup_esle(self, tarih: str, ev: str, dep: str, lig: str | None, pencere: int = 2):
        gun = np.datetime64(str(tarih)[:10])
        idx = self._lig_idx.get(lig) if lig else None
        if lig and idx is None:
            return None
        aday = self._aday(idx, self.k_tarih, gun, pencere)
        en, en_s = None, 0.0
        for i in aday:
            s = benzer(ev, self.k_ev[i]) + benzer(dep, self.k_dep[i])
            if s > en_s:
                en, en_s = i, s
        if en is not None and en_s >= 1.3:
            return {"kaynak": "kulup", "idx": int(en), "skor": round(en_s, 2), "ters": False}
        return None

    def milli_esle(self, tarih: str, ev: str, dep: str, pencere: int = 2):
        e1, e2 = MILLI_EN.get(ev.strip()), MILLI_EN.get(dep.strip())
        if not e1 or not e2:
            return None
        gun = np.datetime64(str(tarih)[:10])
        aday = self._aday(None, self.m_tarih, gun, pencere)
        for i in aday:
            if self.m_ev[i] == e1 and self.m_dep[i] == e2:
                return {"kaynak": "milli", "idx": int(i), "skor": 2.0, "ters": False}
        for i in aday:
            if self.m_ev[i] == e2 and self.m_dep[i] == e1:
                return {"kaynak": "milli", "idx": int(i), "skor": 2.0, "ters": True}
        return None

    def esle(self, mac: dict):
        """mac: {tarih, ev, dep, turnuva, milli}"""
        t = turnuva(mac.get("turnuva"))
        if mac.get("milli") or t.get("aile") == "MILLI":
            return self.milli_esle(mac["tarih"], mac["ev"], mac["dep"])
        lig = t.get("fd") or t.get("fdn")
        r = self.kulup_esle(mac["tarih"], mac["ev"], mac["dep"], lig) if lig else None
        if r is None and not lig:                 # kupa / bilinmeyen turnuva: tüm ligler, dar pencere
            r = self.kulup_esle(mac["tarih"], mac["ev"], mac["dep"], None, pencere=1)
            if r and r["skor"] < 1.7:
                r = None
        return r
