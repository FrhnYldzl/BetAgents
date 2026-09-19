"""
🟠 TURUNCU TAKIM — MODEL: iddaa'dan BAĞIMSIZ skor dağılımı
==========================================================
Kaynak: kullanıcının "Kombine Market Fiyatlama" eki (2 Eylül 2026) ve
kombine_sinama.py'nin kendi verimizdeki ölçümleri (19 Eylül 2026).

NEDEN AYRI BİR TAKIM: Kırmızı takımın skor modeli gol beklentisini (λ/μ)
iddaa'nın KENDİ oranından çözer — model iddaa'nın aynasıdır, kombine fiyatı
ondan ayrışamaz (ölçüldü: medyan edge −%16). Turuncu λ/μ'yü takımların
GEÇMİŞ GOLLERİNDEN üretir; iddaa'nın fiyatına hiç bakmaz. Belgenin dediği
gibi "ajanların asıl eğitileceği yer" burası.

İZOLASYON: bu modül hiçbir takımın kodunu, tablosunu ya da ayarını
değiştirmez; diğer takımların modüllerini import ETMEZ. matches_v2'yi
yalnız OKUR.

MODEL (Dixon & Coles 1997, zaman ağırlıklı, lig bazında):
    λ = C · H · A_ev · D_dep          μ = C · A_dep · D_ev
    A hücum gücü, D savunma zaafı (lig ortalaması 1), H ev avantajı.
    Ağırlık w = 2^(−yaş/180 gün); 3 yıldan eski maç kullanılmaz.
    Az maçlı takım 4 sanal maçla lig ortalamasına çekilir.
    ρ (düşük skor düzeltmesi) lig bazında, modelin KENDİ λ/μ'süyle eğitim
    verisinden en çok olabilirlikle kestirilir. Belgenin ρ = −0,13'ü
    KULLANILMAZ: kendi verimizde −0,054 ölçüldü ve −0,13 beraberliği
    %30'a şişiriyordu (gerçek %24,6).

İKİ AD DÜNYASI: geçmiş sezonlar football-data adlarıyla ("Man United"),
güncel sezon iddaa adlarıyla ("Manchester United", "Bayern Münih").
esle() iddaa adını aynı ligin football-data adına bağlar; bağlanamayan
takım yalnız kendi (iddaa adıyla) geçmişiyle ölçülür — yetmezse tahmin
YAPILMAZ, uydurulmaz.

    python turuncu_model.py --esleme     # ad eşleme raporu
    python turuncu_model.py --sinav      # ön kayıtlı ileriye dönük sınav
"""
from __future__ import annotations

import math
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import db

LIGLER = ("E0", "SP1", "I1", "D1", "F1", "T1")
YARI_OMUR = 180.0           # gün
PENCERE = 1095              # gün
SANAL_MAC = 4.0             # lig ortalamasına çeken sanal maç
MIN_ETKIN = 3.0             # tahmin için takımın en az etkin maç ağırlığı
N = 10                      # skor matrisi 0..9
RHO_IZGARA = [x / 1000 for x in range(-250, 101, 5)]

# ── Pazarlar: iddaa pazar defterinin (market_odds) etiketleriyle ──────
def _sonuc(r):
    return lambda h, a: ("1" if h > a else ("0" if h == a else "2")) == r


def _ust(u):
    return (lambda h, a: h + a >= 3) if u == "Üst" else (lambda h, a: h + a <= 2)


def _kg(k):
    return (lambda h, a: h > 0 and a > 0) if k == "Var" else \
           (lambda h, a: not (h > 0 and a > 0))


def _ve(f, g):
    return lambda h, a: f(h, a) and g(h, a)


