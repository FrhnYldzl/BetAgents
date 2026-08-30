"""
🤖 AGENT LİGİ — profil-tabanlı çoklu ajan motoru
================================================
Üç ajan, AYNI para (1.000 TL), AYNI dönem (1 ay), FARKLI karakter:

  🛡 TEMKİNLİ — düşük risk. Sadece kanıtla pozitif/başabaş pazarlar,
                TEK öncelik, dar oran tavanı, erken PAS.
  📋 MEMUR    — orta risk. Aynı kanıt seti + biraz gevşek eşikler,
                ALT 2.5'e izin, orta oran tavanı.
  🎯 AVCI     — risk sever ama KAZANMA odaklı. SHARP (oran hareketi)
                önceliği, yüksek oran bandı (1.30+), geniş kombine tavanı.
                KG_VAR yine yasak (kanıt: -%22.5 — risk almak ayrı,
                bilerek kaybetmek ayrı).

Ortak kanıt tabanı (227 karar bahis, 2026-07):
  KG_YOK %80/+1.3 · UST_25 %77/+0.4 · GUCLU_FAV %79/-1.8 · KG_VAR %60/-22.5
  1-2 ayak 10/10 kazanç vs 3 ayak %41/-27.2

Worker: agents.run_all() — her profil kendi kasasında kupon kurar.
Settle/recompute: auto_settle zaten TÜM portföyleri dolaşıyor.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import db
from paper_engine import PaperEngine

INITIAL = 1000.0
TARGET_PCT = 1.50            # hepsi için 1.000 → 2.500 (adil kıyas)

PROFILES: dict[str, dict] = {
    "TEMKINLI_V1": {
        "name": "TEMKİNLİ (düşük risk)",
        "stop_pct": -0.15,
        "markets": {"KG_YOK", "UST_25", "ALT_25"},
        "fav_min": 0.68,
        "min_mp": 0.63, "min_odds": 1.18,
        "combo_cap": 2.60, "max_daily": 2, "max_open": 4,
        "max_tek": 1, "loss_streak": 3,
        "tek_stake": 0.05, "k3_stake": 0.04,
        "sort": "safety",                   # model_prob desc
    },
    "MEMUR_V1": {
        "name": "MEMUR (orta risk)",
        "stop_pct": -0.20,
        "markets": {"KG_YOK", "UST_25", "ALT_25"},
        "fav_min": 0.66,
        "min_mp": 0.62, "min_odds": 1.22,
        "combo_cap": 3.20, "max_daily": 2, "max_open": 5,
        "max_tek": 1, "loss_streak": 4,
        "tek_stake": 0.05, "k3_stake": 0.04,
        "sort": "score",                    # signal_score desc
    },
    "AVCI_V1": {
        "name": "AVCI (risk sever, kazanma odaklı)",
        "stop_pct": -0.25,
        "markets": {"KG_YOK", "UST_25", "ALT_25"},
        "fav_min": 0.58,
        "min_mp": 0.55, "min_odds": 1.30,   # yüksek oran bandı (1.35-1.55 en az kötüydü)
        "combo_cap": 4.50, "max_daily": 3, "max_open": 6,
        "max_tek": 2, "loss_streak": 5,
        "tek_stake": 0.06, "k3_stake": 0.05,
        "sort": "hunt",                     # SHARP > edge > oran
    },
    # ── MODEL-AJANLARI: bağımsız Poisson gol modeli (independent_model) ──
    "HOCA_V1": {
        # ÇİFT-ONAY hipotezi: model + piyasa AYNI fikirdeyse oyna.
        # Backtest dersi: modelin doğru kullanımı teyit, tahmin değil.
        "name": "HOCA (Poisson çift-onay)",
        "stop_pct": -0.15,
        "markets": {"KG_YOK", "UST_25", "ALT_25"},
        "fav_min": 0.58,
        "min_mp": 0.58, "min_odds": 1.20,
        "combo_cap": 2.80, "max_daily": 2, "max_open": 4,
        "max_tek": 1, "loss_streak": 3,
        "tek_stake": 0.05, "k3_stake": 0.04,
        "sort": "safety",
        "mode": "confirm", "confirm_max_dev": 0.10,
        "pas_tolerance_days": 10,
    },
    "SIMYACI_V1": {
        # DEĞER hipotezi (KONTROL DENEYİ): model piyasadan >= +6p yüksek
        # dediğinde oyna. Backtest -%8 dedi — canlı kontrol grubu; kazanırsa
        # hipotez ayağa kalkar, kaybederse kanıt pekişir. Küçük stake.
        "name": "SİMYACI (model-değer deneyi)",
        "stop_pct": -0.25,
        "markets": {"KG_YOK", "UST_25", "ALT_25"},
        "fav_min": 0.50,
        "min_mp": 0.50, "min_odds": 1.30,
        "combo_cap": 4.00, "max_daily": 2, "max_open": 4,
        "max_tek": 2, "loss_streak": 4,
        "tek_stake": 0.04, "k3_stake": 0.03,
        "sort": "value",
        "mode": "value", "value_min_edge": 0.03,
        "pas_tolerance_days": 10,
    },
    "ERKENKUS_V1": {
        # ⏰ ERKENKUŞ: Era-1 arşiv madenciliğinin (315 bahis) tek pozitif cebi:
        # kickoff'a >48 saat kala girilen bahisler %80 isabet / +1.3% flatROI
        # (n=44); 6-18sa penceresi -%26 (ölüm penceresi). Mantık: erken pazar
        # gevşek — kitap bilgiyi sindirmemiş; CLV>0 yakalama şansı en yüksek
        # (CLV>0 bahisler %73/-7.6 vs CLV<=0 %66/-14.5). Avrupa saat bandı
        # filtresi de kanıttan (12-24 UTC: -9%; Asya sabahı: -20%).
        "name": "ERKENKUŞ (erken pazar avcısı)",
        "stop_pct": -0.20,
        "markets": {"KG_YOK", "UST_25", "ALT_25"},
        "fav_min": 0.65,
        "min_mp": 0.62, "min_odds": 1.20,
        "combo_cap": 3.00, "max_daily": 2, "max_open": 5,
        "max_tek": 1, "loss_streak": 4,
        "tek_stake": 0.05, "k3_stake": 0.04,
        "sort": "safety",
        "min_lead_h": 40, "kick_hours": None,
        "pas_tolerance_days": 10,
    },
    "POPULER_V1": {
        # 🔥 POPÜLER: iddaa.com'un GERÇEK yazarları (contentv2 editors, track
        # record'lu) + KONSENSÜS (aynı pick'e ≥2 yazar = kalabalık bilgeliği
        # vekili) + SHARP teyidi (currentOdd < pick oranı = piyasa da o yöne).
        # Not: gerçek oynanma-%'si API'de yok; konsensüs+sharp en dürüst vekil.
        # Yazar seçimi hipotezi gereği KG dahil tüm desteklenen pazarlar açık.
        # 🗓 ERA-2 (23 Ağu 2026): sezon geldi → UYANDIRILDI. Off-season'daki
        # −%71 karnesi arşivde kaldı; yazar picks'i sezonda gerçek maçlara
        # dayanıyor, hipotez temiz sayfayla yeniden ölçülüyor.
        "name": "POPÜLER (yazar + konsensüs)",
        "stop_pct": -0.20,
        "markets": set(), "fav_min": 0.0,      # kendi aday kaynağı var
        "min_mp": 0.0, "min_odds": 1.25,
        "combo_cap": 3.50, "max_daily": 2, "max_open": 5,
        "max_tek": 2, "loss_streak": 4,
        "tek_stake": 0.05, "k3_stake": 0.04,
        "sort": "pop",
        "mode": "popular", "pop_min_score": 0.45,
    },
    "CESUR_V1": {
        # 🦁 CESUR: 30-gün piyasa taramasının (2.129 maç) ana bulgusu:
        # iddaa marjı ORTA-ORAN (1.60-2.00) favorilerde en ince: −%2.6
        # (sıfıra en yakın bölge, n=449). Tüm eski ajanlar en pahalı bölgede
        # (1.10-1.40: −14/−22) kümelenmişti. CESUR tek başına bu bölgeyi oynar.
        "name": "CESUR (orta-oran avcısı 1.60-2.00) v1.1",
        # v1.1 (canlı veri, 2026-08-14): ALT bacağı atıldı (%38/−39.5 sızıntı);
        # UST %75/+21.9 · KG_YOK %71/+16 · TEK +27.4 vs K3 −5.5 → TEK ağırlık.
        "stop_pct": -0.25,
        "markets": {"UST_25", "KG_YOK"},
        "fav_min": 0.50,
        "min_mp": 0.48, "min_odds": 1.60, "max_odds": 2.00,
        "combo_cap": 4.50, "max_daily": 3, "max_open": 6,
        "max_tek": 3, "loss_streak": 5,
        "tek_stake": 0.05, "k3_stake": 0.035,
        "sort": "score", "mode": "midband",
    },
    "TERS_V1": {
        # 🪞 TERS: yazar-tersleme hipotezi. Ampirik: yazar sinyallerinin
        # KARŞI tarafı %88 isabet / +73.8% ROI (n=16 — küçük örneklem!).
        # Kontrast: KURUCU'yu terslemek ÇALIŞMIYOR (−7.7%) → bu "her kötüyü
        # tersle" değil; yalnız marjdan-daha-kötü kaynak terslenir. Yazarlar
        # off-season'da −%76'ydı; sezonda değişebilir → küçük stake deneyi.
        # Yazar KG_VAR'ı terslerken KG_YOK oynanır vb. (hipotez bütünlüğü).
        "name": "TERS (yazar-tersleme deneyi)",
        "stop_pct": -0.25,
        "markets": set(), "fav_min": 0.0,
        "min_mp": 0.0, "min_odds": 1.30, "max_odds": 2.10,
        "combo_cap": 4.00, "max_daily": 2, "max_open": 5,
        "max_tek": 2, "loss_streak": 4,
        "tek_stake": 0.04, "k3_stake": 0.03,
        "sort": "score", "mode": "fade",
        "pas_tolerance_days": 10,
    },
    "KALECI_V1": {
        # 🧤 KALECİ: 546-bahis örüntü analizinin "kazanan kesişimi" — iki
        # dönemde de tekrarlayan ÜÇ örüntüyü tek gövdede birleştirir:
        #   1) KG_YOK tek pozitif pazar (+8.0%, %80 isabet; Era-1'de de +)
        #   2) 1.30-1.55 bandı = en dar fiyat uçurumu (−5p vs kısa oranda −17p)
        #   3) U-zamanlama: 6-40sa ÖLÜM PENCERESİ yasak (iki dönemde −26/−31);
        #      yalnız çok-erken (>40sa) veya geç (<6sa) girer.
        "name": "KALECİ (düşük-gol kesişim uzmanı)",
        "stop_pct": -0.20,
        "markets": {"KG_YOK", "ALT_25"},
        "fav_min": 1.01,                    # 1X2 kapalı — saf düşük-gol ailesi
        "min_mp": 0.60, "min_odds": 1.30, "max_odds": 1.55,
        "combo_cap": 3.20, "max_daily": 2, "max_open": 5,
        "max_tek": 2, "loss_streak": 4,
        "tek_stake": 0.05, "k3_stake": 0.04,
        "sort": "safety",
        "lead_forbid": (6, 40),             # ölüm penceresi yasağı
        "pas_tolerance_days": 10,
    },
    "JOKER_V1": {
        # 🃏 JOKER: KONTROL AJANI — deterministik-rastgele seçim (şans çizgisi).
        # Bilimsel amaç: her ajanın geçmesi gereken taban; JOKER'i yenemeyen
        # "beceri" iddia edemez. Beklenen ROI ≈ −marj (dürüst referans).
        "name": "JOKER (rastgele kontrol)",
        "stop_pct": -0.30,
        "markets": set(), "fav_min": 0.0,
        "min_mp": 0.0, "min_odds": 1.50, "max_odds": 2.20,
        "combo_cap": 5.00, "max_daily": 2, "max_open": 5,
        "max_tek": 2, "loss_streak": 99,
        "tek_stake": 0.03, "k3_stake": 0.025,
        "sort": "score", "mode": "joker",
    },
    "KONSEY_V1": {
        # 🏛 KONSEY: iç-Polymarket — 8 seçmen ajanın filtrelerini aynı maça
        # uygular; SERVET-AĞIRLIKLI oy (kasa/1000, 0.25-2.0 aralığı) + quorum
        # (≥3 seçmen) + aile-çeşitliliği (≥2 kaynak: motor/model/band) sağlayan
        # pick'leri oynar. Fayda VARSAYILMAZ: ligde yarışır, skor ölçer.
        "name": "KONSEY (ajan heyeti — iç-Polymarket)",
        "stop_pct": -0.20,
        "markets": set(), "fav_min": 0.0,
        "min_mp": 0.0, "min_odds": 1.18,
        "combo_cap": 3.50, "max_daily": 2, "max_open": 5,
        "max_tek": 2, "loss_streak": 4,
        "tek_stake": 0.05, "k3_stake": 0.04,
        "sort": "score",
        "mode": "council", "quorum": 3, "min_families": 2,
        "pas_tolerance_days": 10,
    },
    # ── 😴 SEZON AJANLARI: kayıtlı ama UYKUDA (Ağustos'ta aktive edilecek) ──
    # MODEL_REGISTRY'de 13 model var; iki amiral gemisi burada ajan olarak
    # açıldı ki UNUTULMASIN. dormant=True → kasa hazır, kupon OYNAMAZ.
    # Aktivasyon (Ağustos): dormant kaldır + lig eşleme (T1/E0/SP1...) +
    # model sinyal hattını bağla. Alt-modeller (MONOVOX/DUOVOX/BTTS-*/OU25-*)
    # aktivasyonda filtre/bacak olarak bunlara bağlanır.
    "TRIVOX_V1": {
        # 🏁 EMEKLİ (29 Ağu 2026) — GERİYE DÖNÜK TEST KARARI.
        # 2.884 Süper Lig maçı / 9 sezon (2017-2026, Pinnacle kapanış) motor
        # sinyalleriyle yeniden oynatıldı; her oran iddaa fiyatına çevrildi
        # (×0.880, marj 3.5% → 17.6%). SONUÇ: iddaa fiyatlarıyla TEK BİR
        # kârlı hücre yok. En iyi: 1X2 mp 0.55-0.62 → +0.04% (n=89) ve
        # dönemler arası işaret değiştiriyor (eğitim +6.5%, sınav −13.9%).
        # Ayrıca "halk büyükleri şişirir → terslesek" hipotezi de çürüdü:
        # büyükleri terslemek −31% ile −36%. Motorun Pinnacle fiyatlarında
        # ~+5% becerisi var, ama iddaa marjı onu tamamen yiyor.
        # Karar: T1 tek başına uzmanlık alanı değil; slot boşaltıldı.
        "name": "TRIVOX (emekli — T1'de kanıtlanmış edge yok)",
        "retired": True,
        "stop_pct": -0.15, "leagues": {"T1"},
        "markets": {"KG_YOK", "UST_25"}, "fav_min": 0.72,
        "min_mp": 0.66, "min_odds": 1.20,
        "combo_cap": 3.00, "max_daily": 2, "max_open": 4,
        "max_tek": 1, "loss_streak": 3,
        "tek_stake": 0.05, "k3_stake": 0.04, "sort": "safety",
    },
    "EUVOX_V1": {
        "name": "EUVOX (Avrupa uzmanı — SEZONDA, motor-v1)",
        "stop_pct": -0.15, "leagues": {"SP1", "I1", "F1", "D1", "E0"},
        "markets": {"KG_YOK", "UST_25", "ALT_25"}, "fav_min": 0.68,
        "min_mp": 0.64, "min_odds": 1.22,
        "combo_cap": 3.00, "max_daily": 2, "max_open": 4,
        "max_tek": 1, "loss_streak": 3,
        "tek_stake": 0.05, "k3_stake": 0.04, "sort": "safety",
    },
}

# Bağımsız model rating önbelleği (run_all içinde 1 kez kurulur)
_RATINGS = {"ts": None, "obj": None}


def _get_ratings():
    from datetime import datetime as _dt
    import independent_model as im
    now = _dt.utcnow()
    if _RATINGS["obj"] is not None and _RATINGS["ts"] is not None \
            and (now - _RATINGS["ts"]).total_seconds() < 600:
        return _RATINGS["obj"]
    _RATINGS["obj"] = im.build_current_ratings()
    _RATINGS["ts"] = now
    return _RATINGS["obj"]


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


# 🌉 AĞUSTOS'A KÖPRÜ MODU — sezon başlangıcına (10 Ağu aktivasyon) kadar:
#   • tüm ajanlarda stake ×0.5 (off-season gürültüsüne para yakma)
#   • saat bandı zorunlu 12-24 UTC (Asya-sabah −%19.7 / gece −%16.5 kanıtı)
# 2026-08-10'da OTOMATİK kalkar (tarih bazlı — unutma riski yok).
BRIDGE_UNTIL = "2026-08-10"


def bridge_active() -> bool:
    return _now()[:10] < BRIDGE_UNTIL


def ensure_portfolio(pid: str) -> None:
    prof = PROFILES[pid]
    conn = db.connect()
    try:
        now = _now()
        conn.execute(
            """
            INSERT OR IGNORE INTO paper_portfolio
              (portfolio_id, name, initial_bankroll, current_bankroll,
               peak_bankroll, total_bets, total_wins, total_coupons,
               won_coupons, total_staked, total_return, status,
               strategy_version, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 'active', ?, ?, ?, ?)
            """,
            (pid, prof["name"], INITIAL, INITIAL, INITIAL,
             pid.lower(), f"Agent ligi — {prof['name']}", now, now))
        conn.commit()
        try:
            conn.execute(
                "UPDATE paper_portfolio SET period_start_bankroll=?, "
                "period_start_date=?, period_status='active', "
                "monthly_target_pct=?, stop_loss_pct=?, locked_profit=0, "
                "completed_periods=0 WHERE portfolio_id=? "
                "AND period_start_date IS NULL",
                (INITIAL, now, TARGET_PCT, prof["stop_pct"], pid))
            conn.commit()
        except Exception:
            conn.rollback()
    finally:
        conn.close()


def _mbs(m: dict) -> int:
    v = m.get("mbs")
    try:
        return int(v) if v else 3
    except Exception:
        return 3


def _loss_streak(conn, pid: str, n: int) -> bool:
    """n ardışık kayıp → PAS. PERMALOCK FIX: mola 48 saat — süre dolunca
    ajan tekrar oynayabilir (eskisi süresiz kilitliyordu: hiç oynamayınca
    son n hep 'lost' kalır → sonsuz PAS)."""
    from datetime import datetime as _dt
    # 🗓 ERA: önceki eranın kayıpları yeni erada mola tetikleyemez
    era = era_start(conn, pid)
    rows = conn.execute(
        "SELECT status, settled_at FROM paper_coupons WHERE portfolio_id=? "
        "AND status IN ('won','lost')" + (" AND created_at >= ?" if era else "")
        + " ORDER BY settled_at DESC LIMIT ?",
        (pid,) + ((era,) if era else ()) + (n,)).fetchall()
    if len(rows) < n or not all(r[0] == "lost" for r in rows):
        return False
    try:
        last = _dt.fromisoformat(str(rows[0][1])[:19])
        return (_dt.utcnow() - last).total_seconds() < 48 * 3600
    except Exception:
        return False


# ════════════════════════════════════════════════════════════════
# 📜 SÖZLEŞME LİGİ — motivasyon: ihtar → kadro dışı → kasa lidere
# ════════════════════════════════════════════════════════════════
# Haftalık değerlendirme (lig saati: PAPER_V1.last_review):
#   A) PERFORMANS: ≥5 karar kuponlular arasında en kötü PnL% (ve <0) → ⚠️ ihtar
#   B) PASİFLİK : son 7 günde 0 kupon kuran saha ajanı → ⚠️ ihtar
#   C) ROTA     : 14. günden sonra PnL% ≤ −10 olan herkes → ⚠️ ihtar
#   2 ihtar → 🚫 KADRO DIŞI: oynayamaz, KALAN KASASI LİG LİDERİNE DEVREDİLİR.
# Yeni ajanlara 5 gün hoşgörü. Her karar journal'a yazılır.

def ensure_contract_columns(conn) -> None:
    for col, typ in (("ihtar_count", "INTEGER"), ("benched", "INTEGER"),
                     ("last_review", "TEXT"), ("era_start", "TEXT"),
                     ("era_no", "INTEGER")):
        try:
            conn.execute(f"ALTER TABLE paper_portfolio ADD COLUMN {col} {typ}")
            conn.commit()
        except Exception:
            conn.rollback()


def _is_benched(conn, pid: str) -> bool:
    try:
        r = conn.execute(
            "SELECT benched FROM paper_portfolio WHERE portfolio_id=?",
            (pid,)).fetchone()
        return bool(r and r[0])
    except Exception:
        # PG: patlayan statement transaction'ı abort eder — rollback ŞART,
        # yoksa aynı bağlantıdaki SONRAKİ tüm sorgular da ölür
        # ("current transaction is aborted"). Canlıdaki sessiz ajan
        # arızasının kök nedeni buydu.
        try:
            conn.rollback()
        except Exception:
            pass
        return False


def _journal(conn, pid: str, title: str, content: str) -> None:
    import uuid
    try:
        conn.execute(
            "INSERT INTO paper_journal (journal_id, portfolio_id, entry_date, "
            "entry_type, title, content, created_at) VALUES (?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), pid, _now()[:10], "LESSON", title, content, _now()))
    except Exception:
        pass


def review_league() -> None:
    """Haftalık sözleşme değerlendirmesi. Lig saati dolmadıysa sessizce çıkar."""
    from datetime import datetime as _dt
    conn = db.connect()
    try:
        ensure_contract_columns(conn)
        clock = conn.execute(
            "SELECT last_review FROM paper_portfolio WHERE portfolio_id='PAPER_V1'"
        ).fetchone()
        clock = clock[0] if clock else None
        now = _dt.utcnow()
        if not clock:
            conn.execute("UPDATE paper_portfolio SET last_review=? "
                         "WHERE portfolio_id='PAPER_V1'", (now.isoformat(),))
            conn.commit()
            print("[LIG] sozlesme saati baslatildi — ilk degerlendirme 7 gun sonra")
            return
        try:
            if (now - _dt.fromisoformat(str(clock)[:19])).days < 7:
                return
        except Exception:
            return

        # 🌉 SEZON ÖNCESİ AF: köprü modunda ihtar DAĞITILMAZ ve mevcut ihtarlar
        # silinir. Gerekçe: köprü bilerek az oynatıyor (stake ×0.5, dar saat
        # bandı) — aynı anda pasiflik/performans cezası kesmek çelişkidir.
        # Gerçek sözleşme baskısı sezonla (10 Ağu sonrası) başlar.
        if bridge_active():
            conn.execute("UPDATE paper_portfolio SET ihtar_count=0 "
                         "WHERE COALESCE(benched,0)=0")
            conn.execute("UPDATE paper_portfolio SET last_review=? "
                         "WHERE portfolio_id='PAPER_V1'", (now.isoformat(),))
            conn.commit()
            print("[LIG] 🌉 sezon öncesi af — ihtarlar sıfırlandı, "
                  "değerlendirme sezona ertelendi")
            return

        from datetime import timedelta as _td
        print("[LIG] 📜 HAFTALIK SOZLESME DEGERLENDIRMESI")
        # KURUCU_V2 (Era-2) de yarışta — lig kuralları ona da işler
        field = [p for p in list(PROFILES) + ["KURUCU_V2"]
                 if not PROFILES.get(p, {}).get("dormant")
                 and not PROFILES.get(p, {}).get("retired")
                 and not _is_benched(conn, p)]
        stats = []
        for pid in field:
            row = conn.execute(
                "SELECT current_bankroll, initial_bankroll, created_at, "
                "COALESCE(ihtar_count,0) FROM paper_portfolio "
                "WHERE portfolio_id=?", (pid,)).fetchone()
            if not row:
                continue
            cur, init, created, ihtar = row[0] or 0, row[1] or 1, row[2], row[3]
            try:
                age_d = (now - _dt.fromisoformat(str(created)[:19])).days
            except Exception:
                age_d = 99
            n_dec = conn.execute(
                "SELECT COUNT(*) FROM paper_coupons WHERE portfolio_id=? "
                "AND status IN ('won','lost')", (pid,)).fetchone()[0]
            from datetime import timedelta as _td
            # Hipotez ajanlarına (HOCA/SIMYACI/ERKENKUS) geniş pasiflik
            # penceresi: PAS onların meşru davranışı (pas_tolerance_days).
            tol = PROFILES.get(pid, {}).get("pas_tolerance_days", 7)
            n_win = conn.execute(
                "SELECT COUNT(*) FROM paper_coupons WHERE portfolio_id=? "
                "AND created_at > ?",
                (pid, (now - _td(days=tol)).isoformat())).fetchone()[0]
            stats.append({"pid": pid, "cur": cur, "init": init,
                          "pnl_pct": (cur - init) / init * 100,
                          "age": age_d, "n_dec": n_dec, "n_win": n_win,
                          "tol": tol, "ihtar": ihtar})

        new_ihtar: dict[str, list] = {}
        # A) performans: en kötü negatif (n_dec>=5)
        perf = [s for s in stats if s["n_dec"] >= 5 and s["pnl_pct"] < 0
                and s["age"] >= 5]
        if perf:
            worst = min(perf, key=lambda s: s["pnl_pct"])
            new_ihtar.setdefault(worst["pid"], []).append(
                f"performans (lig sonuncusu, {worst['pnl_pct']:+.1f}%)")
        # B) pasiflik — 🩺 ÖLÇÜM ŞARTI: ceza YALNIZCA teşhis "oynayabilirdin"
        # dediğinde. Sessizliğin nedeni teknik tıkanıklık (🔴), meşru PAS (⚪),
        # limit/dönem/uyku ise ajan suçlu değildir; sistem suçludur.
        # (2026-08 dersi: scipy çöküşü 9 ajanı haksız kadro dışı bıraktı.)
        try:
            conn.execute("CREATE TABLE IF NOT EXISTS agent_diag "
                         "(ts TEXT, pid TEXT, status TEXT, detail TEXT)")
            drows = conn.execute(
                "SELECT pid, status FROM agent_diag WHERE ts > ?",
                ((now - _td(days=7)).isoformat(),)).fetchall()
        except Exception:
            conn.rollback()
            drows = []
        could_play = {r[0] for r in drows if "OYNAYAB" in (r[1] or "")}
        diag_seen = {r[0] for r in drows}
        for s in stats:
            if s["age"] >= s["tol"] and s["n_win"] == 0:
                if diag_seen and s["pid"] not in could_play:
                    print(f"[LIG] 🩺 {s['pid']} pasiflik ihtarı DÜŞTÜ — "
                          f"teşhis: oynayabileceği pozisyon yoktu")
                    continue
                new_ihtar.setdefault(s["pid"], []).append(
                    f"pasiflik ({s['tol']} günde 0 kupon)")
        # C) rota: 14+ gün ve <= -10%
        for s in stats:
            if s["age"] >= 14 and s["pnl_pct"] <= -10:
                new_ihtar.setdefault(s["pid"], []).append(
                    f"rota ({s['pnl_pct']:+.1f}% hedeften uzak)")

        leader = max(stats, key=lambda s: s["pnl_pct"]) if stats else None
        for pid, reasons in new_ihtar.items():
            s = next(x for x in stats if x["pid"] == pid)
            total = s["ihtar"] + 1          # değerlendirme başına max +1 ihtar
            reason_txt = "; ".join(reasons)
            if total >= 2 and leader and leader["pid"] != pid:
                # 🚫 KADRO DIŞI + kasa devri (initial üzerinden — recompute uyumlu)
                devir = max(0.0, s["cur"])
                conn.execute(
                    "UPDATE paper_portfolio SET benched=1, ihtar_count=?, "
                    "updated_at=? WHERE portfolio_id=?",
                    (total, now.isoformat(), pid))
                conn.execute(
                    "UPDATE paper_portfolio SET initial_bankroll="
                    "initial_bankroll - ?, updated_at=? WHERE portfolio_id=?",
                    (devir, now.isoformat(), pid))
                conn.execute(
                    "UPDATE paper_portfolio SET initial_bankroll="
                    "initial_bankroll + ?, updated_at=? WHERE portfolio_id=?",
                    (devir, now.isoformat(), leader["pid"]))
                _journal(conn, pid, "🚫 KADRO DIŞI",
                         f"2. ihtar ({reason_txt}). Kalan kasa "
                         f"{devir:.0f} TL lig lideri {leader['pid']}'e devredildi.")
                _journal(conn, leader["pid"], "💰 KASA DEVRİ",
                         f"Kadro dışı {pid}'den {devir:.0f} TL devraldı (lig lideri).")
                print(f"[LIG] 🚫 {pid} KADRO DISI ({reason_txt}) -> "
                      f"{devir:.0f} TL {leader['pid']}'e")
            else:
                conn.execute(
                    "UPDATE paper_portfolio SET ihtar_count=?, updated_at=? "
                    "WHERE portfolio_id=?", (total, now.isoformat(), pid))
                _journal(conn, pid, f"⚠️ İHTAR {total}/2",
                         f"Sözleşme ihlali: {reason_txt}. Bir ihtar daha = "
                         f"kadro dışı + kasa lidere devir.")
                print(f"[LIG] ⚠️ {pid} ihtar {total}/2 ({reason_txt})")

        conn.execute("UPDATE paper_portfolio SET last_review=? "
                     "WHERE portfolio_id='PAPER_V1'", (now.isoformat(),))
        conn.commit()
        # Devir sonrası sayaçları senkronla
        try:
            from recompute_portfolio import recompute
            for s in stats:
                recompute(s["pid"], verbose=False)
        except Exception:
            pass
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════
# 🔥 POPÜLER aday kaynağı — yazar pick'leri + konsensüs + sharp
# ════════════════════════════════════════════════════════════════

def _vig_strip(odds_list):
    inv = [1.0 / o for o in odds_list if o and o > 1.0]
    if len(inv) != len(odds_list) or not inv:
        return None
    t = sum(inv)
    return [x / t for x in inv]


def _popular_candidates(prof: dict, tag: str) -> list[dict]:
    from datetime import datetime as _dt, timedelta as _td
    import json as _json

    # 1) Taze ingest (2 saatte bir; iddaa contentv2 — Railway'den erişilebilir)
    try:
        scr = str(THIS_DIR / "scrapers")
        if scr not in sys.path:
            sys.path.insert(0, scr)
        conn = db.connect()
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tipster_picks ("
            "tipster_id TEXT, tipster_name TEXT, source TEXT, posted_at TEXT, "
            "kickoff_iso TEXT, home_team TEXT, away_team TEXT, market TEXT, "
            "selection TEXT, pick_odd REAL, stake_units REAL, confidence REAL, "
            "settled INTEGER, won INTEGER, inserted_at TEXT, raw_json TEXT)")
        conn.commit()
        last = conn.execute(
            "SELECT MAX(inserted_at) FROM tipster_picks").fetchone()[0]
        conn.close()
        stale = True
        if last:
            try:
                stale = (_dt.utcnow() - _dt.fromisoformat(str(last)[:19])) > _td(hours=2)
            except Exception:
                stale = True
        if stale:
            from iddaa_tipster_scraper import ingest_all_editors
            res = ingest_all_editors(delay=0.3)
            print(f"{tag} yazar taramasi: {res}")
    except Exception as e:
        print(f"{tag} yazar taramasi atlandi: {str(e)[:70]}")

    # 2) Bekleyen pick'ler + yazar kalitesi (Wilson alt sınırı)
    now19 = _now()[:19]
    conn = db.connect()
    try:
        pend = [dict(r) for r in conn.execute(
            "SELECT tipster_id, tipster_name, market, selection, pick_odd, "
            "kickoff_iso, raw_json, inserted_at FROM tipster_picks "
            "WHERE settled=0").fetchall()]
        qual_rows = conn.execute(
            "SELECT tipster_id, SUM(won), COUNT(*) FROM tipster_picks "
            "WHERE settled=1 GROUP BY tipster_id").fetchall()
    finally:
        conn.close()
    try:
        from iddaa_tipster_scraper import wilson_interval
    except Exception:
        def wilson_interval(w, n, z=1.96):
            return ((w / n) if n else 0.0, 1.0)
    quality = {}
    n_mature = 0
    for tid, w, n in qual_rows:
        w, n = int(w or 0), int(n or 0)
        quality[tid] = wilson_interval(w, n)[0] if n >= 10 else 0.42
        if n >= 10:
            n_mature += 1
    mature = n_mature >= 3   # ≥3 yazarın gerçek track-record'u oluşana dek KORUMA

    # 3) Pazar eşleme + eventId ile matches_v2 join + konsensüs gruplama
    def _map(mkt, sel):
        s = (sel or "").strip()
        if mkt == "1X2" and s in ("1", "X", "2", "0"):
            return ("1X2", "X" if s in ("X", "0") else s)
        if mkt in ("OU2.5", "OU2,5"):
            if "st" in s.lower():          # Üst/Ust
                return ("UST_25", "UST")
            if "lt" in s.lower():          # Alt
                return ("ALT_25", "ALT")
        if mkt == "BTTS":
            if s.lower().startswith("var"):
                return ("KG_VAR", "VAR")
            if s.lower().startswith("yok"):
                return ("KG_YOK", "YOK")
        return None

    ODDS_COL = {("1X2", "1"): "closing_1", ("1X2", "X"): "closing_X",
                ("1X2", "2"): "closing_2", ("UST_25", "UST"): "closing_over25",
                ("ALT_25", "ALT"): "closing_under25",
                ("KG_VAR", "VAR"): "closing_btts_yes",
                ("KG_YOK", "YOK"): "closing_btts_no"}

    groups: dict = {}
    for p in pend:
        ko = str(p.get("kickoff_iso") or "")[:19]
        if not ko or ko <= now19:
            continue
        mapped = _map(p.get("market"), p.get("selection"))
        if not mapped:
            continue
        try:
            raw = _json.loads(p.get("raw_json") or "{}")
        except Exception:
            raw = {}
        eid = raw.get("eventId")
        if not eid:
            continue
        key = (str(eid),) + mapped
        g = groups.setdefault(key, {"editors": set(), "sharp": [], "q": []})
        g["editors"].add(p.get("tipster_id"))
        g["q"].append(quality.get(p.get("tipster_id"), 0.42))
        odd, cur = raw.get("odd"), raw.get("currentOdd")
        if odd and cur:
            g["sharp"].append(1.0 if float(cur) < float(odd) else 0.0)

    conn = db.connect()
    picks: list[dict] = []
    try:
        for (eid, mkt, sel), g in groups.items():
            m = conn.execute(
                "SELECT * FROM matches_v2 WHERE external_id_iddaa=? "
                "AND is_settled=0 AND kickoff_utc > ?",
                (eid, now19)).fetchone()
            if m is None:
                continue
            m = dict(m)
            odds = m.get(ODDS_COL[(mkt, sel)]) or m.get(ODDS_COL[(mkt, sel)].lower())
            try:
                odds = float(odds)
            except (TypeError, ValueError):
                continue
            if odds < prof["min_odds"]:
                continue
            # vig'siz olasılık (dürüst model_prob)
            if mkt == "1X2":
                probs = _vig_strip([m.get("closing_1"), m.get("closing_X"),
                                    m.get("closing_2")])
                mp = probs[{"1": 0, "X": 1, "2": 2}[sel]] if probs else None
            elif mkt in ("UST_25", "ALT_25"):
                probs = _vig_strip([m.get("closing_over25"), m.get("closing_under25")])
                mp = probs[0 if mkt == "UST_25" else 1] if probs else None
            else:
                probs = _vig_strip([m.get("closing_btts_yes"), m.get("closing_btts_no")])
                mp = probs[0 if mkt == "KG_VAR" else 1] if probs else None
            if mp is None:
                mp = 1.0 / odds
            n_ed = len(g["editors"])
            best_q = max(g["q"]) if g["q"] else 0.42
            sharp = (sum(g["sharp"]) / len(g["sharp"])) if g["sharp"] else 0.0
            # 🌉 köprü: Avrupa saat bandı herkese
            if bridge_active():
                try:
                    if not (12 <= int(str(m.get("kickoff_utc"))[11:13]) < 24):
                        continue
                except Exception:
                    continue
            # KORUMA: karne olgunlaşmadan yalnız SHARP-teyitli pick oyna
            if not mature and sharp < 0.5:
                continue
            score = 0.45 * best_q + 0.30 * sharp + 0.25 * (1.0 if n_ed >= 2 else 0.4)
            if score < prof.get("pop_min_score", 0.45):
                continue
            picks.append({
                "market": mkt, "pick": sel, "odds": odds,
                "implied_prob": 1.0 / odds, "model_prob": mp,
                "edge": mp - 1.0 / odds,
                "signal_name": f"POP_{n_ed}Y" + ("_SHARP" if sharp >= 0.5 else ""),
                "signal_score": round(score, 3), "_match": m,
            })
    finally:
        conn.close()
    print(f"{tag} popüler aday: {len(groups)} grup -> {len(picks)} kural-geçen pick")
    return picks


def _midband_candidates(prof: dict, tag: str, matches: list[dict]) -> list[dict]:
    """🦁 CESUR aday kaynağı: 2-yollu pazarlarda 1.60-2.00 bandındaki tarafı
    vig'siz olasılığıyla değerlendir, maç başına EN OLASI adayı al. Sinyal
    motoru bu bandda yapısal olarak sessiz (eşikleri düşük-oran için) —
    bu yüzden kendi kaynağı var."""
    picks: list[dict] = []
    for m in matches:
        opts = []
        for pair, legs in (
            (("closing_over25", "closing_under25"),
             (("UST_25", "UST"), ("ALT_25", "ALT"))),
            (("closing_btts_yes", "closing_btts_no"),
             (("KG_VAR", "VAR"), ("KG_YOK", "YOK"))),
        ):
            try:
                o_a = float(m.get(pair[0]) or m.get(pair[0].lower()) or 0)
                o_b = float(m.get(pair[1]) or m.get(pair[1].lower()) or 0)
            except (TypeError, ValueError):
                continue
            probs = _vig_strip([o_a, o_b])
            if not probs:
                continue
            for (mkt, pick), o, mp in ((legs[0], o_a, probs[0]),
                                       (legs[1], o_b, probs[1])):
                if mkt == "KG_VAR":
                    continue          # kanıt yasağı CESUR'da da geçerli
                if mkt not in prof.get("markets", {mkt}):
                    continue          # v1.1: profil pazar seti (ALT atıldı)
                if prof["min_odds"] <= o <= prof.get("max_odds", 99) \
                        and mp >= prof["min_mp"]:
                    opts.append((mkt, pick, o, mp))
        if not opts:
            continue
        mkt, pick, o, mp = max(opts, key=lambda x: x[3])
        picks.append({
            "market": mkt, "pick": pick, "odds": o,
            "implied_prob": 1.0 / o, "model_prob": mp,
            "edge": mp - 1.0 / o, "signal_name": "MIDBAND",
            "signal_score": mp, "_match": m,
        })
    print(f"{tag} 🦁 orta-band aday: {len(picks)}")
    return picks


def _fade_candidates(prof: dict, tag: str) -> list[dict]:
    """🪞 TERS: iddaa yazarlarının BEKLEYEN 2-yollu pick'lerinin KARŞI tarafı.
    Aynı maçta yazarlar iki zıt taraftaysa çelişki → maç atlanır."""
    from datetime import datetime as _dt, timedelta as _td
    import json as _json
    # Yazar taraması taze mi (POPULER uykuda olsa da tersleme akışı canlı kalır)
    try:
        scr = str(THIS_DIR / "scrapers")
        if scr not in sys.path:
            sys.path.insert(0, scr)
        conn = db.connect()
        last = conn.execute("SELECT MAX(inserted_at) FROM tipster_picks").fetchone()[0]
        conn.close()
        stale = True
        if last:
            try:
                stale = (_dt.utcnow() - _dt.fromisoformat(str(last)[:19])) > _td(hours=2)
            except Exception:
                pass
        if stale:
            from iddaa_tipster_scraper import ingest_all_editors
            ingest_all_editors(delay=0.3)
    except Exception as e:
        print(f"{tag} yazar taramasi atlandi: {str(e)[:60]}")

    OPP = {("OU2.5", "u"): ("ALT_25", "ALT", "closing_under25"),
           ("OU2.5", "a"): ("UST_25", "UST", "closing_over25"),
           ("BTTS", "v"):  ("KG_YOK", "YOK", "closing_btts_no"),
           ("BTTS", "y"):  ("KG_VAR", "VAR", "closing_btts_yes")}
    now19 = _now()[:19]
    conn = db.connect()
    try:
        pend = [dict(r) for r in conn.execute(
            "SELECT market, selection, raw_json, kickoff_iso, tipster_id "
            "FROM tipster_picks WHERE settled=0").fetchall()]
        groups: dict = {}
        for pck in pend:
            ko = str(pck.get("kickoff_iso") or "")[:19]
            if not ko or ko <= now19:
                continue
            mkt = pck.get("market"); sel = (pck.get("selection") or "").lower()
            if mkt in ("OU2.5", "OU2,5"):
                side = "u" if ("st" in sel) else ("a" if "lt" in sel else None)
                key0 = ("OU2.5", side)
            elif mkt == "BTTS":
                side = "v" if sel.startswith("var") else ("y" if sel.startswith("yok") else None)
                key0 = ("BTTS", side)
            else:
                continue
            if not side or key0 not in OPP:
                continue
            try:
                eid = _json.loads(pck.get("raw_json") or "{}").get("eventId")
            except Exception:
                eid = None
            if not eid:
                continue
            g = groups.setdefault((str(eid), key0[0]), {})
            g.setdefault(side, set()).add(pck.get("tipster_id"))
        picks: list[dict] = []
        for (eid, fam), sides in groups.items():
            if len(sides) > 1:
                continue                      # yazarlar çelişiyor → atla
            side = next(iter(sides))
            n_y = len(sides[side])
            omkt, opick, ocol = OPP[(fam, side)]
            m = conn.execute(
                "SELECT * FROM matches_v2 WHERE external_id_iddaa=? "
                "AND is_settled=0 AND kickoff_utc > ?", (eid, now19)).fetchone()
            if m is None:
                continue
            m = dict(m)
            o = m.get(ocol) or m.get(ocol.lower())
            try:
                o = float(o)
            except (TypeError, ValueError):
                continue
            if not (prof["min_odds"] <= o <= prof.get("max_odds", 99)):
                continue
            pair = {"ALT_25": ("closing_over25", "closing_under25", 1),
                    "UST_25": ("closing_over25", "closing_under25", 0),
                    "KG_YOK": ("closing_btts_yes", "closing_btts_no", 1),
                    "KG_VAR": ("closing_btts_yes", "closing_btts_no", 0)}[omkt]
            probs = _vig_strip([m.get(pair[0]), m.get(pair[1])])
            mp = probs[pair[2]] if probs else 1.0 / o
            picks.append({
                "market": omkt, "pick": opick, "odds": o,
                "implied_prob": 1.0 / o, "model_prob": mp,
                "edge": mp - 1.0 / o,
                "signal_name": f"TERS_{n_y}Y", "signal_score": float(n_y),
                "_match": m,
            })
        print(f"{tag} 🪞 yazar-ters aday: {len(groups)} pick grubu -> {len(picks)}")
        return picks
    finally:
        conn.close()


def _joker_candidates(prof: dict, tag: str, matches: list[dict]) -> list[dict]:
    """🃏 Deterministik-rastgele kontrol seçimi: maç kimliğinden hash ile
    pazar seç (tekrarlanabilir — Date.now/random yok). Şans çizgisi üretir."""
    picks: list[dict] = []
    for m in matches:
        opts = []
        for mkt, pick, col in (("1X2", "1", "closing_1"), ("1X2", "2", "closing_2"),
                               ("UST_25", "UST", "closing_over25"),
                               ("ALT_25", "ALT", "closing_under25"),
                               ("KG_VAR", "VAR", "closing_btts_yes"),
                               ("KG_YOK", "YOK", "closing_btts_no")):
            o = m.get(col) or m.get(col.lower())
            try:
                o = float(o)
            except (TypeError, ValueError):
                continue
            if prof["min_odds"] <= o <= prof.get("max_odds", 99):
                opts.append((mkt, pick, o))
        if not opts:
            continue
        h = (int(m.get("match_id") or 0) * 2654435761) % (2 ** 32)
        mkt, pick, o = opts[h % len(opts)]
        picks.append({
            "market": mkt, "pick": pick, "odds": o,
            "implied_prob": 1.0 / o, "model_prob": 1.0 / o,
            "edge": 0.0, "signal_name": "JOKER",
            "signal_score": (h % 1000) / 1000.0, "_match": m,
        })
    print(f"{tag} 🃏 rastgele aday: {len(picks)}")
    return picks


def _engine_candidates(prof: dict, tag: str, matches: list[dict],
                       eng: PaperEngine) -> list[dict]:
    """Sinyal-motoru aday aşaması (profil filtreleriyle). build_coupons ve
    🏛 KONSEY oylaması aynı fonksiyonu kullanır."""
    mode = prof.get("mode")
    # Model modu (HOCA/SIMYACI): bağımsız Poisson gol modelini yükle
    ratings = None
    im = None
    if mode in ("confirm", "value"):
        # ⚠️ TEMBEL IMPORT: independent_model ağır bağımlılık taşır. Koşulsuz
        # import edilirse (eski hâli) motor ailesinin TAMAMI runtime'da
        # ModuleNotFoundError ile düşer — 2026-08 tıkanıklığının kök nedeni.
        try:
            ratings = _get_ratings()
            import independent_model as im  # noqa: F401 (sadece model modunda)
        except Exception as e:
            print(f"{tag} model yuklenemedi ({e}) -> PAS")
            return []
    _probs_cache: dict = {}

    picks: list[dict] = []
    lgs = prof.get("leagues")
    for m in matches:
        # 🏟 Lig-scope (TRIVOX=T1, EUVOX=Avrupa): yalnız kendi ligleri
        if lgs and (m.get("league_code") not in lgs):
            continue
        # ⏰ Zaman filtreleri (ERKENKUŞ): erken-giriş penceresi + saat bandı
        kh_eff = prof.get("kick_hours")   # saat kısıtı yalnız profil bazlı (30g veri global yasağı desteklemedi)
        if prof.get("min_lead_h") or kh_eff or prof.get("lead_forbid"):
            from datetime import datetime as _dt
            ko = str(m.get("kickoff_utc") or "")[:19]
            try:
                lead_h = (_dt.fromisoformat(ko) - _dt.utcnow()).total_seconds() / 3600
                ko_hour = int(ko[11:13])
            except Exception:
                continue
            if prof.get("min_lead_h") and lead_h < prof["min_lead_h"]:
                continue
            lf = prof.get("lead_forbid")
            if lf and lf[0] <= lead_h < lf[1]:   # 🧤 ölüm penceresi (6-40sa)
                continue
            if kh_eff and not (kh_eff[0] <= ko_hour < kh_eff[1]):
                continue
        try:
            sigs = eng.evaluate_match(m)
        except Exception:
            continue
        for s in sigs:
            s["_match"] = m
            mkt = s.get("market") or ""
            mp = s.get("model_prob") or 0
            if mkt == "KG_VAR":                    # tüm ajanlarda yasak (kanıt)
                continue
            if mkt == "1X2":
                if mp < prof["fav_min"]:
                    continue
            elif mkt not in prof["markets"]:
                continue
            if mp < prof["min_mp"] or (s.get("odds") or 0) < prof["min_odds"]:
                continue
            if prof.get("max_odds") and (s.get("odds") or 0) > prof["max_odds"]:
                continue
            # ── MODEL FİLTRESİ (HOCA=çift-onay · SIMYACI=değer) ──
            if ratings is not None:
                mid = m.get("match_id")
                if mid not in _probs_cache:
                    try:
                        _probs_cache[mid] = ratings.predict(m)
                    except Exception:
                        _probs_cache[mid] = None
                ip = im.model_prob_for(_probs_cache[mid], mkt, s.get("pick"))
                if ip is None:                      # ikinci görüş yoksa oynamaz
                    continue
                dev = ip - mp
                s["_dev"] = dev
                if mode == "confirm" and abs(dev) > prof["confirm_max_dev"]:
                    continue
                if mode == "value" and dev < prof["value_min_edge"]:
                    continue
            picks.append(s)

    return picks


# ════════════════════════════════════════════════════════════════
# 🏛 KONSEY — iç-Polymarket: ajan heyeti oylaması
# ════════════════════════════════════════════════════════════════
# Oy hakkı olan aileler (JOKER=şans, POPULER=uykuda, sezon ajanları hariç):
COUNCIL_VOTERS = {
    "TEMKINLI_V1": "motor", "MEMUR_V1": "motor", "AVCI_V1": "motor",
    "ERKENKUS_V1": "motor", "KALECI_V1": "motor",
    "HOCA_V1": "model", "SIMYACI_V1": "model",
    "CESUR_V1": "band", "TERS_V1": "fade",
}


def _council_candidates(prof: dict, tag: str, matches: list[dict],
                        eng: PaperEngine) -> list[dict]:
    """Her seçmen ajanın filtrelerini aynı maç havuzuna uygula, oyları
    SERVET-AĞIRLIKLI topla (Polymarket mantığı: kasası büyüyenin sözü ağır),
    quorum (≥3 seçmen) + aile-çeşitliliği (≥2 kaynak ailesi — yankı odası
    engeli) sağlayan pick'ler KURUL KARARI olur."""
    conn = db.connect()
    banks = {r[0]: (r[1] or 1000.0) for r in conn.execute(
        "SELECT portfolio_id, current_bankroll FROM paper_portfolio").fetchall()}
    conn.close()
    votes: dict = {}
    for vpid, fam in COUNCIL_VOTERS.items():
        vprof = PROFILES.get(vpid)
        if not vprof or vprof.get("dormant"):
            continue
        vtag = f"[KURUL·{vpid.split('_')[0]}]"
        try:
            if vprof.get("mode") == "midband":
                vp = _midband_candidates(vprof, vtag, matches)
            else:
                vp = _engine_candidates(vprof, vtag, matches, eng)
        except Exception:
            continue
        w = max(0.25, min(2.0, banks.get(vpid, 1000.0) / 1000.0))
        for x in vp:
            key = (x["_match"].get("match_id"), x["market"], x["pick"])
            v = votes.setdefault(key, {"w": 0.0, "voters": set(),
                                       "fams": set(), "s": x})
            v["w"] += w
            v["voters"].add(vpid)
            v["fams"].add(fam)
    picks: list[dict] = []
    for key, v in votes.items():
        if len(v["voters"]) >= prof.get("quorum", 3)                 and len(v["fams"]) >= prof.get("min_families", 2):
            x = dict(v["s"])
            x["signal_name"] = f"KURUL_{len(v['voters'])}oy"
            x["signal_score"] = round(v["w"], 2)
            picks.append(x)
    print(f"{tag} 🏛 oylama: {len(votes)} aday pick -> {len(picks)} kurul kararı "
          f"(quorum≥{prof.get('quorum',3)}, aile≥{prof.get('min_families',2)}, "
          f"servet-ağırlıklı)")
    return picks


