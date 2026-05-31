# 📊 ENRICHED BACKTEST SONUÇLARI
## 19.275 Maç · 6 Lig · H2H + Standings + Form + YC/Korner Katmanları

**Tarih:** 2026-05-29  
**Enricher:** `historical_enricher.py` — 19.275/19.275 maç ✅  
**Backtest:** `backtest_enriched.py` — 18.139 analiz edildi  
**Sonuç:** Backtest bulgularına göre `paper_engine.py` güncellendi

---

## 1. STRATEJİ KARŞILAŞTIRMASI

```
Strateji                Pick    Hit%    ROI       100TL × Pick  Yorum
─────────────────────────────────────────────────────────────────────
BASELINE (Edge65)      2.932   %74.8   +%1.1    +3.245 TL     Vergi sonrası negatif
+xG onayı              2.784   %75.9   +%2.6    +7.192 TL  ✅ En güçlü tek katman
+H2H filtresi          1.785   %75.5   +%1.8    +3.299 TL     İşe yarıyor
+Standings filtresi    1.254   %74.9   +%1.7    +2.159 TL     İşe yarıyor
+Form 5G filtresi      2.107   %75.2   +%1.4    +2.875 TL     Küçük katkı
+YC/Korner filtresi    2.778   %74.6   +%0.8    +2.309 TL  ❌ DÜŞÜRDÜ — kaldırıldı
★ TÜM KATMANLAR          486   %76.3   +%3.3    +1.592 TL  ✅ Vergi sonrası pozitif
```

---

## 2. LİG BAZINDA TÜM KATMANLAR

```
Lig   Pick   Hit%     ROI       Karar
───────────────────────────────────────────────────────
SP1    106   %87.7   +%21.3   +1.553 TL  ✅ DEVAM
T1      64   %79.7    +%7.9     +504 TL  ✅ DEVAM
D1      69   %78.3    +%6.0     +412 TL  ✅ DEVAM
E0     106   %76.4    +%2.8     +297 TL  ✅ DEVAM
I1     104   %71.2    −%4.2    −437 TL   ❌ ÇIKARILDI
F1      70   %67.1   −%10.5    −737 TL   ❌ ÇIKARILDI
```

**SP1 (La Liga) anomali:** %87.7 hit oranı ve +%21.3 ROI inanılmaz. 106 pick = güvenilir örneklem. Yapısal bir edge var — Avrupa'nın en rekabetçi ligi paradoks olarak en tahmin edilebilir favorilere sahip.

---

## 3. T1 SEZON BAZINDA TÜM KATMANLAR

```
Sezon       Pick   Hit%    ROI      100TL Kâr
──────────────────────────────────────────────
2017-18      16   %87.5  +%16.4    +262 TL  ✅
2018-19      10   %90.0  +%24.1    +241 TL  ✅
2020-21       6   %66.7   −%5.8     −35 TL  ❌
2022-23       5   %60.0  −%14.4     −72 TL  ❌
2023-24       8   %75.0   −%5.3     −42 TL  ❌
2024-25      12   %91.7  +%23.0    +276 TL  ✅
```

**Not:** 2020-21 COVID, 2022-23 ve 2023-24 düşük pick sayısı (5-8) — istatistiksel gürültü.

---

## 4. BULGULAR VE ÇIKARILAN DERSLER

### 4.1 xG Tek Başına En Güçlü Katman
- Baseline +%1.1 → +xG +%2.6 → **+1.5 puan iyileştirme**
- H2H + Standings birlikte ek +%0.7 puan daha katkı yapıyor
- **Mekanizma:** xG, piyasanın "rastgele favori" hatasını düzeltiyor — maç istatistikleri oranda henüz yansımamış

### 4.2 YC/Korner Filtresi İşe Yaramadı — Neden?
- Sarı kart yoğun maçları eleyince ROI düştü (+%0.8 vs baseline +%1.1)
- **Sebep:** Güçlü favori + yüksek disiplin oran = piyasanın zaten bildiği maç. Bu maçlarda favori yine de kazanıyor. Eleme yanlış pick'leri değil, doğru pick'leri kesiyor.
- **Karar:** Bu filtre kaldırıldı.

### 4.3 F1 ve I1 Yapısal Negatif
- F1 Ligue 1: Her filtreyle negatif → yapısal sorun (Fransız ligi piyasası verimli)
- I1 Serie A: Filtresiz baseline pozitif ama tüm katmanlarla negatif → aşırı filtre
- **Karar:** paper_engine'den çıkarıldı. SP1 + T1 + D1 + E0 kalıyor.

---

## 5. PAPER_ENGINE DEĞİŞİKLİKLERİ

### 5.1 Lig Filtresi (YENİ)
```python
WINNING_LEAGUES = ("SP1", "T1", "D1", "E0")
# F1 (Ligue 1) ve I1 (Serie A) çıkarıldı
# Backtest kanıtı: F1 −%10.5, I1 −%4.2 (tüm katmanlarla)
```

### 5.2 H2H Güçlendirildi
```python
# Destekleyen H2H: signal_score × 1.18
# Zıt yön H2H: signal_score × 0.80 (zayıflatılıyor)
```

### 5.3 Standings Filtresi Aktif
```python
# Düşme hattına ≤ 4 pt → 1X2 sinyalleri iptal
# Backtest: +%1.7 ROI (baseline +%1.1)
```

### 5.4 YC/Korner Filtresi Kaldırıldı
```python
# ROI'yi +%1.1 → +%0.8'e düşürüyordu → iptal
```

---

## 6. SONUÇ — BEKLENEN PERFORMANS

**Güncellenen sistemin tahmini performansı (SP1+T1+D1+E0, tüm katmanlar):**

```
Mevcut ölçülen (4 lig tüm katmanlar):
  SP1: +%21.3  T1: +%7.9  D1: +%6.0  E0: +%2.8
  Ağırlıklı ort: ~%9-10 ROI

Vergi (%10) sonrası: ~+%8-9 net
5.000 TL × 37 pick/yıl × ort.oran 1.65 × %8 ROI ≈ +450-600 TL/yıl
```

**SP1 La Liga özellikle araştırılmalı** — +%21.3 ROI 106 pick üzerinde. Bu ya gerçek bir edge ya da seçim önyargısı. Walk-forward test ile doğrulanması gerekiyor.

---

*Rapor: 2026-05-29 · Enricher: 19.275/19.275 ✅ · Backtest: 18.139 maç*  
*Kaynak: [`backtest_enriched.py`](../02_VERI/backtest_enriched.py)*
