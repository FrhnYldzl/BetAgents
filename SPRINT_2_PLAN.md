# SPRINT 2 — Execution Plan

**Tarih:** 2026-05-27
**Bağlam:** Sprint 1 sonucu — DC mevcut pazarda yeterince güçlü, ensemble yenmedi. CLV -%1.77. Yeni strateji: iddaa'nın gerçek pazar genişliği + AI augmentation.

---

## 🎯 Ana Vizyon (Kullanıcı sözünden)

> **"AI yoluyla bulmak ve kazandırmak diğerlerinin göremediği bir yol ile..."**

Edge sayısal modelden değil, **yapılandırılmamış veriyi feature'a çeviren AI'dan** gelecek.

---

## iddaa Bülteni Gerçeği (Screenshot 27.05.2026)

- **102 futbol maçı bugün** — ağırlık alt ligler
- **Liglet**: Kazakistan, Belarus, İran Azadegan, ASEAN Club, vb.
- **7 ana pazar sütunu**:
  1. Maç Sonucu (1/0/2)
  2. İlk Yarı Sonucu (1/0/2)
  3. Handikaplı Maç Sonucu (H, 1, 0, 2)
  4. Alt/Üst 2.5 (Alt, Üst)
  5. Karşılıklı Gol (Var, Yok)
  6. + 113 alt-pazar (her maç için)
- MBS (Minimum Bahis Sayısı) genellikle **3**

---

## SPRINT 2.1 — 7 İddaa Pazarı (1-2 gün) ⬅ ŞU AN BAŞLIYOR

**Çıktı:** Mevcut DC modelinden tüm pazarlar için olasılık + fair odds + edge.

### Geliştirilecek pazarlar

| # | Pazar | Mevcut | Yapılacak |
|---|---|---|---|
| 1 | Maç Sonucu 1X2 | ✅ Hazır (prob_1x2) | UI'da göster |
| 2 | İlk Yarı 1X2 | ❌ | İlk yarı için ayrı DC fit (sadece ilk yarı gol verisi) |
| 3 | Handikaplı Sonuç | ❌ | DC score matrix'ten +1/-1/+2 handicap shift |
| 4 | Alt/Üst 2.5 | ✅ Hazır | UI'da göster |
| 5 | Alt/Üst 1.5, 3.5 | Kısmen | UI'da seçenek ekle |
| 6 | Karşılıklı Gol | ✅ Hazır (prob_btts) | UI'da göster |
| 7 | İY/MS Kombine | ❌ | Joint distribution (Pr(İY=X) × Pr(MS=Y\|İY=X)) |

### Bonus pazarlar (zaman varsa)
- Maç skoru top-5 exact
- Çifte şans (1X, X2, 12)
- Beraberlikte iade
- Maç günü toplam gol

---

## SPRINT 2.2 — Alt Lig Coverage (1 gün, ~5-8 API call)

**Hedef ligler (verimsizlik sırasıyla):**
- Kazakistan Premier (api-football LIG ID kontrol)
- Belarus Premier
- İran Azadegan
- Norveç Eliteserien
- İsveç Allsvenskan
- Yunanistan, Polonya

**Risk:** Sample küçüklüğü (~200-300 maç/sezon). DC fit zor. Daha geniş time-decay (xi düşürmek).

---

## SPRINT 2.3 — 🌟 GEMINI LLM AUGMENTATION (3-5 gün, moonshot)

**Kullanıcı Gemini API key sahibi.**

### Mimari

```
[Veri Kaynakları]              [Gemini]                [Feature]
iddaa Yazar Yorumları          Sentiment              motivation_score
Twitter @takim_handle    →    Entity ext      →     key_player_doubt
Transfermarkt headlines        Tactical                tactical_change
Lokal Türkçe/İngilizce         Narrative              recent_form_narrative
Hava durumu                    Match prep             pitch_condition
```

### Implementation

```python
# pseudo
def llm_features(fixture):
    text = aggregate_news(fixture, last_24h)
    prompt = f"""
    Below are news/social posts about {fixture.home} vs {fixture.away}.
    Extract structured signals:
    - motivation_score [0-1]
    - key_player_doubt [0-1]
    - tactical_change [0-1]
    - sentiment [-1,1]
    - injury_severity [0-1]
    Return JSON only.

    Posts:
    {text}
    """
    return gemini.generate(prompt, response_format="json")
```

### Free tier yeterli mi?
- Gemini 1.5 Flash: 1500 RPM, 15 RPD ücretsiz
- iddaa 102 maç/gün × 1 call = 102 call/gün → günde 6× over limit
- Çözüm: **Sadece edge-positive maçlar için LLM call** (DC ön-filtre)

---

## SPRINT 2.4 — İşlem Maliyeti & Risk Yönetimi (0.5 gün)

```python
# Pre-trade filter
def should_bet(p_model, odds_iddaa, all_market_odds):
    vig = sum(1/o for o in all_market_odds) - 1  # iddaa marjı
    fair_odds_net = odds_iddaa * (1 + vig)        # vig sonrası
    edge_net = p_model * fair_odds_net - 1
    return edge_net > 0.03  # %3 net edge sonrası bet
```

Kelly clamp:
- Max stake: %2 bankroll
- Daily loss limit: %5 bankroll
- Stop trading if drawdown > %20

---

## SPRINT 2.5 — Continuous Validation (her gün)

- Her bahisten sonra CLV ölç
- Aylık Brier/LogLoss raporu
- A/B: AI-augmented vs baseline
- **Otomatik kapatma**: 30 gün CLV<0 → sistem durur

---

## Bilimsel Kabul Kriterleri

Sprint 2 sonunda **canlı bahse geçmek için** şu metrikleri görmek gerekir:

| Metrik | Hedef | Mevcut |
|---|---|---|
| CLV ortalaması | > +%1 | ❌ -%1.77 |
| CLV > 0 oran | > %50 | ❌ %36 |
| t-test p-value | < 0.05 | ❌ 0.20 |
| Sample boyutu | > 500 | ❌ 195 |
| Brier (vs vig-adjusted) | < piyasa | ⏳ test edilmedi |

**Bu kriterlerden hepsi geçmeden Pro plan satın alma yok, gerçek bahis yok.**

---

## Risk Yönetimi (Kullanıcı vizyonuyla uyumlu)

> "Kaybetmeyi minimuma indirip kazanmak işlem maliyetini minimize ederek"

- iddaa marjı (vig) **her bahisin EV'sinden düşülür**
- Çoklu hesap segmentasyon (limit yeme riski)
- Maç-sabitleme alarm (alt liglerde özellikle Asya)
- Stop-loss otomatik

---

## Multi-LLM Stratejisi

| LLM | Kullanım | Sebep |
|---|---|---|
| **Gemini Pro** (kullanıcının) | Birincil feature extraction | Free tier, multimodal |
| GPT-4 / Claude (opsiyonel) | Cross-validation | Hallucination kontrolü |
| Embedding modeller | News clustering | Maliyetsiz |

---

## Sıralama

1. ✅ **Sprint 2.1** (şu an başlıyor) — pazar genişletme
2. ⏳ Sprint 2.2 — alt lig coverage
3. ⏳ Sprint 2.3 — Gemini LLM augmentation (asıl moonshot)
4. ⏳ Sprint 2.4 — transaction cost
5. ⏳ Sprint 2.5 — continuous validation

Her sprint sonunda **bilimsel test** çalıştırılıp CLV/Brier kontrol edilir.
