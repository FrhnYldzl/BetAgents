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


# iddia competition_id → canonical league_code — YALNIZ ana 6 lig DIŞINDAKİ
# kodlar için sabit eşleme. Ana 6 lig kadro saflığıyla TANINIR (ci_ligleri).
# ⚠️ 19.09.2026 denetimi: ci numaraları sezonla değişiyor ve sabit eşleme
# sessizce çürüyordu — 347 (eski "D1") ve 1484 ("INTL") artık boş; 970
# ("USA1") MLS değil USL Championship'ti (Birmingham Legion, Detroit City…).
# Doğrulanan: 348 = Brezilya Série A · 15 = MLS (Atlanta United–Orlando City).
IDDAA_CI_MAPPING = {
    348: "BRA1",   # Brezilya Série A (doğrulandı 19.09.2026)
    15: "USA1",    # MLS (doğrulandı 19.09.2026)
}
ANA_LIGLER = ("E0", "SP1", "I1", "D1", "F1", "T1")


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
    # ⚠️ "manchester utd" veride "Manchester United" olarak geliyordu ve
    # HIC eslesmiyordu: Premier Lig maci "Premier Lig degil" sayiliyordu.
    # "manchester" ikisini de yakalar, ikisi de E0 — guvenli genelleme.
    "E0": ["manchester","liverpool","chelsea","arsenal",
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


# Takım adında bunlardan biri varsa o maç ANA LİG DEĞİLDİR.
# Kadın/genç/rezerv takımlar erkek A takımıyla AYNI adı taşır:
# "Real Madrid (K)" içinde "real madrid" geçer. Red listesi eskiden
# yalnız lig adına uygulanıyordu, takım adına hiç — bu yüzden kadın
# maçları erkek ligi koduyla kaydedildi.
TAKIM_RED = (" (k)", "(k)", " kadin", " kadın", " women", " fem",
             " u19", " u21", " u23", "u-19", "u-21", "u-23",
             " ii", " b2", " res.", " reserve")


def _isaret_var(ad: str, isaret: str) -> bool:
    """Takim isareti KELIME SINIRINDA gecsin — duz alt dizi degil.

    ⚠️ Duz "in" testi su yanlislari uretiyordu:
        "inter"  -> "Internacional de Bogota"  (Kolombiya -> I1)
        "como"   -> "Comodoro"
        "nice"   -> herhangi bir "...nice..." adi
    Isaretlerin cogu iki sozcuk ("manchester city") ve zararsiz; tehlike
    kisa tek sozcuklerde: inter, milan, roma, lazio, genoa, como, lecce,
    parma, monaco, nice, lens, brest, mainz, koln.
    """
    import re
    # ⚠️ AKSAN NORMALLEŞTİRMESİ — iki taraf da.
    # İşaret listesi umlautlu yazılmış ("mönchengladbach", "bayern münih",
    # "köln", "beşiktaş"), iddaa verisi ise çoğu zaman aksansız geliyor
    # ("Monchengladbach"). Karşılaştırma ham yapılınca GERÇEK Bundesliga
    # maçı "işaret değil" sayılıyor ve lig kodu haksız yere şüpheye
    # düşüyordu. _norm_tr zaten vardı ama burada kullanılmıyordu.
    a = _norm_tr(ad)
    i = _norm_tr(isaret)
    return re.search(r"(?<![a-z0-9])" + re.escape(i) +
                     r"(?![a-z0-9])", a) is not None


def _takim_reddedildi(nm: str) -> bool:
    """Kadın/genç/rezerv takım mı — ana lig oyu kullanamaz."""
    n = " " + nm.lower().strip() + " "
    if any(r in n for r in TAKIM_RED):
        return True
    # "Celta Vigo B", "Barcelona B" gibi rezerv takımlar: tek harf 'b' son sozcuk
    return n.rstrip().endswith(" b")


def learn_ci_leagues(events: list) -> dict:
    """events listesinden ci→league_code eslemesini cogunluk oyuyla ogren.

    ⚠️ Bu bir SEZGIDIR, kanit degil. Artik yalniz lig adinin (cn) hic
    olmadigi yerde kullanilir — cn varsa o otoritedir. Yine de kendi
    icinde saglam olmali, cunku yanlis kod 'ALL'den kotudur.

    Uc koruma:
      1. Kadin/genc/rezerv takim oy KULLANAMAZ (ad ayni, lig degil).
      2. Kazanan ile ikincinin arasi acik olmali — cekismeli ci
         (or. Sampiyonlar Ligi: hem E0 hem I1 takimi var) 'ALL' kalir.
      3. En az 2 oy — tek maclik tesaduf eslesmeyi eler.
    """
    from collections import Counter
    votes: dict = {}
    for ev in events:
        ci = ev.get("ci")
        if ci is None:
            continue
        h = (ev.get("hn") or ev.get("eh") or "")
        a = (ev.get("an") or ev.get("ea") or "")
        if _takim_reddedildi(h) or _takim_reddedildi(a):
            continue                    # 1) kadin/genc/rezerv -> oy yok
        nm = (h + " " + a).lower()
        for lg, markers in TEAM_MARKERS.items():
            if any(_isaret_var(nm, m) for m in markers):
                votes.setdefault(ci, Counter())[lg] += 1
    learned = {}
    for ci, ctr in votes.items():
        sira = ctr.most_common(2)
        lg, n = sira[0]
        ikinci = sira[1][1] if len(sira) > 1 else 0
        if n >= 2 and n > ikinci:       # 2) + 3) net cogunluk sart
            learned[ci] = lg
    return learned


def map_iddaa_league(event: dict) -> str | None:
    """iddia event → canonical league_code: önce ci eşlemesi, sonra lig adı (cn)."""
    ci = event.get("ci")
    if ci is not None and ci in IDDAA_CI_MAPPING:
        return IDDAA_CI_MAPPING[ci]
    return map_league_by_name(event.get("cn") or "")


# ══════════════════════════════════════════════════════════════════════
# 🏷 LİG KODU — yarışmanın KADRO SAFLIĞI (19.09.2026)
# ══════════════════════════════════════════════════════════════════════
# NEDEN: iddaa olaylarla birlikte lig ADINI (cn) artık göndermiyor — üretimde
# tek bir satırda bile yok. Kod yalnız "ünlü takım adı" oylamasıyla (yukarıdaki
# learn_ci_leagues) öğreniliyordu ve bu, yarışmayı içindeki ünlü takımdan
# tanıyordu: Şampiyonlar Ligi (Milan–Benfica) → E0, Lig Kupası ve Championship
# (Bristol City–Watford) → E0, DFB-Pokal ve 3. Liga ("köln" işareti Viktoria
# Köln'ü yakaladı) → D1, İspanyol alt ligi ("Real Madrid C") → SP1, TFF 1. Lig
# → T1. Sezon başı lig maçları ise 'ALL' kaldı (Deportivo–Elche 17.08).
#
# YENİ KURAL: bir yarışma (ci) ancak TAKIMLARININ ÇOĞU o ligin kadrosundaysa
# o ligdir. Kadro = son sezonun football-data adları + daha önce bu kuralla
# tanınmış ci'ların takımları (lig_ci tablosu — football-data güncellenmese
# de kadro kendini sezondan sezona taşır). Kanıt = son 120 günün satırları
# (competition_id ile) + bu çekimin olayları.
ASGARI_TAKIM = 17      # en küçük ana lig 18 takım; kupanın son turları elenir
ASGARI_SAFLIK = 0.70   # takımların en az %70'i ligin kadrosunda
_CI_ONBELLEK: dict = {"ts": None, "v": None}


def _lig_ci_tablosu(conn) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS lig_ci (ci INTEGER PRIMARY KEY, "
                 "league_code TEXT, saflik REAL, n INTEGER, ts TEXT, kaynak TEXT)")
    conn.commit()


# Tohum: 19.09.2026'da takım listelerine bakılarak ELLE doğrulandı. Kanıt
# o gün inceydi (eski kapsam hatası yüzünden Bundesliga'nın 45'inde yalnız 3
# satır vardı) — tohum olmadan saflık kuralı Bundesliga'yı "ana lig değil"
# sayardı. Tohum kalıcı bir sabit eşleme DEĞİL: kayıtlı ci, güçlü karşı kanıtla
# (≥ 17 takım ve kadro payı < %50) düşer; yeni sezonun ci'ları saflıkla tanınır.
TOHUM_CI = {43: "E0", 129: "SP1", 143: "I1", 45: "D1", 381: "F1", 584: "T1"}


def lig_ci_tohumla() -> None:
    conn = db.connect()
    try:
        _lig_ci_tablosu(conn)
        for ci, lg in TOHUM_CI.items():
            conn.execute(
                "INSERT INTO lig_ci (ci, league_code, saflik, n, ts, kaynak) "
                "VALUES (?,?,NULL,0,?,?) ON CONFLICT (ci) DO NOTHING",
                (ci, lg, datetime.utcnow().isoformat(), "elle doğrulandı 19.09.2026"))
        conn.commit()
        for r in conn.execute("SELECT ci, league_code, saflik, n, kaynak FROM lig_ci "
                              "ORDER BY league_code").fetchall():
            print(f"  ci={r[0]:<7} {r[1]:4s} saflık {r[2]} n={r[3]} · {r[4]}")
    finally:
        conn.close()


def _kadrolar(conn) -> dict:
    """Ana ligin kadrosu: son 450 günün football-data adları + lig_ci'da o
    lige tanınmış yarışmaların son 400 gündeki takımları."""
    from collections import defaultdict
    simdi = datetime.utcnow()
    out: dict = defaultdict(set)
    yer = ",".join("'" + l + "'" for l in ANA_LIGLER)
    for r in conn.execute(
            "SELECT league_code, home_team, away_team FROM matches_v2 "
            "WHERE external_id_fd IS NOT NULL AND kickoff_utc >= ? "
            "AND league_code IN (" + yer + ")",
            ((simdi - timedelta(days=450)).isoformat(),)).fetchall():
        out[r[0]].update((r[1], r[2]))
    try:
        for r in conn.execute(
                "SELECT l.league_code, m.home_team, m.away_team FROM matches_v2 m "
                "JOIN lig_ci l ON l.ci = CAST(m.competition_id AS INTEGER) "
                "WHERE m.kickoff_utc >= ?",
                ((simdi - timedelta(days=400)).isoformat(),)).fetchall():
            out[r[0]].update((r[1], r[2]))
    except Exception:
        conn.rollback()
    return out


def _ci_takimlari(conn, events: list) -> dict:
    """ci → farklı takım adları: son 120 günün satırları + bu çekimin olayları."""
    from collections import defaultdict
    out: dict = defaultdict(set)
    for r in conn.execute(
            "SELECT competition_id, home_team, away_team FROM matches_v2 "
            "WHERE competition_id IS NOT NULL AND kickoff_utc >= ?",
            ((datetime.utcnow() - timedelta(days=120)).isoformat(),)).fetchall():
        try:
            out[int(r[0])].update(x for x in (r[1], r[2]) if x)
        except (TypeError, ValueError):
            continue
    for ev in events or []:
        try:
            ci = int(ev.get("ci"))
        except (TypeError, ValueError):
            continue
        out[ci].update(x for x in (ev.get("hn"), ev.get("an")) if x)
    return out


def ci_ligleri(conn, events: list, taze_dk: int = 60) -> tuple[dict, set]:
    """(tanınan {ci: lig}, 'ana lig DEĞİL' kesin ci kümesi).

    Bir ci ancak şu üç şartla X olur:
      · ASGARI_TAKIM (17) farklı takım — kupanın son turu elenir
      · takımların ≥ %70'i X'in kadrosunda
      · başka hiçbir ana ligden 2+ takım yok — Avrupa kupası elenir
    ≥ 8 farklı takımı olup şartları sağlamayan ci 'ana lig değil'dir: eski
    yanlış kodu düzeltmeye yeter kanıt var. Daha azı 'bilinmiyor' (satırın
    mevcut kodu korunur)."""
    simdi = datetime.utcnow()
    if (_CI_ONBELLEK["v"] is not None and _CI_ONBELLEK["ts"] is not None
            and (simdi - _CI_ONBELLEK["ts"]).total_seconds() < taze_dk * 60):
        return _CI_ONBELLEK["v"]
    from takim_adi import esle_ad, _jeton, _onek, _temiz, _yedek_mi, ELLE
    _lig_ci_tablosu(conn)
    kadro = _kadrolar(conn)
    havuz = {lg: {t for ad in adlar for t in _jeton(ad)} for lg, adlar in kadro.items()}
    kayitli = {int(r[0]): r[1] for r in conn.execute(
        "SELECT ci, league_code FROM lig_ci").fetchall()}
    bellek: dict = {}

    def uye(ad: str, lg: str) -> bool:
        k = (ad, lg)
        if k not in bellek:
            t = _temiz(ad)
            if _yedek_mi(ad):
                bellek[k] = False
            elif ad in kadro[lg] or (t in ELLE and ELLE[t] in kadro[lg]):
                bellek[k] = True        # birebir ya da elle eşleme — süzgeçten ÖNCE
            else:
                j = _jeton(ad)
                bellek[k] = (any(_onek(a, u) for a in j for u in havuz.get(lg, ()))
                             and esle_ad(ad, kadro[lg]) is not None)
        return bellek[k]

    tanindi: dict = {}
    degil: set = set()
    kayit = []
    for ci, takimlar in _ci_takimlari(conn, events).items():
        if ci in IDDAA_CI_MAPPING:
            continue
        n = len(takimlar)
        if n < 4:
            if ci in kayitli:
                tanindi[ci] = kayitli[ci]
            continue
        say = {lg: sum(1 for t in takimlar if uye(t, lg)) for lg in ANA_LIGLER}
        en = max(say, key=say.get)
        diger = max((v for k, v in say.items() if k != en), default=0)
        if n >= ASGARI_TAKIM and say[en] >= ASGARI_SAFLIK * n and diger <= 1:
            tanindi[ci] = en
            kayit.append((ci, en, round(say[en] / n, 3), n, simdi.isoformat(), "saflık"))
        elif ci in kayitli:
            lg = kayitli[ci]
            # Kayıtlı ci yalnız GÜÇLÜ karşı kanıtla düşer: ci numarası yeni
            # sezonda başka yarışmaya verildiyse (ör. 45 → 2. Bundesliga)
            # kadro payı çöker.
            if n >= ASGARI_TAKIM and say.get(lg, 0) < 0.5 * n:
                degil.add(ci)
                print(f"  ⚠️ lig_ci {ci}={lg} düştü: {say.get(lg, 0)}/{n} kadro payı")
            else:
                tanindi[ci] = lg
        elif n >= 8:
            degil.add(ci)
    try:
        for k in kayit:
            conn.execute(
                "INSERT INTO lig_ci (ci, league_code, saflik, n, ts, kaynak) "
                "VALUES (?,?,?,?,?,?) "
                "ON CONFLICT (ci) DO UPDATE SET league_code=excluded.league_code, "
                "saflik=excluded.saflik, n=excluded.n, ts=excluded.ts, "
                "kaynak=excluded.kaynak", k)
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"  (lig_ci yazılamadı: {e})")
    v = (tanindi, degil)
    _CI_ONBELLEK.update(ts=simdi, v=v)
    return v


