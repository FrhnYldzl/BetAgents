# Faz V — Test Önerileri (v4 hazırlık)

**Tarih:** 2026-05-27
**Çerçeve:** Akademik araştırma planı
**Önceki:** v3 (T01-T11)

---

## Araştırma Programı

> "Borsadaki giriş-çıkış kadar kritik" — kullanıcı

Sezgisel olarak iddialar:
1. Sezon başında modelin geçmişi az → sinyaller zayıf
2. Sezon ortasında form yerleşmiş → sinyaller güçlü
3. Sezon sonu motivasyon dağılır (şampiyon belli, küme düştü) → noise artar
4. Kayıp serisinde "pas geçmek" mean reversion'dan faydalanır
5. Bütçe dağıtımı: tek lig konsantrasyon vs çeşitlendirme

Bu sezgileri **veri ile test edeceğiz**.

---

## Hipotezler

### H6 — Entry Timing
- **H6a:** Sezon başında ROI düşük olur (warm-up gerek).
- **H6b:** Sezon ortasında (matchday 10-25) ROI en yüksek olur.
- **H6c:** Sezon sonu (son 5 hafta) "motivasyon" gürültü artar.

### H7 — Skip Strategy (PAS)
- **H7a:** Düşük sinyal yoğunluklu haftalar kaybettiriyor.
- **H7b:** Ardışık kayıp sonrası birkaç hafta "pas" daha iyi.
- **H7c:** Milli arası sonrası kaotik sezon → skip.

### H8 — Multi-League Budget
- **H8a:** Her ligten 1000 TL paralel → toplam kar T1-only'den yüksek (T11 ALL = +81K).
- **H8b:** 5 lig (E0+D1+T1+SP1+I1+F1) hazırlanırsa toplam +120-150K mümkün.
- **H8c:** Lig sayısı arttıkça volatilite düşer (diversifikasyon korelasyon ≤ 0).

### H9 — Combined Optimum
- **H9a:** Entry timing + skip + multi-league birleşik en iyi config tek-faktöre üstün.

### H10 — Loss-Streak Reset
- **H10a:** 3+ ardışık kayıp sonrası 1-2 hafta pas → sonraki periyot ROI artar.
- **H10b:** Bu **bilişsel bias** olabilir (gambler's fallacy) → test edilmeli.

---

## Test Tasarımları

### T12 — Entry Timing Analizi
**Soru:** Sezonun hangi haftasından itibaren oynamaya başlamalı?

**Yöntem:**
1. T1 K=3 picks'i sezon-bazlı grupla (her sezon 36-38 matchday)
2. Her sezon için "Matchday N'den başlasaydım" simülasyonu:
   - N ∈ {1, 5, 10, 15, 20, 25, 30}
   - Her N için ROI, hit rate, weekly distribution
3. **Cross-season aggregation**: tüm sezonlar boyunca aynı N'den başla → ortalama
4. **Walking entry**: ilk K hafta gözlem (kupon yok), sonra başla

**Çıktı:** Optimal entry matchday N*

### T13 — Skip Week (PAS) Stratejisi
**Soru:** Hangi haftalarda hiç kupon almamak daha karlı?

**Yöntem:**
1. Skip kuralları test et:
   - a) Sezon başı (matchday < 5)
   - b) Sezon sonu (matchday > 33)
   - c) Düşük score haftaları (max score_v13 < 0.75)
   - d) Düşük signal_count haftaları (< 2 sinyal)
   - e) Sonrası: 2+ ardışık kayıp
2. Her kurala ROI değişimi: skip vs hep oyna
3. Multi-rule kombinasyonu

**Çıktı:** Optimal skip-rule seti

### T14 — Multi-League 5000 TL Budget
**Soru:** 5 lig × 1000 TL paralel → toplam ne yapar?

**Yöntem:**
1. Mevcut 3 lig (E0+D1+T1) + 3 yeni lig (SP1+I1+F1)
2. SP1/I1/F1 için xG var (T1 dışı 5 lig hazır) — DC eğit yoksa
3. K=3 her lig için, flat 1000 TL/lig/hafta
4. Aylık/yıllık toplam, lig-bazlı kırılım
5. Korelasyon matrisi 6 lig için
6. Sharpe karşılaştırma 3-lig vs 6-lig

**Çıktı:** 5-6 lig budget stratejisi sonuçları

### T15 — Optimum Kombinasyon
**Soru:** En iyi entry + skip + lig seti nedir?

**Yöntem:**
1. T12, T13, T14 sonuçlarını al
2. **Grid search**:
   - Entry matchday: {1, 5, 10}
   - Skip rules: {none, all-low-score, post-loss-streak, multi}
   - League set: {T1, E0+T1, ALL}
3. Cross-validation: 2122-2223'te train, 2324-2425'te test
4. Best config göre final strateji

**Çıktı:** Ürün-hazır config

### T16 — Loss-Streak Pause
**Soru:** Ardışık 3+ kayıptan sonra K hafta pas geçmek edge'i değiştirir mi?

**Yöntem:**
1. T1 K=3 picks → ardışık kayıp dönemlerini işaretle
2. Loss-streak sonrası N hafta pas (N ∈ {0, 1, 2, 3, 5})
3. Sonraki M hafta ROI ölç (M = 10)
4. Karşılaştırma: pas-vs-pas-yok ROI farkı
5. Statistical test: gambler's fallacy mi gerçek mi?

**Çıktı:** Pause rule efficacy

---

## Beklenen Çıktılar

| Test | Beklenen Sonuç (hipotez) | Doğrulanma Yöntemi |
|---|---|---|
| T12 | Optimal entry: matchday ~10 | Per-N ROI grafiği |
| T13 | Skip low-score → ROI +5pp | Skip rule comparison |
| T14 | 6-lig +120K | Total NET PnL |
| T15 | Combined ROI maksimum | Grid search winner |
| T16 | Loss-streak pause minor | t-test pre/post pause |

---

## Bilim Disiplin Çerçevesi

- **Out-of-sample**: 2425 sezonu T15 doğrulaması için (eğer 2122-2324'te grid yapıldıysa)
- **Multiple-testing correction**: Bonferroni p-eşik adjustment (~ 0.05 / 5 test = 0.01)
- **Effect size**: Cohen's d, sadece p-value değil
- **Robustness**: Result confidence intervals

---

## Sonra Yapılacaklar

T12 → T16 sırasıyla çalıştır, her test sonrası rapor (RAPOR/T12_*.md ... T16_*.md).
v4 final yönetici özeti tüm 16 testi içerir, sistemin nihai konfigürasyonunu sunar.
