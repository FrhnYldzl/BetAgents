# UI/UX MİMARİSİ — DIGITAL TWIN TRADER
## "Trader'ın yanında olan AI — ekranı, sesi, mesajı"

**Tarih:** 2026-05-28
**Felsefe:** Karar destek = anlık iletişim. Trader telefonu/PC'yi açtığında **anında ne yapacağını** görür.
**Hedef cihazlar:** Mobile (öncelikli, %70 kullanım), Desktop (%25), Voice/Telegram (%5)

---

## 1) UI FELSEFESİ — 5 İLKE

1. **Karar odaklı** — "Bu hafta ne oynayayım?" sorusuna 5 saniyede cevap
2. **Şeffaflık** — Her pick için "neden" tek tıkla erişilebilir
3. **Disiplin** — Sistem trader'a uyarı verir, koruma sağlar
4. **Öğrenilebilirlik** — İlk gün başlayan trader anlar; uzman trader daha derin görür
5. **Çok kanallı** — Web, Mobile, Telegram, Voice — trader'ın yerine göre

---

## 2) ANA EKRANLAR (5 TEMEL EKRAN)

### EKRAN 1: HAFTA DASHBOARD'ı (Anlık karar görünümü)

```
┌──────────────────────────────────────────────────────────────┐
│  ☰  AI TRADER                       🔔  💰 12,450 TL  👤    │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  📅  HAFTA: 30 Mayıs - 1 Haziran 2026          🎯 Toplam: 4  │
│                                                              │
│  ⚡ ULTRA-CONSENSUS (1)                                       │
│  ┌──────────────────────────────────────────────────────┐    │
│  │ Liverpool - Tottenham                                │    │
│  │ Pick: 1 (Ev Sahibi)              Oran: 1.55          │    │
│  │ Confidence: ⭐⭐⭐⭐⭐ Q5 + 2 model konsensüsü        │    │
│  │ Önerilen: 500 TL (ALL-IN, bankroll %4)               │    │
│  │ Hit beklentisi: %78    Beklenen kazanç: +275 TL net  │    │
│  │                                                       │    │
│  │ [Detay] [Yatır] [Atla]                               │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  🟢 ALL-IN (2)                                                │
│  ┌─────────────────┬───────────────────────────────────┐     │
│  │ Real Madrid 1   │ Galatasaray 1                     │     │
│  │ @ 1.45  Q5+a2   │ @ 1.85  Q5+a2                     │     │
│  │ 500 TL ALL-IN   │ 500 TL ALL-IN                     │     │
│  │ [Detay] [Yatır] │ [Detay] [Yatır]                   │     │
│  └─────────────────┴───────────────────────────────────┘     │
│                                                              │
│  🟡 STANDART (1)                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │ Arsenal 1 @ 1.70  Q5+a1   100 TL  STANDART           │    │
│  │ [Detay] [Yatır]                                      │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  ─────────────────────────────────────────────────────       │
│  💡 STRATEJİ ÖNERİSİ:                                         │
│  3 ALL-IN aday için → 2/3 SİSTEM önerilir (varyans düşür)    │
│  Toplam stake: 1500 TL  |  Max kayıp: -1500 (sadece %3)       │
│  Beklenen kazanç: +783 TL net (ROI %52)                       │
│  [Sistemi göster] [Tek tek yatırmak istiyorum]                │
│                                                              │
│  📊 BANKROLL TREND                                            │
│  10K ──→ 12.5K  (+%24.5)  Son 4 hafta                         │
│  Drawdown: -%6 (kontrollü)                                    │
│  Hit rate: 14/18 = %78                                        │
│                                                              │
│  ⚠️ UYARI YOK  ✓ Risk seviyesi normal                         │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Etkileşim:**
- "Detay" → EKRAN 2 (Pick detay)
- "Yatır" → manuel iddaa.com'a yönlendirme + log
- "Atla" → Sebep sor + Learning Agent'a feedback
- "Sistemi göster" → EKRAN 3 (kupon strateji karşılaştırma)

---

### EKRAN 2: PICK DETAY — "Neden Bu Pick?"

```
┌──────────────────────────────────────────────────────────────┐
│  ← Geri                                          🔄 Paylaş   │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Liverpool - Tottenham                                       │
│  31 Mayıs 2026, 18:30 TSI         Anfield Stadium            │
│                                                              │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                  │
│  🎯 PİCK: Liverpool Kazanır (1)                              │
│  Oran: 1.55          Önerilen pozisyon: 500 TL ALL-IN        │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                  │
│                                                              │
│  📊 NEDEN BU PICK?                                            │
│                                                              │
│  ✓ MODEL KONSENSÜSÜ                                           │
│    • MONOVOX-E0: Q5 (score 0.93) — Liverpool 1                │
│    • DUOVOX: Q5 (score 0.91) — Liverpool 1                    │
│    → 2 model aynı yönde ULTRA-konsensüs                       │
│                                                              │
│  ✓ SİNYAL DOĞRULAMA (agree=2)                                 │
│    • Cross-market anomaly: Liverpool (✓ teyit)                │
│    • Dixon-Coles model: Liverpool (✓ teyit)                   │
│    • xG luck: Liverpool (✓ teyit)                             │
│    • Form: Liverpool (✓ teyit)                                │
│    → 4/4 sinyal aynı yönü işaret ediyor                       │
│                                                              │
│  ✓ TAKIM ANALİZİ (Team Analyst)                               │
│    Liverpool: Son 5 maç: W-W-D-W-W, ev avantajı güçlü         │
│    Tottenham: 3 anahtar oyuncu sakatlık (Son, Maddison, Romero)│
│    H2H (son 5): 4W-0D-1L Liverpool lehine                     │
│                                                              │
│  ✓ MAÇ BAĞLAMI (Match Context)                                │
│    Hava: Açık 16°C — normal                                   │
│    Tottenham geçen hafta CL maçı oynadı — fixture yoğunluğu   │
│    Liverpool dinlenmiş (8 gün hafta arası)                    │
│                                                              │
│  ✓ PAZAR ANALİZİ (Market Analyst)                             │
│    Opening odd: 1.62 → Closing: 1.55 (Liverpool fav)          │
│    Sharp money Liverpool yönünde (%3 drift)                   │
│    Bookmaker karşılaştırma: iddaa 1.55, B365 1.57, Pinnacle 1.53│
│    → Sharp money ile aynı yöndeyiz, iyi işaret                │
│                                                              │
│  ✓ TARİHSEL PERFORMANS                                        │
│    DUOVOX Q5+agree2: 19 maçta 16 hit = %84                    │
│    Hafta-aralığı: bu sezon ilk 8 hafta → STABIL bölge          │
│                                                              │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                  │
│  ⚠️ RİSKLER:                                                  │
│  • Liverpool son 2 maç ev sahasında −1.5 hcap kaybetti        │
│  • Tottenham deplasmanda surpriz yapabilir (%14 ihtimal)      │
│  • Bahis oranı düşük (1.55), value sınırlı ama hit yüksek     │
│                                                              │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                  │
│  💡 AI TRADER YORUMU:                                         │
│  "Liverpool için ALL-IN öneriyorum. Konsensüs maks, sakatlık   │
│  Liverpool lehine, sharp money ile aynı yöndeyiz. Bu sezonun  │
│  ilk 'kolay para' fırsatlarından."                           │
│                                                              │
│  [Yatır] [Tartış] [Atla — Neden?]                            │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**"Tartış" butonu:** Trader Orchestrator ile yazılı/sesli konuşabilir
- "Tottenham deplasman formu nasıl?"
- "Eğer 2x stake yaparsam risk ne?"
- "Bu maçta A/Ü 2.5 üst nasıl?"