def _sort_key(prof: dict):
    mode = prof["sort"]
    if mode == "hunt":
        return lambda s: (1 if "SHARP" in (s.get("signal_name") or "") else 0,
                          s.get("edge") or -9, s.get("odds") or 0)
    if mode == "score":
        return lambda s: (s.get("signal_score") or 0, s.get("model_prob") or 0)
    if mode == "value":
        return lambda s: (s.get("_dev") or -9, s.get("odds") or 0)
    if mode == "pop":
        return lambda s: (s.get("signal_score") or 0, s.get("odds") or 0)
    return lambda s: (s.get("model_prob") or 0, s.get("signal_score") or 0)


# ════════════════════════════════════════════════════════════════
# 🎫 LİSANS SİSTEMİ — SABİT BIDDING (prop-firm modeli)
# ────────────────────────────────────────────────────────────────
# İlke (finansal matematik): SEÇİM becerisi (alpha) ile BOYUTLANDIRMA
# (sizing) asla aynı metrikte karışmaz. Herkes SABİT 100 TL/kupon oynar →
# ROI/karşılaştırma stake politikasından arınır. Kanıtlanmış beceri
# (flat-LCB = ortalama birim-kâr − 1σ/√n şans cezası) daha büyük sabit
# stake İZNİ kazandırır; terfide kasa tahsisi initial_bankroll'a eklenir
# (kâr sayılmaz — recompute ile tutarlı). Beceri bozulursa stake izni
# otomatik 100'e döner (tahsis edilen kasa kalır).
LICENSE_TIERS = [
    # (isim, sabit stake, kasa tabanı, min karar kuponu, min flat-LCB)
    ("🥇 EFSANE", 1000.0, 10000.0, 60, 0.05),
    ("🥈 USTA",    500.0,  5000.0, 30, 0.00),
    ("🎫 ÇAYLAK",  100.0,     0.0,  0, None),
]