def lig_kodu(ev: dict, tanindi: dict, degil: set) -> tuple[str, bool]:
    """(kod, kesin_mi). kesin=False → mevcut satırın kodu korunur."""
    try:
        ci = int(ev.get("ci"))
    except (TypeError, ValueError):
        return "ALL", False
    if ci in IDDAA_CI_MAPPING:
        return IDDAA_CI_MAPPING[ci], True
    if ci in tanindi:
        return tanindi[ci], True
    if ci in degil:
        return "ALL", True
    return "ALL", False


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


def _fetch_and_ingest(dry_run: bool = False, max_events: int = 50,
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

    # 1.5) LİG KODU — yarışmanın KADRO SAFLIĞI (bkz. ci_ligleri, 19.09.2026).
    # ⚠️ Eski yol (takım adı oylaması, learn_ci_leagues) Şampiyonlar Ligi'ni,
    # Lig Kupası'nı ve Championship'i E0 yapıyordu; lig adı (cn) iddaa'dan
    # artık HİÇ gelmiyor. Oylama kullanılmaz. Kural değişmedi: YANLIŞ KOD,
    # 'ALL'DAN KÖTÜDÜR — tanınmayan yarışma 'ALL' kalır.
    conn_l = db.connect()
    try:
        tanindi, degil = ci_ligleri(conn_l, events)
        izlenen, acik = _takip_kumeleri(conn_l)
    finally:
        conn_l.close()
    n_bilinmez = 0
    for ev in events:
        kod, kesin = lig_kodu(ev, tanindi, degil)
        ev["_league_code"], ev["_lig_kesin"] = kod, kesin
        n_bilinmez += 0 if kesin else 1
    print(f"  lig kodu: {len(tanindi)} ana lig yarışması tanındı "
          f"{sorted(tanindi.items())} · {len(degil)} yarışma 'ana lig değil' · "
          f"{n_bilinmez} olay bilinmiyor")

    # 2) HANGİ OLAYLAR İŞLENİR
    # ⚠️ 19.09.2026: yalnız ilk max_events (120) olay işleniyordu ve liste
    # tarihe göre SIRALI DEĞİL. Önümüzdeki 3 günün 27 ana lig maçının 22'sinin
    # fiyatı 17-56 saattir tazelenmemişti: ajanlar bayat fiyattan oynuyor,
    # ana pazar CLV'lerinin %49'u TAM SIFIR çıkıyordu (giriş = "kapanış" = aynı
    # bayat fiyat). Artık: ilk max_events + TAKİPTEKİ her maç (veritabanında
    # oynanmamış) + 7 gün içindeki ana lig maçları. Fiyatlar olayın içinde
    # gelir — ek API çağrısı yok, yalnız veritabanı yazımı.
    simdi_ts = datetime.utcnow().timestamp()

    def _ana_yakin(ev: dict) -> bool:
        return (ev.get("_league_code") in ANA_LIGLER and bool(ev.get("_lig_kesin"))
                and 0 < (ev.get("d") or 0) - simdi_ts <= 7 * 86400)

    def _birlesik(*gruplar) -> list:
        gor, out = set(), []
        for g in gruplar:
            for ev in g:
                k = str(ev.get("i"))
                if k and k not in gor:
                    gor.add(k)
                    out.append(ev)
        return out

    if only_target_leagues:
        secili = [ev for ev in events if _ana_yakin(ev)]
    else:
        secili = _birlesik(events[:max_events],
                           [e for e in events if str(e.get("i")) in izlenen],
                           [e for e in events if _ana_yakin(e)])
    print(f"  işlenecek: {len(secili)} olay (ilk {max_events} + takipteki "
          f"{len(izlenen)} maç + 7 gün içi ana lig)")

    if not secili:
        print("  İşlenecek olay yok.")
        return

    # 3) Fiyatlar — olayın içinden; yoksa SINIRLI detay çağrısı
    print(f"\n[2] {len(secili)} olay işleniyor...")
    results = []
    detay_hak = 40
    for i, ev in enumerate(secili):
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
                  f"({ev.get('_league_code')}{'' if ev.get('_lig_kesin') else '?'}, "
                  f"ci={ev.get('ci','?')}, "
                  f"{kickoff_iso[:16] if kickoff_iso else '?'})")
            continue

        # Direkt event'in m (markets) field'ı varsa kullan, yoksa detail çek
        markets = ev.get("m", [])
        if not markets:
            if detay_hak <= 0:
                continue
            detay_hak -= 1
            detail = fetch_event_detail(event_id)
            if not detail: continue
            markets = detail.get("m", [])

        odds_combined = {}
        for m in markets:
            odds_combined.update(extract_odds_from_market(m))

        results.append({
            "event_id": event_id,
            "lig_code": ev.get("_league_code", "ALL"),
            "lig_kesin": bool(ev.get("_lig_kesin")),
            "kickoff": kickoff_iso,
            "home": home_name,
            "away": away_name,
            "competition_id": ev.get("ci"),
            # ⚠️ Lig ADI eskiden ATILIYORDU. (19.09: iddaa artık göndermiyor —
            # alan boş kalır; ci her satırda saklanır, lig ci'dan kurulur.)
            "lig_adi": (ev.get("cn") or "").strip() or None,
            "mbs": ev.get("mbc"),   # iddaa Minimum Bahis Sayısı (1=tek olur, 3=3'lü zorunlu)
            "odds": odds_combined,
        })

        if (i+1) % 50 == 0:
            print(f"  {i+1}/{len(secili)} ...")

    print(f"\n[3] {len(results)} olay fiyatlandı")

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
    # Kapsam (19.09): ilk max_events + 7 gün içi ana lig + AÇIK bahisli maçlar
    # — açık bahsin kapanış fiyatı (CLV) kaçmasın. Takipteki her maç DEĞİL:
    # defter yalnız değişen fiyatı yazsa da günün ilk çekimi hepsini yazar.
    if not dry_run:
        try:
            import market_book
            defter = _birlesik(events[:max_events],
                               [e for e in events if _ana_yakin(e)],
                               [e for e in events if str(e.get("i")) in acik])
            n_mb = market_book.capture(defter)
            if n_mb:
                print(f"  🎰 pazar defteri: {n_mb} yeni fiyat kaydi ({len(defter)} olay)")
        except Exception as e:
            print(f"  (pazar defteri atlandi: {e})")

    # 4) Database insert
    if not dry_run and results:
        print(f"\n[4] matches_v2 + signal_snapshots'a yaziliyor...")
        conn = db.connect()
        # Kolonlar yoksa ekle — VARSA TABLOYA DOKUNMA. Koşulsuz ALTER her
        # 3 saatte bir matches_v2'nin en ağır kilidini istiyordu; skor
        # yazan ya da okuyan her işlem onun arkasında bekliyordu.
        # (bu dosyada `db` = database modülü; yardımcı merkezî db.py'de)
        from db import kolon_ekle as _kolon_ekle
        # mbs (Minimum Bahis Sayısı)
        _kolon_ekle(conn, "matches_v2", "mbs", "INTEGER")
        # iddaa lig adı — kanonik koda çevrilemeyen ligler için TEK bilgi
        _kolon_ekle(conn, "matches_v2", "iddaa_league_name", "TEXT")
        now = datetime.utcnow().isoformat()
        n_ins_m2 = 0
        n_upd_m2 = 0
        n_btts_added = 0

        # Kimlik araması TOPLU: olay başına bir SELECT, proxy üzerinden
        # yüzlerce gidiş-dönüş demekti (kapsam 120'den ~400 olaya çıktı).
        var_olan: dict = {}
        _ids = [str(r["event_id"]) for r in results if r.get("event_id")]
        for _i in range(0, len(_ids), 400):
            _p = _ids[_i:_i + 400]
            for _row in conn.execute(
                    "SELECT external_id_iddaa, match_id FROM matches_v2 "
                    "WHERE external_id_iddaa IN (" + ",".join("?" * len(_p)) + ")",
                    tuple(_p)).fetchall():
                var_olan[str(_row[0])] = _row[1]

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

                # Var mı? — KİMLİK SIRASI ÖNEMLİ
                #
                # ⚠️ Eskiden aramada league_code VARDI. Öğrenilen kod
                # fetch'ler arasında değişince aynı maç BULUNAMIYOR ve
                # YENİDEN EKLENİYORDU. Üretimde 107 mükerrer grup oluştu;
                # Nottingham Forest - Brest tek iddaa event'iyle DÖRT satır
                # (ALL + E0 + I1 + SP1). Mükerrer maç satırı her ölçümü
                # bozar — aynı maç kalibrasyona birden çok kez girer.
                #
                # Doğru kimlik kaynağın kendi id'sidir: external_id_iddaa.
                # Yedek anahtarda da league_code YOK — football-data'dan
                # gelmiş bir satırı iddaa akışıyla eşleştirirken kodlar
                # zaten farklı olur.
                existing_id = var_olan.get(str(r.get("event_id")))
                if existing_id is None:
                    _ex = conn.execute("""
                        SELECT match_id FROM matches_v2
                        WHERE season=? AND matchday=?
                          AND home_team=? AND away_team=?
                    """, (season, md, r["home"], r["away"])).fetchone()
                    existing_id = _ex["match_id"] if _ex else None

                if existing_id is not None:
                    # UPDATE odds
                    # Lig kodu yalnız KESİN karar varsa yazılır (tanınan lig
                    # ya da "ana lig değil" kanıtı) — eski yanlış kod da böyle
                    # düzelir. Bilinmiyorsa mevcut kod korunur.
                    conn.execute("""
                        UPDATE matches_v2
                        SET league_code=CASE WHEN ?=1 THEN ? ELSE league_code END,
                            closing_1=?, closing_X=?, closing_2=?,
                            closing_over25=?, closing_under25=?,
                            closing_btts_yes=?, closing_btts_no=?,
                            closing_source='iddaa',
                            external_id_iddaa=?,
                            mbs=?,
                            iddaa_league_name=COALESCE(?, iddaa_league_name),
                            competition_id=COALESCE(?, competition_id),
                            refreshed_at=?
                        WHERE match_id=?
                    """, (
                        1 if r.get("lig_kesin") else 0, lg,
                        odds.get("1"), odds.get("X"), odds.get("2"),
                        odds.get("over25"), odds.get("under25"),
                        odds.get("btts_yes"), odds.get("btts_no"),
                        str(r["event_id"]),
                        r.get("mbs"),
                        r.get("lig_adi"),
                        r.get("competition_id"),
                        now,
                        existing_id
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
                            iddaa_league_name, competition_id,
                            has_full_odds, has_opening_odds, has_xg, has_result,
                            is_settled,
                            ingested_at, refreshed_at, quality_score
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'NS', ?, ?, ?, ?, ?, ?, ?,
                                  'iddaa', ?, ?, ?, ?, 0, 0, 0, 0, ?, ?, 0.50)
                    """, (
                        str(r["event_id"]), lg, season, md, kickoff,
                        r["home"], r["away"],
                        odds.get("1"), odds.get("X"), odds.get("2"),
                        odds.get("over25"), odds.get("under25"),
                        odds.get("btts_yes"), odds.get("btts_no"),
                        r.get("mbs"),
                        r.get("lig_adi"),
                        r.get("competition_id"),
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


def _takip_kumeleri(conn) -> tuple[set, set]:
    """(takipteki oynanmamış maçların iddaa id'leri, AÇIK bahisli maçlarınki)."""
    izlenen = {str(r[0]) for r in conn.execute(
        "SELECT external_id_iddaa FROM matches_v2 WHERE is_settled=0 "
        "AND external_id_iddaa IS NOT NULL AND kickoff_utc > ?",
        (datetime.utcnow().isoformat(),)).fetchall()}
    try:
        acik = {str(r[0]) for r in conn.execute(
            "SELECT DISTINCT COALESCE(pb.iddaa_event_id, m.external_id_iddaa) "
            "FROM paper_bets pb JOIN paper_coupons pc ON pc.coupon_id=pb.coupon_id "
            "LEFT JOIN matches_v2 m ON m.match_id=pb.match_id "
            "WHERE pc.status='open'").fetchall() if r[0]}
    except Exception:
        conn.rollback()
        acik = set()
    return izlenen, acik


_KILIT = __import__("threading").Lock()


def kapanis_yakala(pencere_dk: int = 45) -> dict:
    """⏱ KAPANIŞ YAKALAMA — maça ≤ pencere_dk kalan maçların fiyatını yaz.

    Worker 15 dakikada bir çağırır. Maliyet: TEK API çağrısı (fiyatlar
    olayın içinde), detay çağrısı yok; pazar defterine yalnız DEĞİŞEN fiyat.
    Kapsam: takipteki maçlar + açık bahisli maçlar + tanınmış ana lig maçları.

    NEDEN (19.09.2026, kullanıcı onayı): ana çekim 3 saatte bir koşuyor —
    son saatlerdeki fiyat hareketi kaçıyordu; CLV'nin "kapanışı" maçtan
    saatler (çoğu zaman günler) önceki fiyattı."""
    if not _KILIT.acquire(blocking=False):
        return {"olay": 0, "atlandi": "ana çekim sürüyor"}
    try:
        events = fetch_events(sport_type=1)
        simdi_ts = datetime.utcnow().timestamp()
        conn = db.connect()
        try:
            tanindi, degil = ci_ligleri(conn, events)
            izlenen, acik = _takip_kumeleri(conn)
        finally:
            conn.close()
        secili = []
        for ev in events:
            kalan = (ev.get("d") or 0) - simdi_ts
            if not (0 < kalan <= pencere_dk * 60):
                continue
            kod, kesin = lig_kodu(ev, tanindi, degil)
            ev["_league_code"], ev["_lig_kesin"] = kod, kesin
            k = str(ev.get("i"))
            if k in izlenen or k in acik or (kod in ANA_LIGLER and kesin):
                secili.append(ev)
        if not secili:
            return {"olay": 0, "defter": 0, "mac": 0}
        n_mb = 0
        try:
            import market_book
            n_mb = market_book.capture(secili)
        except Exception as e:
            print(f"  (kapanış: pazar defteri atlandı: {e})")
        conn = db.connect()
        n_m = 0
        try:
            simdi = datetime.utcnow().isoformat()
            for ev in secili:
                odds: dict = {}
                for m in ev.get("m") or []:
                    odds.update(extract_odds_from_market(m))
                if not odds:
                    continue
                conn.execute(
                    "UPDATE matches_v2 SET closing_1=COALESCE(?,closing_1), "
                    "closing_X=COALESCE(?,closing_X), closing_2=COALESCE(?,closing_2), "
                    "closing_over25=COALESCE(?,closing_over25), "
                    "closing_under25=COALESCE(?,closing_under25), "
                    "closing_btts_yes=COALESCE(?,closing_btts_yes), "
                    "closing_btts_no=COALESCE(?,closing_btts_no), refreshed_at=? "
                    "WHERE external_id_iddaa=? AND is_settled=0",
                    (odds.get("1"), odds.get("X"), odds.get("2"),
                     odds.get("over25"), odds.get("under25"),
                     odds.get("btts_yes"), odds.get("btts_no"),
                     simdi, str(ev.get("i"))))
                n_m += 1
            conn.commit()
        finally:
            conn.close()
        return {"olay": len(secili), "defter": n_mb, "mac": n_m}
    finally:
        _KILIT.release()


def fetch_and_ingest(dry_run: bool = False, max_events: int = 50,
                     only_target_leagues: bool = True):
    """Ana ingest — kapanış yakalamayla AYNI ANDA koşmaz (kilit): ikisi de
    matches_v2 ve pazar defterine yazar; üst üste binerse defter mükerrer
    satır alır."""
    with _KILIT:
        return _fetch_and_ingest(dry_run=dry_run, max_events=max_events,
                                 only_target_leagues=only_target_leagues)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry", action="store_true")
    parser.add_argument("--max", type=int, default=30, help="Max event detail çek")
    parser.add_argument("--all-leagues", action="store_true",
                        help="6 lig filtresi kapalı")
    parser.add_argument("--lig-ci-tohum", action="store_true",
                        help="lig_ci tablosunu elle doğrulanmış 6 ci ile tohumla")
    parser.add_argument("--kapanis", action="store_true",
                        help="maça ≤45 dk kalan maçların fiyatını bir kez yakala")
    args = parser.parse_args()

    if args.lig_ci_tohum:
        lig_ci_tohumla()
    elif args.kapanis:
        print(kapanis_yakala())
    else:
        fetch_and_ingest(
            dry_run=args.dry,
            max_events=args.max,
            only_target_leagues=not args.all_leagues
        )
