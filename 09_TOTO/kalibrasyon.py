"""
TOTO · KALİBRASYON — canlı kullanım için model parametrelerini üretir (yerelde)
===============================================================================
  1. Veri seti (veri_seti.pkl) — PİYASA ajanı açılış fiyatını görür (canlıdaki gibi)
  2. Ajan pazarı tüm geçmişte yürütülür → son cüzdanlar (kimin sesi ne kadar)
  3. Kalabalık modeli bilgili tüm haftalarla kalibre edilir (sezon ölçekleri dahil)
  4. Elo → olasılık eşlemesi katsayıları
Çıktı: 09_TOTO/model_parametre.json (repoya girer; üretim yalnız OKUR, scipy istemez)

Kullanım:  python kalibrasyon.py
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from geri_test import hazirla_veri
from kalabalik import PARAM_DOSYA, VARSAYILAN, hafta_ozeti, kalibre_et
from sportoto import haftalar


def calis() -> dict:
    t0 = time.time()
    df, pazar = hazirla_veri()
    H = {h["id"]: h for h in haftalar()}
    veri = []
    for hid, g in df.groupby("hafta_id"):
        h = H.get(hid)
        if not h or not h["sonuclandi"] or not h["D"]:
            continue
        oz = hafta_ozeti(g.sort_values("sira").to_dict("records"), "p_ref")
        if oz is None or len(oz["unc"]) > 2:
            continue
        veri.append((oz, np.array([h["n"][k] or 0 for k in (15, 14, 13, 12)], float), h["D"], h["kapanis"]))
    th, f = kalibre_et(veri, baslangic=VARSAYILAN)
    # Elo eşleme katsayıları (veri_seti ile aynı yöntem)
    from ajanlar import elo_kulup, elo_milli, sirali_lojit_fit
    from kaynaklar import kulup, milli
    K, M = kulup(), milli()
    ok = elo_kulup(K); om, _ = elo_milli(M)
    dk = (ok[:, 0] + ok[:, 2] - ok[:, 1]) / 400.0; yk = K["sonuc"].values
    mk = ((K["tarih"] >= "2014-07-01") & pd.notna(yk)).values
    dm = (om[:, 0] + om[:, 2] - om[:, 1]) / 400.0; ym = M["sonuc"].values
    mm = ((M["tarih"] >= "1990-01-01") & (ym >= 0)).values
    lk = sirali_lojit_fit(dk[mk], yk[mk].astype(int))
    lm = sirali_lojit_fit(dm[mm], ym[mm].astype(int))
    out = {
        "guncelleme": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hafta_sayisi": len(veri), "nll_hafta": round(f / max(len(veri), 1), 3),
        "kalabalik": th,
        "pazar_servet": {a: float(w) for a, w in pazar["KULUP"].W.items()},
        "pazar_servet_milli": {a: float(w) for a, w in pazar["MILLI"].W.items()},
        "pazar_kesir": 0.1, "pazar_kesir_milli": 0.3,
        "elo_lojit": {"kulup": [float(x) for x in lk], "milli": [float(x) for x in lm]},
    }
    PARAM_DOSYA.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"kalibrasyon: {len(veri)} hafta · NLL/hafta {f / len(veri):.1f} · {time.time() - t0:.0f} sn")
    print("  β:", {g: round(v, 2) for g, v in th["beta"].items()},
          "γTR", round(th["gTR"], 2), "γEU", round(th["gEU"], 2), "γTRM", round(th["gTRM"], 2))
    print("  sezon ölçeği:", {s: round(v, 2) for s, v in th["log_s"].items()})
    print("  cüzdan kulüp:", {a: round(w, 3) for a, w in pazar["KULUP"].W.items()})
    print("  cüzdan milli:", {a: round(w, 3) for a, w in pazar["MILLI"].W.items()})
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    calis()