def era_start(conn, pid: str):
    """Yürürlükteki eranın başlangıcı (yoksa None → tüm tarih)."""
    try:
        r = conn.execute("SELECT era_start FROM paper_portfolio WHERE portfolio_id=?",
                         (pid,)).fetchone()
        return r[0] if r and r[0] else None
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return None


def flat_skill(conn, pid: str, era: str | None = "auto"):
    """Karar kuponlarından stake-bağımsız beceri: (n, ortalama birim-kâr, LCB).
    Her kupon 1 birim sabit stake ile yeniden hesaplanır: won → oran−1, lost → −1.
    Varsayılan olarak YALNIZ yürürlükteki era ölçülür (era=None → tüm tarih)."""
    if era == "auto":
        era = era_start(conn, pid)
    rows = conn.execute(
        "SELECT status, combined_odds FROM paper_coupons "
        "WHERE portfolio_id=? AND status IN ('won','lost')"
        + (" AND created_at >= ?" if era else ""),
        (pid,) + ((era,) if era else ())).fetchall()
    fp = [((r[1] or 1) - 1) if r[0] == 'won' else -1.0 for r in rows]
    n = len(fp)
    if not n:
        return 0, None, None
    mean = sum(fp) / n
    if n < 5:
        return n, mean, None
    std = (sum((x - mean) ** 2 for x in fp) / n) ** 0.5
    return n, mean, mean - std / (n ** 0.5)


