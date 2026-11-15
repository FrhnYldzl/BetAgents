"""
PROJE 2027 · PLAN VERİSİ — Excel'den alınan SABİT plan
========================================================
Kaynak: Iddaa_Bet_Agent_2027_Proje_Plani.xlsx (kullanıcı, 11.11.2026)

⚠️ BURADAKİ SAYILAR PLANIN KENDİSİDİR, ÖLÇÜM DEĞİL.
Planın varsaydığı p ve yield bilerek SABİT tutuluyor ki panel
"plan ne diyordu / gerçekte ne oldu" karşılaştırmasını yapabilsin.
Ölçülen değerler `02_VERI/finans.py` ve `ferhan_kupon` defterinden gelir.

⚠️ PLANIN MOTOR PARAMETRESİ ÖLÇÜMLE ÇELİŞİYOR — ölçüldü (15.11.2026):
    plan        p = 0,90 · o = 1,80 · yield = +%62
    ölçülen     p = 0,4934 · ROI = −%12,6  (plan bandı 1,60-2,00, n=758)
41 puanlık fark. Panel bunu saklamaz, yan yana gösterir.
"""
from __future__ import annotations

# ── Parametreler sayfası ─────────────────────────────────────────────
PLAN_P = 0.90
PLAN_ORAN = 1.80
PLAN_YIELD = PLAN_P * PLAN_ORAN - 1.0        # 0,62
GUVENLIK_PAYI = 1.15
BANKROLL_KATSAYI = 10
BASLANGIC_SERMAYE = 3000      # Ocak merdiven (3 × 1.000)
MERDIVEN_BIRIM = 1000
MERDIVEN_ADET = 3
MERDIVEN_BASAMAK = 3
YEDEK_SERMAYE = 6000
VERGI_ORANI = 0.20
KS1_PENCERE, KS1_ESIK = 20, 0.75
KS2_PENCERE, KS2_ESIK = 40, 0.70

PARAMETRE_ACIKLAMA = [
    ("Kupon isabet oranı (p)", PLAN_P,
     "Çoklu kupon bazında isabet. Defterden ölçülür, elle girilmez."),
    ("Efektif kupon oranı (o)", PLAN_ORAN, "1,60–2,00 bandında kal."),
    ("Kupon başına yield", PLAN_YIELD, "p×o−1. Beklenen kâr / stake."),
    ("Güvenlik payı", GUVENLIK_PAYI, "Stake %15 fazla."),
    ("Bankroll katsayısı", BANKROLL_KATSAYI, "Masada = stake × bu."),
    ("Merdiven birimi", MERDIVEN_BIRIM, "Her merdivenin başlangıç stake'i."),
    ("Paralel merdiven", MERDIVEN_ADET, "Aynı anda yürüyen merdiven."),
    ("Merdiven basamağı", MERDIVEN_BASAMAK, "Ardışık all-in kupon."),
    ("Vergi oranı", VERGI_ORANI, "Şans oyunu ikramiye kesintisi."),
    ("Kill-switch 1 (son 20)", KS1_ESIK, "Altına inerse stake yarıya."),
    ("Kill-switch 2 (son 40)", KS2_ESIK, "Altına inerse DUR."),
]

# ── 2027 Plan sayfası: (ay, faz, hedef brüt kâr, kupon/ay) ───────────
AYLIK = [
    ("Ocak", "Faz 1 — Merdiven", 10000, 9),
    ("Şubat", "Faz 2 — Flat", 15000, 60),
    ("Mart", "Faz 2 — Flat", 20000, 60),
    ("Nisan", "Faz 2 — Flat", 40000, 60),
    ("Mayıs", "Faz 3 — 2x büyüme", 80000, 90),
    ("Haziran", "Faz 3 — 2x büyüme", 160000, 90),
    ("Temmuz", "Faz 3 — 2x büyüme", 320000, 120),
    ("Ağustos", "Faz 3 — 2x büyüme", 640000, 120),
    ("Eylül", "Faz 3 — 2x büyüme", 1280000, 120),
    ("Ekim", "Faz 4 — Tavan", 1280000, 120),
    ("Kasım", "Faz 4 — Tavan", 1280000, 120),
    ("Aralık", "Faz 4 — Tavan", 1280000, 120),
]

