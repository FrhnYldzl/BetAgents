"""
HATASIZLIK DENETİMİ — her panel, her modül, her üreteç tek tek koşturulur
=========================================================================
Göz kararı denetim işe yaramıyor: bir sayfa ancak AÇILDIĞINDA patlar, bir
üreteç ancak ÇAĞRILDIĞINDA. Bu araç hepsini gerçekten çalıştırır ve geçti/
kaldı yazar.

Altı aşama:
  1 MODÜL      canlı yoldaki her modül içe aktarılıyor mu
  2 SAYFA      panelin 22 sayfasının her biri çağrılıyor mu (çizim dahil)
  3 KENDİ TESTİ modüllerin kendi sınavları (toto_takim, sistem, …)
  4 ÜRETEÇ     her ajan modu aday üretebiliyor mu
  5 ŞEMA       kodun beklediği tablo/sütunlar var mı
  6 BAKIM      Haftalık Bakım kontrolleri

⚠️ ÜRETİME BAĞLANMAZ. db.database_url kapatılır ve bağlantı anlık görüntüye
(02_VERI/ui_onizleme.db) zorlanır. Üretim bağlantısı tespit edilirse denetim
DURUR — yanlış veritabanında "hatasız" demek, denetim yapmamaktan kötüdür.

⚠️ SINAMA SADAKATİ: anlık görüntü tabloları KISITSIZ kurulur (ui_onizleme_al
şemayı sade CREATE ile yazar). Bu yüzden PRIMARY KEY / UNIQUE'e bağlı
davranışlar (INSERT OR IGNORE, ON CONFLICT) burada üretimdeki gibi
davranmaz. Şema aşaması bunu ayrıca raporlar.

Kullanım:  python 11_BAKIM/hatasizlik.py
"""
from __future__ import annotations

import contextlib
import io
import os
import sys
import traceback
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
for alt in ("02_VERI", "08_AI_TRADER", "09_TOTO", "10_CANLI", "11_BAKIM"):
    p = str(KOK / alt)
    if p not in sys.path:
        sys.path.append(p)

GECTI, KALDI, ATLANDI = "GEÇTİ", "KALDI", "atlandı"
_sonuc: list[tuple[str, str, str, str]] = []     # (aşama, ad, durum, not)


def _ekle(asama: str, ad: str, durum: str, not_: str = "") -> None:
    _sonuc.append((asama, ad, durum, not_))


def _kisa(e: BaseException) -> str:
    return f"{type(e).__name__}: {str(e)[:110]}"


class _Yutucu(io.StringIO):
    """stdout yerine geçer ama reconfigure() çağrısını YUTAR.

    ⚠️ Düz StringIO kullanınca auto_play / auto_settle / fetch_results
    "KALDI" verdi: o modüller içe aktarılırken sys.stdout.reconfigure()
    çağırıyor ve StringIO'da o metot yok. Ürün sağlamdı, ARACIN kendisi
    yanlış alarm üretiyordu — denetim aracının yanlış alarmı, denetlenen
    üründen daha tehlikelidir.
    """

    def reconfigure(self, *a, **k):
        return None


def _sessiz(fn, *a, **k):
    """Çağır, çıktıyı yut, (sonuç, hata) döndür."""
    try:
        with contextlib.redirect_stdout(_Yutucu()), \
             contextlib.redirect_stderr(_Yutucu()):
            return fn(*a, **k), None
    except BaseException as e:            # SystemExit dahil — sayfa sys.exit ederse de yakala
        return None, e


# ----------------------------------------------------------------------
# ÜRETİM KİLİDİ
# ----------------------------------------------------------------------
def _kilitle() -> str:
    os.environ["BETAGENTS_DB"] = "sqlite"
    anlik = KOK / "02_VERI" / "ui_onizleme.db"
    if not anlik.exists():
        sys.exit(f"anlık görüntü yok: {anlik}\n  önce: python 02_VERI/ui_onizleme_al.py")
    os.environ["BETAGENTS_SQLITE_PATH"] = str(anlik)
    import db
    db.database_url = lambda: ""           # .env'deki üretim URL'ini bastır
    if db.is_postgres():
        sys.exit("DENETİM DURDU: bağlantı PostgreSQL'e çözümleniyor. "
                 "Üretim verisinde denetim koşulmaz.")
    return str(anlik)


