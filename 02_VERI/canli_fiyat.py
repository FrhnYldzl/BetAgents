"""
📡 CANLI FİYAT — iddaa'nın ŞU ANKİ fiyatı (veri katmanı, tüm takımlar)
======================================================================
Tek çağrı (~800 maç, pazarlar olayın içinde gelir, ~2 sn). Dönen:
    {iddaa_event_id: {(pazar, seçim): oran}}
Pazar/seçim etiketleri pazar defteriyle (market_odds) AYNI — ikisi de
iddaa_odds_scraper.decode_event_markets'ten geçer. Beraberlik "0".

NEDEN (19.09.2026, kullanıcı: "HARMAN'ın oranları yanlış gibi"): ajanlar
fiyatı pazar defterinin SON SATIRINDAN okuyordu. O satır güncel fiyat
DEĞİLDİR — ana çekim 803 maçın yalnız ilk 120'sini işliyor ve liste tarihe
göre sıralı değil; dışarıda kalan maçın son satırı günlerce eski kalıyor.
HARMAN Sevilla'yı 10,50'den oynadı (defterin 18.09 09:52 fiyatı), iddaa'da
o an ~8,4'tü. Kâğıt bahis ancak GERÇEKTEN alınabilecek fiyattan kurulur.

Önbellek 90 sn: bir worker döngüsünde on ajan üç kez (kalkan, teşhis,
koşu) aday üretir — hepsi aynı çağrıyı paylaşır. Çağrı başarısızsa istisna
yükselir; çağıran eski fiyata SESSİZCE düşmemeli (hatanın ta kendisi).
"""
from __future__ import annotations

import sys
import time
from collections import defaultdict
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
sys.path.insert(0, str(THIS_DIR / "scrapers"))

_ONBELLEK: dict = {"ts": 0.0, "v": None}


def fiyatlar(taze_sn: int = 90) -> dict:
    """{iddaa_event_id: {(pazar, seçim): oran}} — iddaa'nın şu anki fiyatı."""
    if _ONBELLEK["v"] is not None and time.time() - _ONBELLEK["ts"] < taze_sn:
        return _ONBELLEK["v"]
    from iddaa_odds_scraper import fetch_events, decode_event_markets
    # Bir yeniden deneme: iddaa ara sıra bağlantıyı yanıtsız kapatıyor ya da
    # zaman aşımına düşüyor (19.09'da yerelden ölçüldü). İkincisi de düşerse
    # istisna çağırana gider.
    try:
        olaylar = fetch_events(1)
    except Exception:
        time.sleep(5)
        olaylar = fetch_events(1)
    out: dict = defaultdict(dict)
    for ev in olaylar:
        try:
            satirlar = decode_event_markets(ev)
        except Exception:
            continue
        for r in satirlar:
            mk = str(r.get("market"))
            sel = str(r.get("selection") or "").strip()
            if mk == "1X2" and sel.upper() == "X":
                sel = "0"
            try:
                o = float(r.get("odd") or 0)
            except (TypeError, ValueError):
                continue
            if o > 1.0:
                out[str(r.get("iddaa_match_id"))][(mk, sel)] = o
    v = dict(out)
    _ONBELLEK.update(ts=time.time(), v=v)
    return v


if __name__ == "__main__":
    t = time.time()
    f = fiyatlar()
    print(f"📡 {len(f)} maç · {sum(len(v) for v in f.values())} fiyat · "
          f"{time.time() - t:.1f} sn")