# ── Görevler sayfası ─────────────────────────────────────────────────
GOREVLER = [
    ("0.1", "Faz 0", "Bet agent logundan kupon bazlı p ve ortalama efektif "
     "oranı çıkar", "Son 150+ kuponda p ve o hesaplanmış", "YAZILIM"),
    ("0.2", "Faz 0", "Spor Toto / bayi kupon üst limiti ve maksimum kazanç "
     "limitini öğren", "Üç rakam Kurallar sayfasına yazıldı", "Ferhan"),
    ("0.3", "Faz 0", "Ayrı bahis hesabı belirle, günlük paradan ayır",
     "Hesap açık, 9.000 ₺ aktarılmış", "Ferhan"),
    ("0.4", "Faz 0", "Kupon Defteri'ni kullanmaya başla",
     "En az 20 kupon işlenmiş, rolling p görünüyor", "Ferhan"),
    ("0.5", "Faz 0", "Ajana 'kupon oranı 1,60–2,00' ve günlük kısıt ver",
     "Kuponların %90+'ı bantta", "YAZILIM"),
    ("1.1", "Faz 1", "3 paralel merdiven başlat (3 × 1.000)",
     "9 kupon oynandı, sonuçlar deftere işlendi", "Ferhan"),
    ("1.2", "Faz 1", "Döngü sonu kuralı: brüt < 10.000 ise yedekten yeni "
     "döngü", "Toplam brüt ≥ 10.000 veya 3 döngü tamam", "Ferhan"),
    ("1.3", "Faz 1", "Ocak kapanış: 10.000 cebe, Şubat bankroll'u bırak",
     "Nakit Akışı Ocak satırı dolduruldu", "Ferhan"),
    ("1.4", "Faz 1", "Ocak kupon p'sini hesapla, planla karşılaştır",
     "Fark > 5 puan ise plan güncellendi", "YAZILIM"),
    ("2.1", "Faz 2", "Stake'i plandan al, ay boyunca sabit tut",
     "Ay içinde stake değişmedi", "Ferhan"),
    ("2.2", "Faz 2", "Günlük kupon, efektif oran 1,60–2,00",
     "Ay sonunda kupon sayısı plan ±%10", "YAZILIM"),
    ("2.3", "Faz 2", "Kuponu deftere işle, kill-switch'i kontrol et",
     "Defterde boş gün yok", "Ferhan"),
    ("2.4", "Faz 2", "Hedef kârı cebe çek, bankroll'u bırak",
     "İki sayfada ilgili ay dolu", "Ferhan"),
    ("2.5", "Faz 2", "Faz 3'e geçiş kontrolü (180 kuponda p ≥ eşik)",
     "Evet → Faz 3; Hayır → hedef sabit", "YAZILIM"),
    ("3.1", "Faz 3", "Kupon/gün 3'e çıkar (90/ay)",
     "90 kupon, p %85 altına inmedi", "YAZILIM"),
    ("3.2", "Faz 3", "Kupon/gün 4'e çıkar (120/ay)",
     "120 kupon, p %85 altına inmedi", "YAZILIM"),
    ("3.3", "Faz 3", "Stake'i kupon üst limitiyle karşılaştır",
     "Stake ≤ limit", "Ferhan"),
    ("3.4", "Faz 3", "Hedef altı kalan ayda hedefi %75'e çek",
     "Karar deftere not edildi", "Ferhan"),
    ("3.5", "Faz 3", "Vergi: ilk yarı kesintilerini topla",
     "Gerçekleşen efektif oran girildi", "Ferhan"),
    ("4.1", "Faz 4", "Büyümeyi durdur, hedefi Eylül seviyesinde tut",
     "Plan satırları doğrulandı", "Ferhan"),
    ("4.2", "Faz 4", "Aylık kârı tamamen çek",
     "Masada yalnız gerekli bankroll", "Ferhan"),
    ("4.3", "Faz 4", "Yıl kapanışı özeti",
     "Tek sayfalık yıl özeti yazıldı", "YAZILIM"),
    ("K.1", "Kill-switch", "Son 20'de p < %75 → stake yarıya",
     "Bayrak göründüğü gün uygulanmış", "Ferhan"),
    ("K.2", "Kill-switch", "Son 40'ta p < %70 → DUR, yeniden kalibre et",
     "Oyun durdu, kalibrasyon notu yazıldı", "Ferhan"),
    ("K.3", "Kill-switch", "Plan dışı stake yok — telafi kuponu yok",
     "Defterde stake planla birebir", "Ferhan"),
]