PAZARLAR: dict = {
    "1X2": {r: _sonuc(r) for r in ("1", "0", "2")},
    "OU2.5": {u: _ust(u) for u in ("Üst", "Alt")},
    "BTTS": {k: _kg(k) for k in ("Var", "Yok")},
    "1X2_OU": {f"{r} ve {u}": _ve(_sonuc(r), _ust(u))
               for r in ("1", "0", "2") for u in ("Üst", "Alt")},
    "1X2_BTTS": {f"{r} ve {k}": _ve(_sonuc(r), _kg(k))
                 for r in ("1", "0", "2") for k in ("Var", "Yok")},
    "OU_BTTS": {f"{u} ve {k}": _ve(_ust(u), _kg(k))
                for u in ("Üst", "Alt") for k in ("Var", "Yok")},
    "TOTAL_GOALS": {
        "0-1 gol": lambda h, a: h + a <= 1,
        "2-3 gol": lambda h, a: 2 <= h + a <= 3,
        "4-5 gol": lambda h, a: 4 <= h + a <= 5,
        "6+ gol": lambda h, a: h + a >= 6},
}


# ── Ad eşleme ─────────────────────────────────────────────────────────
_DUR = {"fc", "afc", "cf", "sc", "ac", "as", "ss", "us", "sk", "fk", "ssc",
        "calcio", "club", "cd", "ud", "sd", "rc", "rcd", "sv", "vfb", "vfl",
        "tsg", "bv", "ogc", "osc", "aj", "fsv", "de", "the"}
# iddaa'nın Türkçe yazdığı ya da kısaltmanın tutmadığı adlar — ELLE.
# Anahtar _temiz() sonrası iddaa adı, değer football-data adı.
ELLE = {
    "atletico madrid": "Ath Madrid", "atl madrid": "Ath Madrid",
    "olympique marsilya": "Marseille", "marsilya": "Marseille",
    "olympique marseille": "Marseille",
    "istanbul basaksehir": "Buyuksehyr", "basaksehir": "Buyuksehyr",
    "rams basaksehir": "Buyuksehyr",
    "wolverhampton": "Wolves", "wolverhampton wanderers": "Wolves",
    "borussia monchengladbach": "M'gladbach", "monchengladbach": "M'gladbach",
    "paris saint germain": "Paris SG", "psg": "Paris SG",
    "espanyol": "Espanol",
    "bayern munih": "Bayern Munich",
    "paris": "Paris FC",          # iddaa PSG'yi "Paris Saint Germain" yazar
}


def _temiz(s: str) -> str:
    s = (s or "").replace("ı", "i").replace("İ", "I")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = "".join(c if c.isalnum() else " " for c in s)
    return " ".join(s.split())


def _jeton(s: str) -> list[str]:
    return [t for t in _temiz(s).split()
            if t not in _DUR and len(t) >= 2 and not t.isdigit()]


def _onek(t: str, u: str) -> bool:
    """Jetonlar aynı mı, ya da biri ötekinin (en az 3 harflik) kısaltması mı:
    'man'→'manchester' evet; 'le'→'lens' HAYIR ('Le Havre' ile 'RC Lens'
    birbirine karışıyordu)."""
    if t == u:
        return True
    k, uz = (t, u) if len(t) <= len(u) else (u, t)
    return len(k) >= 3 and uz.startswith(k)


def _uyum(a: str, b: str) -> float:
    """İki takım adının benzerliği (0..1): kısa adın her jetonu uzun adda
    (önek olarak) bulunuyorsa 1; değilse bulunan pay + yazım benzerliği."""
    ja, jb = _jeton(a), _jeton(b)
    if not ja or not jb:
        return 0.0
    kisa, uzun = (ja, jb) if len(ja) <= len(jb) else (jb, ja)
    bulunan = sum(1 for t in kisa if any(_onek(t, u) for u in uzun))
    pay = bulunan / len(kisa)
    yazim = SequenceMatcher(None, " ".join(ja), " ".join(jb)).ratio()
    return 1.0 if pay >= 1.0 else pay * 0.5 + yazim * 0.5


_YEDEK_HER = re.compile(r"^(u\d{2}|castilla|juvenil|primavera|reserve|reserves|"
                        r"women|kadin|kadinlar|fem|youth|akademi)$")
_YEDEK_SON = re.compile(r"^(b|c|ii|iii)$")