def license_for(conn, pid: str):
    """Ajanın GÜNCEL lisansı: (isim, sabit stake, kasa tabanı)."""
    n, _mean, lcb = flat_skill(conn, pid)
    for name, unit, floor, min_n, min_lcb in LICENSE_TIERS:
        if min_lcb is None:
            return name, unit, floor
        if n >= min_n and lcb is not None and lcb > min_lcb:
            return name, unit, floor
    return LICENSE_TIERS[-1][:3]


def manage_licenses():
    """Terfi kontrolü: hak eden ajana kalıcı lisans kaydı + kasa tahsisi."""
    conn = db.connect()
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS agent_license "
                     "(pid TEXT PRIMARY KEY, tier TEXT, unit REAL, granted_ts TEXT)")
        for pid in list(PROFILES.keys()) + ["KURUCU_V2"]:
            tier, unit, floor = license_for(conn, pid)
            row = conn.execute(
                "SELECT unit FROM agent_license WHERE pid=?", (pid,)).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO agent_license (pid, tier, unit, granted_ts) "
                    "VALUES (?,?,?,?)", (pid, tier, unit, _now()))
                continue
            if unit > (row[0] or 100.0):
                delta = 0.0
                pr = conn.execute(
                    "SELECT initial_bankroll FROM paper_portfolio "
                    "WHERE portfolio_id=?", (pid,)).fetchone()
                if pr:
                    delta = max(0.0, floor - (pr[0] or 0.0))
                    if delta > 0:
                        conn.execute(
                            "UPDATE paper_portfolio SET "
                            "initial_bankroll=initial_bankroll+?, "
                            "current_bankroll=current_bankroll+? "
                            "WHERE portfolio_id=?", (delta, delta, pid))
                conn.execute(
                    "UPDATE agent_license SET tier=?, unit=?, granted_ts=? "
                    "WHERE pid=?", (tier, unit, _now(), pid))
                print(f"[LISANS] 🎉 {pid}: {tier} terfisi — "
                      f"sabit stake {unit:.0f} TL, kasa tahsisi +{delta:.0f} TL")
        conn.commit()
    finally:
        conn.close()


