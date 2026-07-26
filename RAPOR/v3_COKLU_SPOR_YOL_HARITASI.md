# 🏟 ÇOKLU-SPOR YOL HARİTASI — iddaa'nın diğer sporları (2026-07-25)

Rol: Ürün Yöneticisi × Vegas-seviye oyuncu × Veri Bilimci. Karar ÖLÇÜMLE verildi.

## 1) CANLI KEŞİF (iddaa API, bugün)
| Spor (st) | Event | MBS yapısı | ANA pazar marjı | Ort. tüm-pazar marjı |
|---|---|---|---|---|
| ⚽ Futbol (1) | 180 | %8 TEKLİ + %16 ikili + %76 üçlü | 1X2: **%16.1** (off-season; sezon içi ana ligde ~%7-9) | %19.1 |
| 🏀 Basket (2) | **3** (yaz — sezon Ekim) | 3/3 ÜÇLÜ-zorunlu | MS 2-yollu: %19.2 (n=3, yaz çöpü) | %19.5 |
| 🎾 Tenis (5) | 38 (çiftler/challenger) | **37/38 ÜÇLÜ-zorunlu** | MS 2-yollu: **%19.9** | %19.9 |
| Diğerleri (voleybol/hentbol vb.) | 0 | — | sezon kapalı | — |

## 2) VEGAS HÜKMÜ — "faydalı olabilir mi?" DÜRÜST CEVAP
**Şimdi HAYIR.** Üç öldürücü kanıt:
1. **Marj avantajı YOK, tersine felaket**: 2-yollu tenis MS'te %19.9 marj — dünya
   standardının (Pinnacle %2-3, Vegas %4-5) **4-7 KATI**. "Niş spor = yumuşak
   çizgi" hipotezi iddaa'da ÇÜRÜDÜ: iddaa niş sporda marjı düşürmüyor, artırıyor.
2. **MBS yapısı futboldan BETER**: basket+tenis neredeyse tamamen üçlü-zorunlu.
   Kendi arşiv kanıtımız: 1-2 ayak 10/10 kazanç vs 3 ayak −%27. Bizi zorla en
   kötü yapıya itiyorlar.
3. **Sezonlar kapalı** (basket Ekim, voleybol Kasım) + her spor için yeni
   settle/istatistik/model hattı maliyeti VAR, futbolda edge bile henüz kanıtsız.

PM ilkesi: **kazanamadığın oyunun kopyasını yeni sahaya taşıma.** Önce futbolda
CLV kapısını geç; kopya o zaman değerli olur.

## 3) KOŞULLU YOL HARİTASI
- **Faz 0 — ÖLÇÜM** ✅ (bugün, maliyet 0): bu rapor.
- **Faz T — FUTBOL SINAVI (Ağu-Eyl)**: TRIVOX/EUVOX + sezon verisi + CLV kapısı.
  Genişlemenin ön şartı burada kanıt üretmek.
- **Faz B — 🏀 BASKET PİLOTU (1 Ekim, KOŞULLU — hatırlatıcı kuruldu)**:
  Koşul A: NBA/EuroLeague ana pazar marjı ≤%10 (Ekim'de yeniden ölçülecek —
  bugünkü %19 yaz-ligi çöpünden). Koşul B: futbolda ≥1 kanıtlı pozitif cep
  (CLV>0, n≥150 veya +ROI ajan). İkisi de sağlanırsa:
  → **🏀 POTACI ajanı**: TEK pazar (Toplam Sayı A/Ü — pace×efficiency ile en
  modellenebilir, NBA veri bolluğu), altyapının ~%70'i hazır (portföy/lig/CLV/
  UI aynen; maliyet: sport kolonu + st=2 fetch + basket settle + sinyal ≈ 3 gün).
  Fayda: **yıl boyu kesintisiz öğrenme hattı** (futbol arasında basket doldurur)
  + diversifikasyon.
- **🎾 TENİS — KALICI RED**: %19.9 marj + üçlü-zorunlu + retirement riski +
  challenger/çiftler veri karanlığı. Matematiksel olarak oynanabilir değil.
- **Voleybol/hentbol**: Kasım'da yalnız ÖLÇÜM (marj+MBS); karar o zaman.

## 4) MALİYET-FAYDA ÖZETİ
| Seçenek | Maliyet | Beklenen fayda | Karar |
|---|---|---|---|
| Tüm sporlara şimdi yayıl | Yüksek (spor başı ~3-5 gün + bakım) | Negatif (marj %19-20'ye para yakma) | ❌ |
| Basket pilotu ŞİMDİ | Orta | Negatif (sezon yok, 3 event) | ❌ |
| **Basket pilotu EKİM, çift-koşullu** | ~3 gün | Yıl-boyu veri hattı + diversifikasyon | ✅ planlandı |
| Tenis | Orta | Kalıcı negatif | ❌ RED |

**Tek cümle**: Genişlemek bir hedef değil ARAÇTIR; araç ancak futbolda kanıtlanan
bir edge'i yeni marjı-makul havuza taşırken işe yarar — o kapı Ekim'de,
ölçümle açılır.