def _yedek_mi(ad: str) -> bool:
    """Rezerv / genç / kadın takımı: 'Real Madrid C', 'Elche B', 'Roma U20'.
    Aynı kulübün A takımı DEĞİLDİR — asla bağlanmaz. (İlk sürüm 'Real
    Madrid C'yi Real Madrid'e bağlıyordu: tek harf jetonu atılınca ad
    birebir aynı kalıyordu.) Tek harf / roma rakamı yalnız SONDAYSA rezerv:
    'B. Dortmund'daki B Borussia'dır."""
    j = _temiz(ad).split()
    if not j:
        return False
    return any(_YEDEK_HER.match(t) for t in j) or bool(_YEDEK_SON.match(j[-1]))


def esle_ad(iddaa_ad: str, fd_adlari: set) -> str | None:
    """iddaa adı → aynı ligin football-data adı (yoksa None)."""
    if _yedek_mi(iddaa_ad):
        return None
    if iddaa_ad in fd_adlari:
        return iddaa_ad
    t = _temiz(iddaa_ad)
    if t in ELLE and ELLE[t] in fd_adlari:
        return ELLE[t]
    for f in fd_adlari:
        if _temiz(f) == t:
            return f
    puan = sorted(((_uyum(iddaa_ad, f), f) for f in fd_adlari), reverse=True)
    if not puan:
        return None
    en, ad = puan[0]
    ikinci = puan[1][0] if len(puan) > 1 else 0.0
    # Tam kapsama (1,0) yalnız TEK aday varsa; kısmi uyum en az 0,75 ve
    # ikinciden belirgin uzak olmalı — yanlış bağlamak, bağlamamaktan kötü.
    if en >= 1.0 and ikinci < 1.0:
        return ad
    if 0.75 <= en < 1.0 and en - ikinci >= 0.10:
        return ad
    return None


# ── Uydurma ───────────────────────────────────────────────────────────
def _tarih(s) -> datetime | None:
    try:
        return datetime.fromisoformat(str(s).replace("Z", "")[:19])
    except Exception:
        return None


def uydur(maclar: list, ref: datetime) -> dict | None:
    """maclar: [(tarih, ev, dep, x, y)] — yalnız ref'ten ÖNCEKİLER kullanılır."""
    veri = []
    for t, i, j, x, y in maclar:
        yas = (ref - t).total_seconds() / 86400.0
        if 0 < yas <= PENCERE:
            veri.append((0.5 ** (yas / YARI_OMUR), i, j, x, y))
    if len(veri) < 100:
        return None
    takim = sorted({v[1] for v in veri} | {v[2] for v in veri})
    W: dict = defaultdict(float)
    for w, i, j, _x, _y in veri:
        W[i] += w
        W[j] += w
    sw = sum(v[0] for v in veri)
    ort_ev = sum(w * x for w, _i, _j, x, _y in veri) / sw
    ort_dep = sum(w * y for w, _i, _j, _x, y in veri) / sw
    g = (ort_ev + ort_dep) / 2
    A = dict.fromkeys(takim, 1.0)
    D = dict.fromkeys(takim, 1.0)
    C, H = ort_dep, ort_ev / max(ort_dep, 1e-9)
    for _ in range(80):
        na, da = defaultdict(float), defaultdict(float)
        for w, i, j, x, y in veri:
            na[i] += w * x
            da[i] += w * C * H * D[j]
            na[j] += w * y
            da[j] += w * C * D[i]
        A2 = {t: (na[t] + SANAL_MAC * g) / (da[t] + SANAL_MAC * g) for t in takim}
        nd, dd = defaultdict(float), defaultdict(float)
        for w, i, j, x, y in veri:
            nd[j] += w * x
            dd[j] += w * C * H * A2[i]
            nd[i] += w * y
            dd[i] += w * C * A2[j]
        D2 = {t: (nd[t] + SANAL_MAC * g) / (dd[t] + SANAL_MAC * g) for t in takim}
        ga = math.exp(sum(math.log(v) for v in A2.values()) / len(takim))
        gd = math.exp(sum(math.log(v) for v in D2.values()) / len(takim))
        A2 = {t: v / ga for t, v in A2.items()}
        D2 = {t: v / gd for t, v in D2.items()}
        H = (sum(w * x for w, _i, _j, x, _y in veri) /
             sum(w * C * A2[i] * D2[j] for w, i, j, _x, _y in veri))
        C = (sum(w * (x + y) for w, _i, _j, x, y in veri) /
             sum(w * (H * A2[i] * D2[j] + A2[j] * D2[i])
                 for w, i, j, _x, _y in veri))
        fark = max(abs(A2[t] - A[t]) + abs(D2[t] - D[t]) for t in takim)
        A, D = A2, D2
        if fark < 1e-7:
            break
    dus = [(w, x, y, C * H * A[i] * D[j], C * A[j] * D[i])
           for w, i, j, x, y in veri if x <= 1 and y <= 1]

    def ll(r):
        s = 0.0
        for w, x, y, lam, mu in dus:
            t = _tau(x, y, lam, mu, r)
            if t <= 0:
                return -1e18
            s += w * math.log(t)
        return s
    rho = max(RHO_IZGARA, key=ll)
    return {"A": A, "D": D, "C": C, "H": H, "rho": rho, "W": dict(W),
            "n": len(veri)}


