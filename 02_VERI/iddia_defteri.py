"""
BETAGENTS · İDDİA DEFTERİ — ajanın KOTASIZ görüşünü ileriye doğru kaydet
========================================================================
Neden gerekti
-------------
surekli_puan_kos.py ajanları geçmiş maçlarda puanlıyor, ama 20 ajanın
yalnız 5'ini koşturabiliyor. Kalan 15'i geçmişe uygulanamıyor:

  ÇARPAN ailesi (SİMETRİ, KAVŞAK, KOMBO, BANT, DEVRE)
      `market_odds`tan okuyor ve sorgusu `kickoff_utc > şimdi` —
      tasarımı gereği YALNIZ gelecek maçlara bakıyor. Kombine fiyatların
      geçmişi tutulmadığı için geriye koşturmak imkânsız, tablo eklense bile.
  POPÜLER / TERS
      iddaa yazarlarının BEKLEYEN tahminlerinden besleniyor; geçmiş
      tahminler kapandığı an aday havuzundan çıkıyor.
  KONSEY
      diğer ajanların o anki oylarını topluyor.
  HOCA / SİMYACI
      bağımsız Poisson modeli nokta-zamanlı reyting ister; anlık görüntünün
      tamamından kurmak geleceği sızdırır.
  TURUNCU beşlisi
      kendi izole hattından besleniyor.

Bu ajanları ölçmenin tek dürüst yolu İLERİYE doğru: her gün ne söylediklerini
yaz, sonuç gelince derecelendir. Birkaç ay sonra hepsi aynı ölçekte olur.

Neden kuponlardan ayrı bir defter
----------------------------------
Kupon defteri ajanın OYNADIĞINI tutar; bu defter SÖYLEDİĞİNİ tutar. Fark
büyük: bir ajan günde 2 kupon kurabiliyorsa görüş bildirdiği maçların
çoğunu oynamaz ve o görüşler ölçülmeden kaybolur. Örneklem farkı ölçüldü
(25.09.2026): defterde 1.271 sonuçlanmış bahis vardı, aynı dönemde
puanlanabilir maç 5.772.

Ne YAPMAZ
---------
Bahis yerleştirmez, kupon kurmaz, kasaya dokunmaz. Yalnız kendi tablosuna
(`ajan_iddia`) yazar; BetAgents'ın tablolarını salt-okunur kullanır.
Kotalar, kadro dışı bırakma, kayıp serisi molası UYGULANMAZ — amaç ajanın
kısıtsız görüşünü kaydetmek.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

import db  # noqa: E402

TR = timezone(timedelta(hours=3))
EVREN_LIMIT = 300          # build_coupons 200 alıyor; iddia için biraz geniş


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ----------------------------------------------------------------------
# TABLO
# ----------------------------------------------------------------------
def kur(conn=None) -> None:
    """Kendi tablosunu kur. BetAgents'ın tablolarına DOKUNMAZ."""
    kapat = conn is None
    conn = conn or db.connect()
    try:
        # Conn.is_postgres bir ÖZNİTELİK (bool), metot değil — modül düzeyindeki
        # db.is_postgres() ile karıştırılmasın.
        pg = bool(getattr(conn, "is_postgres", False))
        oto = "SERIAL PRIMARY KEY" if pg else "INTEGER PRIMARY KEY AUTOINCREMENT"
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS ajan_iddia (
                id            {oto},
                kayit_ts      TEXT,
                ajan          TEXT,
                match_id      INTEGER,
                iddaa_event_id TEXT,
                lig           TEXT,
                ev            TEXT,
                dep           TEXT,
                kickoff_utc   TEXT,
                market        TEXT,
                pick          TEXT,
                oran          REAL,
                sinyal        TEXT,
                skor          REAL,
                lead_h        REAL,
                -- derecelendirme (sonuç gelince dolar)
                sonuc_ev      INTEGER,
                sonuc_dep     INTEGER,
                tuttu         INTEGER,
                kapanis_oran  REAL,
                derece_ts     TEXT
            )""")
        # Aynı ajan aynı maçta aynı iddiayı günde bir kez yazsın.
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_ajan_iddia_tekil "
                     "ON ajan_iddia (ajan, match_id, market, pick, "
                     "               substr(kayit_ts,1,10))")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_ajan_iddia_derece "
                     "ON ajan_iddia (tuttu, kickoff_utc)")
        conn.commit()
    finally:
        if kapat:
            conn.close()


# ----------------------------------------------------------------------
# KAYIT
# ----------------------------------------------------------------------
def _evren(conn) -> list[dict]:
    """Ajanların göreceği maç evreni — build_coupons ile aynı, portföye özel
    dışlamalar OLMADAN (iddia defteri kotasız çalışır)."""
    rows = conn.execute(
        "SELECT * FROM matches_v2 WHERE is_settled=0 AND kickoff_utc > ? "
        "AND closing_1 IS NOT NULL ORDER BY kickoff_utc ASC LIMIT ?",
        (_ts(), EVREN_LIMIT)).fetchall()
    return [dict(r) for r in rows]


def _adaylar(A, pid: str, prof: dict, matches: list[dict], eng) -> list[dict]:
    """Ajanın üretecini çağır — build_coupons'daki dağıtımın aynısı, kapılar yok."""
    tag = f"[{pid.split('_')[0]}]"
    mode = prof.get("mode")
    if mode == "multiplier":
        return A._multiplier_candidates(prof, tag)
    if mode == "council":
        return A._council_candidates(prof, tag, matches, eng)
    if mode == "turuncu":
        import turuncu_agent as T
        return T.adaylar(prof, tag)
    if mode == "midband":
        return A._midband_candidates(prof, tag, matches)
    if mode == "fade":
        return A._fade_candidates(prof, tag)
    if mode == "joker":
        return A._joker_candidates(prof, tag, matches)
    if mode == "popular":
        return A._popular_candidates(prof, tag)
    return A._engine_candidates(prof, tag, matches, eng)


