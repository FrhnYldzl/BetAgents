"""
🔍 MODEL KAYDI DENETİMİ — kayıt gerçekle uyuşuyor mu
======================================================
Kayıt (03_MODELLER/MODEL_REGISTRY/model_registry.json) bir modelin
durumunu söyler. Ama kayıt ELLE tutuluyor ve canlı sistemle bağı yok;
bu yüzden sessizce yalancı hale gelebiliyor.

Denetimde bulunanlar (2026-09-02):
  · 13 modelin 13'ünde de roi = None — kayıt hiç ölçüm taşımıyor
  · EUVOX durum=DEPRECATED, ama EUVOX_V1 ajanı CANLI ve güven
    tablosunda ilk sırada
  · TRIVOX durum=VALIDATED, ama ajan adı "TRIVOX (emekli — T1'de
    kanıtlanmış edge yok)"

Kayıt yanlışsa "hangi model çalışıyor" sorusuna verilen her cevap
yanlıştır. Bu modül kaydı GERÇEKLE karşılaştırır ve ölçülebilen ROI'yi
canlı veriden doldurur.

⚠️ SINIR: ajanlar hangi modeli kullandığını BEYAN ETMİYOR. Eşleme ajan
adının model adını içermesiyle kuruluyor (EUVOX_V1 → EUVOX). Bu bir
tahmindir ve raporda öyle işaretlenir. Kalıcı çözüm ajanın kendi
tanımında model alanı taşımasıdır — yol haritası Faz 3.

    python audit_model_registry.py           # yalnız ölç
    python audit_model_registry.py --yaz     # ölçülen ROI'yi kayda yaz
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import db

KAYIT = THIS_DIR.parent / "03_MODELLER" / "MODEL_REGISTRY" / "model_registry.json"


def denetle(yaz: bool = False) -> dict:
    kok = json.loads(KAYIT.read_text(encoding="utf-8"))
    # Kayıt bir sözlük ve modeller "models" listesinde; üst düzeydeki
    # diğer anahtarlar metaveri (schema_version, lifecycle_stages...).
    reg_liste = kok.get("models") if isinstance(kok, dict) else kok
    reg = {}
    for m in reg_liste:
        ad = (m.get("model_id") or m.get("name") or m.get("id") or "?")
        reg[str(ad)] = m
    conn = db.connect()
    try:
        canli = {}
        for r in conn.execute(
                "SELECT pp.portfolio_id p, "
                "COUNT(*) FILTER (WHERE pc.status IN ('won','lost')) n, "
                "COALESCE(SUM(pc.pnl) FILTER "
                "  (WHERE pc.status IN ('won','lost')),0) pnl, "
                "COALESCE(SUM(pc.stake) FILTER "
                "  (WHERE pc.status IN ('won','lost')),0) ciro "
                "FROM paper_portfolio pp "
                "LEFT JOIN paper_coupons pc ON pc.portfolio_id=pp.portfolio_id "
                "AND (pp.era_start IS NULL OR pc.created_at >= pp.era_start) "
                "GROUP BY pp.portfolio_id").fetchall():
            d = dict(r)
            canli[d["p"]] = {
                "n": int(d["n"] or 0),
                "roi": (float(d["pnl"]) / float(d["ciro"])
                        if float(d["ciro"] or 0) else None)}
    finally:
        conn.close()

    # Ajanların MODEL BEYANI — varsa ad tahmini yerine bu kullanılır.
    # agents.py'deki PROFILES sözlüğüne "model" alanı eklendi.
    _beyan = {}
    try:
        from agents import PROFILES as _AG
        _beyan = {k: v.get("model") for k, v in _AG.items() if v.get("model")}
    except Exception:
        pass
    print(f"📕 kayıtta {len(reg)} model · canlıda {len(canli)} portföy · "
          f"model BEYAN eden ajan: {len(_beyan)}\n")
    celiski, olculen, sessiz = [], [], []
    for ad, m in reg.items():
        durum = str(m.get("status", "?"))
        # ajan eşlemesi — TAHMİN (ajanlar modelini beyan etmiyor)
        eslesen = [p for p in canli
                   if ad.split()[0].split("-")[0].upper() in p.upper()]
        n = sum(canli[p]["n"] for p in eslesen)
        roi = None
        if eslesen:
            ciro_n = [canli[p]["roi"] for p in eslesen
                      if canli[p]["roi"] is not None]
            roi = sum(ciro_n) / len(ciro_n) if ciro_n else None
        satir = {"ad": ad, "durum": durum, "eslesen": eslesen,
                 "n": n, "roi": roi}
        if durum == "DEPRECATED" and n > 0:
            celiski.append(dict(satir, neden="DEPRECATED ama CANLI oynuyor"))
        elif durum == "VALIDATED" and n == 0:
            celiski.append(dict(satir, neden="VALIDATED ama hiç bahsi yok"))
        if roi is not None:
            olculen.append(satir)
        else:
            sessiz.append(satir)

    print(f"  ÇELİŞKİ: {len(celiski)}")
    for c in celiski:
        print(f"    {c['ad'][:22]:22s} {c['neden']:34s} "
              f"n={c['n']:4d}  ajan={','.join(c['eslesen']) or '—'}")
    print(f"\n  ÖLÇÜLEBİLEN ROI: {len(olculen)} / {len(reg)}")
    for o in olculen:
        print(f"    {o['ad'][:22]:22s} n={o['n']:4d}  "
              f"roi={o['roi']*100:+.1f}%  ajan={','.join(o['eslesen'])}")
    print(f"\n  ÖLÇÜLEMEYEN: {len(sessiz)} — canlı karşılığı olmayan model")
    print("    (kayıtta duruyor ama sahada yok; 'PROTOTYPE' ise normal)")

    if yaz and olculen:
        for o in olculen:
            # reg[ad] listedeki sözlüğün TA KENDİSİ (kopya değil) —
            # burada değiştirmek kok["models"] içindekini değiştirir.
            reg[o["ad"]]["roi"] = round(o["roi"], 4)
            reg[o["ad"]]["roi_n"] = o["n"]
            # ⚠️ Çıplak bir ROI sayısı, n'i olmadan okunduğunda yalan
            # söyler: n=12'de +%45,7 bir bulgu değil, gürültüdür. Kayıt
            # başka yerlerden okunuyor; sayının kendisi güvenilir olup
            # olmadığını TAŞIMALI. Ürünün tek eşiği burada da geçerli.
            reg[o["ad"]]["roi_guvenilir"] = bool(o["n"] >= 30)
            reg[o["ad"]]["roi_kaynak"] = (
                "paper_coupons · ajan adı eşlemesi (TAHMİN — ajan modelini "
                "beyan etmiyor). roi_guvenilir=false ise n<30, yani sayı "
                "doğru ama HÜKÜM DEĞİL.")
        KAYIT.write_text(json.dumps(kok, ensure_ascii=False, indent=2),
                         encoding="utf-8")
        print(f"\n✅ {len(olculen)} modelin ROI'si kayda yazıldı "
              f"(kaynak alanıyla birlikte — tahmin olduğu kayıtta duruyor).")
    elif olculen:
        print("\n  (ölçüm — değişiklik yok · --yaz ile kayda işlenir)")
    return {"celiski": len(celiski), "olculen": len(olculen)}


if __name__ == "__main__":
    denetle(yaz="--yaz" in sys.argv)