# ----------------------------------------------------------------------
# 1 · MODÜLLER
# ----------------------------------------------------------------------
# Canlı yolda kullanılan modüller. Arşiv/tek seferlik betikler DIŞARIDA:
# onların kırık olması ürünü etkilemez, listeye girerse denetim gürültülenir.
MODULLER = [
    ("02_VERI", ["db", "agents", "paper_engine", "auto_play", "auto_settle",
                 "sistem", "surekli_puan", "iddia_defteri", "clv",
                 "multiplier_agent", "turuncu_agent", "combo_tables",
                 "recompute_portfolio", "fetch_results"]),
    ("09_TOTO", ["toto_db", "toto_takim", "deger", "kalabalik", "pazar",
                 "geri_test", "canli", "sportoto", "kadro", "vibe_db"]),
    ("10_CANLI", ["canli_db", "canli_kaynak", "canli_model"]),
    ("11_BAKIM", ["bakim_kontrol"]),
]


def asama_modul() -> None:
    import importlib
    for klasor, adlar in MODULLER:
        for ad in adlar:
            _, hata = _sessiz(importlib.import_module, ad)
            if hata:
                _ekle("1 MODÜL", f"{klasor}/{ad}", KALDI, _kisa(hata))
            else:
                _ekle("1 MODÜL", f"{klasor}/{ad}", GECTI)


# ----------------------------------------------------------------------
# 2 · PANEL SAYFALARI
# ----------------------------------------------------------------------
def asama_sayfa() -> None:
    try:
        import app_v2 as APP
    except Exception as e:
        _ekle("2 SAYFA", "app_v2 içe aktarma", KALDI, _kisa(e))
        return
    for bolum, sayfalar in APP.SAYFA_TANIM:
        for giris in sayfalar:
            ad, fn = giris[0], giris[1]
            _, hata = _sessiz(fn)
            if hata:
                _ekle("2 SAYFA", f"{bolum} · {ad}", KALDI, _kisa(hata))
            else:
                _ekle("2 SAYFA", f"{bolum} · {ad}", GECTI)


# ----------------------------------------------------------------------
# 3 · KENDİ TESTLERİ
# ----------------------------------------------------------------------
def asama_kendi_testi() -> None:
    import importlib
    for ad in ("toto_takim", "sistem"):
        try:
            m = importlib.import_module(ad)
        except Exception as e:
            _ekle("3 KENDİ TESTİ", ad, KALDI, _kisa(e))
            continue
        fn = getattr(m, "kendi_testi", None)
        if fn is None:
            _ekle("3 KENDİ TESTİ", ad, ATLANDI, "kendi_testi yok")
            continue
        r, hata = _sessiz(fn)
        if hata:
            _ekle("3 KENDİ TESTİ", ad, KALDI, _kisa(hata))
        elif r:
            _ekle("3 KENDİ TESTİ", ad, KALDI, f"{len(r)} sorun: {r[0][:80]}")
        else:
            _ekle("3 KENDİ TESTİ", ad, GECTI)


# ----------------------------------------------------------------------
# 4 · AJAN ÜRETEÇLERİ
# ----------------------------------------------------------------------
def asama_uretec() -> None:
    import sqlite3
    try:
        import agents as A
        from paper_engine import PaperEngine
    except Exception as e:
        _ekle("4 ÜRETEÇ", "agents içe aktarma", KALDI, _kisa(e))
        return
    c = sqlite3.connect(os.environ["BETAGENTS_SQLITE_PATH"])
    c.row_factory = sqlite3.Row
    M = [dict(r) for r in c.execute(
        "SELECT * FROM matches_v2 WHERE closing_1>1.05 AND closing_X>1.05 "
        "AND closing_2>1.05 LIMIT 300")]
    c.close()
    eng = PaperEngine()
    # mod → (fonksiyon, argümanlar). Veritabanına giden üreteçler (çarpan,
    # popüler, ters, konsey, turuncu) burada ATLANIR: canlı fiyat/yazar
    # akışı ister, anlık görüntüde yok. Onların sağlığı 1. aşamada
    # (içe aktarma) ve canlıda agent_diag ile izlenir.
    DIS = {"multiplier", "popular", "fade", "council", "turuncu"}
    gorulen = set()
    for pid, prof in A.PROFILES.items():
        mode = prof.get("mode") or "engine"
        if mode in gorulen:
            continue
        gorulen.add(mode)
        if mode in DIS:
            _ekle("4 ÜRETEÇ", f"{mode} ({pid})", ATLANDI, "canlı veri ister")
            continue
        p = dict(prof)
        p["min_lead_h"] = 0
        if mode == "sistem":
            fn, args = A._sistem_adaylari, (p, pid, M, eng)
        elif mode == "midband":
            fn, args = A._midband_candidates, (p, pid, M)
        elif mode == "joker":
            fn, args = A._joker_candidates, (p, pid, M)
        else:
            fn, args = A._engine_candidates, (p, pid, M, eng)
        r, hata = _sessiz(fn, *args)
        if hata:
            _ekle("4 ÜRETEÇ", f"{mode} ({pid})", KALDI, _kisa(hata))
        else:
            _ekle("4 ÜRETEÇ", f"{mode} ({pid})", GECTI, f"{len(r or [])} aday")


