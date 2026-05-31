# BAHIS AGENT — Ürün Yol Haritası

**Son güncelleme:** 27 Mayıs 2026

```
PHASE 0  Veri & Altyapı       ✅ TAMAM
PHASE 1  Baseline Model        ✅ TAMAM (ama edge yok)
PHASE 2  Edge Yaratma         🚧 DEVAM EDİYOR
PHASE 3  Production Launch    ⏳ Phase 2 sonrası
PHASE 4  Ölçeklendirme        ⏳ Gelecek
```

---

## PHASE 0 — Veri & Altyapı ✅

> "Sağlam temeli at, sonra üzerine kur."

| Görev | Durum | Detay |
|---|---|---|
| Football-Data.co.uk indirici | ✅ | 5,180 maç (T1, E0, D1) |
| api-football entegrasyonu | ✅ | Free plan, 12/100 günlük kota |
| SQLite database | ✅ | 2,098 fixture + 5,330 xG + 15,475 sakatlık |
| Cache sistemi | ✅ | API çağrıları diske kaydedilir, 0 wasted call |
| Streamlit UI iskelet | ✅ | localhost:8501, hot-reload |
| Klasör yapısı (YAZILIM/) | ✅ | 01-07 modülleri |
| Bilimsel literatür özet | ✅ | Dixon-Coles, Constantinou, Kelly |

---

## PHASE 1 — Baseline Model ✅

> "İlk modelin çalışsın, sonra iyileştir."

| Görev | Durum | Detay |
|---|---|---|
| Dixon-Coles (bivariate Poisson) | ✅ | Tüm 3 ligde fit |
| Platt scaling kalibrasyonu | ✅ | Brier 0.2526 → 0.2366 |
| 7 iddaa pazarı türetilmesi | ✅ | MS 1X2, İY, Handikap, A/Ü, KG, Çifte Şans, İY/MS |
| Walk-forward backtest | ✅ | Her 7 günde refit |
| Multi-league validation (n=577) | ✅ | **CLV -%1.85, p=0.0000 — EDGE YOK** |
| Fractional Kelly sizing | ✅ | 0.20× Kelly, max %3 bankroll |
| Risk-tiered kupon önerisi | ✅ | Konservatif / Dengeli / Agresif |
| UI v0.4 (iddaa.com paleti, SaaS) | ✅ | Hamburger, hikaye, kupon paneli |

**Phase 1 bilimsel hükmü:**
- ❌ Edge KANITLANMADI (CLV negatif, t-test p=0.48)
- ✅ Temel işlevler ÇALIŞIYOR (kupon üretiyor, risk yönetiyor)
- ✅ Sample yeterli (577 bahis)
- ✅ Şeffaf bilimsel rapor

**Sonuç:** Sayısal modellerle (DC + xG + Elo + LightGBM + Sakatlık) bookmaker'ı yenmek **imkansız**.
Faz 2'de **ortogonal bilgi kaynakları** denenecek.

---

## PHASE 2 — Edge Yaratma 🚧

> "Bookmaker'ın göremediği bilgiyi sentezle."

### Sprint 2.1 — 7 iddaa pazarı ✅
Tamamlandı (Phase 1 ile birlikte).

### Sprint 2.2 — Alt Lig Coverage ⏳ Sıradaki
**Süre:** 1 gün · **API maliyeti:** ~5 call

Hedef ligler (verimsizlik = edge potansiyeli):
- 🇰🇿 Kazakistan Premier
- 🇧🇾 Belarus Premier
- 🇮🇷 İran Azadegan
- 🇳🇴 Norveç Eliteserien
- 🇸🇪 İsveç Allsvenskan

**Risk:** Sample boyutu küçük (~250 maç/sezon). xi düşürmek gerek.

### Sprint 2.3 — LLM Augmentation ⏳ Asıl Moonshot
**Süre:** 3-5 gün · **API maliyeti:** ~50 call Gemini/gün

```
Veri kaynağı           Gemini ile çıkar       LightGBM feature
─────────────────      ──────────────         ─────────────────
iddaa yazar yorumu  → sentiment, tahmin    → expert_consensus
Twitter @takım       → entity extraction     → key_player_status
Haber RSS            → tactical_change       → tactical_score
Transfermarkt        → injury severity       → injury_impact
Hava durumu          → match preparation     → weather_factor
```

