"""
🏷 LİG KODU DÜZELTME — bu sezonun iddaa satırları (tek seferlik bakım)
======================================================================
Kullanıcı kararı (19.09.2026): "Düzeltebilirsin — ölçümleri sonra
etkilemesin, standartlaştırmak lazım."

HATA: fetch_iddaa_live lig kodunu ünlü takım adı oylamasıyla öğreniyordu
(iddaa lig adını artık göndermiyor). Şampiyonlar Ligi, Lig Kupası ve
Championship E0; DFB-Pokal ve 3. Liga D1; İspanyol alt ligi SP1; TFF 1. Lig
T1 yazıldı. Sezon başı lig maçları ise 'ALL' kaldı (Deportivo–Elche 17.08).
Fetcher düzeltildi (kadro saflığı, ci_ligleri); bu betik GEÇMİŞİ düzeltir.

İKİ KATMAN
  1) competition_id'li satırlar (≈ 01.09'dan beri): kod ci'dan gelir —
     tanınan ana lig ya da "ana lig değil" kanıtı. Kesin.
  2) ci'sız eski satırlar (01.07 → 03.09): MUHAFAZAKÂR. Bir satır ancak İKİ
     takım da X'in bu sezonki kadrosundaysa ve maç X'in sezon başından
     SONRAYSA X olur (sezon başı = kadro-içi maçların ilk yoğunlaştığı gün;
     hazırlık maçları dışarıda kalır). Kodu X olup bu şartı sağlamayan satır
     'ALL' olur. Kadro: ci satırları + canlı olaylar + geçen sezonun
     football-data adlarına bağlanan iddaa adları (aynı ada birden çok iddaa
     adı bağlanırsa en çok maçı olan kalır — 'Vik. Köln' Köln sayılmaz).

GÜVENLİK: önce kuru koşu; --uygula ile yazar. Her değişiklik
yedek_lig_kodu.json'a (eski → yeni) yazılır, geri alınabilir. Güncellemeler
200'lük kısa işlemlerle (kilit kuyruğu dersi). paper_bets.league'e
DOKUNULMAZ — bahis anında görülen etiketin tarihsel kaydıdır.

    python lig_kodu_duzelt.py            # kuru koşu (rapor)
    python lig_kodu_duzelt.py --uygula   # yaz
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
sys.path.insert(0, str(THIS_DIR / "scrapers"))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import database as db
import fetch_iddaa_live as F
from takim_adi import esle_ad

BASLANGIC = "2026-07-01"
YEDEK = THIS_DIR / "yedek_lig_kodu.json"


def _t(s):
    try:
        return datetime.fromisoformat(str(s)[:19])
    except Exception:
        return None


def plan(conn, olaylar: list) -> tuple[list, dict]:
    tanindi, degil = F.ci_ligleri(conn, olaylar, taze_dk=0)
    satir = [dict(r) for r in conn.execute(
        "SELECT match_id, league_code lg, competition_id ci, home_team h, "
        "away_team a, kickoff_utc ko FROM matches_v2 "
        "WHERE external_id_fd IS NULL AND kickoff_utc >= ?", (BASLANGIC,)).fetchall()]
    # ── kadro: ci satırları + canlı olaylar (bu sezon, iddaa adlarıyla)
    kadro: dict = defaultdict(set)
    for r in satir:
        try:
            lg = tanindi.get(int(r["ci"])) if r["ci"] is not None else None
        except (TypeError, ValueError):
            lg = None
        if lg:
            kadro[lg].update((r["h"], r["a"]))
    for ev in olaylar:
        try:
            lg = tanindi.get(int(ev.get("ci")))
        except (TypeError, ValueError):
            lg = None
        if lg:
            kadro[lg].update(x for x in (ev.get("hn"), ev.get("an")) if x)
    # ── + geçen sezonun football-data adına bağlanan iddaa adları
    fd = F._kadrolar(conn)
    gorunme = Counter()
    for r in satir:
        gorunme[r["h"]] += 1
        gorunme[r["a"]] += 1
    for lg in F.ANA_LIGLER:
        hedef: dict = defaultdict(list)
        for ad in gorunme:
            m = esle_ad(ad, fd.get(lg, set()))
            if m:
                hedef[m].append(ad)
        for m, adlar in hedef.items():
            kadro[lg].add(max(adlar, key=lambda x: gorunme[x]))
    # ── sezon başı: kadro-içi maçların ilk HAFTA KÜMESİ. Maç günleri en fazla
    # 1 gün arayla zincirlenir; ≥ 6 maçlı ilk küme ilk hafta sayılır. (İlk
    # sürüm "4 günde ≥ 3" diyordu: Deportivo–Real Madrid hazırlık maçı (12.08)
    # ilk haftayla aynı pencereye düşüp La Liga'yı 12.08'de başlatıyordu.)
    bas: dict = {}
    for lg in F.ANA_LIGLER:
        sayim = Counter(t.date() for r in satir
                        if r["h"] in kadro[lg] and r["a"] in kadro[lg]
                        and (t := _t(r["ko"])) and t >= datetime(2026, 7, 20))
        kume, onceki = [], None
        for g in sorted(sayim):
            if onceki is not None and (g - onceki).days > 1:
                if sum(sayim[x] for x in kume) >= 6:
                    break
                kume = []
            kume.append(g)
            onceki = g
        if kume and sum(sayim[x] for x in kume) >= 6:
            bas[lg] = kume[0]
    degis = []
    for r in satir:
        eski = r["lg"]
        yeni = None
        ci = None
        try:
            ci = int(r["ci"]) if r["ci"] is not None else None
        except (TypeError, ValueError):
            pass
        if ci is not None:                                   # katman 1
            if ci in F.IDDAA_CI_MAPPING:
                yeni = F.IDDAA_CI_MAPPING[ci]
            elif ci in tanindi:
                yeni = tanindi[ci]
            elif ci in degil:
                yeni = "ALL"
            katman = 1
        else:                                                # katman 2
            t = _t(r["ko"])
            aday = [lg for lg in F.ANA_LIGLER
                    if r["h"] in kadro[lg] and r["a"] in kadro[lg]
                    and lg in bas and t and t.date() >= bas[lg]]
            if len(aday) == 1:
                yeni = aday[0]
            elif eski in F.ANA_LIGLER:
                yeni = "ALL"
            katman = 2
        if yeni is not None and yeni != eski:
            degis.append({"match_id": r["match_id"], "eski": eski, "yeni": yeni,
                          "katman": katman, "mac": f"{r['h']} - {r['a']}",
                          "ko": str(r["ko"])[:16], "ci": ci})
    ozet = {"tanindi": tanindi, "sezon_basi": {k: str(v) for k, v in bas.items()},
            "kadro": {k: len(v) for k, v in kadro.items()}}
    return degis, ozet


def uygula(conn, degis: list) -> None:
    onceki = json.loads(YEDEK.read_text(encoding="utf-8")) if YEDEK.exists() else []
    onceki.append({"ts": datetime.utcnow().isoformat(), "degisiklik": degis})
    YEDEK.write_text(json.dumps(onceki, ensure_ascii=False, default=str, indent=1),
                     encoding="utf-8")
    for i in range(0, len(degis), 200):
        for d in degis[i:i + 200]:
            conn.execute("UPDATE matches_v2 SET league_code=? WHERE match_id=?",
                         (d["yeni"], d["match_id"]))
        conn.commit()
    print(f"  ✅ matches_v2: {len(degis)} satır · yedek {YEDEK.name}")


def pazar_defteri(conn, olaylar: list, uygula_: bool) -> int:
    """Oynanmamış maçların pazar defteri satırları — Kırmızı'nın meta'sı son
    satırın kodunu okuyor; fiyat değişmezse yeni satır gelmez, eski kod kalır."""
    tanindi, degil = F.ci_ligleri(conn, olaylar)
    simdi = datetime.utcnow().isoformat()
    kod = {}
    for ev in olaylar:
        k, kesin = F.lig_kodu(ev, tanindi, degil)
        if kesin:
            kod[str(ev.get("i"))] = k
    mevcut = {str(r[0]): r[1] for r in conn.execute(
        "SELECT iddaa_event_id, MAX(league_code) FROM market_odds WHERE kickoff_utc > ? "
        "GROUP BY iddaa_event_id", (simdi,)).fetchall()}
    fark = {e: k for e, k in kod.items() if e in mevcut and mevcut[e] != k}
    if uygula_:
        items = list(fark.items())
        for i in range(0, len(items), 200):
            for e, k in items[i:i + 200]:
                conn.execute("UPDATE market_odds SET league_code=? WHERE iddaa_event_id=? "
                             "AND kickoff_utc > ?", (k, e, simdi))
            conn.commit()
    return len(fark)


def bahis_etiketleri(uygula_: bool) -> None:
    """paper_bets.league → maçın DÜZELTİLMİŞ kodu (bu sezonun iddaa satırları).

    İlk karar etikete dokunmamaktı ("bahis anında görülen etiketin kaydı").
    Canlıda görüldü ki ajan dosyasında "Cardiff City — Charlton · E0" yazıyor
    ve ajan karnesinin lig kırılımı bu etiketi okuyor — kullanıcının şartı
    "ölçümler sonra etkilenmesin" bunu gerektirir. Eski etiket yedekte
    (yedek_lig_kodu_bahis.json) — ajanın o gün ne gördüğü kaybolmaz."""
    yedek = THIS_DIR / "yedek_lig_kodu_bahis.json"
    conn = db.connect()
    try:
        rows = [dict(r) for r in conn.execute(
            "SELECT pb.bet_id, pb.portfolio_id, pb.league eski, m.league_code yeni "
            "FROM paper_bets pb JOIN matches_v2 m ON m.match_id = pb.match_id "
            "WHERE m.kickoff_utc >= ? AND m.external_id_fd IS NULL "
            "AND COALESCE(pb.league,'') <> COALESCE(m.league_code,'')",
            (BASLANGIC,)).fetchall()]
        print(f"  bahis etiketi: {len(rows)} bahis · " +
              ", ".join(f"{e}→{y} {n}" for (e, y), n in
                        Counter((r['eski'], r['yeni']) for r in rows).most_common(8)))
        if not uygula_ or not rows:
            return
        onceki = json.loads(yedek.read_text(encoding="utf-8")) if yedek.exists() else []
        onceki.append({"ts": datetime.utcnow().isoformat(), "bahisler": rows})
        yedek.write_text(json.dumps(onceki, ensure_ascii=False, default=str, indent=1),
                         encoding="utf-8")
        for i in range(0, len(rows), 200):
            for r in rows[i:i + 200]:
                conn.execute("UPDATE paper_bets SET league=? WHERE bet_id=?",
                             (r["yeni"], r["bet_id"]))
            conn.commit()
        print(f"  ✅ paper_bets.league: {len(rows)} bahis · yedek {yedek.name}")
    finally:
        conn.close()


if __name__ == "__main__":
    if "--bahis" in sys.argv:
        bahis_etiketleri("--uygula" in sys.argv)
        sys.exit(0)
    from iddaa_odds_scraper import fetch_events
    yaz = "--uygula" in sys.argv
    olaylar = fetch_events(1)
    conn = db.connect()
    try:
        degis, ozet = plan(conn, olaylar)
        print(f"🏷 LİG KODU DÜZELTME — {'UYGULA' if yaz else 'KURU KOŞU'}")
        print(f"  tanınan: {sorted(ozet['tanindi'].items())}")
        print(f"  kadro boyu: {ozet['kadro']} · sezon başı: {ozet['sezon_basi']}")
        say = Counter((d["katman"], d["eski"], d["yeni"]) for d in degis)
        for (k, e, y), n in sorted(say.items(), key=lambda x: -x[1]):
            print(f"  katman {k}: {e:5s} → {y:5s} {n:5d} satır")
        for (k, e, y), _n in sorted(say.items(), key=lambda x: -x[1]):
            ornek = [d for d in degis if (d["katman"], d["eski"], d["yeni"]) == (k, e, y)][:4]
            print(f"   örnek {k} {e}→{y}: " + " | ".join(f"{d['mac']} ({d['ko'][:10]})" for d in ornek))
        n_mo = pazar_defteri(conn, olaylar, yaz)
        print(f"  pazar defteri (oynanmamış maç): {n_mo} olayın kodu farklı")
        if yaz and degis:
            uygula(conn, degis)
        elif not yaz:
            print("  KURU KOŞU — yazmak için --uygula")
    finally:
        conn.close()