---

### EKRAN 3: KUPON STRATEJİ — A/B/C Karşılaştırma

```
┌──────────────────────────────────────────────────────────────┐
│  ← Geri    KUPON STRATEJİSİ                                  │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  3 ALL-IN aday için 3 seçenek var:                           │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐     │
│  │ ⓐ SNIPER SPREAD (3 ayrı K=1)                        │     │
│  │ ────────────────────────────────                    │     │
│  │ • Liverpool 1 @ 1.55 → 500 TL                       │     │
│  │ • Real Madrid 1 @ 1.45 → 500 TL                     │     │
│  │ • Galatasaray 1 @ 1.85 → 500 TL                     │     │
│  │                                                      │     │
│  │ Toplam stake: 1,500 TL                              │     │
│  │ Max kayıp: -1,500 TL                                │     │
│  │ EV: +543 TL  (ROI %36)                              │     │
│  │ Varyans: ORTA                                        │     │
│  │                                                      │     │
│  │ [Bu seçeneği yat]                                    │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐     │
│  │ ⓑ KOMBİN K=3                                        │     │
│  │ ────────────────────────────────                    │     │
│  │ Liv 1 × RM 1 × GS 1 @ 4.16                          │     │
│  │ Stake: 500 TL                                        │     │
│  │ Max kazanç: +1,422 TL net   Max kayıp: -500          │     │
│  │ EV: +403 TL  (ROI %81 — yüksek)                     │     │
│  │ Varyans: ÇOK YÜKSEK (%53 ihtimal full miss)          │     │
│  │                                                      │     │
│  │ ⚠️ Korelasyon riski: 3 maç bağımsız değil           │     │
│  │ ⚠️ Adrenalin yüksek ama EV daha düşük                │     │
│  │                                                      │     │
│  │ [Yine de yat]                                        │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐     │
│  │ ⓒ SİSTEM 2/3 ⭐ ÖNERİ                                │     │
│  │ ────────────────────────────────                    │     │
│  │ 3 maç, en az 2'si tutsun                             │     │
│  │ 3 farklı 2'li kupon × 500 TL = 1,500 TL toplam       │     │
│  │                                                      │     │
│  │ Senaryolar:                                          │     │
│  │  3 tut → 3 kupon kazanır  → +2,400 TL  (%47)         │     │
│  │  2 tut → 1 kupon kazanır  → +250 TL    (%36)         │     │
│  │  1 tut → 0 kupon           → -1,500    (%14)         │     │
│  │  0 tut → 0 kupon           → -1,500    (%3)          │     │
│  │                                                      │     │
│  │ EV: +783 TL  (ROI %52) ⭐ EN YÜKSEK                  │     │
│  │ Varyans: DÜŞÜK (en az 2 tutsa kayıp olmaz!)          │     │
│  │                                                      │     │
│  │ [Bu seçeneği yat]                                    │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                              │
│  🤖 AI TRADER ÖNERİSİ: Seçenek C (Sistem 2/3)                │
│    Hem en yüksek EV hem en düşük varyans. Profile uygun.      │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

### EKRAN 4: SEZON PLANI — "Bu Sezon Neredeyiz?"

```
┌──────────────────────────────────────────────────────────────┐
│  📅  SEZON 2026-27   Hafta 4 / 38                            │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  📊 GENEL DURUM                                               │
│  Bankroll:   10,000 → 11,250 TL   (+%12.5)                   │
│  Hit rate:   13/18 = %72                                      │
│  ROI:        +%12.5 (gross), +%11.2 (net vergi sonrası)      │
│  CLV ortalama: −%0.8 (yaklaşıyor, hedef 0+)                  │
│                                                              │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                  │
│  🗓️ SEZON HARITASI                                           │
│                                                              │
│  H1-H8  (sezon başı):       ✓ Burada       hit %78 [STABIL]  │
│  H9     (devre arası başı): ⏳ Sonraki    PAS önerilir       │
│  H10-18 (devre arası riski): 🟡 Uyarı       sadece konsensüs │
│  H19-27 (sezon ortası 2):   🟢 Aktif        normal düzen     │
│  H28-38 (sezon sonu):       🟢 Aktif        yüksek güven     │
│                                                              │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                  │
│  📈 MODEL PERFORMANSI                                         │
│  ┌──────────────────┬─────┬───────┬────────┐                 │
│  │ Model            │ Pick│ Hit % │ ROI    │                 │
│  ├──────────────────┼─────┼───────┼────────┤                 │
│  │ TRIVOX           │  6  │  83%  │ +%24   │ ⭐ Lider        │
│  │ DUOVOX           │  8  │  75%  │ +%9    │                 │
│  │ MONOVOX-E0       │  4  │  50%  │ -%3    │ ⚠ Düşüş        │
│  └──────────────────┴─────┴───────┴────────┘                 │
│                                                              │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                  │
│  💡 SEZON ÖNERİLERİ                                           │
│  • MONOVOX-E0 son 3 hafta zayıf → ağırlığı azalt              │
│  • TRIVOX Q5+a2 stratejisi mükemmel ilerliyor                 │
│  • Devre arası 4 hafta sonra geliyor → bankroll'u koru       │
│                                                              │
│  [Detaylı Sezon Raporu] [Strateji Ayarla]                    │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