**Multi-LLM**:
- Birincil: **Gemini 1.5 Flash** (free, 1500 RPM)
- Cross-check: **GPT-4 / Claude** (anomali kontrolü)
- Embedding: **HuggingFace** Türkçe BERT (ücretsiz)
- GPU: Colab T4 (ücretsiz)

**Risk:** LLM hallucination → manuel review zorunlu (ilk hafta).

### Sprint 2.4 — Transaction Cost & Risk Yönetimi
**Süre:** 0.5 gün

- iddaa vig hesabı (margin'i her edge'den düş)
- Max günlük kayıp limiti (bankroll %5)
- Stake clamp (max bahis %2 bankroll)
- Drawdown stop (>%20 → sistem durur)
- Hesap segmentasyon (limit yeme riski)

### Sprint 2.5 — Continuous Validation
**Süre:** sürekli (production)

- Her bahisten sonra CLV ölç → öğren
- Aylık Brier/LogLoss raporu
- A/B test: AI-augmented vs baseline
- 30 gün CLV<0 → otomatik kapat

---

## PHASE 3 — Production Launch ⏳

> "Sistem kanıtlandı, gerçek kullanıma aç."

**Tetikleyici:** Phase 2 sonunda CLV pozitif + sample 1000+.

| Görev | Süre | Detay |
|---|---|---|
| Kullanıcı kaydı + auth | 2 gün | Streamlit-Authenticator |
| Plan yönetimi | 3 gün | Free (1 lig, sınırlı), Pro (tüm) |
| Webhook / e-posta uyarı | 2 gün | "Edge yüksek maç bulundu" |
| Mobile responsive | 2 gün | Mobil tarayıcı uyumlu |
| Telegram bot | 3 gün | Anlık kupon bildirimi |
| Cloud deployment | 2 gün | Streamlit Cloud / Railway |

---

## PHASE 4 — Ölçeklendirme ⏳

> "Tek lig'den global'e."

| Görev | Süre |
|---|---|
| Basketbol modeli | 2 hafta |
| Tenis modeli | 2 hafta |
| E-spor (CS:GO, Dota2, LoL) | 3 hafta |
| Diğer ligler (J-League, MLS, vb.) | 2 hafta |
| Otomatik veri pipeline (cron + Airflow) | 1 hafta |
| Live (in-play) prediction | 4 hafta |
| API olarak hizmet sunma | 2 hafta |

---

## 🎯 Karar Noktaları (kullanıcı yönlendirmesi için)

Kullanıcı şu noktalarda yön belirleyebilir:

1. **Sprint sıralaması** — 2.2 mi 2.3 mü önce?
2. **LLM seçimi** — Gemini birincil mi yoksa Claude/GPT mi?
3. **Veri kaynağı** — Twitter API key'i alacak mıyız?
4. **Bütçe** — Pro plan ne zaman?
5. **Phase 3 launch zamanı** — alpha/beta/public?

---

## 📊 Mevcut Durum (Snapshot)

```
PHASE 0   ████████████████████ 100%
PHASE 1   ████████████████████ 100%
PHASE 2   ████░░░░░░░░░░░░░░░░  20%  (Sprint 2.1 done)
PHASE 3   ░░░░░░░░░░░░░░░░░░░░   0%
PHASE 4   ░░░░░░░░░░░░░░░░░░░░   0%

Tamamlanan task: 23/40+
Bilimsel hüküm: ❌ Edge kanıtlanmadı (Phase 2 ile değişecek)
UI durumu     : ✅ v0.4, fonksiyonel
DB           : ✅ 2K+ fixture, 5K+ xG, 15K+ injury
API kotası   : 12/100 günlük (88 kalan)
```

---

## 💡 Yenilikçi Fikir Havuzu (kullanıcı önerileri için)

| Fikir | Faz | Açıklama |
|---|---|---|
| Hakem profili modeli | 2 | Kart eğilimi → kart pazarı edge |
| Hava durumu × saha tipi | 2 | Yağmurda Üst düşer |
| Motivasyon faktörü | 2 | Cup final vs nothing-to-play |
| Sentiment momentum | 2 | Twitter trend %48h Δ |
| Lineup-bazlı xG | 2 | İlk 11 değişimi ile xG güncelle |
| Bayesian rolling DC | 2 | Her maçtan sonra online güncelleme |
| Player props (gol/kart/şut) | 3 | En verimsiz market |
| Live (in-play) prediction | 4 | DC + maç skor anlık |
| Hesap segmentasyon | 3 | Limit yeme önleme |
| Çoklu bookmaker karşılaştırma | 3 | iddaa vs Bet365 vs Pinnacle |
