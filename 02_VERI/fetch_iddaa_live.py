"""
IDDAA LIVE FETCH — Yakın gelecek maçları + Multi-market odds
==============================================================

Amaç:
  iddaa.com'dan canlı/yakın maçları çek + 7 pazarın odds'larını al
  matches_v2 + signal_snapshots tablolarına yaz

Çekilecek 7 pazar (signal_snapshots'ta KG eksik!):
  (1,1)   Maç Sonucu (1X2)
  (2,101) A/Ü 2.5
  (2,89)  KG (Karşılıklı Gol) ⭐ EKSİK PAZAR
  (2,92)  Çifte Şans
  (2,100) AH (Handikaplı)
  (2,90)  İY/MS
  (2,1)   İlk Yarı 1X2

Çıktı:
  - matches_v2: future maçlar unsettled (is_settled=0)
  - signal_snapshots: odd_btts_yes/no doldurma
  - UI Live Calendar sayfasında gösterilebilir
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
sys.path.insert(0, str(THIS_DIR / "scrapers"))

import database as db
from iddaa_odds_scraper import (
    fetch_events, fetch_event_detail, fetch_competitions, fetch_market_config
)


# iddia competition_id → canonical league_code
# (iddia.com /sportsbook/competitions endpoint'inden tespit edilen)
IDDAA_CI_MAPPING = {
    # Ana 6 büyük lig (sezon arası boş kalabilir)
    347: "D1",   # Almanya Bundesliga
    # 348: "I1", # Brezilya Serie A — NOT, bu Brezilya değil İtalya'yı bekleyebiliriz
    # 579: "I1", # İtalya Serie A Playoff (sezon sonu)
    # Premier, La Liga, Süper Lig, Ligue 1, Serie A: yaz arası iddia ci yok
    # Sezon başında yeni ci'lar gelir.

    # GEÇICI YAZ ARASI Active liglerden:
    1484: "INTL",  # Uluslararası Hazırlık (geçici test için)
    348: "BRA1",   # Brezilya Serie A
    970: "USA1",   # MLS
}


# Lig kategorileri — UI'da grupla
LIG_CATEGORIES = {
    "ACTIVE_MAIN": ["T1","E0","D1","SP1","I1","F1"],  # Bizim 6 ana lig
    "ACTIVE_OTHER": ["INTL","BRA1","USA1"],  # Yaz arası aktif diğerleri
}


def _norm_tr(s: str) -> str:
    s = (s or "").casefold()
    for a, b in (("ı", "i"), ("i̇", "i"), ("ş", "s"), ("ğ", "g"),
                 ("ü", "u"), ("ö", "o"), ("ç", "c")):
        s = s.replace(a, b)
    return s


# SEZON HAZIRLIĞI (Ağustos): ci sabit-eşlemesi sezon başında değişir; lig ADI
# (cn) üzerinden kanonik kod türet. Kural: ülke-ipucu + lig-ipucu + red-listesi.
# Eşleşmezse None → lig_code 'ALL' (mevcut güvenli davranış).
LEAGUE_NAME_RULES = [
    # code  ülke_ipuçları        lig_ipuçları             red (kadın/alt lig)
    ("T1",  ("turkiye",),        ("super lig",),          ("kadin", "u19", "u21", "2.")),
    ("E0",  ("ingiltere",),      ("premier",),            ("kadin", "u21")),
    ("SP1", ("ispanya",),        ("laliga", "la liga"),   ("kadin", "laliga 2", "la liga 2")),
    ("D1",  ("almanya",),        ("bundesliga",),         ("kadin", "2.")),
    ("I1",  ("italya",),         ("serie a",),            ("kadin",)),
    ("F1",  ("fransa",),         ("ligue 1",),            ("kadin", "ligue 2")),
]


def map_league_by_name(cn: str) -> str | None:
    """Lig adından (cn) kanonik kod. Örn 'Türkiye Süper Lig' → T1."""
    n = _norm_tr(cn)
    if not n:
        return None
    for code, countries, leagues, deny in LEAGUE_NAME_RULES:
        if (any(c in n for c in countries)
                and any(l in n for l in leagues)
                and not any(d in n for d in deny)):
            return code
    return None


# ── SEZON-KANITLI LİG TESPİTİ: takım adından ci öğren (2026-08) ──
# ci numaraları her sezon değişir; bunun yerine her fetch'te ünlü takım
# adlarından ci→lig eşlemesi ÖĞRENİLİR (çoğunluk oyu) ve tüm event'lere
# uygulanır. Elle ci güncellemesi bir daha gerekmez.
TEAM_MARKERS = {
    "T1": ["galatasaray","fenerbah","beşiktaş","trabzonspor","başakşehir",
           "kasımpaşa","alanyaspor","antalyaspor","konyaspor","kayserispor",
           "rizespor","samsunspor","göztepe","eyüpspor","gaziantep",
           "kocaelispor","gençlerbirliği","karagümrük"],
    "E0": ["manchester city","manchester utd","liverpool","chelsea","arsenal",
           "tottenham","everton","newcastle","aston villa","west ham",
           "brighton","fulham","brentford","crystal palace","wolverhampton",
           "nottingham forest","sunderland","leeds","burnley","bournemouth"],
    "SP1":["real madrid","barcelona","atletico madrid","sevilla","villarreal",
           "real betis","athletic bilbao","real sociedad","valencia","getafe",
           "osasuna","celta vigo","mallorca","alaves","espanyol","girona"],
    "I1": ["juventus","inter","milan","napoli","roma","lazio","atalanta",
           "fiorentina","torino","bologna","udinese","genoa","cagliari",
           "como","lecce","sassuolo","parma"],
    "D1": ["bayern münih","borussia dortmund","leverkusen","rb leipzig",
           "eintracht frankfurt","stuttgart","wolfsburg","freiburg",
           "union berlin","mönchengladbach","mainz","augsburg","hoffenheim",
           "werder bremen","köln","hamburg"],
    "F1": ["paris sg","paris saint","marsilya","marseille","olympique lyon",
           "monaco","lille","nice","rennes","lens","toulouse","strasbourg",
           "nantes","brest","auxerre"],
}


def learn_ci_leagues(events: list) -> dict:
    """events listesinden ci→league_code eşlemesini çoğunluk oyuyla öğren."""
    from collections import Counter
    votes: dict = {}
    for ev in events:
        nm = ((ev.get("hn") or ev.get("eh") or "") + " " +
              (ev.get("an") or ev.get("ea") or "")).lower()
        ci = ev.get("ci")
        if ci is None:
            continue
        for lg, markers in TEAM_MARKERS.items():
            if any(m in nm for m in markers):
                votes.setdefault(ci, Counter())[lg] += 1
    learned = {}
    for ci, ctr in votes.items():
        lg, n = ctr.most_common(1)[0]
        if n >= 2:                      # tek maçlık tesadüf eşleşmeyi eleme
            learned[ci] = lg
    return learned


def map_iddaa_league(event: dict) -> str | None:
    """iddia event → canonical league_code: önce ci eşlemesi, sonra lig adı (cn)."""
    ci = event.get("ci")
    if ci is not None and ci in IDDAA_CI_MAPPING:
        return IDDAA_CI_MAPPING[ci]
    return map_league_by_name(event.get("cn") or "")


def extract_odds_from_market(market: dict) -> dict:
    """Bir market dict'inden 1X2 veya KG veya A/Ü odds'unu çıkar."""
    market_type = market.get("t")
    sub_type = market.get("st")
    outcomes = market.get("o", [])
    sov = market.get("sov", "")

    odds_data = {}

    # 1X2 (Maç Sonucu)
    if market_type == 1 and sub_type == 1:
        for o in outcomes:
            n = o.get("n", "").strip()
            odd = o.get("odd")
            if n == "1": odds_data["1"] = odd
            elif n == "0" or n.upper() == "X": odds_data["X"] = odd
            elif n == "2": odds_data["2"] = odd

    # A/Ü 2.5
    elif market_type == 2 and sub_type == 101 and str(sov) in ("2.5", "2,5"):
        for o in outcomes:
            n = o.get("n", "").upper()
            odd = o.get("odd")
            if "ÜST" in n or "UST" in n or "OVER" in n:
                odds_data["over25"] = odd
            elif "ALT" in n or "UNDER" in n:
                odds_data["under25"] = odd

    # KG (Karşılıklı Gol)
    elif market_type == 2 and sub_type == 89:
        for o in outcomes:
            n = o.get("n", "").upper()
            odd = o.get("odd")
            if "VAR" in n or "YES" in n:
                odds_data["btts_yes"] = odd
            elif "YOK" in n or "NO" in n:
                odds_data["btts_no"] = odd

    return odds_data


def fetch_and_ingest(dry_run: bool = False, max_events: int = 50,
                    only_target_leagues: bool = True):
    """Ana ingest."""
    print("=" * 70)
    print("IDDAA LIVE FETCH — Future Fixtures + Multi-market odds")
    print("=" * 70)

    # 1) Events list (tüm futbol)
    print("\n[1] Event listesi çekiliyor...")
    try:
        events = fetch_events(sport_type=1)
    except Exception as e:
        print(f"  ERR: {e}")
        print("\nMuhtemel sebep: iddia.com erişim sorunu (geo-block?)")
        print("Test için Türkiye IP gerekebilir.")
        return

    print(f"  {len(events)} event geldi")
    if not events:
        print("  Boş — iddia.com'da bugün/yakın maç yok veya endpoint değişti")
        return

    # 1.5) Sezon-kanıtlı lig öğrenme: ci→lig (takım adlarından, her fetch'te)
    learned = {}
    try:
        learned = learn_ci_leagues(events)
        if learned:
            print(f"  Lig tespiti: {len(learned)} ci öğrenildi -> {learned}")
        for ev in events:
            lg = learned.get(ev.get("ci"))
            if lg and "_league_code" not in ev:
                ev["_league_code"] = lg
    except Exception as e:
        print(f"  lig öğrenme atlandı: {e}")

    # 2) Filter target leagues via competition_id (ci)
    if only_target_leagues:
        filtered = []
        for ev in events:
            lg_code = map_iddaa_league(ev)  # ci-based mapping
            if lg_code:
                ev["_league_code"] = lg_code
                filtered.append(ev)
        events = filtered
        print(f"  Target lig filter sonrasi: {len(events)} event")
    else:
        # Tüm-ligler modunda da kanonik kodu ata (sezonda T1/E0... 'ALL' düşmesin).
        n_mapped = 0
        for ev in events:
            if "_league_code" not in ev:
                code = map_iddaa_league(ev)
                if code:
                    ev["_league_code"] = code
                    n_mapped += 1
        if n_mapped:
            print(f"  Lig adi eslemesi: {n_mapped} event kanonik koda baglandi")

    if not events:
        print("  Bizim 6 lig için event yok. Yaz arası olabilir.")
        print("  Tüm liglerden örnek:")
        # Show what's available
        raw_events = fetch_events(sport_type=1)[:5]
        for ev in raw_events:
            print(f"    {ev.get('cn','?')}: {ev.get('eh','?')} vs {ev.get('ea','?')}")
        return

    # 3) Detail fetch (event-by-event, limit)
    print(f"\n[2] {min(max_events, len(events))} event için detay çekiliyor...")
    results = []
    for i, ev in enumerate(events[:max_events]):
        event_id = ev.get("i")
        if not event_id: continue

        # iddia event field'ları: i, hn (home), an (away), ci (comp_id), d (epoch)
        home_name = ev.get("hn") or ev.get("eh") or "?"
        away_name = ev.get("an") or ev.get("ea") or "?"

        # Epoch timestamp -> ISO
        epoch = ev.get("d")
        if epoch:
            kickoff_iso = datetime.fromtimestamp(epoch).isoformat()
        else:
            kickoff_iso = None

        if dry_run:
            print(f"  [DRY] {home_name} vs {away_name} "
                  f"(ci={ev.get('ci','?')}, "
                  f"{kickoff_iso[:16] if kickoff_iso else '?'})")
            continue

        # Direkt event'in m (markets) field'ı varsa kullan, yoksa detail çek
        markets = ev.get("m", [])
        if not markets:
            detail = fetch_event_detail(event_id)
            if not detail: continue
            markets = detail.get("m", [])

        odds_combined = {}
        for m in markets:
            odds_combined.update(extract_odds_from_market(m))

        results.append({
            "event_id": event_id,
            "lig_code": ev.get("_league_code", "ALL"),
            "kickoff": kickoff_iso,
            "home": home_name,
            "away": away_name,
            "competition_id": ev.get("ci"),
            "mbs": ev.get("mbc"),   # iddaa Minimum Bahis Sayısı (1=tek olur, 3=3'lü zorunlu)
            "odds": odds_combined,
        })

        if (i+1) % 10 == 0:
            print(f"  {i+1}/{min(max_events, len(events))} ...")

    print(f"\n[3] {len(results)} event detayli cekildi")

    # 📈 FİYAT GEÇMİŞİ: bu veri zaten elimizde, kaydetmeden atıyorduk.
    # Sıfır ek API çağrısı; yalnız DEĞİŞEN fiyatlar yazılır. Asla patlamaz.
    if not dry_run and results:
        try:
            import price_history
            n_ph = price_history.capture(results)
            if n_ph:
                print(f"  📈 fiyat gecmisi: {n_ph} yeni kayit (degisen fiyat)")
        except Exception as e:
            print(f"  (fiyat gecmisi atlandi: {e})")

    # 🎰 PAZAR DEFTERİ: yüksek çarpanlı + maç içi KOMBİNE pazarlar
    # (1X2_OU, 1X2_BTTS, HT_FT, TOTAL_GOALS...). AYRI tabloya yazılır;
    # matches_v2'ye dokunulmaz, sinyal motoru bu veriyi HİÇ görmez.
    if not dry_run:
        try:
            import market_book
            n_mb = market_book.capture(events[:max_events])
            if n_mb:
                print(f"  🎰 pazar defteri: {n_mb} yeni fiyat kaydi")
        except Exception as e:
            print(f"  (pazar defteri atlandi: {e})")

    # 4) Database insert
    if not dry_run and results:
        print(f"\n[4] matches_v2 + signal_snapshots'a yaziliyor...")
        conn = db.connect()
        # mbs (Minimum Bahis Sayısı) kolonu yoksa ekle (idempotent)
        try:
            conn.execute("ALTER TABLE matches_v2 ADD COLUMN mbs INTEGER")
            conn.commit()
        except Exception:
            conn.rollback()
        now = datetime.utcnow().isoformat()
        n_ins_m2 = 0
        n_upd_m2 = 0
        n_btts_added = 0

        for r in results:
            try:
                lg = r["lig_code"]
                kickoff = r["kickoff"][:19] if r.get("kickoff") else None
                md = kickoff[:10] if kickoff else None
                if not (lg and md and r["home"] and r["away"]):
                    continue

                # Determine season
                k_dt = datetime.fromisoformat(kickoff[:10]) if kickoff else datetime.now()
                if k_dt.month >= 7:
                    season = f"{k_dt.year}-{(k_dt.year+1)%100:02d}"
                else:
                    season = f"{k_dt.year-1}-{k_dt.year%100:02d}"

                odds = r["odds"]

                # Var mı? — match
                existing = conn.execute("""
                    SELECT match_id FROM matches_v2
                    WHERE league_code=? AND season=? AND matchday=?
                      AND home_team=? AND away_team=?
                """, (lg, season, md, r["home"], r["away"])).fetchone()

                if existing:
                    # UPDATE odds
                    conn.execute("""
                        UPDATE matches_v2
                        SET league_code=CASE WHEN ? != 'ALL' THEN ? ELSE league_code END,
                            closing_1=?, closing_X=?, closing_2=?,
                            closing_over25=?, closing_under25=?,
                            closing_btts_yes=?, closing_btts_no=?,
                            closing_source='iddaa',
                            external_id_iddaa=?,
                            mbs=?,
                            refreshed_at=?
                        WHERE match_id=?
                    """, (
                        lg, lg,
                        odds.get("1"), odds.get("X"), odds.get("2"),
                        odds.get("over25"), odds.get("under25"),
                        odds.get("btts_yes"), odds.get("btts_no"),
                        str(r["event_id"]),
                        r.get("mbs"),
                        now,
                        existing["match_id"]
                    ))
                    n_upd_m2 += 1
                else:
                    # INSERT
                    conn.execute("""
                        INSERT INTO matches_v2 (
                            external_id_iddaa, league_code, season, matchday,
                            kickoff_utc, home_team, away_team, status,
                            closing_1, closing_X, closing_2,
                            closing_over25, closing_under25,
                            closing_btts_yes, closing_btts_no,
                            closing_source, mbs,
                            has_full_odds, has_opening_odds, has_xg, has_result,
                            is_settled,
                            ingested_at, refreshed_at, quality_score
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'NS', ?, ?, ?, ?, ?, ?, ?,
                                  'iddaa', ?, ?, 0, 0, 0, 0, ?, ?, 0.50)
                    """, (
                        str(r["event_id"]), lg, season, md, kickoff,
                        r["home"], r["away"],
                        odds.get("1"), odds.get("X"), odds.get("2"),
                        odds.get("over25"), odds.get("under25"),
                        odds.get("btts_yes"), odds.get("btts_no"),
                        r.get("mbs"),
                        1 if (odds.get("1") and odds.get("X") and odds.get("2")) else 0,
                        now, now
                    ))
                    n_ins_m2 += 1

                if odds.get("btts_yes") and odds.get("btts_no"):
                    n_btts_added += 1

            except Exception as e:
                print(f"  ROW ERR: {e}")

        conn.commit()
        conn.close()

        print(f"\n[5] DB Sonuç:")
        print(f"  matches_v2 inserted: {n_ins_m2}")
        print(f"  matches_v2 updated:  {n_upd_m2}")
        print(f"  KG odds eklendi:     {n_btts_added}")
        print(f"  → KG sinyali için artık market_p hesaplanabilir!")

    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry", action="store_true")
    parser.add_argument("--max", type=int, default=30, help="Max event detail çek")
    parser.add_argument("--all-leagues", action="store_true",
                        help="6 lig filtresi kapalı")
    args = parser.parse_args()

    fetch_and_ingest(
        dry_run=args.dry,
        max_events=args.max,
        only_target_leagues=not args.all_leagues
    )