def build_coupons(pid: str, eng: PaperEngine) -> list[dict]:
    prof = PROFILES[pid]
    tag = f"[{pid.split('_')[0]}]"
    if prof.get("retired"):
        print(f"{tag} 🏁 EMEKLI (kanit yok) -> oynamaz")
        return []
    if prof.get("dormant"):
        print(f"{tag} 😴 sezon bekliyor (Agustos'ta aktive edilecek) -> PAS")
        return []
    conn = db.connect()
    if _is_benched(conn, pid):
        conn.close()
        print(f"{tag} 🚫 KADRO DISI (sozlesme feshedildi) -> oynayamaz")
        return []
    try:
        if _loss_streak(conn, pid, prof["loss_streak"]):
            print(f"{tag} {prof['loss_streak']} ardisik kayip -> PAS")
            return []
        today = _now()[:10]
        # 🗓 ERA: önceki eranın kuponları yeni eranın günlük/açık limitini yemez
        _era = era_start(conn, pid)
        _ec = " AND created_at >= ?" if _era else ""
        _ep = (_era,) if _era else ()
        n_today = conn.execute(
            "SELECT COUNT(*) FROM paper_coupons WHERE portfolio_id=? "
            "AND session_date=?" + _ec, (pid, today) + _ep).fetchone()[0]
        n_open = conn.execute(
            "SELECT COUNT(*) FROM paper_coupons WHERE portfolio_id=? "
            "AND status='open'" + _ec, (pid,) + _ep).fetchone()[0]
        if n_today >= prof["max_daily"] or n_open >= prof["max_open"]:
            print(f"{tag} limit (bugun {n_today}/{prof['max_daily']}, "
                  f"acik {n_open}/{prof['max_open']}) -> PAS")
            return []
        rows = conn.execute(
            """
            SELECT * FROM matches_v2
            WHERE is_settled=0 AND kickoff_utc > ? AND closing_1 IS NOT NULL
              AND match_id NOT IN (
                  SELECT pb.match_id FROM paper_bets pb
                  JOIN paper_coupons pc ON pb.coupon_id=pc.coupon_id
                  WHERE pc.status='open' AND pc.portfolio_id=?
                    AND pb.match_id IS NOT NULL)
            ORDER BY kickoff_utc ASC LIMIT 200
            """, (_now(), pid)).fetchall()
        matches = [dict(r) for r in rows]
        # 🔒 ÇİFT BAHİS KİLİDİ: bu portföyün ZATEN açık pozisyonu olan maçlar.
        # Motor modları bunu matches sorgusunda alıyordu; fade/popular kendi
        # aday kaynağını kullandığı için filtreyi ATLIYORDU → aynı bahis
        # günlerce tekrar kuruluyordu (TERS 3x, POPÜLER 2x — karneyi şişirdi).
        open_matches = set()
        open_keys = set()
        try:
            for r in conn.execute(
                    "SELECT pb.match_id, pb.market, pb.pick FROM paper_bets pb "
                    "JOIN paper_coupons pc ON pb.coupon_id=pc.coupon_id "
                    "WHERE pc.portfolio_id=? AND pc.status='open'", (pid,)).fetchall():
                open_matches.add(r[0])
                open_keys.add((r[0], r[1], r[2]))
        except Exception:
            conn.rollback()
    finally:
        conn.close()

    per = eng.manage_period(pid)
    if not per["can_bet"]:
        print(f"{tag} donem kilidi ({per['status']}) -> PAS")
        return []
    bankroll = per["period_start_bankroll"]

    # 🎫 SABİT BIDDING: stake = lisans birimi (varsayılan 100 TL)
    try:
        conn_l = db.connect()
        _tier, unit, _fl = license_for(conn_l, pid)
        conn_l.close()
    except Exception:
        unit = 100.0

    mode = prof.get("mode")
    # 🏛 KONSEY modu: ajan heyeti oylaması (iç-Polymarket)
    if mode == "council":
        picks = _council_candidates(prof, tag, matches, eng)
        picks = _lock_open(picks, open_matches, open_keys, tag)
        picks.sort(key=_sort_key(prof), reverse=True)
        return _assemble_coupons(prof, bankroll, picks, unit)

    # 🦁 CESUR modu: orta-band (1.60-2.00) kendi aday kaynağı
    if mode == "midband":
        picks = _midband_candidates(prof, tag, matches)
        picks = _lock_open(picks, open_matches, open_keys, tag)
        picks.sort(key=_sort_key(prof), reverse=True)
        return _assemble_coupons(prof, bankroll, picks, unit)

    # 🪞 TERS modu: yazar pick'lerinin karşı tarafı
    if mode == "fade":
        picks = _fade_candidates(prof, tag)
        picks = _lock_open(picks, open_matches, open_keys, tag)
        picks.sort(key=_sort_key(prof), reverse=True)
        return _assemble_coupons(prof, bankroll, picks, unit)

    # 🃏 JOKER modu: kontrol ajanı — rastgele seçim, sinyal motoru yok
    if mode == "joker":
        picks = _joker_candidates(prof, tag, matches)
        picks = _lock_open(picks, open_matches, open_keys, tag)
        picks.sort(key=_sort_key(prof), reverse=True)
        return _assemble_coupons(prof, bankroll, picks, unit)

    # 🔥 POPÜLER modu: aday kaynağı sinyal motoru DEĞİL — yazar+konsensüs
    if mode == "popular":
        picks = _popular_candidates(prof, tag)
        picks = _lock_open(picks, open_matches, open_keys, tag)
        picks.sort(key=_sort_key(prof), reverse=True)
        return _assemble_coupons(prof, bankroll, picks, unit)

    picks = _engine_candidates(prof, tag, matches, eng)
    picks = _lock_open(picks, open_matches, open_keys, tag)
    picks.sort(key=_sort_key(prof), reverse=True)
    return _assemble_coupons(prof, bankroll, picks, unit)


