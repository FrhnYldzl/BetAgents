# FAZ 1 — MVP Çalışma Planı

**Hedef:** Futbol Alt/Üst 2.5 ve KG pazarları için end-to-end çalışan bir karar destek sistemi.
**Süre tahmini:** 5-10 gün geliştirme + 2-4 hafta gözlem
**Bankroll:** 10.000₺ (5-25K aralığından orta nokta)
**Çalışma modu:** Günde 30 dk, yarı-otomatik

---

## Faz 1 Çıktısı

Kullanıcı her gün 30 dakikada şunu yapabilecek:

1. `python daily_report.py` çalıştır
2. Sistem o günün maçları için: model olasılığı, iddaa oranı, edge, önerilen stake üretir
3. Kullanıcı listeyi okur, EV+ olanları iddaa.com'da manuel olarak yatırır
4. `python log_bet.py` ile koyduğu bahisi sisteme kaydeder
5. Maç sonrası `python update_results.py` sonuçları çeker, P&L hesaplar

---

## Geliştirme Sırası (Yapılacaklar Listesi)

### Adım 1 — Veri Altyapısı ⚙️ (Gün 1-2)
- [x] Config dosyası ([config.yaml](config.yaml))
- [ ] Football-Data.co.uk indirici (`02_VERI/scrapers/football_data_downloader.py`)
- [ ] Süper Lig + Premier League + Bundesliga için son 5 sezon veri çek
- [ ] Veri temizleme + normalizasyon (`02_VERI/processed/matches.parquet`)

### Adım 2 — Dixon-Coles Modeli 📊 (Gün 2-4)
- [ ] Dixon-Coles likelihood implementation (`03_MODELLER/base/dixon_coles.py`)
- [ ] Maximum likelihood estimation (scipy.optimize)
- [ ] Tau correction (düşük skor düzeltmesi)
- [ ] Zaman bozulması (time decay)
- [ ] Skor matrisi → market olasılıkları (Alt/Üst, KG, 1X2)
- [ ] Kalibrasyon testleri (Brier score, log loss)

### Adım 3 — Backtest Motoru 🧪 (Gün 4-5)
- [ ] Walk-forward validation (`04_BACKTEST/engine/simple_backtest.py`)
- [ ] Kelly sizing simülasyonu
- [ ] CLV hesabı (Football-Data.co.uk hem açılış hem kapanış oranlarını veriyor)
- [ ] Rapor üretici (HTML/Markdown)

### Adım 4 — Edge Detection 🎯 (Gün 5-6)
- [ ] Maç öncesi tahmin pipeline'ı (`06_PRODUCTION/pre_match_prediction.py`)
- [ ] iddaa oran karşılaştırması (manuel girişle başlangıçta)
- [ ] Edge filtresi (config'teki min_edge_pct ile)
- [ ] Kelly stake önerisi

### Adım 5 — Risk Yönetimi 🛡️ (Gün 6-7)
- [ ] Bankroll tracker (`05_RISK_YONETIMI/bankroll_tracker.py`)
- [ ] Drawdown monitor
- [ ] Bet log yapısı (`07_LOG_VE_RAPORLAR/bet_log.parquet`)

### Adım 6 — Günlük Operasyon 🔄 (Gün 7-8)
- [ ] `daily_report.py` — günün maçları için tüm öneriler
- [ ] `log_bet.py` — bahis kayıt CLI
- [ ] `update_results.py` — sonuç güncelleme + P&L

### Adım 7 — Gözlem & İterasyon 📈 (Hafta 3-6)
- [ ] İlk hafta: kağıt üzerinde bahis (paper trading), gerçek para yok
- [ ] CLV ortalaması ölç, edge gerçek mi anla
- [ ] CLV > %2 ise gerçek paraya çık (önce küçük stake)

---

## Faz 1'de YAPMAYACAKLARIMIZ

- ❌ Otomatik iddaa bot (ToS ihlali, ban riski)
- ❌ Oyuncu propları (Faz 2'ye)
- ❌ Canlı bahis (advanced, Faz 3)
- ❌ Tenis/basketbol (Faz 2)
- ❌ xG verisi (Faz 2 — Understat scraping)
- ❌ Lineup/sakatlık integration (Faz 2)

**Felsefe:** Önce çalışan minimum, sonra genişletme.

---

## Başarı Kriterleri (Faz 1 Bitti Sayılması İçin)

| Kriter | Hedef | Ölçüm |
|---|---|---|
| Veri toplama | 3 lig × 5 sezon = 5.700+ maç | parquet dosyası |
| Model kalibrasyonu | Brier score < 0.22 (Alt/Üst için) | backtest report |
| Backtest ROI (OOT) | Pozitif veya marjinal | 2023-24 sezonu test |
| Backtest CLV | Ortalama > %1 | bet log |
| Günlük pipeline | < 5 saniye çalışıyor | benchmark |
| Faz 1 paper trading | 50+ bet, CLV > %1 | log analizi |

---

## Faz 1'den Faz 2'ye Geçiş Şartları

1. ✅ Paper trading'de 50 bet sonu CLV > %1
2. ✅ Backtest ROI'si en az 2 sezonda pozitif
3. ✅ Kullanıcı operasyonel akışı rahat (günde 30 dk yeterli)
4. ✅ Risk yönetimi kuralları test edildi

Bu kriterler tutmazsa Faz 1'i derinleştirmek, Faz 2'ye geçmemek.

---

## Şu Anki Durum

- [x] Mimari + dokümantasyon kuruldu
- [x] Config dosyası yazıldı
- [ ] **Adım 1 başlangıç noktası: Football-Data.co.uk indirici**

Bir sonraki aksiyon: `02_VERI/scrapers/football_data_downloader.py` yazımı.
