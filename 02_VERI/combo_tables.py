"""
🔴 KIRMIZI TAKIM — KOMBO KORELASYON HARİTALARI
===============================================
iddaa'nın oyun türü taksonomisi: KİM KAZANIR · ALT/ÜST · GOLLER · İLK YARI
· KOMBO. "KOMBO" aslında bir mantık kapısıdır: (A VE B). Bahisçi bunu
ayakların ÇARPIMI olarak fiyatlar — yani bağımsız varsayar. Gerçekte aynı
maçın sonuçları güçlü korelasyonludur.

Bu dosya, üç kombo pazarı için ÖLÇÜLEN koşullu korelasyon katsayılarını
tutar. Katsayı = gerçek ortak sıklık ÷ bağımsızlık çarpımı.
    >1 → gerçek daha sık olur, kombine UCUZ fiyatlanmış olabilir
    <1 → gerçek daha seyrek, kombine PAHALI (oynanmaz)

Kaynak: matches_v2 kapanış oranları + gerçek skorlar.
    1X2_OU   : 18.059 maç · 54 hücre (P(X) bantlı)
    OU_BTTS  :  4.261 maç · 24 hücre   ⭐ en güçlü sinyal (0.33 – 1.97)
    1X2_BTTS :  4.241 maç · 48 hücre (P(X) bantlı)

Bantlar piyasanın kendi fiyatından türetilir (marjsızlaştırılmış olasılık),
böylece harita maç profiline KOŞULLUDUR — tek bir global sabit değildir.
"""
from __future__ import annotations

# ── bant sınırları ────────────────────────────────────────────────────
B_X = [0.22, 0.27, 0.31]       # ⭐ P(BERABERLİK) = maç dengesi vekili.
# DERS: önce P(ev sahibi) ile bantlamıştım — o, "dengeli maç" ile
# "deplasman ezici favori"yi AYNI kutuya koyuyordu (ikisinde de P(1) düşük).
# Oysa bunlar bambaşka profiller. P(X) dengeyi doğrudan ölçer.
B_OU = [0.45, 0.55]            # P(ÜST 2.5)
B_KG = [0.50, 0.58]            # P(KG VAR)


def band(p: float, edges: list) -> int:
    for i, e in enumerate(edges):
        if p < e:
            return i
    return len(edges)


# ── 1) 1X2 × ALT/ÜST  (18.040 maç) ────────────────────────────────────
T_1X2_OU = {
    (0, 1, "0", "A"): 1.384,
    (0, 1, "0", "U"): 0.615,
    (0, 1, "1", "A"): 0.915,
    (0, 1, "1", "U"): 1.085,
    (0, 1, "2", "A"): 0.924,
    (0, 1, "2", "U"): 1.076,
    (0, 2, "0", "A"): 1.786,
    (0, 2, "0", "U"): 0.586,
    (0, 2, "1", "A"): 0.812,
    (0, 2, "1", "U"): 1.099,
    (0, 2, "2", "A"): 0.937,
    (0, 2, "2", "U"): 1.033,
    (1, 0, "0", "A"): 1.345,
    (1, 0, "0", "U"): 0.531,
    (1, 0, "1", "A"): 0.847,
    (1, 0, "1", "U"): 1.209,
    (1, 0, "2", "A"): 0.972,
    (1, 0, "2", "U"): 1.039,
    (1, 1, "0", "A"): 1.557,
    (1, 1, "0", "U"): 0.489,
    (1, 1, "1", "A"): 0.796,
    (1, 1, "1", "U"): 1.187,
    (1, 1, "2", "A"): 0.852,
    (1, 1, "2", "U"): 1.136,
    (1, 2, "0", "A"): 1.733,
    (1, 2, "0", "U"): 0.552,
    (1, 2, "1", "A"): 0.765,
    (1, 2, "1", "U"): 1.144,
    (1, 2, "2", "A"): 0.781,
    (1, 2, "2", "U"): 1.134,
    (2, 0, "0", "A"): 1.43,
    (2, 0, "0", "U"): 0.402,
    (2, 0, "1", "A"): 0.824,
    (2, 0, "1", "U"): 1.245,
    (2, 0, "2", "A"): 0.803,
    (2, 0, "2", "U"): 1.274,
    (2, 1, "0", "A"): 1.507,
    (2, 1, "0", "U"): 0.468,
    (2, 1, "1", "A"): 0.791,
    (2, 1, "1", "U"): 1.22,
    (2, 1, "2", "A"): 0.787,
    (2, 1, "2", "U"): 1.223,
    (2, 2, "0", "A"): 1.598,
    (2, 2, "0", "U"): 0.488,
    (2, 2, "1", "A"): 0.803,
    (2, 2, "1", "U"): 1.169,
    (2, 2, "2", "A"): 0.733,
    (2, 2, "2", "U"): 1.229,
    (3, 0, "0", "A"): 1.326,
    (3, 0, "0", "U"): 0.422,
    (3, 0, "1", "A"): 0.813,
    (3, 0, "1", "U"): 1.332,
    (3, 0, "2", "A"): 0.875,
    (3, 0, "2", "U"): 1.223,
}