def _lock_open(picks: list[dict], open_matches: set, open_keys: set,
               tag: str = "") -> list[dict]:
    """🔒 Açık pozisyonu olan maça İKİNCİ kez girme (mod fark etmez)."""
    out = []
    for p in picks:
        m = p.get("_match") or {}
        mid = m.get("match_id")
        if mid in open_matches or (mid, p.get("market"), p.get("pick")) in open_keys:
            continue
        out.append(p)
    if tag and len(out) != len(picks):
        print(f"{tag} 🔒 {len(picks)-len(out)} aday elendi (zaten açık pozisyon)")
    return out


def _assemble_coupons(prof: dict, bankroll: float, picks: list[dict],
                      unit: float = 100.0) -> list[dict]:
    """Aday pick'lerden MBS-uyumlu kupon montajı (TEK öncelik + tavanlı K3).
    Hem sinyal-motorlu ajanlar hem 🔥 POPÜLER aynı montajı kullanır.
    🎫 SABİT BIDDING: her kupon lisans birimi kadar (varsayılan 100 TL) —
    beceri ölçümü stake politikasından arınır; % stake tarihe karıştı."""
    coupons: list[dict] = []
    used: set = set()
    slots = prof["max_daily"]

    # ⏱ GERÇEKLİK KURALI (filtre değil, oynanabilirlik): maça 30 dakikadan
    # az kalan ayak kupona giremez. Gerekçe: iddaa maç başlarken kapatır;
    # kâğıt üstünde "kazanan" bir kupon gerçekte hiç oynanamamış olurdu →
    # ölçüm yalan söyler. (Ölçüldü: 154 kuponun 3'ü <60 dk, biri +3 dk.)
    from datetime import datetime as _dtl, timedelta as _tdl
    _floor = (_dtl.utcnow() + _tdl(minutes=30)).isoformat()
    _before = len(picks)
    picks = [x for x in picks
             if str((x.get("_match") or {}).get("kickoff_utc") or "") > _floor]
    if _before != len(picks):
        print(f"    ⏱ {_before - len(picks)} aday elendi (maça <30 dk)")

    # 1) TEK'ler (MBS=1) — kanıt: 1-2 ayak ezici üstün
    n_tek = 0
    for s in picks:
        if len(coupons) >= slots or n_tek >= prof["max_tek"]:
            break
        m = s["_match"]
        if _mbs(m) != 1 or m.get("match_id") in used:
            continue
        stake = round(unit, 2)
        coupons.append({
            "coupon_type": "A_TEK", "picks": [s], "stake": stake,
            "combined_odds": round(s["odds"], 3),
            "potential_return": round(stake * s["odds"], 2)})
        used.add(m.get("match_id"))
        n_tek += 1

    # 1.5) K2 (MBS<=2 çiftler) — arşiv hücresi: 2-ayak 7/7 kazanç +43.9%
    if len(coupons) < slots:
        pair = []
        for x in picks:
            mid = x["_match"].get("match_id")
            if mid in used or any(p["_match"].get("match_id") == mid for p in pair):
                continue
            if _mbs(x["_match"]) > 2:
                continue
            co = 1.0
            for p in pair + [x]:
                co *= p["odds"]
            if co > prof["combo_cap"]:
                continue
            pair.append(x)
            if len(pair) == 2:
                break
        if len(pair) == 2:
            co = pair[0]["odds"] * pair[1]["odds"]
            stake = round(unit, 2)
            coupons.append({
                "coupon_type": "A_K2", "picks": pair, "stake": stake,
                "combined_odds": round(co, 3),
                "potential_return": round(stake * co, 2)})
            for p in pair:
                used.add(p["_match"].get("match_id"))

    # 2) Kalan slotlara sıkı-filtreli 3'lüler (kombine tavanlı)
    while len(coupons) < slots:
        sel: list[dict] = []
        for s in picks:
            mid = s["_match"].get("match_id")
            if mid in used or any(p["_match"].get("match_id") == mid for p in sel):
                continue
            if _mbs(s["_match"]) > 3:
                continue
            co = 1.0
            for p in sel + [s]:
                co *= p["odds"]
            if co > prof["combo_cap"]:
                continue
            sel.append(s)
            if len(sel) == 3:
                break
        if len(sel) < 3:
            break
        co = 1.0
        for p in sel:
            co *= p["odds"]
        stake = round(unit, 2)
        coupons.append({
            "coupon_type": "A_K3", "picks": sel, "stake": stake,
            "combined_odds": round(co, 3),
            "potential_return": round(stake * co, 2)})
        for p in sel:
            used.add(p["_match"].get("match_id"))

    return coupons[:slots]