def tahmin(par: dict, ev: str, dep: str) -> tuple | None:
    """(λ, μ) — iki takımın da yeterli geçmişi yoksa None (uydurulmaz)."""
    W = par["W"]
    if W.get(ev, 0.0) < MIN_ETKIN or W.get(dep, 0.0) < MIN_ETKIN:
        return None
    A, D = par["A"], par["D"]
    return par["C"] * par["H"] * A[ev] * D[dep], par["C"] * A[dep] * D[ev]


# ── Skor matrisi ve fiyat ─────────────────────────────────────────────
def _tau(x: int, y: int, lam: float, mu: float, rho: float) -> float:
    if x == 0 and y == 0:
        return 1 - lam * mu * rho
    if x == 0 and y == 1:
        return 1 + lam * rho
    if x == 1 and y == 0:
        return 1 + mu * rho
    if x == 1 and y == 1:
        return 1 - rho
    return 1.0


def _pmf(l: float) -> list[float]:
    out, p = [], math.exp(-l)
    for k in range(N):
        out.append(p)
        p *= l / (k + 1)
    return out


def matris(lam: float, mu: float, rho: float) -> list[list[float]]:
    ph, pa = _pmf(lam), _pmf(mu)
    M = [[max(_tau(x, y, lam, mu, rho), 0.0) * ph[x] * pa[y] for y in range(N)]
         for x in range(N)]
    s = sum(map(sum, M))
    return [[v / s for v in r] for r in M]


def fiyatla(M: list) -> dict:
    """{pazar: {seçim: (olasılık, etkin_skor)}} — etkin skor = 1/Σ(pay²)."""
    out: dict = {}
    for mk, secimler in PAZARLAR.items():
        out[mk] = {}
        for sel, f in secimler.items():
            hucre = [M[x][y] for x in range(N) for y in range(N) if f(x, y)]
            p = sum(hucre)
            etkin = (1.0 / sum((c / p) ** 2 for c in hucre)) if p > 0 else 0.0
            out[mk][sel] = (p, etkin)
    return out


# ── Veri ──────────────────────────────────────────────────────────────
def _satirlar(conn, bas_iso: str, yalniz_fd: bool = False) -> list[dict]:
    q = ("SELECT league_code lg, kickoff_utc ko, home_team h, away_team a, "
         "home_score hs, away_score aws, external_id_fd fd, "
         "external_id_iddaa idd, closing_1 c1, closing_X cx, closing_2 c2, "
         "closing_over25 co, closing_under25 cu FROM matches_v2 "
         "WHERE league_code IN (" + ",".join("'" + l + "'" for l in LIGLER) +
         ") AND home_score IS NOT NULL AND away_score IS NOT NULL "
         "AND kickoff_utc >= ?")
    if yalniz_fd:
        q += " AND external_id_fd IS NOT NULL"
    return [dict(r) for r in conn.execute(q, (bas_iso,)).fetchall()]