# ── 2) ALT/ÜST × KG  (4.261 maç) — EN GÜÇLÜ SİNYAL ────────────────────
#     "ALT ve YOK" 1.97'ye kadar · "ÜST ve YOK" 0.40'a kadar
T_OU_BTTS = {
    (0, 0, "U", "V"): 1.671, (0, 0, "U", "Y"): 0.396,
    (0, 0, "A", "V"): 0.519, (0, 0, "A", "Y"): 1.433,
    (1, 0, "U", "V"): 1.683, (1, 0, "U", "Y"): 0.412,
    (1, 0, "A", "V"): 0.330, (1, 0, "A", "Y"): 1.577,
    (1, 1, "U", "V"): 1.499, (1, 1, "U", "Y"): 0.437,
    (1, 1, "A", "V"): 0.450, (1, 1, "A", "Y"): 1.620,
    (2, 0, "U", "V"): 1.458, (2, 0, "U", "Y"): 0.659,
    (2, 0, "A", "V"): 0.359, (2, 0, "A", "Y"): 1.477,
    (2, 1, "U", "V"): 1.422, (2, 1, "U", "Y"): 0.511,
    (2, 1, "A", "V"): 0.333, (2, 1, "A", "Y"): 1.772,
    (2, 2, "U", "V"): 1.341, (2, 2, "U", "Y"): 0.426,
    (2, 2, "A", "V"): 0.423, (2, 2, "A", "Y"): 1.970,
}

# ── 3) 1X2 × KG  (4.261 maç) ──────────────────────────────────────────
T_1X2_BTTS = {
    (0, 0, "0", "V"): 1.589,
    (0, 0, "0", "Y"): 0.508,
    (0, 0, "1", "V"): 0.923,
    (0, 0, "1", "Y"): 1.064,
    (0, 0, "2", "V"): 0.861,
    (0, 0, "2", "Y"): 1.116,
    (0, 1, "0", "V"): 1.361,
    (0, 1, "0", "Y"): 0.601,
    (0, 1, "1", "V"): 0.959,
    (0, 1, "1", "Y"): 1.045,
    (0, 1, "2", "V"): 0.862,
    (0, 1, "2", "Y"): 1.152,
    (1, 0, "0", "V"): 1.317,
    (1, 0, "0", "Y"): 0.704,
    (1, 0, "1", "V"): 0.812,
    (1, 0, "1", "Y"): 1.176,
    (1, 0, "2", "V"): 1.102,
    (1, 0, "2", "Y"): 0.905,
    (1, 1, "0", "V"): 1.35,
    (1, 1, "0", "Y"): 0.575,
    (1, 1, "1", "V"): 0.918,
    (1, 1, "1", "Y"): 1.1,
    (1, 1, "2", "V"): 0.894,
    (1, 1, "2", "Y"): 1.129,
    (1, 2, "0", "V"): 1.236,
    (1, 2, "0", "Y"): 0.602,
    (1, 2, "1", "V"): 0.949,
    (1, 2, "1", "Y"): 1.085,
    (1, 2, "2", "V"): 0.902,
    (1, 2, "2", "Y"): 1.165,
    (2, 0, "0", "V"): 1.425,
    (2, 0, "0", "Y"): 0.609,
    (2, 0, "1", "V"): 0.806,
    (2, 0, "1", "Y"): 1.179,
    (2, 0, "2", "V"): 0.865,
    (2, 0, "2", "Y"): 1.125,
    (2, 1, "0", "V"): 1.358,
    (2, 1, "0", "Y"): 0.625,
    (2, 1, "1", "V"): 0.874,
    (2, 1, "1", "Y"): 1.132,
    (2, 1, "2", "V"): 0.865,
    (2, 1, "2", "Y"): 1.141,
    (3, 0, "0", "V"): 1.26,
    (3, 0, "0", "Y"): 0.807,
    (3, 0, "1", "V"): 0.826,
    (3, 0, "1", "Y"): 1.13,
    (3, 0, "2", "V"): 0.924,
    (3, 0, "2", "Y"): 1.057,
}