KURALLAR = [
    ("Para", "Masada sadece plandaki bankroll durur. Üstü cebe."),
    ("Para", "Stake ay başında bir kez belirlenir, ay içi değişmez."),
    ("Para", "Ocak dışında all-in yok. Merdiven yalnız Faz 1'de."),
    ("Para", "Telafi kuponu, duygusal kupon, plan dışı maç yok."),
    ("Para", "Hedef aylık değil 3 aylık okunur."),
    ("Kill-switch", f"K-S1: son {KS1_PENCERE} kuponda p < "
     f"%{KS1_ESIK*100:.0f} → stake yarıya."),
    ("Kill-switch", f"K-S2: son {KS2_PENCERE} kuponda p < "
     f"%{KS2_ESIK*100:.0f} → DUR, yeniden kalibre et."),
    ("Dış limit", "Kupon başına maksimum bahis: Faz 0'da doldurulacak."),
    ("Dış limit", "Kupon başına maksimum kazanç: Faz 0'da doldurulacak."),
    ("Dış limit", "Stake limitlerin %80'ine ulaştığı ay → Faz 4."),
]


def aylik_hesap(yield_: float, guvenlik: float = GUVENLIK_PAYI) -> list[dict]:
    """Aylık tabloyu VERİLEN yield ile hesapla.

    Plan yield'i ile çağrılırsa planın kendi tablosu çıkar; ÖLÇÜLEN
    yield ile çağrılırsa "bu sistemle gerçekte ne olurdu" çıkar.
    İkisini yan yana göstermek panelin asıl işi.
    """
    out = []
    for ay, faz, hedef, kupon in AYLIK:
        if yield_ > 0 and kupon > 0:
            stake = hedef / (kupon * yield_) * guvenlik
            gecerli = True
        else:
            stake, gecerli = 0.0, False
        out.append({
            "ay": ay, "faz": faz, "hedef": hedef, "kupon": kupon,
            "stake": stake, "bankroll": stake * BANKROLL_KATSAYI,
            "gecerli": gecerli,
            "beklenen_kar": kupon * stake * yield_ if gecerli else 0.0,
        })
    return out


def kendi_testi() -> list[str]:
    hata = []
    if abs(PLAN_YIELD - 0.62) > 1e-9:
        hata.append(f"plan yield 0,62 olmalı: {PLAN_YIELD}")
    if len(AYLIK) != 12:
        hata.append(f"12 ay olmalı, {len(AYLIK)}")
    if len(GOREVLER) != 25:
        hata.append(f"25 görev olmalı, {len(GOREVLER)}")
    t = aylik_hesap(PLAN_YIELD)
    # Ocak: 10.000 ÷ (9 × 0,62) × 1,15 ≈ 2.061
    bek = 10000 / (9 * 0.62) * 1.15
    if abs(t[0]["stake"] - bek) > 1e-6:
        hata.append(f"Ocak stake {t[0]['stake']:.2f} ≠ {bek:.2f}")
    if abs(t[0]["bankroll"] - bek * 10) > 1e-6:
        hata.append("bankroll katsayısı uygulanmadı")
    # ⚠️ EKSİ yield'de tablo SAYI ÜRETMEMELİ
    e = aylik_hesap(-0.126)
    if any(x["gecerli"] or x["stake"] != 0 for x in e):
        hata.append("eksi yield'de stake üretildi — plan bu sistemle "
                    "matematiksel olarak tutturulamaz, sayı uydurulmamalı")
    return hata


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    h = kendi_testi()
    print("kendi testi:", "TEMİZ" if not h else f"{len(h)} sorun")
    for x in h:
        print("  ", x)