def _gelecek(conn, simdi: datetime) -> list[dict]:
    """Oynanmamış iddaa maçları — yalnız AD KANITI (skorsuz, eğitime girmez).
    Bir kulübün lig maçları football-data'ya geçince iddaa adıyla yalnız kupa
    maçı kalabiliyor ('B. Leverkusen'); gelecek lig fikstürü o adın bu ligde
    oynadığının kanıtıdır."""
    return [dict(r) for r in conn.execute(
        "SELECT league_code lg, home_team h, away_team a, kickoff_utc ko "
        "FROM matches_v2 WHERE is_settled=0 AND external_id_iddaa IS NOT NULL "
        "AND kickoff_utc > ? AND league_code IN (" +
        ",".join("'" + l + "'" for l in LIGLER) + ")",
        ((simdi - timedelta(days=2)).isoformat(),)).fetchall()]


def _lig_verisi(satirlar: list, simdi: datetime,
                gelecek: list = ()) -> tuple[dict, dict, dict]:
    """Lig → birleşik maç listesi, lig → {iddaa_adı: bağlanan_ad | None} ve
    lig → {yeni çıkan takımın iddaa adı}.

    ⚠️ iddaa satırlarının lig kodu KİRLİ (ölçüldü, 19.09): E0 kodlu satırlar
    arasında Championship, League One ve Avrupa kupası maçları var
    (Norwich–Bolton, Celtic, Benfica…); SP1'de Segunda B ve rezervler, I1'de
    Finlandiya'nın 'Inter Turku'su. Bu yüzden bir iddaa satırı YALNIZ iki
    takımı da aynı ligin son sezon football-data kadrosuna GÜVENLE
    bağlanıyorsa modele girer. Güven iki şart: rezerv/genç değil, ve en az
    bir maçını yine bağlanan bir rakibe karşı oynamış — 'Inter Turku' bir
    İtalyan rakiple hiç oynamaz. Bağlanamayan takım (yeni çıkan dahil)
    tahminsiz kalır: yanlış takımı fiyatlamaktansa hiç fiyatlamamak.

    YENİ ÇIKAN TAKIM (Deportivo, Venezia, Amed…) football-data kadrosunda
    yoktur, adı bağlanamaz. Bu sezon ligde oynadığı kanıtlanırsa geçmişi
    kendi iddaa adıyla kurulur: son 120 günde güvenle bağlanmış rakiplere
    karşı en az 3 maç VE bu lig kodundaki maçlarının en az %60'ı böyle.
    Avrupa kupası konuğu (Celtic) ya da kupadaki alt lig takımı (Norwich)
    bu şartı geçemez."""
    fd_adlari: dict = defaultdict(set)
    for r in satirlar:
        t = _tarih(r["ko"])
        if r["fd"] and t and (simdi - t).days <= 450:
            fd_adlari[r["lg"]].update((r["h"], r["a"]))
    iddaa = [r for r in satirlar if not r["fd"]]
    kanit = iddaa + [r for r in gelecek if r["lg"] in LIGLER]
    gecici: dict = defaultdict(dict)
    gorunme: dict = defaultdict(int)
    for r in kanit:
        for ad in (r["h"], r["a"]):
            gorunme[(r["lg"], ad)] += 1
            if ad not in gecici[r["lg"]]:
                gecici[r["lg"]][ad] = esle_ad(ad, fd_adlari[r["lg"]])
    bag: dict = defaultdict(int)
    for r in kanit:
        g = gecici[r["lg"]]
        mh, ma = g.get(r["h"]), g.get(r["a"])
        if mh and ma and mh != ma:
            bag[(r["lg"], r["h"])] += 1
            bag[(r["lg"], r["a"])] += 1
    esleme: dict = defaultdict(dict)
    for lg, g in gecici.items():
        for ad, m in g.items():
            guvenli = bool(m) and (bag[(lg, ad)] >= 1 or ad == m
                                   or _temiz(ad) in ELLE)
            esleme[lg][ad] = m if guvenli else None

    def _tam(ad: str, m: str) -> bool:
        return ad == m or _temiz(ad) == _temiz(m) or _temiz(ad) in ELLE
    # Aynı football-data takımına birden çok iddaa adı bağlandıysa (ör. gerçek
    # Mainz ile bir kupa maçındaki amatör 'TSV Schott Mainz') tek ad kalır:
    # önce birebir ad, sonra bağlantı, sonra görünme sayısı. (Yalnız bağlantıya
    # bakan ilk sürüm eşitlikte amatör kulübü seçti — 'Mainz' düştü.)
    for lg, g in esleme.items():
        hedef: dict = defaultdict(list)
        for ad, m in g.items():
            if m:
                hedef[m].append(ad)
        for m, adlar in hedef.items():
            if len(adlar) > 1:
                en = max(adlar, key=lambda a: (_tam(a, m), bag[(lg, a)],
                                               gorunme[(lg, a)]))
                for a in adlar:
                    if a != en:
                        g[a] = None
    # Yeni çıkan takımlar — kendi iddaa adıyla (yalnız OYNANMIŞ maçlardan)
    son = simdi - timedelta(days=120)
    toplam: dict = defaultdict(int)
    karsi: dict = defaultdict(int)
    for r in iddaa:
        t = _tarih(r["ko"])
        if not t or t < son:
            continue
        g = esleme[r["lg"]]
        for ad, rakip in ((r["h"], r["a"]), (r["a"], r["h"])):
            if g.get(ad) or _yedek_mi(ad):
                continue
            toplam[(r["lg"], ad)] += 1
            if g.get(rakip):
                karsi[(r["lg"], ad)] += 1
    yeni: dict = defaultdict(set)
    for (lg, ad), n in toplam.items():
        if karsi[(lg, ad)] >= 3 and karsi[(lg, ad)] >= 0.6 * n:
            yeni[lg].add(ad)
    for lg, adlar in yeni.items():
        for ad in adlar:
            esleme[lg][ad] = ad
    maclar: dict = defaultdict(dict)
    for r in satirlar:
        t = _tarih(r["ko"])
        if not t:
            continue
        lg, h, a = r["lg"], r["h"], r["a"]
        if not r["fd"]:
            h, a = esleme[lg].get(h), esleme[lg].get(a)
            if not h or not a or h == a:
                continue
        maclar[lg].setdefault((t.date(), h, a),
                              (t, h, a, int(r["hs"]), int(r["aws"])))
    return ({lg: sorted(v.values()) for lg, v in maclar.items()},
            {lg: dict(v) for lg, v in esleme.items()},
            {lg: set(v) for lg, v in yeni.items()})