def _diag_write(pid: str, status: str, detail: str) -> None:
    """Teşhis satırı yaz (bağımsız bağlantı — çağıranın transaction'ını bozmaz)."""
    try:
        c = db.connect()
        c.execute("CREATE TABLE IF NOT EXISTS agent_diag "
                  "(ts TEXT, pid TEXT, status TEXT, detail TEXT)")
        c.execute("INSERT INTO agent_diag (ts, pid, status, detail) VALUES (?,?,?,?)",
                  (_now(), pid, status, detail[:300]))
        c.commit()
        c.close()
    except Exception:
        pass


def run_profile(pid: str, place: bool = True) -> list[str]:
    ensure_portfolio(pid)
    eng = PaperEngine(pid)
    tag = f"[{pid.split('_')[0]}]"
    # 🛡 FAIL-LOUD: çöken ajan SESSİZ kalmaz — teşhis tablosuna 🔴 yazılır.
    # (2026-08 dersi: scipy çöküşü haftalarca 'pasiflik' sanıldı.)
    try:
        coupons = build_coupons(pid, eng)
    except Exception as e:
        import traceback
        print(f"{tag} 🔴 TIKANIKLIK: {e}")
        traceback.print_exc()
        _diag_write(pid, "🔴 TIKANIKLIK", f"{type(e).__name__}: {e}")
        return []
    if not coupons:
        print(f"{tag} uygun sinyal yok -> PAS")
        return []
    for c in coupons:
        legs = ", ".join(
            f"{p['_match'].get('home_team','?')[:14]} {p['market']}:{p['pick']}@{p['odds']:.2f}"
            for p in c["picks"])
        print(f"{tag} {c['coupon_type']} oran {c['combined_odds']:.2f} "
              f"stake {c['stake']:.0f} TL -> {legs}")
    if not place:
        return []
    ids = eng.place_coupons(coupons, dry_run=False)
    print(f"{tag} {len(ids)} kupon yerlestirildi.")
    return ids


def diagnose_all() -> list[dict]:
    """🩺 GÜNLÜK TIKANIKLIK TEŞHİSİ — her ajan için: neden oynamıyor?
    Filtrelere DOKUNMAZ; sadece huniyi ölçer ve nedeni kayda geçirir:
    😴 dormant · 🚫 kadro dışı · 🧊 mola · ⏸ limit · 🔒 dönem ·
    ⚪ meşru PAS (0 aday) · 🟠 montaj engeli (aday var, MBS/tavan kesti) ·
    🟢 oynadı/oynayabilir · 🔴 TIKANIKLIK (hata)."""
    eng = PaperEngine("KURUCU_V2")
    conn = db.connect()
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS agent_diag "
                     "(ts TEXT, pid TEXT, status TEXT, detail TEXT)")
        conn.commit()
        matches = [dict(r) for r in conn.execute(
            "SELECT * FROM matches_v2 WHERE is_settled=0 AND kickoff_utc > ? "
            "AND closing_1 IS NOT NULL ORDER BY kickoff_utc ASC LIMIT 300",
            (_now(),)).fetchall()]
        today = _now()[:10]
        out = []

        # 🛰 VERİ HATTI NÖBETÇİSİ (kör nokta #1): fetch çökerse tüm ajanlar
        # "⚪ meşru PAS" görünürdü — sistemik arıza, masum sessizlik sanılırdı.
        # Maliyet: günde TEK ek sorgu (MAX(refreshed_at)); API çağrısı yok.
        pool = len(matches)
        data_broken = False
        try:
            lf = conn.execute("SELECT MAX(refreshed_at) FROM matches_v2").fetchone()[0]
            from datetime import datetime as _dtx
            age_h = ((_dtx.utcnow() - _dtx.fromisoformat(str(lf)[:19])).total_seconds()
                     / 3600.0) if lf else 999.0
        except Exception:
            conn.rollback()
            age_h = 999.0
        # ⏳ SONUÇ KUYRUĞU: biten ama 6 saattir işlenmemiş maç var mı?
        # (auto_settle 90 dk'da bir koşar; kuyruk birikirse kupon sonucu geç
        # gelir ve karne yanıltır. Ölçüldü: medyan 1.2 sa, kuyruk ucu 35.7 sa.)
        try:
            lag_n = conn.execute(
                "SELECT COUNT(DISTINCT m.match_id) FROM matches_v2 m "
                "JOIN paper_bets pb ON pb.match_id=m.match_id "
                "JOIN paper_coupons pc ON pc.coupon_id=pb.coupon_id "
                "WHERE pc.status='open' AND m.is_settled=0 AND m.kickoff_utc < ?",
                ((_dtx.utcnow() - __import__("datetime").timedelta(hours=6))
                 .isoformat(),)).fetchone()[0]
        except Exception:
            conn.rollback()
            lag_n = 0

        if pool == 0 or age_h > 8:
            # 'TIKANIKLIK' kelimesi bilinçli: UI alarm kutusu bunu sayıyor
            sys_st = "🔴 TIKANIKLIK · VERİ HATTI"
            sys_dt = (f"oynanabilir havuz {pool} maç · son fetch {age_h:.0f} sa önce "
                      f"— ajanların sessizliği KENDİ kararı değil, veri yok")
            data_broken = True
        elif lag_n >= 5:
            sys_st = "🟠 SONUÇ KUYRUĞU"
            sys_dt = (f"{lag_n} maç 6+ saattir sonuçsuz (açık kuponlu) — "
                      f"karne geç güncelleniyor · havuz {pool} maç")
        elif pool < 25:
            sys_st = "🟠 VERİ ZAYIF"
            sys_dt = f"havuz {pool} maç (son fetch {age_h:.0f} sa) — seçenek dar"
        else:
            sys_st = "🟢 VERİ AKIYOR"
            sys_dt = (f"{pool} oynanabilir maç · son fetch {age_h:.0f} sa önce · "
                      f"sonuç kuyruğu {lag_n}")
        conn.execute("INSERT INTO agent_diag (ts, pid, status, detail) VALUES (?,?,?,?)",
                     (_now(), "SISTEM", sys_st, sys_dt))
        out.append({"pid": "SISTEM", "status": sys_st, "detail": sys_dt})
        print(f"[DIAG·SİSTEM] {sys_st} — {sys_dt}")

        for pid, prof in PROFILES.items():
            tag = f"[DIAG·{pid.split('_')[0]}]"
            status, detail = "", ""
            try:
                if prof.get("retired"):
                    status, detail = "🏁 EMEKLİ", ("geriye dönük test: iddaa "
                                                  "fiyatlarıyla kârlı hücre yok")
                elif prof.get("dormant"):
                    status, detail = "😴 DORMANT", "sezona kadar bilinçli uyku"
                elif _is_benched(conn, pid):
                    status, detail = "🚫 KADRO DIŞI", "sözleşme feshi"
                elif _loss_streak(conn, pid, prof["loss_streak"]):
                    status, detail = "🧊 MOLA", f"{prof['loss_streak']} ardışık kayıp (48sa)"
                else:
                    _era = era_start(conn, pid)
                    _ec = " AND created_at >= ?" if _era else ""
                    _ep = (_era,) if _era else ()
                    n_today = conn.execute(
                        "SELECT COUNT(*) FROM paper_coupons WHERE portfolio_id=? "
                        "AND session_date=?" + _ec,
                        (pid, _now()[:10]) + _ep).fetchone()[0]
                    n_open = conn.execute(
                        "SELECT COUNT(*) FROM paper_coupons WHERE portfolio_id=? "
                        "AND status='open'" + _ec, (pid,) + _ep).fetchone()[0]
                    if n_today >= prof["max_daily"]:
                        status, detail = "🟢 OYNADI", f"bugün {n_today}/{prof['max_daily']} kupon"
                    elif n_open >= prof["max_open"]:
                        status, detail = "⏸ AÇIK LİMİT", f"açık {n_open}/{prof['max_open']}"
                    else:
                        per = PaperEngine(pid).manage_period(pid)
                        if not per["can_bet"]:
                            status, detail = "🔒 DÖNEM", per["status"]
                        else:
                            mode = prof.get("mode")
                            if mode == "council":
                                picks = _council_candidates(prof, tag, matches, eng)
                            elif mode == "midband":
                                picks = _midband_candidates(prof, tag, matches)
                            elif mode == "joker":
                                picks = _joker_candidates(prof, tag, matches)
                            elif mode == "fade":
                                picks = _fade_candidates(prof, tag)
                            elif mode == "popular":
                                picks = _popular_candidates(prof, tag)
                            else:
                                picks = _engine_candidates(prof, tag, matches, eng)
                            if not picks:
                                status = "⚪ MEŞRU PAS"
                                detail = (f"{len(matches)} maç tarandı, "
                                          f"0 profil-geçen aday")
                                if data_broken:
                                    detail += " · ⚠️ SEBEP SİSTEMİK: veri hattı kesik"
                            else:
                                picks.sort(key=_sort_key(prof), reverse=True)
                                cps = _assemble_coupons(
                                    prof, per["period_start_bankroll"], picks)
                                if cps:
                                    status = "🟢 OYNAYABİLİR"
                                    detail = (f"{len(picks)} aday → {len(cps)} kupon "
                                              f"kurar (bugün {n_today}/{prof['max_daily']})")
                                else:
                                    status = "🟠 MONTAJ ENGELİ"
                                    # sebebi somutlaştır: MBS dağılımı + tavan
                                    mbss = sorted(_mbs(x["_match"]) for x in picks)
                                    tek_ok = sum(1 for v in mbss if v == 1)
                                    detail = (
                                        f"{len(picks)} aday (MBS {mbss[:6]}) · "
                                        f"tek oynanabilir {tek_ok} · "
                                        f"kombine tavanı {prof['combo_cap']:.2f} — "
                                        f"iddaa MBS kuralı yeterli ayak vermiyor")
            except Exception as e:
                status, detail = "🔴 TIKANIKLIK", str(e)[:120]
            conn.execute("INSERT INTO agent_diag (ts, pid, status, detail) "
                         "VALUES (?,?,?,?)", (_now(), pid, status, detail))
            out.append({"pid": pid, "status": status, "detail": detail})
            print(f"{tag} {status} — {detail}")

        # 👑 KURUCU (kendi auto_play hattı — PROFILES'da yok ama ligde yarışıyor)
        try:
            k_era = era_start(conn, "KURUCU_V2")
            k_ec = " AND created_at >= ?" if k_era else ""
            k_ep = (k_era,) if k_era else ()
            k_today = conn.execute(
                "SELECT COUNT(*) FROM paper_coupons WHERE portfolio_id='KURUCU_V2' "
                "AND session_date=?" + k_ec, (_now()[:10],) + k_ep).fetchone()[0]
            kb = conn.execute(
                "SELECT current_bankroll, initial_bankroll FROM paper_portfolio "
                "WHERE portfolio_id='KURUCU_V2'").fetchone()
            if kb and (kb[0] or 0) < (kb[1] or 1) * 0.50:
                k_st, k_dt = "🛑 TABAN FRENİ", f"kasa {kb[0]:.0f} < %50 taban — koruma modu"
            elif k_today:
                k_st, k_dt = "🟢 OYNADI", f"bugün {k_today} kupon (auto_play hattı)"
            else:
                k_st, k_dt = "⚪ BEKLEMEDE", "auto_play penceresi (06:00/15:00 UTC)"
            conn.execute("INSERT INTO agent_diag (ts, pid, status, detail) "
                         "VALUES (?,?,?,?)", (_now(), "KURUCU_V2", k_st, k_dt))
            out.append({"pid": "KURUCU_V2", "status": k_st, "detail": k_dt})
            print(f"[DIAG·KURUCU] {k_st} — {k_dt}")
        except Exception as e:
            conn.rollback()
            print(f"[DIAG·KURUCU] okunamadı: {e}")
        conn.commit()
        return out
    finally:
        conn.close()