def kaydet(sessiz: bool = False) -> dict:
    """Bugünün iddialarını yaz. Bahis YERLEŞTİRMEZ."""
    import contextlib, io as _io
    import agents as A
    from paper_engine import PaperEngine

    conn = db.connect()
    try:
        kur(conn)
        matches = _evren(conn)
        if not matches:
            return {"mac": 0, "iddia": 0, "ajan": 0}
        eng = PaperEngine()
        # ON CONFLICT DO NOTHING istisna üretmediği için "kaç satır yazıldı"
        # ancak tablonun büyümesinden okunur — denenen sayısı yanıltır.
        onceki = conn.execute("SELECT COUNT(*) FROM ajan_iddia").fetchone()[0]
        denenen = 0
        calisan = 0
        hatalar: list[str] = []
        for pid, prof in A.PROFILES.items():
            if prof.get("retired"):
                continue
            tampon = _io.StringIO()
            try:
                with contextlib.redirect_stdout(tampon):
                    picks = _adaylar(A, pid, prof, matches, eng)
            except Exception as e:
                hatalar.append(f"{pid}: {type(e).__name__}: {str(e)[:60]}")
                continue
            calisan += 1
            for p in picks or []:
                m = p.get("_match") or {}
                try:
                    # ⚠️ DERS: önce try/except + rollback yazmıştım. Tekrar eden
                    # bir iddia geldiğinde rollback AYNI İŞLEMDEKİ ÖNCEKİ TÜM
                    # iddiaları da siliyordu — günün kaydı sessizce boşalıyordu.
                    # ON CONFLICT DO NOTHING istisna üretmez, işlem bozulmaz.
                    conn.execute(
                        "INSERT INTO ajan_iddia (kayit_ts, ajan, match_id, iddaa_event_id, "
                        "lig, ev, dep, kickoff_utc, market, pick, oran, sinyal, skor, lead_h) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
                        "ON CONFLICT DO NOTHING",
                        (_ts(), pid, m.get("match_id"), str(m.get("external_id_iddaa") or ""),
                         m.get("league_code"), m.get("home_team"), m.get("away_team"),
                         m.get("kickoff_utc"), p.get("market"), str(p.get("pick")),
                         float(p.get("odds") or 0), p.get("signal_name"),
                         float(p.get("signal_score") or 0), p.get("lead_h")))
                    denenen += 1
                except Exception as e:
                    hatalar.append(f"{pid} yazım: {type(e).__name__}: {str(e)[:50]}")
                    conn.rollback()
                    break          # bu ajanın kalanını deneme, işlem bozuk
        conn.commit()
        yazilan = conn.execute("SELECT COUNT(*) FROM ajan_iddia").fetchone()[0] - onceki
    finally:
        conn.close()
    r = {"mac": len(matches), "iddia": yazilan, "denenen": denenen,
         "ajan": calisan, "hata": hatalar}
    if not sessiz:
        print(f"[iddia defteri] {r['ajan']} ajan · {r['mac']} maç · "
              f"{r['iddia']} yeni iddia ({r['denenen']} görüş, kalanı bugün zaten yazılı)"
              + (f" · {len(hatalar)} hata" if hatalar else ""))
        for h in hatalar:
            print(f"   {h}")
    return r