_ONBELLEK: dict = {"ts": None, "m": None}


def guncel_model(taze_dk: int = 360) -> dict:
    """Canlı model — bugüne kadarki bütün maçlarla uydurulur, önbellekli."""
    simdi = datetime.utcnow()
    if (_ONBELLEK["m"] is not None and _ONBELLEK["ts"] is not None
            and (simdi - _ONBELLEK["ts"]).total_seconds() < taze_dk * 60):
        return _ONBELLEK["m"]
    conn = db.connect()
    try:
        satir = _satirlar(conn, (simdi - timedelta(days=PENCERE + 30)).isoformat())
        gelecek = _gelecek(conn, simdi)
    finally:
        conn.close()
    maclar, esleme, yeni = _lig_verisi(satir, simdi, gelecek)
    m = {"ts": simdi, "ligler": {}, "esleme": esleme, "yeni": yeni}
    for lg in LIGLER:
        par = uydur(maclar.get(lg, []), simdi)
        if par:
            m["ligler"][lg] = par
    _ONBELLEK.update(ts=simdi, m=m)
    return m


def takim(m: dict, lig: str, iddaa_ad: str) -> str | None:
    """Canlı maçtaki iddaa adını modelin takım anahtarına çevir — YALNIZ
    güvenle bağlanmış adlar (bkz. _lig_verisi). Bağlanmamışsa None: o maç
    fiyatlanmaz."""
    return m["esleme"].get(lig, {}).get(iddaa_ad)