# ----------------------------------------------------------------------
# 5 · ŞEMA
# ----------------------------------------------------------------------
BEKLENEN_TABLO = {
    "paper_portfolio": ["portfolio_id", "current_bankroll", "initial_bankroll",
                        "benched", "ihtar_count", "era_no"],
    "paper_coupons": ["coupon_id", "portfolio_id", "status", "stake",
                      "actual_return"],
    "paper_bets": ["bet_id", "coupon_id", "match_id", "market", "pick",
                   "odds", "status", "clv"],
    "matches_v2": ["match_id", "closing_1", "closing_X", "closing_2",
                   "home_score", "away_score", "status", "is_settled"],
    "agent_diag": ["ts", "pid", "status", "detail"],
}


def asama_sema() -> None:
    import sqlite3
    c = sqlite3.connect(os.environ["BETAGENTS_SQLITE_PATH"])
    for tablo, sutunlar in BEKLENEN_TABLO.items():
        try:
            var = {d[1] for d in c.execute(f"PRAGMA table_info({tablo})")}
        except Exception as e:
            _ekle("5 ŞEMA", tablo, KALDI, _kisa(e))
            continue
        if not var:
            _ekle("5 ŞEMA", tablo, KALDI, "tablo yok")
            continue
        eksik = [x for x in sutunlar if x not in var]
        if eksik:
            _ekle("5 ŞEMA", tablo, KALDI, f"eksik sütun: {', '.join(eksik)}")
        else:
            _ekle("5 ŞEMA", tablo, GECTI, f"{len(var)} sütun")
    # Kısıt sadakati — anlık görüntü PK taşımıyorsa açıkça söyle
    r = c.execute("SELECT sql FROM sqlite_master WHERE name='paper_portfolio'").fetchone()
    if r and "PRIMARY KEY" not in (r[0] or "").upper():
        _ekle("5 ŞEMA", "kısıt sadakati", ATLANDI,
              "anlık görüntüde PRIMARY KEY yok — INSERT OR IGNORE burada "
              "üretimdeki gibi davranmaz (üretimde PK var)")
    c.close()


# ----------------------------------------------------------------------
# 6 · HAFTALIK BAKIM
# ----------------------------------------------------------------------
def asama_bakim() -> None:
    try:
        import bakim_kontrol as BK
    except Exception as e:
        _ekle("6 BAKIM", "içe aktarma", KALDI, _kisa(e))
        return
    r, hata = _sessiz(BK.kos)
    if hata:
        _ekle("6 BAKIM", "kos()", KALDI, _kisa(hata))
        return
    for k in r["kontroller"]:
        d = k["durum"]
        durum = KALDI if d == "kirmizi" else (ATLANDI if d in ("sari", "bilgi") else GECTI)
        _ekle("6 BAKIM", k["id"], durum, f"{k['ad']} = {k['deger']}")


# ----------------------------------------------------------------------
# RAPOR
# ----------------------------------------------------------------------
def kos() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    yol = _kilitle()
    print("HATASIZLIK DENETİMİ")
    print(f"veri: {yol}  (anlık görüntü — üretime bağlanılmaz)\n")
    for ad, fn in (("1 MODÜL", asama_modul), ("2 SAYFA", asama_sayfa),
                   ("3 KENDİ TESTİ", asama_kendi_testi), ("4 ÜRETEÇ", asama_uretec),
                   ("5 ŞEMA", asama_sema), ("6 BAKIM", asama_bakim)):
        try:
            fn()
        except BaseException as e:
            _ekle(ad, "(aşama çöktü)", KALDI, _kisa(e))
            traceback.print_exc(limit=3)

    simge = {GECTI: "✓", KALDI: "✗", ATLANDI: "·"}
    asama_simdi = None
    for asama, ad, durum, not_ in _sonuc:
        if asama != asama_simdi:
            print(f"\n── {asama} " + "─" * (62 - len(asama)))
            asama_simdi = asama
        print(f"  {simge[durum]} {ad:34} {not_[:62]}")

    g = sum(1 for x in _sonuc if x[2] == GECTI)
    k = sum(1 for x in _sonuc if x[2] == KALDI)
    a = sum(1 for x in _sonuc if x[2] == ATLANDI)
    print("\n" + "=" * 70)
    print(f"SONUÇ: {g} geçti · {k} KALDI · {a} atlandı  (toplam {len(_sonuc)})")
    if k:
        print("\nKALANLAR:")
        for asama, ad, durum, not_ in _sonuc:
            if durum == KALDI:
                print(f"  ✗ [{asama}] {ad} — {not_}")
    else:
        print("✅ HATASIZ — her aşama geçti.")
    return 1 if k else 0


if __name__ == "__main__":
    sys.exit(kos())