# ----------------------------------------------------------------------
# DERECELENDİRME
# ----------------------------------------------------------------------
def derecelendir(sessiz: bool = False) -> dict:
    """Sonucu gelmiş iddiaları derecelendir."""
    import surekli_puan as SP

    conn = db.connect()
    try:
        kur(conn)
        rows = conn.execute(
            "SELECT i.id, i.match_id, i.market, i.pick, m.home_score, m.away_score, "
            "       m.closing_1, m.closing_X, m.closing_2 "
            "FROM ajan_iddia i JOIN matches_v2 m ON m.match_id = i.match_id "
            "WHERE i.tuttu IS NULL AND m.home_score IS NOT NULL "
            "  AND m.away_score IS NOT NULL").fetchall()
        n = 0
        for r in rows:
            r = dict(r)
            t = SP.tuttu_mu(r["market"], str(r["pick"]),
                            int(r["home_score"]), int(r["away_score"]))
            if t is None:
                continue
            kap = None
            if r["market"] == "1X2":
                kap = r.get({"1": "closing_1", "X": "closing_X",
                             "2": "closing_2"}.get(str(r["pick"]), ""))
            conn.execute(
                "UPDATE ajan_iddia SET sonuc_ev=?, sonuc_dep=?, tuttu=?, "
                "kapanis_oran=?, derece_ts=? WHERE id=?",
                (int(r["home_score"]), int(r["away_score"]), 1 if t else 0,
                 kap, _ts(), r["id"]))
            n += 1
        conn.commit()
    finally:
        conn.close()
    if not sessiz:
        print(f"[iddia defteri] {n} iddia derecelendirildi")
    return {"derecelendirilen": n}


# ----------------------------------------------------------------------
# RAPOR
# ----------------------------------------------------------------------
def rapor() -> None:
    """İleriye dönük karne — surekli_puan ile aynı ölçüt ve aynı taban."""
    import surekli_puan as SP

    conn = db.connect()
    try:
        kur(conn)
        iddia = [dict(r) for r in conn.execute(
            "SELECT * FROM ajan_iddia WHERE tuttu IS NOT NULL").fetchall()]
        maclar = [dict(r) for r in conn.execute(
            "SELECT * FROM matches_v2 WHERE home_score IS NOT NULL "
            "AND away_score IS NOT NULL AND closing_1 IS NOT NULL").fetchall()]
    finally:
        conn.close()

    if not iddia:
        print("İDDİA DEFTERİ · henüz derecelenmiş iddia yok.\n"
              "  Defter her gün dolar; ilk anlamlı karne birkaç hafta sonra.")
        return

    kal = SP.Kalibrasyon(maclar)
    gunler = sorted({str(x["kayit_ts"])[:10] for x in iddia})
    print(f"İDDİA DEFTERİ · {len(iddia)} derecelenmiş iddia · "
          f"{len(gunler)} gün ({gunler[0]} → {gunler[-1]})\n")

    from collections import defaultdict
    g = defaultdict(list)
    for x in iddia:
        g[x["ajan"]].append(x)

    sonuc = []
    for ajan, k in g.items():
        def _ak(k=k):
            for x in k:
                yield x["market"], x["pick"], float(x["oran"] or 0), {
                    "home_score": x["sonuc_ev"], "away_score": x["sonuc_dep"]}
        sonuc.append(SP.puanla(_ak(), ajan, kal))

    print(SP.BASLIK)
    print("-" * len(SP.BASLIK))
    for o in sorted([x for x in sonuc if x.get("n")], key=lambda x: -x["z"]):
        print(SP.satir(o))
    print("\nYORUM")
    for o in sorted([x for x in sonuc if x.get("n")], key=lambda x: -x["z"]):
        print(f"   {o['ajan']:22} {SP.yorum(o)}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    emir = sys.argv[1] if len(sys.argv) > 1 else "rapor"
    if emir == "kaydet":
        kaydet()
    elif emir == "derecelendir":
        derecelendir()
    elif emir == "kur":
        kur()
        print("ajan_iddia tablosu hazır")
    else:
        rapor()