# ── Ön kayıtlı sınav ──────────────────────────────────────────────────
SINAV_KURALI = ("Sınav 2024-07 → 2026-06, her ay yeniden eğitim. Model ile "
                "piyasa harmanının log-kaybı, piyasanın KAPANIŞ log-kaybından "
                "anlamlı düşükse (t < −2) model piyasaya BİLGİ ekliyor. "
                "1X2 ve Alt/Üst 2,5 için ayrı hüküm; ikisi de geçerse GEÇTİ.")


def _harman(p: list, q: list, w: float = 0.5) -> list:
    b = [(max(a, 1e-9) ** w) * (max(c, 1e-9) ** (1 - w)) for a, c in zip(p, q)]
    s = sum(b)
    return [v / s for v in b]


def sinav(conn=None, bas: str = "2024-07-01", bit: str = "2026-07-01",
          yazdir: bool = True) -> dict:
    kendi = conn is None
    if kendi:
        conn = db.connect()
    try:
        satir = _satirlar(conn, "2020-07-01", yalniz_fd=True)
    finally:
        if kendi:
            conn.close()
    maclar, _, _ = _lig_verisi(satir, datetime(2026, 7, 1))
    oran = {}
    for r in satir:
        t = _tarih(r["ko"])
        try:
            o = [float(r[k]) for k in ("c1", "cx", "c2", "co", "cu")]
        except (TypeError, ValueError):
            continue
        if t and all(v > 1.01 for v in o):
            oran[(r["lg"], t.date(), r["h"], r["a"])] = o
    fark = {"1X2": {"model": [], "harman": []}, "OU": {"model": [], "harman": []}}
    bilgi = {"n": 0, "piyasa": 0.0, "model": 0.0, "gercek": 0.0}
    satir_lig = defaultdict(int)
    ay = datetime.fromisoformat(bas)
    son = datetime.fromisoformat(bit)
    while ay < son:
        sonraki = (ay.replace(day=28) + timedelta(days=4)).replace(day=1)
        for lg in LIGLER:
            ms = maclar.get(lg, [])
            test = [m for m in ms if ay <= m[0] < sonraki]
            if not test:
                continue
            par = uydur(ms, ay)
            if not par:
                continue
            for t, h, a, x, y in test:
                o = oran.get((lg, t.date(), h, a))
                lm = tahmin(par, h, a)
                if not o or not lm:
                    continue
                M = matris(lm[0], lm[1], par["rho"])
                f = fiyatla(M)
                pm = [f["1X2"]["1"][0], f["1X2"]["0"][0], f["1X2"]["2"][0]]
                s = sum(1 / v for v in o[:3])
                qm = [(1 / v) / s for v in o[:3]]
                k = 0 if x > y else (1 if x == y else 2)
                ph = _harman(pm, qm)
                fark["1X2"]["model"].append(-math.log(pm[k]) + math.log(qm[k]))
                fark["1X2"]["harman"].append(-math.log(ph[k]) + math.log(qm[k]))
                pu = [f["OU2.5"]["Üst"][0], f["OU2.5"]["Alt"][0]]
                su = 1 / o[3] + 1 / o[4]
                qu = [(1 / o[3]) / su, (1 / o[4]) / su]
                ku = 0 if x + y >= 3 else 1
                pb = _harman(pu, qu)
                fark["OU"]["model"].append(-math.log(pu[ku]) + math.log(qu[ku]))
                fark["OU"]["harman"].append(-math.log(pb[ku]) + math.log(qu[ku]))
                # model piyasadan ≥5 puan YÜKSEK dediğinde gerçek ne oldu
                for j in range(3):
                    if pm[j] - qm[j] >= 0.05:
                        bilgi["n"] += 1
                        bilgi["piyasa"] += qm[j]
                        bilgi["model"] += pm[j]
                        bilgi["gercek"] += 1.0 if j == k else 0.0
                satir_lig[lg] += 1
        ay = sonraki

    def ozet(v):
        n = len(v)
        if n < 30:
            return n, 0.0, 0.0
        m = sum(v) / n
        sd = math.sqrt(sum((z - m) ** 2 for z in v) / (n - 1))
        return n, m, m / (sd / math.sqrt(n)) if sd > 0 else 0.0

    s1 = ozet(fark["1X2"]["harman"])
    s2 = ozet(fark["OU"]["harman"])
    m1 = ozet(fark["1X2"]["model"])
    m2 = ozet(fark["OU"]["model"])
    gecti = (s1[2] < -2) and (s2[2] < -2)
    bn = bilgi["n"] or 1
    detay = (f"{s1[0]} maç · harman−piyasa log-kaybı 1X2 {s1[1]*1000:+.2f}‰ "
             f"(t={s1[2]:+.1f}), A/Ü {s2[1]*1000:+.2f}‰ (t={s2[2]:+.1f}) · "
             f"yalnız model 1X2 {m1[1]*1000:+.1f}‰, A/Ü {m2[1]*1000:+.1f}‰ · "
             f"model ≥5p yüksek dediğinde (n={bilgi['n']}): piyasa "
             f"%{bilgi['piyasa']/bn*100:.1f}, model %{bilgi['model']/bn*100:.1f}, "
             f"gerçek %{bilgi['gercek']/bn*100:.1f}")
    if yazdir:
        print("🟠 TURUNCU MODEL — ön kayıtlı ileriye dönük sınav")
        print("   KURAL: " + SINAV_KURALI)
        print("   lig başına sınav maçı: " +
              " · ".join(f"{k} {v}" for k, v in sorted(satir_lig.items())))
        print("   " + detay)
        print("   HÜKÜM: " + ("✅ model piyasaya bilgi EKLİYOR" if gecti else
                             "❌ kural sağlanmadı — model kapanış fiyatına "
                             "bilgi eklemiyor (negatif ‰ = harman daha iyi)"))
    return {"n": s1[0], "deger": s1[2], "detay": detay[:400], "gecti": gecti}


