# 🧪 Sofa-xG Baseline Model — İnşa & Backtest Sonucu (DÜRÜST)

**Tarih:** 2026-05-31 · **Görev #148 — inşa fazı**

## Ne inşa edildi (✅ kalıcı varlık)
| Bileşen | Durum |
|---|---|
| `02_VERI/data_sources/sofascore.py` — adapter (Playwright + in-page fetch) | ✅ |
| `sofascore_stats` tablosu (xG + 40-metrik + votes) | ✅ |
| **T1 backfill: 0 → ~1004 maç xG** (2023-2026, %99.7) | ✅ |
| `02_VERI/sofa_xg_model.py` — sızıntısız rolling-xG → Poisson → backtest | ✅ |

## Backtest (sızıntısız, pre-match rolling xG, T1 kapanış oranına karşı)
| Market | Maç | Brier MODEL / PİYASA | En iyi ROI (vergisiz / vergili) |
|---|---|---|---|
| 1X2 | 771 | 0.600 / 0.546 | -15.7% / -20.9% |
| Alt/Üst 2.5 | 785 | 0.263 / 0.234 | -11.0% / -15.4% |

**Tüm eşiklerde ROI negatif.** Model her iki markette de piyasanın (kapanış oranı) gerisinde.

## Dürüst yorum
- **Kapanış oranı verimli/keskin.** Halka-açık veriyle (xG) kurulmuş basit bir Poisson modeli onu yenemiyor — bu sektörde beklenen sonuçtur.
- A/Ü 2.5'te model piyasaya **daha yakın** (xG doğrudan gol bilgisi taşır) ama yine de açığı kapatmıyor.
- "Bulunan edge"ler ağırlıkla **model hatası**, gerçek değer değil → negatif ROI.

## Bu, verinin değersiz olduğu anlamına GELMEZ
xG + 40-metrik gerçek ve kalıcı bir varlık. Değeri "tek başına para basan model" değil:
1. **Feature olarak:** mevcut DC/Elo/odds-movement ensemble'ına xG girdisi (standalone değil, harman).
2. **Yumuşak piyasalar:** T1 *kapanış* zaten keskin. Açılış oranı / niş-soft ligler test edilmeli.
3. **CLV teşhisi:** model açılış oranını yeniyor ama kapanışı yenmiyor mu? (sinyal var ama piyasa sonradan fiyatlıyor) — sıradaki en bilgilendirici test.
4. **Analiz/içgörü:** takım xG over/under-performansı, form kalitesi.

## CLV TEŞHİSİ (açılış vs kapanış — sinyal var mı?)
| Eşik | Bahis | ROI@açılış | ROI@kapanış | ort. CLV% |
|---|---|---|---|---|
| 0.05 | 640 | -19.1% | -17.4% | +0.53% |
| 0.08 | 460 | -13.6% | -11.6% | +0.57% |

- **CLV ≈ +0.5%:** piyasa seçimlerimize çok hafif lehimize kıpırdıyor → modelde **mikro sinyal kırıntısı** var (saf gürültü değil) ama gürültü/vig seviyesinde.
- **ROI hem açılışta hem kapanışta NEGATİF** → sömürülebilir edge'e dönüşmüyor.

## 🔚 KESİN VERDICT
Naive standalone xG modeli **hiçbir konfigürasyonda** (1X2 kapanış/açılış, A/Ü, CLV) sömürülebilir edge üretmedi. Piyasa verimli. **Standalone model yolu kapandı (dürüst negatif).**

## Öneri
- ❌ **Standalone modeli canlıya ALMA.** Bu thread'i kapat (daha fazla T1 varyantı kovalama).
- ✅ **Veri varlığını koru** — adapter + `sofascore_stats` + 1004 T1 xG repoda; analiz/içgörü + feature için değerli.
- 🔬 Kalan **iki** gerçek yol (standalone değil): **(B)** xG'yi mevcut DC/Elo ensemble'ına **feature** olarak kat, marjinal lift ölç · **(C)** bir **yumuşak niş lig** backfill + test (T1 kapanış zaten keskindi).
- Mikro +CLV, ensemble-feature yolunun (B) denenmeye değer olduğunu *zayıfça* destekliyor — ama beklenti düşük tutulmalı.

---

*Dürüstlük notu: bu backtest sızıntısız (rolling, pre-match). Negatif ROI gizlenmedi — kapanış çizgisini yenmek sporun en zor testidir; naive model geçemedi. Veri katmanı yine de değerli, kullanım biçimi farklı.*
