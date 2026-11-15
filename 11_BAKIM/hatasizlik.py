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

Kullanım:
  python 11_BAKIM/hatasizlik.py            tam denetim — COMMIT ÖNCESİ bu
  python 11_BAKIM/hatasizlik.py --hizli    üreteç aşamasını ATLAR (geliştirme)

Her satırın süresi ölçülür ve en pahalı adımlar sonda listelenir: darboğaz
dışarıdan ölçülmeden görünür olsun. Ölçüm için önizleme sunucusu (streamlit,
port 8610) KAPALI olmalı — açıkken SQLite kilidi denetimi yavaşlatır.
"""
from __future__ import annotations

import contextlib
import io
import os
import sys
import time
import traceback
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
# ⚠️ ELLE SAYILMAZ. Bu liste sabitti ("02_VERI", "08_AI_TRADER", …) ve
# 12_SWAT eklenince denetim onun modüllerini içe aktaramadı — hem modül
# hem kendi-testi aşaması ModuleNotFoundError verdi. Numaralı klasörler
# dosya sisteminden okunur; bir sonraki klasör kendiliğinden gelir.
for _d in sorted(KOK.iterdir()):
    if _d.is_dir() and _d.name[:2].isdigit():
        p = str(_d)
        if p not in sys.path:
            sys.path.append(p)

GECTI, KALDI, ATLANDI = "GEÇTİ", "KALDI", "atlandı"
# (aşama, ad, durum, not, süre sn)
_sonuc: list[tuple[str, str, str, str, float]] = []


def _ekle(asama: str, ad: str, durum: str, not_: str = "",
          sure: float = 0.0) -> None:
    _sonuc.append((asama, ad, durum, not_, sure))


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
    """Çağır, çıktıyı yut, (sonuç, hata, süre) döndür.

    Süre her çağrıda ölçülür: darboğaz aramak için denetimi dışarıdan
    profillemek gerekmesin. 15.11.2026'da üreteç aşaması 9 dakikalık komut
    sınırını aştı ve hangi adımın yediği ancak ayrı bir ölçüm betiğiyle
    bulunabildi — o betik artık gereksiz, sayı raporun içinde.
    """
    t0 = time.perf_counter()
    try:
        with contextlib.redirect_stdout(_Yutucu()), \
             contextlib.redirect_stderr(_Yutucu()):
            return fn(*a, **k), None, time.perf_counter() - t0
    except BaseException as e:            # SystemExit dahil — sayfa sys.exit ederse de yakala
        return None, e, time.perf_counter() - t0


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


# Denetim indeksleri — ui_onizleme_al.py yeni görüntüleri bunlarla kurar;
# burada ELDEKİ görüntü için de kurulur, 300 MB'ı yeniden çekmek gerekmesin.
#
# ⚠️ ix_mv_idd (düz sütun indeksi) BU İŞİ GÖRMÜYOR: pazar/SWAT üreteçleri
# maçı CAST'li eşitlikle buluyor (CAST(mv.external_id_iddaa AS TEXT) =
# CAST(mo.iddaa_event_id AS TEXT)); ifadeye sarılı sütun için SQLite sütun
# indeksini KULLANAMIYOR, plan "SCAN mv" oluyor. Ölçüldü (15.11.2026):
#   indeks yok  → pazar üreteci 594 sn   (denetimin %98'i)
#   ifade indeksi → 0,12 sn              (yaklaşık 5000 kat)
# Sadece PLAN değişir, SQL ve sonuç aynı kalır: üretim sorgusuna dokunulmaz.
DENETIM_INDEKS = (
    "CREATE INDEX IF NOT EXISTS ix_mv_idd_txt ON matches_v2 "
    "(CAST(external_id_iddaa AS TEXT))",
    "CREATE INDEX IF NOT EXISTS ix_mo_mk ON market_odds (market)",
)


def _indeks_kur(yol: str) -> str:
    """Anlık görüntüde denetim indekslerini garantiye al — (durum metni)."""
    import sqlite3
    try:
        c = sqlite3.connect(yol, timeout=5)
    except Exception as e:
        return f"⚠️ indeks kurulamadı ({_kisa(e)}) — denetim YAVAŞ koşacak"
    try:
        var = {r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='index'")}
        yeni, t0 = [], time.perf_counter()
        for sql in DENETIM_INDEKS:
            ad = sql.split("EXISTS ")[1].split(" ON ")[0]
            if ad in var:
                continue
            c.execute(sql)
            yeni.append(ad)
        c.commit()
        if not yeni:
            return "indeks: hazır"
        return (f"indeks kuruldu: {', '.join(yeni)} "
                f"({time.perf_counter() - t0:.2f} sn)")
    except Exception as e:
        # Kilit (önizleme sunucusu açık) ya da eski SQLite → denetim yine
        # koşsun, ama SESSİZ kalmasın: yavaşlığın nedeni görünür olmalı.
        return (f"⚠️ indeks kurulamadı ({_kisa(e)}) — denetim YAVAŞ koşacak; "
                f"önizleme sunucusu (port 8610) açıksa kapatın")
    finally:
        c.close()


# ----------------------------------------------------------------------
# 1 · MODÜLLER
# ----------------------------------------------------------------------
# Canlı yolda kullanılan modüller. Arşiv/tek seferlik betikler DIŞARIDA:
# onların kırık olması ürünü etkilemez, listeye girerse denetim gürültülenir.
MODULLER = [
    ("02_VERI", ["db", "agents", "paper_engine", "auto_play", "auto_settle",
                 "sistem", "surekli_puan", "iddia_defteri", "clv",
                 "multiplier_agent", "turuncu_agent", "combo_tables",
                 "recompute_portfolio", "fetch_results",
                 "kasa", "kupon_orkestra", "ferhan_kupon",
                 "kupon_master", "denetci", "haber", "finans",
                 "adil_taban"]),
    ("09_TOTO", ["toto_db", "toto_takim", "deger", "kalabalik", "pazar",
                 "geri_test", "canli", "sportoto", "kadro", "vibe_db"]),
    ("10_CANLI", ["canli_db", "canli_kaynak", "canli_model"]),
    ("11_BAKIM", ["bakim_kontrol"]),
    ("12_SWAT", ["swat_db", "swat_kaynak"]),
    ("13_PROJE", ["proje_veri", "proje_olcum", "proje_panel",
                  "kupon_fisi"]),
]


def asama_modul() -> None:
    import importlib
    for klasor, adlar in MODULLER:
        for ad in adlar:
            _, hata, sure = _sessiz(importlib.import_module, ad)
            if hata:
                _ekle("1 MODÜL", f"{klasor}/{ad}", KALDI, _kisa(hata), sure)
            else:
                _ekle("1 MODÜL", f"{klasor}/{ad}", GECTI, "", sure)


# ----------------------------------------------------------------------
# 2 · PANEL SAYFALARI
# ----------------------------------------------------------------------
def asama_sayfa() -> None:
    try:
        import app_v2 as APP
    except Exception as e:
        _ekle("2 SAYFA", "app_v2 içe aktarma", KALDI, _kisa(e))
        return
    _takim_kapsama(APP)
    # Açılış sayfası gezinmede gerçekten var mı? ACILIS yanlış yazılırsa
    # Streamlit sessizce ilk sayfayı açar ve kimse fark etmez.
    _adlar = {g[0] for _b, _s in APP.SAYFA_TANIM for g in _s}
    _ac = getattr(APP, "ACILIS", None)
    if _ac in _adlar:
        _ekle("2 SAYFA", "açılış sayfası", GECTI, str(_ac))
    else:
        _ekle("2 SAYFA", "açılış sayfası", KALDI,
              f"ACILIS={_ac!r} SAYFA_TANIM'da yok")
    # ⚠️ SAAT DİLİMİ TEK SAYI OLMALI. app_v2._TR_FARK ile
    # kupon_fisi.TR_FARKI_SAAT ayrı yerlerde duruyor; ayrışırlarsa aynı
    # maç iki sayfada iki farklı saatte görünür ve kullanıcı maçı
    # bültende bulamaz (yaşandı 15.11.2026: kupon fişi UTC basıyordu,
    # maçlar 3 saat erken görünüyordu).
    try:
        import kupon_fisi as _KF
        a, b = getattr(APP, "_TR_FARK", None), getattr(_KF, "TR_FARKI_SAAT", None)
        if a is not None and a == b:
            _ekle("2 SAYFA", "saat dilimi tutarlılığı", GECTI, f"UTC+{a}")
        else:
            _ekle("2 SAYFA", "saat dilimi tutarlılığı", KALDI,
                  f"app_v2._TR_FARK={a} ≠ kupon_fisi.TR_FARKI_SAAT={b}")
    except Exception as e:
        _ekle("2 SAYFA", "saat dilimi tutarlılığı", KALDI, _kisa(e))
    for bolum, sayfalar in APP.SAYFA_TANIM:
        for giris in sayfalar:
            ad, fn = giris[0], giris[1]
            # ⚠️ _toto_sayfa ile sarılı sayfalar hatayı YUTAR ve sorunsuz
            # döner. Sadece istisnaya bakmak onları denetlenemez kılıyordu;
            # yutulan hata app_v2._SAYFA_HATA'ya yazılıyor, onu da okuyoruz.
            _once = len(getattr(APP, "_SAYFA_HATA", ()))
            _, hata, sure = _sessiz(fn)
            _yutulan = list(getattr(APP, "_SAYFA_HATA", ()))[_once:]
            if hata:
                _ekle("2 SAYFA", f"{bolum} · {ad}", KALDI, _kisa(hata), sure)
            elif _yutulan:
                _ekle("2 SAYFA", f"{bolum} · {ad}", KALDI,
                      "yutulan hata: " + _yutulan[0][1][:160], sure)
            else:
                _ekle("2 SAYFA", f"{bolum} · {ad}", GECTI, "", sure)


# ----------------------------------------------------------------------
# 3 · KENDİ TESTLERİ
# ----------------------------------------------------------------------
def _takim_kapsama(APP) -> None:
    """Her takım, kendisini gösteren HER YERDE tanımlı mı?

    ⚠️ Bu kontrol beş kez tekrarlanan bir hatanın üstüne yazıldı. Takım
    üyeliği agents.PROFILES'tan türetiliyor ama onu TÜKETEN yerler kendi
    listelerini tutuyordu ve yeni takım eklenince her seferinde biri
    unutuldu:
      1 app_v2.load_lig          → KIRMIZI | TURUNCU | TOTO | SISTEM
      2 app_v2.TAKIM_TANIM       → sayfa başlığı/renk (KeyError'la düştü)
      3 app_v2.TAKIM_SIRA        → ajan dosyası ajanı BULAMADI, kullanıcı
                                   ajanın sayfasına gidemiyordu
      4 vibe_studyo.KAPSAM       → kendi testi yakaladı
      5 app_v2 kasa döngüsü      → ajan listede hiç görünmüyordu
    Üçü koddan kaldırıldı (artık türetiliyor), ikisi insan okunur metin
    tuttuğu için elle kalıyor — ama artık SESSİZ kalmıyorlar.
    """
    try:
        import agents as A
        takimlar = {p.get("takim", "mavi") for p in A.PROFILES.values()}
    except Exception as e:
        _ekle("2 SAYFA", "takım kapsaması", KALDI, _kisa(e))
        return
    for ad, kaynak in (
            ("TAKIM_SIRA", set(getattr(APP, "TAKIM_SIRA", ()))),
            ("TAKIM_TANIM", set(getattr(APP, "TAKIM_TANIM", {}))),
    ):
        eksik = sorted(takimlar - kaynak)
        if eksik:
            _ekle("2 SAYFA", f"takım kapsaması · {ad}", KALDI,
                  f"PROFILES'ta olup {ad}'da olmayan: {', '.join(eksik)}")
        else:
            _ekle("2 SAYFA", f"takım kapsaması · {ad}", GECTI,
                  f"{len(takimlar)} takım")
    try:
        lig = APP.load_lig()
        eksik = sorted(takimlar - set(lig))
        if eksik:
            _ekle("2 SAYFA", "takım kapsaması · load_lig", KALDI,
                  f"grup döndürmeyen takım: {', '.join(eksik)}")
        else:
            _ekle("2 SAYFA", "takım kapsaması · load_lig", GECTI,
                  f"{len(lig)} grup")
    except Exception as e:
        _ekle("2 SAYFA", "takım kapsaması · load_lig", KALDI, _kisa(e))


def asama_kendi_testi() -> None:
    import importlib
    # ⚠️ Yeni modülün kendi testi buraya YAZILMAZSA denetimden geçmiş
    # sayılır ama hiç koşmaz — sessiz bir boşluk. Liste elle tutuluyor.
    for ad in ("toto_takim", "sistem", "kupon_orkestra", "ferhan_kupon",
               "kasa", "vibe_studyo", "canli_db", "paper_engine",
               "agents", "swat_db", "swat_kaynak", "kupon_master",
               "denetci", "haber", "finans", "proje_veri",
               "kupon_fisi", "adil_taban"):
        try:
            m = importlib.import_module(ad)
        except Exception as e:
            _ekle("3 KENDİ TESTİ", ad, KALDI, _kisa(e))
            continue
        fn = getattr(m, "kendi_testi", None)
        if fn is None:
            _ekle("3 KENDİ TESTİ", ad, ATLANDI, "kendi_testi yok")
            continue
        r, hata, sure = _sessiz(fn)
        if hata:
            _ekle("3 KENDİ TESTİ", ad, KALDI, _kisa(hata), sure)
        elif r:
            _ekle("3 KENDİ TESTİ", ad, KALDI,
                  f"{len(r)} sorun: {r[0][:80]}", sure)
        else:
            _ekle("3 KENDİ TESTİ", ad, GECTI, "", sure)


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
    # 🧺 MAÇ HAVUZU — aşama boyunca BİR KEZ okunur ve bütün motor-ailesi
    # üreteçlerine (engine/confirm/value/midband/joker/sistem) aynı liste
    # geçer. Ölçüldü: 300 maç × 112 sütun = 0,04 sn, yani havuzu ajan başına
    # yeniden okumak darboğaz DEĞİLDİ; darboğaz pazar üretecinin kendi
    # içindeki CAST'li JOIN'iydi (bkz. _indeks_kur).
    t0 = time.perf_counter()
    c = sqlite3.connect(os.environ["BETAGENTS_SQLITE_PATH"])
    c.row_factory = sqlite3.Row
    M = [dict(r) for r in c.execute(
        "SELECT * FROM matches_v2 WHERE closing_1>1.05 AND closing_X>1.05 "
        "AND closing_2>1.05 LIMIT 300")]
    c.close()
    eng = PaperEngine()
    _ekle("4 ÜRETEÇ", "(maç havuzu · paylaşılan)", GECTI,
          f"{len(M)} maç · {len(M[0]) if M else 0} sütun · bir kez okundu",
          time.perf_counter() - t0)
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
        # ⚠️ Her mod AÇIKÇA yazılır; bilinmeyen mod sessizce _engine_candidates'e
        # DÜŞMEZ. Düşüyordu: 'toto' modu motor üretecine gidip 65 aday
        # raporladı (gerçek Toto üreteci 3 veriyor) — yani o satır Toto'yu hiç
        # sınamadan YEŞİL yazdı. Denetimin yanlış yeşili, kırmızısından beterdir.
        if mode == "master":
            fn, args = A._master_kuponlari, (p, pid, 100.0)
        elif mode == "swat":
            fn, args = A._swat_adaylari, (p, pid)
        elif mode == "pazar":
            fn, args = A._pazar_adaylari, (p, pid)
        elif mode == "toto":
            fn, args = A._toto_adaylari, (p, pid)
        elif mode == "sistem":
            fn, args = A._sistem_adaylari, (p, pid, M, eng)
        elif mode == "midband":
            fn, args = A._midband_candidates, (p, pid, M)
        elif mode == "joker":
            fn, args = A._joker_candidates, (p, pid, M)
        elif mode in ("engine", "confirm", "value"):
            fn, args = A._engine_candidates, (p, pid, M, eng)
        else:
            _ekle("4 ÜRETEÇ", f"{mode} ({pid})", KALDI,
                  "bu mod denetimde TANIMSIZ — sessizce motora düşmesin diye "
                  "açıkça kaldı yazılıyor; hatasizlik.py'ye dalı ekle")
            continue
        # ⏱ Süre ajan başına yazılır. Mod bazında tek çağrı koşuyor (aynı
        # modun ikinci ajanı atlanıyor), yani buradaki sayı "o üretecin bir
        # çağrısı" demektir — üretimde aynı modda 5 ajan varsa canlı maliyet
        # bunun 5 katıdır.
        r, hata, sure = _sessiz(fn, *args)
        if hata:
            _ekle("4 ÜRETEÇ", f"{mode} ({pid})", KALDI, _kisa(hata), sure)
        else:
            _ekle("4 ÜRETEÇ", f"{mode} ({pid})", GECTI,
                  f"{len(r or [])} aday", sure)


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
    r, hata, sure = _sessiz(BK.kos)
    if hata:
        _ekle("6 BAKIM", "kos()", KALDI, _kisa(hata), sure)
        return
    # Tek çağrı bütün kontrolleri koşuyor: süre ilk satıra yazılır, geri
    # kalanı 0 görünür — satır başına ölçüm yokken sahte dağıtım yapmayalım.
    ilk = sure
    for k in r["kontroller"]:
        d = k["durum"]
        durum = KALDI if d == "kirmizi" else (ATLANDI if d in ("sari", "bilgi") else GECTI)
        _ekle("6 BAKIM", k["id"], durum, f"{k['ad']} = {k['deger']}", ilk)
        ilk = 0.0


# ----------------------------------------------------------------------
# RAPOR
# ----------------------------------------------------------------------
ASAMALAR = (("1 MODÜL", asama_modul), ("2 SAYFA", asama_sayfa),
            ("3 KENDİ TESTİ", asama_kendi_testi), ("4 ÜRETEÇ", asama_uretec),
            ("5 ŞEMA", asama_sema), ("6 BAKIM", asama_bakim))

# --hizli'nın atladığı aşamalar. Yalnız ÜRETEÇ: ölçüldü (15.11.2026), geri
# kalan beş aşama toplam ~30 sn ve gerçek kırılmaları onlar yakalıyor —
# atlanacak aşama "yavaş olan" değil, "yavaş olup az şey yakalayan"dır.
HIZLI_ATLA = {"4 ÜRETEÇ"}


def kos(hizli: bool = False) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    yol = _kilitle()
    print("HATASIZLIK DENETİMİ" + ("  ⚡ HIZLI KİP" if hizli else ""))
    print(f"veri: {yol}  (anlık görüntü — üretime bağlanılmaz)")
    print(f"{_indeks_kur(yol)}")
    if hizli:
        print("⚡ --hizli: " + ", ".join(sorted(HIZLI_ATLA)) +
              " KOŞMAYACAK — bu TAM denetim değil, commit öncesi bayraksız koş")
    print()
    sureler: dict[str, float] = {}
    for ad, fn in ASAMALAR:
        if hizli and ad in HIZLI_ATLA:
            # ⚠️ Atlanan aşama SATIR OLARAK yazılır. Sessizce geçilse
            # raporda hiç görünmez ve "denetimden geçti" sanılır — denetimin
            # yanlış yeşili, kırmızısından beterdir.
            _ekle(ad, "(AŞAMA ATLANDI · --hizli)", ATLANDI,
                  "koşmadı — tam denetim için bayrağı kaldır")
            sureler[ad] = 0.0
            continue
        t0 = time.perf_counter()
        try:
            fn()
        except BaseException as e:
            _ekle(ad, "(aşama çöktü)", KALDI, _kisa(e))
            traceback.print_exc(limit=3)
        sureler[ad] = time.perf_counter() - t0

    simge = {GECTI: "✓", KALDI: "✗", ATLANDI: "·"}
    asama_simdi = None
    for asama, ad, durum, not_, sure in _sonuc:
        if asama != asama_simdi:
            print(f"\n── {asama} " +
                  "─" * max(1, 54 - len(asama)) +
                  f" {sureler.get(asama, 0.0):6.2f} sn")
            asama_simdi = asama
        # Süre yalnız anlamlıysa yazılır (0,05 sn altı gürültü).
        s = f"{sure:6.2f}s " if sure >= 0.05 else " " * 8
        print(f"  {simge[durum]} {ad:34}{s}{not_[:54]}")

    g = sum(1 for x in _sonuc if x[2] == GECTI)
    k = sum(1 for x in _sonuc if x[2] == KALDI)
    a = sum(1 for x in _sonuc if x[2] == ATLANDI)
    atlanan = [x for x in _sonuc if x[2] == ATLANDI and "AŞAMA ATLANDI" in x[1]]
    print("\n" + "=" * 70)
    print(f"SONUÇ: {g} geçti · {k} KALDI · {a} atlandı  (toplam {len(_sonuc)})")
    print(f"SÜRE : " + " · ".join(f"{ad.split(' ', 1)[1]} {s:.1f}sn"
                                  for ad, s in sureler.items())
          + f"  = {sum(sureler.values()):.1f} sn")
    # 🐌 En pahalı adımlar: bir sonraki darboğaz ayrı betik gerektirmeden
    # görünsün. 15.11.2026'da 594 sn'lik üreteç ancak elle profillenerek
    # bulunmuştu.
    pahali = sorted(_sonuc, key=lambda x: -x[4])[:5]
    if pahali and pahali[0][4] >= 1.0:
        print("\nEN PAHALI ADIMLAR:")
        for asama, ad, _d, _n, sure in pahali:
            if sure >= 1.0:
                print(f"  {sure:7.2f} sn  [{asama}] {ad}")
    if k:
        print("\nKALANLAR:")
        for asama, ad, durum, not_, _s in _sonuc:
            if durum == KALDI:
                print(f"  ✗ [{asama}] {ad} — {not_}")
    if atlanan:
        # Hızlı kipte "HATASIZ" YAZILMAZ: atlanan aşama denetlenmiş değildir.
        print("\n⚠️ TAM DENETİM DEĞİL — atlanan aşama: " +
              ", ".join(x[0] for x in atlanan) +
              "\n   commit öncesi: python 11_BAKIM/hatasizlik.py (bayraksız)")
    elif not k:
        print("✅ HATASIZ — her aşama geçti.")
    return 1 if k else 0


def _argv(arg: list[str]) -> bool:
    """--hizli var mı? Tanınmayan bayrakta DUR.

    ⚠️ Sessiz kabul etmiyoruz: "--hizl" yazan kullanıcı tam denetim koştuğunu
    fark etmez, 10 dakika bekler ve aracı suçlar.
    """
    kalan = [a for a in arg if a not in ("--hizli", "-h", "--help", "--yardim")]
    if kalan:
        sys.exit(f"tanınmayan argüman: {' '.join(kalan)}\n"
                 "kullanım: python 11_BAKIM/hatasizlik.py [--hizli]")
    if {"-h", "--help", "--yardim"} & set(arg):
        sys.exit(__doc__)
    return "--hizli" in arg


if __name__ == "__main__":
    sys.exit(kos(hizli=_argv(sys.argv[1:])))
