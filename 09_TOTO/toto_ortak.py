"""
TOTO · ORTAK — sabitler, oyun kuralları, lig haritası, ad normalizasyonu
========================================================================
Spor Toto (müşterek bahis) modülünün tek doğruluk kaynağı. BetAgents'tan
BAĞIMSIZ: bu klasördeki hiçbir modül BetAgents tablosuna yazmaz, BetAgents
kodunu çağırmaz (yalnız ortak veritabanı bağlantı yardımcısı db.py okunur).

Kural sabitleri resmi oyun planından (sportoto.gov.tr/musterek-oyun-plani.pdf):
  m.8/4   bir bilette en çok 2.500 kolon
  m.9/3   oyun, programdaki İLK maçın başlama anına kadar kabul edilir
  m.10/1  dağıtılan tutar = (hasılat − KDV) × 5602 s.K. m.4/2 üst sınırı (%83)
  m.10/2  derece payları 15:%35 · 14:%20 · 13:%20 · 12:%25
  m.10/3  bir kolon yalnız bildiği EN ÜST dereceden ödeme alır
  m.11    kazananı çıkmayan derecenin tutarı sonraki haftanın aynı derecesine devreder
  m.6-7   oynanmayan maçın sonucu noter çekilişiyle (iki takımın son 5 resmi
          lig maçından 10 top) belirlenir
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

KOK = Path(__file__).resolve().parent
CACHE = KOK / "veri_cache"

# ── Oyun kuralları ──────────────────────────────────────────────
MAC_SAYISI = 15
KADEME_PAY = {15: 0.35, 14: 0.20, 13: 0.20, 12: 0.25}
MAX_KOLON = 2500
SECENEK = ("1", "0", "2")            # ev · beraberlik · deplasman (indeks 0,1,2)
YASAL_ORAN = 0.83                    # 5602 m.4/2 üst sınırı (7146 s.K. ile)
KDV = 0.20                           # 10.07.2023 öncesi 0.18 — fark ihmal edilebilir
RHO = YASAL_ORAN / (1 + KDV)         # brüt hasılatın dağıtılan payı ≈ 0,692

# Kolon bedeli (TL) — haber arşivi + verideki basamaklar (RAPOR §2).
# 4 TL'ye geçiş tarihi resmi kaynaktan doğrulanamadı; veri Ağustos 2024'ü gösteriyor.
KOLON_BEDEL_TARIHCE = [("2000-01-01", 0.50), ("2023-08-06", 2.0), ("2024-08-01", 4.0), ("2025-03-18", 10.0)]


def kolon_bedeli(tarih_iso: str) -> float:
    b = KOLON_BEDEL_TARIHCE[0][1]
    for t, v in KOLON_BEDEL_TARIHCE:
        if tarih_iso[:10] >= t:
            b = v
    return b


# ── Turnuva haritası (Spor Toto tournamentId → kaynak/aile) ─────
# aile: TR-UST · TR-ALT · EU-BIG · EU-ALT · DUNYA · MILLI · KUPA
# fd: football-data ana lig kodu · fdn: football-data ek lig kodu
TURNUVA = {
    70: {"ad": "Süper Lig", "aile": "TR-UST", "fd": "T1"},
    69: {"ad": "TFF 1. Lig", "aile": "TR-ALT"},
    36: {"ad": "Premier League", "aile": "EU-BIG", "fd": "E0"},
    37: {"ad": "Championship", "aile": "EU-ALT", "fd": "E1"},
    30: {"ad": "League One", "aile": "EU-ALT", "fd": "E2"},
    56: {"ad": "Serie A", "aile": "EU-BIG", "fd": "I1"},
    57: {"ad": "Serie B", "aile": "EU-ALT", "fd": "I2"},
    44: {"ad": "La Liga", "aile": "EU-BIG", "fd": "SP1"},
    45: {"ad": "La Liga 2", "aile": "EU-ALT", "fd": "SP2"},
    6: {"ad": "Bundesliga", "aile": "EU-BIG", "fd": "D1"},
    5: {"ad": "2. Bundesliga", "aile": "EU-ALT", "fd": "D2"},
    26: {"ad": "Ligue 1", "aile": "EU-BIG", "fd": "F1"},
    165: {"ad": "Eredivisie", "aile": "EU-ALT", "fd": "N1"},
    80: {"ad": "Belçika Pro Lig", "aile": "EU-ALT", "fd": "B1"},
    95: {"ad": "Portekiz Ligi", "aile": "EU-ALT", "fd": "P1"},
    49: {"ad": "İsveç Allsvenskan", "aile": "EU-ALT", "fdn": "SWE"},
    68: {"ad": "Norveç Eliteserien", "aile": "EU-ALT", "fdn": "NOR"},
    23: {"ad": "Finlandiya Veikkausliiga", "aile": "EU-ALT", "fdn": "FIN"},
    15: {"ad": "Danimarka Superliga", "aile": "EU-ALT", "fdn": "DNK"},
    207: {"ad": "Polonya Ekstraklasa", "aile": "EU-ALT", "fdn": "POL"},
    54: {"ad": "İsviçre Süper Lig", "aile": "EU-ALT", "fdn": "SWZ"},
    171: {"ad": "İrlanda Ligi", "aile": "EU-ALT", "fdn": "IRL"},
    259: {"ad": "Brezilya Serie A", "aile": "DUNYA", "fdn": "BRA"},
    687: {"ad": "Arjantin Ligi", "aile": "DUNYA", "fdn": "ARG"},
    713: {"ad": "Japonya J1", "aile": "DUNYA", "fdn": "JPN"},
    712: {"ad": "Çin Süper Lig", "aile": "DUNYA", "fdn": "CHN"},
    252: {"ad": "MLS", "aile": "DUNYA", "fdn": "USA"},
    714: {"ad": "Güney Kore K1", "aile": "DUNYA"},
    731: {"ad": "Güney Kore K2", "aile": "DUNYA"},
    60: {"ad": "İzlanda Ligi", "aile": "EU-ALT"},
    13: {"ad": "Danimarka alt lig", "aile": "EU-ALT"},
    258: {"ad": "Milli (hazırlık/karma)", "aile": "MILLI"},
    11: {"ad": "EURO 2024 elemeleri", "aile": "MILLI"},
    682: {"ad": "Dünya Kupası", "aile": "MILLI"},
    16: {"ad": "DK 2026 elemeleri", "aile": "MILLI"},
    162: {"ad": "EURO", "aile": "MILLI"},
    10: {"ad": "Milli turnuva", "aile": "MILLI"},
    137: {"ad": "Copa América", "aile": "MILLI"},
    142: {"ad": "DK elemeleri (CONMEBOL)", "aile": "MILLI"},
    250: {"ad": "Kulüpler Dünya Kupası", "aile": "KUPA"},
    218: {"ad": "Şampiyonlar Ligi", "aile": "KUPA"},
}


def turnuva(tid) -> dict:
    return TURNUVA.get(tid, {"ad": f"Turnuva {tid}", "aile": "KUPA"})


# ── Ad normalizasyonu ───────────────────────────────────────────
_TR = str.maketrans("çğıöşüÇĞİÖŞÜâîûÂÎÛ", "cgiosuCGIOSUaiuAIU")


def norm(s: str | None) -> str:
    s = (s or "").translate(_TR)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s)).strip()


# Anlamsız/sponsor jetonlar — eşleşmede yok sayılır
GENEL = {"fc", "sk", "fk", "as", "ac", "cf", "sc", "afc", "the", "de", "com", "tr", "club", "calcio",
         "cd", "ud", "sd", "rc", "rcd", "ca", "cp", "if", "ik", "ff", "bk", "fk", "sv", "vfb", "vfl",
         "tsg", "1", "04", "05", "a", "s", "jk", "ks", "gks", "sporting", "real", "united", "city",
         "kulubu", "futbol", "spor", "de", "la", "le", "el"}
# Türkçe/İngilizce ad eşdeğerleri (norm edilmiş) — kaynak adına eklenecek ek jetonlar
ESDEGER = {
    "munih": "munich", "marsilya": "marseille", "lizbon": "lisbon lisboa", "varsova": "warszawa warsaw",
    "basaksehir": "buyuksehyr basaksehir", "karagumruk": "karagumruk", "adana demirspor": "ad demirspor",
    "manchester united": "man united manutd", "manchester city": "man city mancity",
    "nottingham forest": "nott m forest nottm", "wolverhampton": "wolves", "tottenham": "tottenham spurs",
    "paris st germain": "paris sg psg", "paris saint germain": "paris sg psg", "atletico madrid": "ath madrid atletico",
    "athletic bilbao": "ath bilbao", "real sociedad": "sociedad", "real betis": "betis", "celta vigo": "celta",
    "espanyol": "espanol", "rayo vallecano": "vallecano", "deportivo alaves": "alaves",
    "borussia monchengladbach": "m gladbach gladbach", "monchengladbach": "m gladbach", "koln": "fc koln cologne",
    "bayer leverkusen": "leverkusen", "eintracht frankfurt": "ein frankfurt frankfurt",
    "inter": "inter internazionale", "milan": "milan", "hellas verona": "verona",
    "olympique lyon": "lyon", "olympique marsilya": "marseille", "saint etienne": "st etienne",
    "psv eindhoven": "psv", "az alkmaar": "az", "go ahead eagles": "go ahead",
    "sporting lizbon": "sp lisbon sporting", "bodo glimt": "bodo glimt bodoe", "malmo": "malmo ff",
    "goteborg": "goteborg ifk", "djurgarden": "djurgarden", "hacken": "hacken", "aik stockholm": "aik",
    "union st gilloise": "st gilloise union", "standard liege": "standard", "club brugge": "club brugge",
    "legia varsova": "legia", "lech poznan": "lech", "beijing guoan": "beijing",
    "shanghai shenhua": "shanghai shenhua", "vissel kobe": "vissel kobe", "flamengo": "flamengo rj",
    "atletico mineiro": "atletico mg", "sao paulo": "sao paulo", "botafogo fr": "botafogo rj",
}

# Milli takım: Toto Türkçe adı → uluslararası sonuç veri setindeki ad
MILLI_EN = {
    "A.B.D.": "United States", "Almanya": "Germany", "Andorra": "Andorra", "Arjantin": "Argentina",
    "Arnavutluk": "Albania", "Avustralya": "Australia", "Avusturya": "Austria", "Azerbaycan": "Azerbaijan",
    "Belarus": "Belarus", "Belçika": "Belgium", "Bolivya": "Bolivia", "Bosna Hersek": "Bosnia and Herzegovina",
    "Brezilya": "Brazil", "Bulgaristan": "Bulgaria", "Cezayir": "Algeria", "Curaçao": "Curaçao",
    "Danimarka": "Denmark", "Demokratik Kongo": "DR Congo", "Ekvador": "Ecuador", "Ermenistan": "Armenia",
    "Estonya": "Estonia", "Faroe Adaları": "Faroe Islands", "Fas": "Morocco", "Fildişi Sahili": "Ivory Coast",
    "Finlandiya": "Finland", "Fransa": "France", "Galler": "Wales", "Gana": "Ghana", "Güney Kore": "South Korea",
    "Gürcistan": "Georgia", "Haiti": "Haiti", "Hollanda": "Netherlands", "Hırvatistan": "Croatia", "Irak": "Iraq",
    "Jamaika": "Jamaica", "Japonya": "Japan", "Kamerun": "Cameroon", "Kanada": "Canada", "Karadağ": "Montenegro",
    "Katar": "Qatar", "Kazakistan": "Kazakhstan", "Kolombiya": "Colombia", "Kosova": "Kosovo",
    "Kosta Rika": "Costa Rica", "Kuzey Makedonya Cumhuriyeti": "North Macedonia", "Kuzey Makedonya": "North Macedonia",
    "Kuzey İrlanda": "Northern Ireland", "Letonya": "Latvia", "Lihtenştayn": "Liechtenstein",
    "Litvanya": "Lithuania", "Lüksemburg": "Luxembourg", "Macaristan": "Hungary", "Malta": "Malta",
    "Meksika": "Mexico", "Moldova": "Moldova", "Mısır": "Egypt", "Nikaragua": "Nicaragua", "Norveç": "Norway",
    "Panama": "Panama", "Paraguay": "Paraguay", "Peru": "Peru", "Polonya": "Poland", "Portekiz": "Portugal",
    "Romanya": "Romania", "Rusya": "Russia", "San Marino": "San Marino", "Senegal": "Senegal",
    "Slovakya": "Slovakia", "Slovenya": "Slovenia", "Suudi Arabistan": "Saudi Arabia", "Sırbistan": "Serbia",
    "Tunus": "Tunisia", "Türkiye": "Turkey", "Ukrayna": "Ukraine", "Uruguay": "Uruguay",
    "Venezuela": "Venezuela", "Yeni Zelanda": "New Zealand", "Yeşil Burun Adaları": "Cape Verde",
    "Yunanistan": "Greece", "Çekya": "Czech Republic", "Çek Cumhuriyeti": "Czech Republic",
    "Özbekistan": "Uzbekistan", "Ürdün": "Jordan", "İngiltere": "England", "İran": "Iran",
    "İrlanda Cumhuriyeti": "Republic of Ireland", "İrlanda": "Republic of Ireland", "İskoçya": "Scotland",
    "İspanya": "Spain", "İsrail": "Israel", "İsveç": "Sweden", "İsviçre": "Switzerland", "İtalya": "Italy",
    "İzlanda": "Iceland", "Şili": "Chile", "Kıbrıs": "Cyprus", "Güney Kıbrıs": "Cyprus", "Gibraltar": "Gibraltar",
    "Avustralya ": "Australia", "Nijerya": "Nigeria", "Güney Afrika": "South Africa", "Mali": "Mali",
    "Burkina Faso": "Burkina Faso", "Honduras": "Honduras", "El Salvador": "El Salvador",
    "Birleşik Arap Emirlikleri": "United Arab Emirates", "Çin": "China PR", "Hindistan": "India",
}

# Kalabalığın "popüler" saydığı takımlar (q-modeli γ terimleri)
POP_TR = ("galatasaray", "fenerbahce", "besiktas", "trabzonspor")
POP_TR_MILLI = ("turkiye", "turkey")
POP_EU = ("real madrid", "barcelona", "bayern", "manchester city", "liverpool", "arsenal", "manchester united",
          "chelsea", "juventus", "inter", "milan", "paris st germain", "paris saint germain")


def populer(ad: str) -> tuple[bool, bool]:
    """(Türk popüler mi, Avrupa devi mi) — Türkiye milli takımı Türk popülere sayılır."""
    n = norm(ad)
    tr = any(p in n for p in POP_TR) or n in POP_TR_MILLI
    eu = (not tr) and any(n == p or n.startswith(p + " ") or n == p for p in POP_EU)
    if not eu and not tr:
        eu = any(n.startswith(p) for p in ("bayern", "real madrid", "barcelona", "paris st", "paris saint"))
    return tr, eu
