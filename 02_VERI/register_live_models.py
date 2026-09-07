"""
📕 CANLI MODELLERİ KAYDA EKLE — kayıt sahayı anlatsın
=======================================================
Denetimde bulundu (2026-09-07): 19 ajanın 13'ü kayıtta HİÇ OLMAYAN
modeller kullanıyor. Kayıttaki 13 modelin yalnız 2'si sahada. Yani
kayıt, çalışan sistemi değil BAŞKA BİR SİSTEMİ anlatıyordu — bu yüzden
"hangi model çalışıyor" sorusuna verilen her cevap yanlıştı.

Eksik üç model, ajanların BEYANINDAN geliyor (agents.py PROFILES["model"])
ve her biri koddan doğrulandı:
  MOTOR-V1        _engine_candidates — sinyal motoru (varsayılan yol)
  MOTOR-V1+RATING motor + bağımsız rating ikinci görüşü (confirm/value)
  SKOR-SUREKLI    multiplier_agent → score_sets.score_set_prob_cont

⚠️ status = PRODUCTION yazılır çünkü ÖLÇÜLEN GERÇEK bu: canlı bahis
üretiyorlar. "VALIDATED" YAZILMAZ — doğrulanmış olmaları ayrı bir
iddiadır ve bu betik onu ölçmez. Kayıt neyin çalıştığını söyler,
neyin doğru olduğunu değil.

    python register_live_models.py --dry
    python register_live_models.py
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

KAYIT = THIS_DIR.parent / "03_MODELLER" / "MODEL_REGISTRY" / "model_registry.json"

TANIM = {
    "MOTOR-V1": {
        "purpose": "Sinyal motorunun varsayilan olasilik hatti",
        "how": "_engine_candidates — signal_snapshots uzerinden aday uretir",
        "input": "signal_snapshots (anomaly, model, xG, form)",
    },
    "MOTOR-V1+RATING": {
        "purpose": "Motor + bagimsiz rating ikinci gorusu",
        "how": "_engine_candidates ciktisi ratings.predict() ile suzulur "
               "(confirm: sapma kucukse gecer · value: sapma lehteyse gecer)",
        "input": "signal_snapshots + bagimsiz rating modeli",
    },
    "SKOR-SUREKLI": {
        "purpose": "Surekli skor dagilimi — kombo pazarlar icin adil fiyat",
        "how": "multiplier_agent -> score_sets.score_set_prob_cont; "
               "kazandiran skorlarin kutlesi bantsiz hesaplanir",
        "input": "1X2 + A/U + KG kapanis fiyatlari (marjsizlastirilmis)",
    },
}


def ekle(dry: bool = False) -> dict:
    kok = json.loads(KAYIT.read_text(encoding="utf-8"))
    var = {m.get("name") or m.get("id") for m in kok["models"]}
    try:
        from agents import PROFILES
        beyan = {v["model"] for v in PROFILES.values() if v.get("model")}
    except Exception as e:
        print(f"agents.py okunamadi: {e}")
        return {}
    eksik = sorted(m for m in beyan
                   if m not in var and not str(m).startswith("YOK"))
    kullanan = {m: sorted(k for k, v in PROFILES.items()
                          if v.get("model") == m) for m in eksik}

    print(f"📕 kayitta {len(kok['models'])} model · ajan beyani {len(beyan)}")
    print(f"   kayitta OLMAYAN, CANLI calisan model: {len(eksik)}\n")
    for m in eksik:
        print(f"   {m:16s} {len(kullanan[m])} ajan: "
              f"{', '.join(x.replace('_V1','') for x in kullanan[m])}")
    if not eksik:
        print("   ✅ kayit sahayi tam anlatiyor.")
        return {"eklenen": 0}
    if dry:
        print("\n   (dry-run — degisiklik yok)")
        return {"eklenen": 0, "eksik": len(eksik)}

    bugun = date.today().isoformat()
    for m in eksik:
        t = TANIM.get(m, {})
        kok["models"].append({
            "id": m + "-canli", "name": m, "version": "canli",
            # ⚠️ PRODUCTION: olculen gercek bu — canli bahis uretiyor.
            # VALIDATED YAZILMAZ: dogrulanmis olmak ayri bir iddiadir ve
            # bu betik onu olcmez. Kayit neyin CALISTIGINI soyler.
            "status": "PRODUCTION",
            "created": bugun, "last_updated": bugun,
            "purpose": t.get("purpose", ""),
            "how": t.get("how", ""),
            "input": t.get("input", ""),
            "kaynak": "agents.py PROFILES['model'] beyani — koddan dogrulandi",
            "kullanan_ajanlar": kullanan[m],
            "roi": None,
        })
    kok["last_updated"] = bugun
    KAYIT.write_text(json.dumps(kok, ensure_ascii=False, indent=2),
                     encoding="utf-8")
    print(f"\n✅ {len(eksik)} canli model kayda eklendi "
          f"(status=PRODUCTION, roi=None — ROI ayri adimda olculur).")
    return {"eklenen": len(eksik)}


if __name__ == "__main__":
    ekle(dry="--dry" in sys.argv)