def esleme_raporu() -> None:
    simdi = datetime.utcnow()
    conn = db.connect()
    try:
        satir = _satirlar(conn, (simdi - timedelta(days=PENCERE + 30)).isoformat())
        kanit = _gelecek(conn, simdi)
    finally:
        conn.close()
    gelecek = [r for r in kanit if str(r["ko"]) > simdi.isoformat()]
    maclar, esleme, yeni = _lig_verisi(satir, simdi, kanit)
    m = {"esleme": esleme, "ligler": {}}
    for lg in LIGLER:
        par = uydur(maclar.get(lg, []), simdi)
        if par:
            m["ligler"][lg] = par
    print("🟠 TURUNCU — AD EŞLEME RAPORU")
    for lg in LIGLER:
        es = esleme.get(lg, {})
        bag = {k: v for k, v in es.items() if v}
        yok = sorted(k for k, v in es.items() if not v)
        par = m["ligler"].get(lg)
        print(f"\n  {lg}: iddaa adı {len(es)} · bağlandı {len(bag)} · "
              f"bağlanamadı {len(yok)} · ρ={par['rho']:+.3f} H={par['H']:.2f}"
              if par else f"\n  {lg}: model kurulamadı")
        for k, v in sorted(bag.items()):
            if _temiz(k) != _temiz(v):
                print(f"      {k:26s} → {v}")
        if yeni.get(lg):
            print("      YENİ ÇIKAN (kendi adıyla): " + ", ".join(sorted(yeni[lg])))
        if yok:
            print("      BAĞLANAMADI: " + ", ".join(yok))
    tahminsiz = []
    for r in gelecek:
        par = m["ligler"].get(r["lg"])
        if not par:
            continue
        if not tahmin(par, takim(m, r["lg"], r["h"]), takim(m, r["lg"], r["a"])):
            tahminsiz.append(f"{r['lg']} {r['h']}-{r['a']}")
    print(f"\n  gelecek maç: {len(gelecek)} · tahmin YAPILAMAYAN: {len(tahminsiz)}")
    for s in tahminsiz[:20]:
        print(f"      {s}")


if __name__ == "__main__":
    if "--sinav" in sys.argv:
        sinav()
    else:
        esleme_raporu()