### EKRAN 5: GEÇMİŞ + ÖĞRENME

```
┌──────────────────────────────────────────────────────────────┐
│  📚  GEÇMİŞ KAYITLAR                                          │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Filtrele: [Tümü ▾] [Bu Ay ▾] [TRIVOX ▾]                     │
│                                                              │
│  📅 24 Mayıs 2026                                             │
│  ┌────────────────────────────────────────────────────┐      │
│  │ ✓ Liverpool 1 @ 1.55  500 TL → +275 TL net         │      │
│  │   MONOVOX-E0 + DUOVOX konsensüs, Q5+a2              │      │
│  │   [Pick detayı] [Sonradan ne gördüm?]               │      │
│  └────────────────────────────────────────────────────┘      │
│                                                              │
│  📅 23 Mayıs                                                  │
│  ┌────────────────────────────────────────────────────┐      │
│  │ ✗ Galatasaray 1 @ 1.85  500 TL → -500 TL           │      │
│  │   TRIVOX Q5, agree=2 ama hatalı                    │      │
│  │   AI yorum: "Kart anomaly sinyali zayıftı, dikkat   │      │
│  │   ettim ama bu yön drift'ti."                       │      │
│  │   Öğrenme: GS kart sinyali ağırlığı %5 düşürüldü    │      │
│  └────────────────────────────────────────────────────┘      │
│                                                              │
│  📅 22 Mayıs                                                  │
│  ┌────────────────────────────────────────────────────┐      │
│  │ ⊘ Real Madrid 1 @ 1.45  ATLADIM                    │      │
│  │   Sebep: "Sezon başı şüpheli"                       │      │
│  │   Sonuç olsaydı: KAZANIRDIN +225 TL                 │      │
│  │   AI yorum: "Sezon başı Q5+a2 atlama hatası,        │      │
│  │   öneri güçlüydü. Sonraki maçlarda dikkat."         │      │
│  └────────────────────────────────────────────────────┘      │
│                                                              │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                  │
│  🧠 ÖĞRENME RAPORU (Aylık)                                    │
│                                                              │
│  Bu ay 8 atladığın pick: 6 kazanır mıydı (+1,200 TL kayıp)    │
│  En çok atladığın model: MONOVOX-E0 (3 kez)                  │
│  Pattern: "Sezon başı şüphecilik" — bu kademeli azalmalı     │
│                                                              │
│  AI Trader: "İlk 4 hafta atlama eğilimin var. Live shadow    │
│  bu hafta için pick'lerin tüm tutmuş. Güvenmeye başlayabilir│
│  miyiz?"                                                     │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 3) TELEGRAM BOT — Hızlı İletişim

```
🤖 AI Trader Bot
─────────────────────────────────────
Pazartesi 09:00 (otomatik)

