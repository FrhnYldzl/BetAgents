"""
🏷 TAKIM ADI — iddaa adını football-data adına bağlama (veri katmanı)
=====================================================================
İki ad dünyası var: geçmiş sezonlar football-data adlarıyla ("Man United",
"Ath Madrid"), güncel sezon iddaa adlarıyla ("Manchester United", "Atletico
Madrid", "Bayern Münih"). esle_ad() bir iddaa adını VERİLEN kadrodaki
football-data adına bağlar ya da None döner — yanlış bağlamak, bağlamamaktan
kötüdür.

Kullananlar: fetch_iddaa_live (lig kodu — yarışmanın kadro saflığı) ve
turuncu_model (skor modeli). İlk sürüm turuncu_model içindeydi; veri katmanı
bir ajan takımının modülüne bağımlı olmasın diye buraya taşındı (19.09.2026).
"""
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

# Anlam taşımayan kulüp önekleri/ekleri
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


_YEDEK_HER = re.compile(r"^(u\d{2}|castilla|mestalla|juvenil|primavera|reserve|"
                        r"reserves|women|kadin|kadinlar|fem|youth|akademi)$")
_YEDEK_SON = re.compile(r"^(b|c|k|ii|iii)$")


def _yedek_mi(ad: str) -> bool:
    """Rezerv / genç / kadın takımı: 'Real Madrid C', 'Elche B', 'Roma U20',
    'Valencia CF Mestalla', 'Arsenal (K)' (iddaa'da K = kadın). Aynı kulübün
    A takımı DEĞİLDİR — asla bağlanmaz. Tek harf / roma rakamı yalnız
    SONDAYSA rezerv: 'B. Dortmund'daki B Borussia'dır."""
    j = _temiz(ad).split()
    if not j:
        return False
    return any(_YEDEK_HER.match(t) for t in j) or bool(_YEDEK_SON.match(j[-1]))


def esle_ad(iddaa_ad: str, fd_adlari: set) -> str | None:
    """iddaa adı → verilen kadrodaki football-data adı (yoksa None)."""
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
