"""
TOTO · AJAN PAZARI — "Polymarket arka ucu" gibi çalışan tahmin pazarı
=====================================================================
Her maç 3 sonuçlu bir pazardır (1/0/2). Her ajanın bir CÜZDANI (serveti)
vardır ve her maçta servetinin bir kesrini (f) kendi inancına göre sonuçlara
dağıtır (Kelly bahisçisi). Parimutuel dengede pazar fiyatı:

    π(s) = Σ_a W_a · p_a(s) / Σ_a W_a          (servet ağırlıklı görüş ortalaması)

Sonuç o gelince cüzdanlar:  W_a ← W_a · (1 − f + f · p_a(o) / π(o))

Neden bu mekanizma (Beygelzimer–Langford–Pennock 2012, "Kelly bettors"):
  • servet, ajanın geçmişteki log-skoru kadar büyür → kim gerçekten bilgi
    katıyorsa sesi kendiliğinden artar; boş konuşan ajan fakirleşir;
  • toplam servet korunur (sıfır toplamlı) — ağırlıklar yorumlanabilir: "PİYASA
    pazarın %61'ine sahip" demek, geçmişte en isabetli onun olduğu demek;
  • her fiyat hareketi bir "işlem" olarak açıklanabilir (hangi ajan neyi aldı).
Noter çekilişiyle belirlenen maçlar cüzdanları GÜNCELLEMEZ (şans, beceri değil).
"""
from __future__ import annotations

import math

import numpy as np

AJANLAR = ("PİYASA", "ELO", "FORM", "H2H", "KADRO")
# KADRO sonradan katıldı (20.09.2026): geçmişte sakatlık verisi yok, bu yüzden
# geçmiş testte cüzdanı YOK. Küçük bir payla girer, değerini canlıda kanıtlar.
ONSEL_SERVET = {"PİYASA": 0.55, "ELO": 0.18, "FORM": 0.14, "H2H": 0.10, "KADRO": 0.03}
# Kulüp ve milli maçlar AYRI pazarlarda yarışır: geçmiş testte milli maçlarda en isabetli ajan H2H
# (log-kayıp 0,813) iken ortak cüzdan onun sesini kulüp maçlarındaki başarısına göre kısıyordu.
# Ayrı milli cüzdan (kesir 0,3) milli log-kaybı 0,835 → 0,826 indirdi.
KESIR = {"KULUP": 0.1, "MILLI": 0.3}


def aile_pazari(aile: str | None) -> str:
    return "MILLI" if aile == "MILLI" else "KULUP"


class Pazar:
    def __init__(self, servet: dict | None = None, kesir: float = 0.3, taban: float = 0.01,
                 yeni_pay: float = 0.03):
        W = dict(servet or ONSEL_SERVET)
        for a in AJANLAR:                      # sonradan eklenen ajan küçük payla katılır
            W.setdefault(a, yeni_pay)
        t = sum(W.values()) or 1.0
        self.W = {a: w / t for a, w in W.items()}
        self.f = kesir
        self.taban = taban                # hiçbir ajan tamamen sıfırlanmasın (yeniden öğrenebilsin)
        self.gecmis = []                  # (hafta_id, {ajan: servet})

    def fiyat(self, gorus: dict) -> tuple[np.ndarray | None, dict]:
        """gorus: {ajan: p(3) | None}. Dönen: (π, {ajan: pay})"""
        kat = {a: p for a, p in gorus.items() if p is not None and a in self.W}
        if not kat:
            return None, {}
        top = sum(self.W[a] for a in kat)
        pi = sum(self.W[a] * np.asarray(p, float) for a, p in kat.items()) / top
        pi = np.clip(pi, 1e-6, 1)
        return pi / pi.sum(), {a: self.W[a] / top for a in kat}

    def cozumle(self, gorus: dict, sonuc: int):
        pi, _ = self.fiyat(gorus)
        if pi is None:
            return
        for a, p in gorus.items():
            if p is None or a not in self.W:
                continue
            carpan = 1.0 - self.f + self.f * float(p[sonuc]) / float(pi[sonuc])
            self.W[a] = max(self.W[a] * carpan, self.taban * 1e-3)
        top = sum(self.W.values())
        for a in self.W:                   # normalize + taban
            self.W[a] = max(self.W[a] / top, self.taban)
        top = sum(self.W.values())
        for a in self.W:
            self.W[a] /= top

    def islemler(self, gorus: dict) -> list[dict]:
        """Açıklama: her ajanın fiyata etkisi ('neyi aldı'): kendi görüşü − pazar fiyatı."""
        pi, pay = self.fiyat(gorus)
        out = []
        if pi is None:
            return out
        for a, p in gorus.items():
            if p is None or a not in pay:
                continue
            fark = np.asarray(p) - pi
            s = int(np.argmax(fark))
            out.append({"ajan": a, "pay": pay[a], "aldigi": ("1", "0", "2")[s],
                        "fark": float(fark[s]), "gorus": [float(x) for x in p]})
        return sorted(out, key=lambda x: -x["pay"])


def ileri_yurut(df, servet: dict | None = None):
    """Veri setini kronolojik yürüt: her maçın pazar fiyatı (o haftanın cüzdanlarıyla).
    Kulüp ve milli maçlar ayrı pazarlarda. Dönen: (pi serisi df sırasıyla, {"KULUP": Pazar, "MILLI": Pazar})"""
    import pandas as pd
    PZ = {a: Pazar(servet, kesir=KESIR[a]) for a in ("KULUP", "MILLI")}
    pi_ser = pd.Series([None] * len(df), index=df.index, dtype=object)
    for hid, g in df.sort_values(["kapanis", "sira"]).groupby("hafta_id", sort=False):
        bekleyen = []
        for idx, r in g.iterrows():
            P = PZ[aile_pazari(r.get("aile"))]
            gor = {"PİYASA": r["p_piyasa"], "ELO": r["p_elo"], "FORM": r["p_form"], "H2H": r["p_h2h"]}
            pi, _ = P.fiyat(gor)
            pi_ser.at[idx] = pi
            bekleyen.append((P, gor, r["sonuc"], r["noter"], pi))
        for P, gor, s, noter, pi in bekleyen:              # hafta kapanınca cüzdanlar güncellenir
            if pi is not None and s == s and s is not None and not noter:
                P.cozumle(gor, int(s))
        for P in PZ.values():
            P.gecmis.append((hid, dict(P.W)))
    return pi_ser, PZ