def preflight() -> list[str]:
    """🛡 KALKAN: her koşudan önce tüm ajanların aday üretebildiğini doğrula.
    Import/bağımlılık/şema kaynaklı çöküşü İLK koşuda yakalar ve 🔴 yazar.
    Filtrelere dokunmaz — sadece 'çöküyor mu?' sorusunu yanıtlar."""
    problems: list[str] = []
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT * FROM matches_v2 WHERE is_settled=0 AND kickoff_utc > ? "
            "AND closing_1 IS NOT NULL ORDER BY kickoff_utc LIMIT 60",
            (_now(),)).fetchall()
        matches = [dict(r) for r in rows]
    except Exception as e:
        conn.rollback()
        matches = []
        problems.append(f"maç sorgusu: {e}")
    finally:
        conn.close()

    for pid, prof in PROFILES.items():
        if prof.get("dormant") or prof.get("retired"):
            continue
        try:
            eng = PaperEngine(pid)
            mode = prof.get("mode")
            if mode == "council":
                _council_candidates(prof, f"[pre:{pid}]", matches, eng)
            elif mode == "midband":
                _midband_candidates(prof, f"[pre:{pid}]", matches)
            elif mode == "joker":
                _joker_candidates(prof, f"[pre:{pid}]", matches)
            elif mode == "fade":
                _fade_candidates(prof, f"[pre:{pid}]")
            elif mode == "popular":
                _popular_candidates(prof, f"[pre:{pid}]")
            else:
                _engine_candidates(prof, f"[pre:{pid}]", matches, eng)
        except Exception as e:
            msg = f"{type(e).__name__}: {e}"
            problems.append(f"{pid} → {msg}")
            _diag_write(pid, "🔴 TIKANIKLIK", f"preflight: {msg}")
            print(f"[PREFLIGHT] 🔴 {pid}: {msg}")
    if problems:
        print(f"[PREFLIGHT] 🔴 {len(problems)} ajan TIKALI — düzeltilmeden "
              f"ceza kesilmez, ölçüm geçersizdir.")
    else:
        print(f"[PREFLIGHT] ✅ {len(PROFILES)} profil temiz — tıkanıklık yok.")
    return problems


def start_era(era_no: int = 2, bankroll: float = 1000.0,
              include_kurucu: bool = True) -> None:
    """🗓 YENİ ERA: mevcut karne ARŞİVLENİR (kuponlar/journal aynen kalır),
    herkes aynı gün · aynı kasa · aynı sabit bahisle yeniden yarışır.
    Gerekçe: Era-1 kıyası kirli — kimi ajan %-stake, kimi köprü yarım stake,
    kimi de çöken motorla 'oynamamış' sayıldı. Kontrollü deney ancak ortak
    başlangıçla mümkün."""
    conn = db.connect()
    try:
        ensure_contract_columns(conn)
        now = _now()
        field = list(PROFILES) + (["KURUCU_V2"] if include_kurucu else [])
        print(f"[ERA] 🗓 ERA-{era_no} başlıyor — {len(field)} oyuncu, "
              f"{bankroll:.0f} TL, sabit 100 TL bahis")
        for pid in field:
            if pid in PROFILES:          # KURUCU_V2'nin profili yok (kendi hattı)
                ensure_portfolio(pid)
            n, mean, lcb = flat_skill(conn, pid, era=era_start(conn, pid))
            row = conn.execute(
                "SELECT current_bankroll, initial_bankroll FROM paper_portfolio "
                "WHERE portfolio_id=?", (pid,)).fetchone()
            cur = (row[0] or 0) if row else 0
            init = (row[1] or 0) if row else 0
            karne = (f"{n} karar kuponu · flat ROI "
                     f"{(mean*100):+.1f}%" if mean is not None else
                     f"{n} karar kuponu")
            _journal(conn, pid, f"📦 ERA-{era_no - 1} ARŞİVLENDİ",
                     f"Kapanış: kasa {cur:.0f}/{init:.0f} TL · {karne}. "
                     f"Kuponlar ve journal arşivde kalır; skor/kasa sıfırlanır. "
                     f"ERA-{era_no}: herkes {bankroll:.0f} TL + sabit 100 TL "
                     f"bahisle aynı gün başlar (kontrollü yarış).")
            conn.execute(
                "UPDATE paper_portfolio SET initial_bankroll=?, current_bankroll=?, "
                "peak_bankroll=?, total_staked=0, total_return=0, total_coupons=0, "
                "won_coupons=0, total_bets=0, total_wins=0, benched=0, ihtar_count=0, "
                "era_start=?, era_no=?, updated_at=? WHERE portfolio_id=?",
                (bankroll, bankroll, bankroll, now, era_no, now, pid))
            print(f"[ERA]   {pid:12s} arşiv: {karne} → sıfırlandı")
        # lisanslar da sıfırdan (beceri yeni erada kanıtlanır)
        try:
            conn.execute("DELETE FROM agent_license")
        except Exception:
            conn.rollback()
        # lig saati yeniden başlasın (ilk değerlendirme 7 gün sonra)
        conn.execute("UPDATE paper_portfolio SET last_review=? "
                     "WHERE portfolio_id='PAPER_V1'", (now,))
        conn.commit()
        print(f"[ERA] ✅ ERA-{era_no} kuruldu. İlk lig değerlendirmesi 7 gün sonra.")
    finally:
        conn.close()


def run_all(place: bool = True) -> dict:
    print(f"[AGENTS] === run_all basladi ({len(PROFILES)} profil) ===")
    # Sözleşme kolonlarını EN BAŞTA garanti et (eksik kolon → abort zinciri)
    try:
        conn = db.connect()
        ensure_contract_columns(conn)
        conn.close()
    except Exception as e:
        print(f"[AGENTS] kolon garanti hatasi: {e}")
    # 🛡 Kalkan: koşudan önce tıkanıklık taraması (sessiz çökme imkânsız)
    try:
        preflight()
    except Exception as e:
        print(f"[PREFLIGHT] HATA: {e}")
    out = {}
    for pid in PROFILES:
        try:
            out[pid] = run_profile(pid, place=place)
        except Exception as e:
            print(f"[{pid}] HATA: {e}")
            out[pid] = []
    n_total = sum(len(v) for v in out.values())
    print(f"[AGENTS] === run_all bitti: {n_total} kupon ===")
    # 💓 HEARTBEAT: worker'ın ajanları gerçekten koşturduğunun DB kanıtı
    # (UI Sistem Sağlığı 'Son Ajan Koşusu' bunu okur — log görünmese de iz kalır)
    try:
        conn = db.connect()
        conn.execute("CREATE TABLE IF NOT EXISTS agent_runs "
                     "(ts TEXT, coupons INTEGER, detail TEXT)")
        conn.execute("INSERT INTO agent_runs (ts, coupons, detail) VALUES (?,?,?)",
                     (_now(), n_total,
                      ",".join(f"{k.split('_')[0]}:{len(v)}" for k, v in out.items())))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[AGENTS] heartbeat yazilamadi: {e}")
    # 🎫 Lisans terfi kontrolü: flat-LCB kanıtı → 500/1000 TL stake izni
    try:
        manage_licenses()
    except Exception as e:
        print(f"[LISANS] HATA: {e}")
    # 🩺 Tıkanıklık teşhisi (10 saatte bir — iki auto_play penceresine denk
    # düşer; filtrelere dokunmaz, sadece ölçer. Maliyet: CPU + birkaç sorgu.)
    try:
        conn = db.connect()
        conn.execute("CREATE TABLE IF NOT EXISTS agent_diag "
                     "(ts TEXT, pid TEXT, status TEXT, detail TEXT)")
        last = conn.execute("SELECT MAX(ts) FROM agent_diag").fetchone()[0]
        conn.close()
        from datetime import datetime as _dt, timedelta as _td
        due = True
        if last:
            try:
                due = (_dt.utcnow() - _dt.fromisoformat(str(last)[:19])) > _td(hours=10)
            except Exception:
                pass
        if due:
            diagnose_all()
    except Exception as e:
        print(f"[DIAG] HATA: {e}")

    # 📜 Sözleşme ligi — haftalık saat dolduysa değerlendir (dolmadıysa sessiz)
    try:
        review_league()
    except Exception as e:
        print(f"[LIG] REVIEW HATA: {e}")
    return out


if __name__ == "__main__":
    run_all(place="--place" in sys.argv)
