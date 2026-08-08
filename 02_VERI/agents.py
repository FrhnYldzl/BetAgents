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
        "name": "POPÜLER (yazar + konsensüs) — sezona kadar uykuda",
        "stop_pct": -0.20, "dormant": True,
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
        "name": "CESUR (orta-oran avcısı 1.60-2.00)",
        "stop_pct": -0.25,
        "markets": {"UST_25", "ALT_25", "KG_YOK"},
        "fav_min": 0.50,
        "min_mp": 0.48, "min_odds": 1.60, "max_odds": 2.00,
        "combo_cap": 4.50, "max_daily": 3, "max_open": 6,
        "max_tek": 2, "loss_streak": 5,
        "tek_stake": 0.05, "k3_stake": 0.035,
        "sort": "score", "mode": "midband",
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
    # ── 😴 SEZON AJANLARI: kayıtlı ama UYKUDA (Ağustos'ta aktive edilecek) ──
    # MODEL_REGISTRY'de 13 model var; iki amiral gemisi burada ajan olarak
    # açıldı ki UNUTULMASIN. dormant=True → kasa hazır, kupon OYNAMAZ.
    # Aktivasyon (Ağustos): dormant kaldır + lig eşleme (T1/E0/SP1...) +
    # model sinyal hattını bağla. Alt-modeller (MONOVOX/DUOVOX/BTTS-*/OU25-*)
    # aktivasyonda filtre/bacak olarak bunlara bağlanır.
    "TRIVOX_V1": {
        "name": "TRIVOX (T1 uzmanı — sezon bekliyor)",
        "stop_pct": -0.15, "dormant": True,
        "markets": {"KG_YOK", "UST_25"}, "fav_min": 0.72,
        "min_mp": 0.66, "min_odds": 1.20,
        "combo_cap": 3.00, "max_daily": 2, "max_open": 4,
        "max_tek": 1, "loss_streak": 3,
        "tek_stake": 0.05, "k3_stake": 0.04, "sort": "safety",
    },
    "EUVOX_V1": {
        "name": "EUVOX (Avrupa DC — sezon bekliyor)",
        "stop_pct": -0.15, "dormant": True,
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
    rows = conn.execute(
        "SELECT status, settled_at FROM paper_coupons WHERE portfolio_id=? "
        "AND status IN ('won','lost') ORDER BY settled_at DESC LIMIT ?",
        (pid, n)).fetchall()
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
                     ("last_review", "TEXT")):
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

        print("[LIG] 📜 HAFTALIK SOZLESME DEGERLENDIRMESI")
        # KURUCU_V2 (Era-2) de yarışta — lig kuralları ona da işler
        field = [p for p in list(PROFILES) + ["KURUCU_V2"]
                 if not PROFILES.get(p, {}).get("dormant")
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
        # B) pasiflik: tolerans penceresinde 0 kupon (ajan yaşı pencereyi doldurmuşsa)
        for s in stats:
            if s["age"] >= s["tol"] and s["n_win"] == 0:
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


def build_coupons(pid: str, eng: PaperEngine) -> list[dict]:
    prof = PROFILES[pid]
    tag = f"[{pid.split('_')[0]}]"
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
        n_today = conn.execute(
            "SELECT COUNT(*) FROM paper_coupons WHERE portfolio_id=? AND session_date=?",
            (pid, today)).fetchone()[0]
        n_open = conn.execute(
            "SELECT COUNT(*) FROM paper_coupons WHERE portfolio_id=? AND status='open'",
            (pid,)).fetchone()[0]
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
    finally:
        conn.close()

    per = eng.manage_period(pid)
    if not per["can_bet"]:
        print(f"{tag} donem kilidi ({per['status']}) -> PAS")
        return []
    bankroll = per["period_start_bankroll"]

    # 🦁 CESUR modu: orta-band (1.60-2.00) kendi aday kaynağı
    mode = prof.get("mode")
    if mode == "midband":
        picks = _midband_candidates(prof, tag, matches)
        picks.sort(key=_sort_key(prof), reverse=True)
        return _assemble_coupons(prof, bankroll, picks)

    # 🃏 JOKER modu: kontrol ajanı — rastgele seçim, sinyal motoru yok
    if mode == "joker":
        picks = _joker_candidates(prof, tag, matches)
        picks.sort(key=_sort_key(prof), reverse=True)
        return _assemble_coupons(prof, bankroll, picks)

    # 🔥 POPÜLER modu: aday kaynağı sinyal motoru DEĞİL — yazar+konsensüs
    if mode == "popular":
        picks = _popular_candidates(prof, tag)
        picks.sort(key=_sort_key(prof), reverse=True)
        return _assemble_coupons(prof, bankroll, picks)

    # Model modu (HOCA/SIMYACI): bağımsız Poisson gol modelini yükle
    ratings = None
    if mode in ("confirm", "value"):
        try:
            ratings = _get_ratings()
        except Exception as e:
            print(f"{tag} model yuklenemedi ({e}) -> PAS")
            return []
    import independent_model as im
    _probs_cache: dict = {}

    picks: list[dict] = []
    for m in matches:
        # ⏰ Zaman filtreleri (ERKENKUŞ): erken-giriş penceresi + saat bandı
        kh_eff = prof.get("kick_hours")   # saat kısıtı yalnız profil bazlı (30g veri global yasağı desteklemedi)
        if prof.get("min_lead_h") or kh_eff:
            from datetime import datetime as _dt
            ko = str(m.get("kickoff_utc") or "")[:19]
            try:
                lead_h = (_dt.fromisoformat(ko) - _dt.utcnow()).total_seconds() / 3600
                ko_hour = int(ko[11:13])
            except Exception:
                continue
            if prof.get("min_lead_h") and lead_h < prof["min_lead_h"]:
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

    picks.sort(key=_sort_key(prof), reverse=True)
    return _assemble_coupons(prof, bankroll, picks)


def _assemble_coupons(prof: dict, bankroll: float, picks: list[dict]) -> list[dict]:
    """Aday pick'lerden MBS-uyumlu kupon montajı (TEK öncelik + tavanlı K3).
    Hem sinyal-motorlu ajanlar hem 🔥 POPÜLER aynı montajı kullanır."""
    coupons: list[dict] = []
    used: set = set()
    slots = prof["max_daily"]
    smult = 0.5 if bridge_active() else 1.0   # 🌉 köprü: stake ×0.5

    # 1) TEK'ler (MBS=1) — kanıt: 1-2 ayak ezici üstün
    n_tek = 0
    for s in picks:
        if len(coupons) >= slots or n_tek >= prof["max_tek"]:
            break
        m = s["_match"]
        if _mbs(m) != 1 or m.get("match_id") in used:
            continue
        stake = round(bankroll * prof["tek_stake"] * smult, 2)
        coupons.append({
            "coupon_type": "A_TEK", "picks": [s], "stake": stake,
            "combined_odds": round(s["odds"], 3),
            "potential_return": round(stake * s["odds"], 2)})
        used.add(m.get("match_id"))
        n_tek += 1

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
        stake = round(bankroll * prof["k3_stake"] * smult, 2)
        coupons.append({
            "coupon_type": "A_K3", "picks": sel, "stake": stake,
            "combined_odds": round(co, 3),
            "potential_return": round(stake * co, 2)})
        for p in sel:
            used.add(p["_match"].get("match_id"))

    return coupons[:slots]


def run_profile(pid: str, place: bool = True) -> list[str]:
    ensure_portfolio(pid)
    eng = PaperEngine(pid)
    coupons = build_coupons(pid, eng)
    tag = f"[{pid.split('_')[0]}]"
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


def run_all(place: bool = True) -> dict:
    print(f"[AGENTS] === run_all basladi ({len(PROFILES)} profil) ===")
    # Sözleşme kolonlarını EN BAŞTA garanti et (eksik kolon → abort zinciri)
    try:
        conn = db.connect()
        ensure_contract_columns(conn)
        conn.close()
    except Exception as e:
        print(f"[AGENTS] kolon garanti hatasi: {e}")
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
    # 📜 Sözleşme ligi — haftalık saat dolduysa değerlendir (dolmadıysa sessiz)
    try:
        review_league()
    except Exception as e:
        print(f"[LIG] REVIEW HATA: {e}")
    return out


if __name__ == "__main__":
    run_all(place="--place" in sys.argv)