🌅 Günaydın Ferhan!

Bu hafta için 4 öneri var:
⚡ 1 ULTRA-CONSENSUS
🟢 2 ALL-IN
🟡 1 STANDART

En güçlü pick: Liverpool 1 @ 1.55
2 model konsensüsü, Q5+agree2, sample 19 → %84 hit beklenir.

🎯 Strateji önerim: Sistem 2/3
   3 ALL-IN için varyansı düşür, EV en yüksek.

[Detaylı bak] [Pick'lere git] [Atla]

─────────────────────────────────────
Hafta sonu (otomatik)

🎉 Hafta sonucu:
✓ Liverpool 1 - 0 Tottenham (kazandı)
✓ Real Madrid 3 - 0 Betis (kazandı)
✗ Galatasaray 1 - 1 FB (beraberlik)

Sistem 2/3: 2 doğru, 1 yanlış
Kazanç: +850 TL net
Bankroll: 12,100 → 12,950 TL (+%7)

[Detaylı rapor] [Pazartesi planı]
```

---

## 4) VOICE — Telefonla Konuşma (Q3+)

**Akış:**
```
Trader: "Hey AI Trader, bu hafta ne öneriyorsun?"
AI: "4 öneri var. En güçlü Liverpool 1. Sistem 2/3 strateji öneriyorum,
     beklenen kazanç 783 TL net. Detayı yollayım mı?"
Trader: "Liverpool oranı kaç?"
AI: "1.55, opening 1.62'den düştü. Sharp money Liverpool yönünde."
Trader: "Tamam Liverpool yatır, 500 TL"
AI: "iddaa.com'a yönlendiriyorum, kupon hazır. Onaylıyor musun?"
Trader: "Evet"
AI: "Yatırıldı, log'a kaydedildi. İyi şanslar."
```

**Teknoloji:** Web Speech API + Telegram voice messages (Whisper API)

---

## 5) TEKNOLOJİ STACK

| Katman | Teknoloji | Sebep |
|---|---|---|
| Backend API | **FastAPI** (Python) | Async, hızlı, mevcut Python kodu ile uyumlu |
| Frontend Web | **Next.js 14 + TypeScript** | Modern, hızlı, SSR + edge runtime |
| Mobile | **PWA (Progressive Web App)** | Native app gerekmez, App Store onayı yok |
| Database | **PostgreSQL** | SQLite'tan upgrade (concurrent users) |
| Cache | **Redis** | Live odds + prediction cache |
| Realtime | **WebSocket (Socket.io)** | Odds + push notification |
| Auth | **NextAuth + JWT** | Simple, secure |
| Bot | **Telegram Bot API** | En yaygın Türk trader kanalı |
| Voice | **Web Speech API + Whisper** | Browser native + AI transcription |
| Notification | **Telegram + Email (Postmark)** | Multi-kanal |
| Charts | **Recharts + D3.js** | Interactive visualization |
| Styling | **Tailwind CSS + Shadcn/ui** | Modern, hızlı, polished |
| Monitoring | **Vercel Analytics + Sentry** | Frontend errors + perf |
| Deployment | **Vercel (frontend) + Railway/Fly (backend)** | Modern serverless |

---

## 6) MOBİL-İLK YAKLAŞIM

Trader yolda, restoranda, evde — her yerden hızlı karar alır. UI **mobile first** tasarlanır:

- **Tek elle kullanım** (büyük butonlar)
- **Swipe gesture'ları** (sola: atla, sağa: yatır)
- **Bottom navigation** (5 tab: Hafta / Geçmiş / Sezon / Profil / Sohbet)
- **Bildirim** (Telegram + push notification)
- **Offline cache** (son haftaya bağlı kalmadan görüntülenebilir)

---

## 7) AI TRADER SOHBET ARAYÜZÜ

Kullanıcı her ekranda **çat penceresini** açabilir. Orchestrator agent ile sohbet.

```
👤 Sen: Liverpool pick'i neden ALL-IN?

🤖 AI: Üç ana sebep:
  1. 2 model (MONOVOX-E0 + DUOVOX) Q5 ile aynı yönde
  2. 4 sinyal de Liverpool teyit (anomaly + DC + xG + form)
  3. Tottenham 3 anahtar oyuncu sakat + CL maçı sonrası

  Tarihsel: Q5+agree2 picks 16/19 hit (%84). Bu profile uygun.

  [Daha derin analiz] [Stratejiyi değiştir]

👤 Sen: 2/3 sistem ile K=1 spread'i kıyasla

🤖 AI: [tablo gösterir]
  • 2/3 sistem: EV +783, Varyans DÜŞÜK, Max kayıp riski %17
  • K=1 spread: EV +543, Varyans ORTA, Max kayıp riski %3

  Hangisi senin için daha rahat?
  - Daha yüksek EV → 2/3
  - Daha az toplu kayıp → K=1 spread

  Tercihin?

👤 Sen: 2/3 sistemi yatır

🤖 AI: ✓ 3 kupon hazırlandı:
  • Liverpool 1 + Real Madrid 1 @ 2.25 → 500 TL
  • Liverpool 1 + Galatasaray 1 @ 2.87 → 500 TL
  • Real Madrid 1 + Galatasaray 1 @ 2.68 → 500 TL

  iddaa.com'a yönlendireyim mi?

  [Evet, yönlendir] [Hayır, manuel yapacağım]
```

---

## 8) UI INKREMENTAL İNŞA

### Faz 1: Minimum Viable UI (4-6 hafta)
**Sadece web (PC) — temel:**
- Hafta Dashboard ekranı
- Pick detay ekranı
- Telegram bot temel bildirim

**Çıktı:** Tek kullanıcı (sen) için çalışan basit web app

### Faz 2: Mobile + Sohbet (Hafta 7-12)
- PWA (mobile uyumlu)
- AI Trader sohbet (Claude API)
- Geçmiş + öğrenme ekranı

### Faz 3: Voice + Multi-User (Hafta 13-20)
- Voice komut entegrasyonu
- Multi-trader auth + profiles
- Sezon planı ekranı

### Faz 4: Production polish (Hafta 21+)
- Animasyonlar, micro-interactions
- A/B testing
- Onboarding flow
- Beta kullanıcı geri bildirimi

---

## 9) UI DESIGN İLKELERİ — Modern Trader Hissi

### Renk Paleti
- **Background:** Slate-900 (koyu) / Slate-50 (açık) — modern, profesyonel
- **Primary:** Emerald-500 (yeşil — kazanç, onay)
- **Danger:** Rose-500 (kırmızı — uyarı, kayıp)
- **Accent:** Amber-400 (sarı — dikkat, orta-risk)
- **Neutral:** Slate-400 (gri — secondary text)

### Tipografi
- **Headlines:** Inter Bold (modern, okunabilir)
- **Body:** Inter Regular
- **Numbers:** JetBrains Mono (oranlar, miktarlar)

### Bileşen Stili
- **Card:** Soft shadow + rounded-2xl + backdrop blur
- **Button:** Gradient + hover lift
- **Charts:** Smooth animations + interactive tooltips
- **Badge:** Quintile renkleri (Q5 = emerald, Q1 = rose)

### İlham
- Linear (clean, fast)
- Stripe Dashboard (data-rich)
- Robinhood (mobile-first finance)
- Notion (modular flexibility)

---

## 10) UI ÖZ-CÜMLE

> **"Trader telefonunu açtığında, AI Trader 5 saniyede 'bu hafta ne oynamalı' sorusuna cevap verir. Her pick'in arkasında şeffaf 'neden' var. Risk uyarısı zamanında gelir. Geçmiş kararlar trader'ı eğitir. Tüm bu hizmetler mobile, web, Telegram ve sesle erişilebilir."**

**UI bu vizyonun yüzüdür. Modeller motor, ama trader UI ile temas eder.**

---

## 11) BU HAFTA UI İÇİN

### Yapılacak (öncelik düşük, Q1 sonrası)
- Bugün sadece kavramsal mockup (bu doküman)
- Inşa 4-6 hafta sonra başlar (model ve data önce)

### Erken Mockup
Yeni 19K Kapı 0 smoke test bittikten sonra:
1. Streamlit ile **Faz 1 UI mockup** (1-2 gün)
   - Mevcut TRIVOX/DUOVOX çıktısını web'de göster
   - Hafta dashboard ekranı
2. Mockup üzerinde iterasyon

Bu, gerçek Next.js inşaatından **çok daha hızlı** ve trader deneyimi prototip görmemizi sağlar.