# ── pazar tanımları: bileşenler, bantlar, seçim etiketleri ────────────
# comp_a/comp_b: (market_key, {kod: selection_adı})
MARKETS = {
    "1X2_OU": {
        "table": T_1X2_OU,
        "band_a": ("1X2", B_X),            # a-bandı P(X) — denge vekili
        "band_b": ("OU2.5", B_OU),         # b-bandı P(ÜST)'ten
        "a_sel": {"1": "1", "0": "0", "2": "2"},
        "b_sel": {"U": "Üst", "A": "Alt"},
        "label": lambda a, b: f"{a} ve {'Üst' if b == 'U' else 'Alt'}",
    },
    "OU_BTTS": {
        "table": T_OU_BTTS,
        "band_a": ("OU2.5", B_OU),
        "band_b": ("BTTS", B_KG),
        "a_sel": {"U": "Üst", "A": "Alt"},
        "b_sel": {"V": "Var", "Y": "Yok"},
        "label": lambda a, b: (f"{'Üst' if a == 'U' else 'Alt'} ve "
                               f"{'Var' if b == 'V' else 'Yok'}"),
    },
    "1X2_BTTS": {
        "table": T_1X2_BTTS,
        "band_a": ("1X2", B_X),
        "band_b": ("BTTS", B_KG),
        "a_sel": {"1": "1", "0": "0", "2": "2"},
        "b_sel": {"V": "Var", "Y": "Yok"},
        "label": lambda a, b: f"{a} ve {'Var' if b == 'V' else 'Yok'}",
    },
}


# ══════════════════════════════════════════════════════════════════════
# 🛡 GÜVENLİK MARJI — BİLEŞEN GÜCÜ DÜZELTMESİ
# ══════════════════════════════════════════════════════════════════════
# BULGU (51.294 örnek-dışı gözlem, korelasyon tablosu 2024 ÖNCESİ veriyle
# kalibre edildi, ölçüm 2024+ diliminde yapıldı):
#
#   Model genelinde MÜKEMMEL kalibre: tahmin %16.68 · gerçek %16.67 (oran 1.00)
#   AMA bileşen gücüne göre sistematik sapıyor:
#     ikisi de ÇOK GÜÇLÜ (üst %35) → oran 1.08  (model fazla TEMKİNLİ)
#     ikisi de güçlü (üst yarı)    → oran 1.05
#     biri zayıf                   → oran 0.98
#     ikisi de ZAYIF               → oran 0.91  (model fazla İYİMSER = TUZAK)
#
# Yani "ucuz görünmek" tek başına yetmiyor — kullanıcının sezgisi doğruydu.
# Uçtan uca 17 puanlık doğruluk farkı var ve bu, edge eşiğimizden (%8) büyük.
#
# UYGULAMA: p_ortak, bileşen gücüne göre düzeltilir. Böylece zayıf-zayıf
# adaylar otomatik olarak eşiğin altına düşer; güçlü-güçlü olanlar öne çıkar.

STRENGTH_MED = {"1": 0.424, "0": 0.263, "2": 0.290,
                "U": 0.524, "A": 0.476, "V": 0.533, "Y": 0.467}
STRENGTH_HI = {"1": 0.495, "0": 0.276, "2": 0.353,
               "U": 0.560, "A": 0.513, "V": 0.562, "Y": 0.496}


# ⚠️ PAZAR-ÖZEL: bu etki HER kombo pazarında yok!
#   1X2_OU   → VAR  (18.040 maç, örnek-dışı: 1.08 ↔ 0.91, 17 puan fark)
#   1X2_BTTS → VAR  (aynı ölçüm)
#   OU_BTTS  → YOK  (4.454 maç, iç bölünmüş sınav: tüm bantlar 0.99-1.02)
# Sebebi yapısal: A/Ü ve KG'nin İKİSİ DE gol sürecine bağlı, aralarındaki
# korelasyon zaten çok güçlü (1.97'ye kadar) — bileşen gücü ek bilgi
# taşımıyor. Oysa 1X2 × gol pazarları SONUÇ ile GOL boyutunu karıştırır;
# orada bileşen gücü gerçek bilgi.
STRENGTH_APPLIES = {"1X2_OU": True, "1X2_BTTS": True, "OU_BTTS": False}


def strength_factor(code_a: str, qa: float, code_b: str, qb: float) -> tuple:
    """Bileşen gücüne göre olasılık düzeltmesi + okunur etiket."""
    ha = qa >= STRENGTH_HI.get(code_a, 9)
    hb = qb >= STRENGTH_HI.get(code_b, 9)
    ma = qa >= STRENGTH_MED.get(code_a, 9)
    mb = qb >= STRENGTH_MED.get(code_b, 9)
    if ha and hb:
        return 1.08, "ikisi de ÇOK GÜÇLÜ"
    if ma and mb:
        return 1.05, "ikisi de güçlü"
    if ma or mb:
        return 0.98, "biri zayıf"
    return 0.91, "ikisi de ZAYIF (tuzak bölgesi)"


# 🛡 RİSK-AYARLI EŞİK: modelin daha az güvenilir olduğu bölgede DAHA FAZLA
# marj iste. Düzeltme katsayısı ortalamadır; zayıf bölgede sapmanın kendisi
# de daha oynaktır. "Aynı edge her yerde aynı değeri taşımaz."
EDGE_MULT = {
    "ikisi de ÇOK GÜÇLÜ": 0.80,          # güvenilir bölge — daha düşük eşik yeter
    "ikisi de güçlü": 1.00,
    "biri zayıf": 1.30,
    "ikisi de ZAYIF (tuzak bölgesi)": 1.80,   # burada iki katına yakın marj iste
}
