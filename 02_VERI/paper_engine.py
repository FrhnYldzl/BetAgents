"""
PAPER TRADER ENGINE v1
======================
iddaa.com'dan cekilen maclari degerlendirir, paper kuponlar olusturur,
DB'ye yazar, sonuclari takip eder.

Kullanim:
  python paper_engine.py --run       # Yeni kuponlar olustur
  python paper_engine.py --settle    # Bitmis maclari kapat
  python paper_engine.py --status    # Portfoy ozeti
"""
from __future__ import annotations

import argparse
import uuid
from datetime import datetime, timezone
from pathlib import Path
import sys

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

import database as db


# ============================================================
# YARDIMCI FONKSİYONLAR
# ============================================================

def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


def _today() -> str:
    return datetime.utcnow().date().isoformat()


def calc_true_prob(odds_list: list[float]) -> list[float]:
    """
    Vig'i soy, gercek implied prob listesi dondur.

    Args:
        odds_list: [o1, o2, ...] — ham bookmaker oranlar (desimal)

    Returns:
        list[float] — vig-soyulmus gercek olasiliklar (ayni sirada)

    Ornek (1X2):
        calc_true_prob([2.10, 3.40, 3.60])
        => [0.46, 0.28, 0.26]  (toplam ~1.00)
    """
    raw = []
    for o in odds_list:
        if o is None or o <= 0:
            raw.append(0.0)
        else:
            raw.append(1.0 / o)
    overround = sum(raw)
    if overround <= 0:
        return [0.0] * len(odds_list)
    return [r / overround for r in raw]


def _safe_float(val) -> float | None:
    """None veya gecersiz degerleri None dondur."""
    try:
        f = float(val)
        return f if f > 0 else None
    except (TypeError, ValueError):
        return None


# ============================================================
# PAPER ENGINE
# ============================================================

class PaperEngine:
    """
    Paper Trader ana sinifi.

    Tum is mantigi burada:
      - matches_v2 satiri degerlendir → sinyaller
      - Oturum kuponu olustur → DB'ye yaz
      - Bitmis kupronlari kapat → bankroll guncelle
      - Portfoy ozeti
    """

    def __init__(self, portfolio_id: str = "PAPER_V1"):
        self.portfolio_id = portfolio_id
        self._portfolio: dict | None = None

    # ----------------------------------------------------------
    # PORTFOY OKUMA
    # ----------------------------------------------------------

    def _load_portfolio(self) -> dict:
        if self._portfolio is None:
            conn = db.connect()
            try:
                row = conn.execute(
                    "SELECT * FROM paper_portfolio WHERE portfolio_id = ?",
                    (self.portfolio_id,),
                ).fetchone()
                if row is None:
                    raise ValueError(
                        f"Portfoy bulunamadi: {self.portfolio_id}. "
                        "Once paper_migration.py calistirin."
                    )
                self._portfolio = dict(row)
            finally:
                conn.close()
        return self._portfolio

    def _refresh_portfolio(self) -> dict:
        self._portfolio = None
        return self._load_portfolio()

    # ----------------------------------------------------------
    # MAÇ DEĞERLENDİRME
    # ----------------------------------------------------------

    # Tarihsel backtest kanıtı olan ligler (8503 araştırma sistemi).
    # 8504 CANLI iddaa.com trader'ı bu listeyle SINIRLI DEĞİL — iddaa.com
    # o gün ne sunuyorsa (yaz ligleri dahil) hepsini değerlendirir.
    BACKTESTED_LEAGUES = {"T1", "E0", "SP1", "D1", "I1", "F1"}

    def evaluate_match(self, match_row: dict) -> list[dict]:
        """
        matches_v2 satirini degerlendir.

        Returns:
            list[dict] — her dict bir sinyal (market + pick + istatistikler).
            Sinyal esigi gecilmemisse bos liste doner.

        NOT: Lig filtresi YOK — iddaa.com canli sisteminin sundugu her mac
        degerlendirilir. Backtest kanitli ligler 'is_backtested' ile etiketlenir.
        """
        signals = []
        lg = match_row.get("league_code", "")
        is_bt = lg in self.BACKTESTED_LEAGUES

        # --- 1X2 ---
        o1 = _safe_float(match_row.get("closing_1"))
        oX = _safe_float(match_row.get("closing_X"))
        o2 = _safe_float(match_row.get("closing_2"))

        if all(v is not None for v in [o1, oX, o2]):
            true_probs = calc_true_prob([o1, oX, o2])
            mp1, mpX, mp2 = true_probs
            raw1, rawX, raw2 = 1 / o1, 1 / oX, 1 / o2

            # EV hesabi: edge = model_prob - implied_prob (ham)
            # HOME
            if mp1 >= 0.65 and o1 >= 1.20:
                signals.append({
                    "market":       "1X2",
                    "pick":         "1",
                    "odds":         o1,
                    "implied_prob": raw1,
                    "model_prob":   mp1,
                    "edge":         mp1 - raw1,
                    "signal_name":  "GUCLU_FAV",
                    "signal_score": min(1.0, (mp1 - 0.65) / 0.15 + 0.5),
                })
            elif mp1 >= 0.58 and o1 >= 1.20:
                signals.append({
                    "market":       "1X2",
                    "pick":         "1",
                    "odds":         o1,
                    "implied_prob": raw1,
                    "model_prob":   mp1,
                    "edge":         mp1 - raw1,
                    "signal_name":  "FAV",
                    "signal_score": min(1.0, (mp1 - 0.58) / 0.07 * 0.5 + 0.3),
                })

            # AWAY
            if mp2 >= 0.65 and o2 >= 1.20:
                signals.append({
                    "market":       "1X2",
                    "pick":         "2",
                    "odds":         o2,
                    "implied_prob": raw2,
                    "model_prob":   mp2,
                    "edge":         mp2 - raw2,
                    "signal_name":  "GUCLU_FAV",
                    "signal_score": min(1.0, (mp2 - 0.65) / 0.15 + 0.5),
                })
            elif mp2 >= 0.58 and o2 >= 1.20:
                signals.append({
                    "market":       "1X2",
                    "pick":         "2",
                    "odds":         o2,
                    "implied_prob": raw2,
                    "model_prob":   mp2,
                    "edge":         mp2 - raw2,
                    "signal_name":  "FAV",
                    "signal_score": min(1.0, (mp2 - 0.58) / 0.07 * 0.5 + 0.3),
                })

        # --- KG VAR (BTTS Yes) ---
        o_btts_y = _safe_float(match_row.get("closing_btts_yes"))
        o_btts_n = _safe_float(match_row.get("closing_btts_no"))

        if o_btts_y is not None and o_btts_n is not None:
            mp_y, mp_n = calc_true_prob([o_btts_y, o_btts_n])
            raw_y = 1 / o_btts_y

            if mp_y >= 0.60 and o_btts_y >= 1.20:
                signals.append({
                    "market":       "KG_VAR",
                    "pick":         "VAR",
                    "odds":         o_btts_y,
                    "implied_prob": raw_y,
                    "model_prob":   mp_y,
                    "edge":         mp_y - raw_y,
                    "signal_name":  "KG_VAR",
                    "signal_score": min(1.0, (mp_y - 0.60) / 0.15 + 0.4),
                })

        if o_btts_y is not None and o_btts_n is not None:
            raw_n = 1 / o_btts_n
            mp_y2, mp_n2 = calc_true_prob([o_btts_y, o_btts_n])
            if mp_n2 >= 0.62:
                signals.append({
                    "market":       "KG_YOK",
                    "pick":         "YOK",
                    "odds":         o_btts_n,
                    "implied_prob": raw_n,
                    "model_prob":   mp_n2,
                    "edge":         mp_n2 - raw_n,
                    "signal_name":  "KG_YOK",
                    "signal_score": min(1.0, (mp_n2 - 0.62) / 0.15 + 0.4),
                })

        # --- ALT / UST 2.5 ---
        o_over = _safe_float(match_row.get("closing_over25"))
        o_under = _safe_float(match_row.get("closing_under25"))

        if o_over is not None and o_under is not None:
            mp_ov, mp_un = calc_true_prob([o_over, o_under])
            raw_ov = 1 / o_over
            raw_un = 1 / o_under

            if mp_un >= 0.60:
                signals.append({
                    "market":       "ALT_25",
                    "pick":         "ALT",
                    "odds":         o_under,
                    "implied_prob": raw_un,
                    "model_prob":   mp_un,
                    "edge":         mp_un - raw_un,
                    "signal_name":  "ALT_25",
                    "signal_score": min(1.0, (mp_un - 0.60) / 0.15 + 0.4),
                })

            if mp_ov >= 0.58:
                signals.append({
                    "market":       "UST_25",
                    "pick":         "UST",
                    "odds":         o_over,
                    "implied_prob": raw_ov,
                    "model_prob":   mp_ov,
                    "edge":         mp_ov - raw_ov,
                    "signal_name":  "UST_25",
                    "signal_score": min(1.0, (mp_ov - 0.58) / 0.15 + 0.35),
                })

        # ── ENRICHED DATA: Yeni sinyaller (statisticsv2 verileri) ──────────────
        # Bu sinyaller matches_v2'deki zenginleştirilmiş kolonları kullanır.
        # stats_enricher.py çalıştırıldıktan sonra aktif hale gelir.

        h2h_n        = match_row.get("h2h_n") or 0
        h2h_hw       = match_row.get("h2h_home_wins") or 0
        h2h_aw       = match_row.get("h2h_away_wins") or 0
        h2h_btts     = match_row.get("h2h_btts_rate") or 0.0
        h2h_goals    = match_row.get("h2h_avg_goals") or 0.0
        home_yc_avg  = match_row.get("home_yc_5g_avg") or 0.0
        away_yc_avg  = match_row.get("away_yc_5g_avg") or 0.0
        home_cor_avg = match_row.get("home_corners_5g_avg") or 0.0
        away_cor_avg = match_row.get("away_corners_5g_avg") or 0.0
        home_pos     = match_row.get("home_league_pos") or 99
        away_pos     = match_row.get("away_league_pos") or 99
        home_relgap  = match_row.get("home_relegation_gap") or 50
        away_relgap  = match_row.get("away_relegation_gap") or 50
        home_titgap  = match_row.get("home_title_gap") or 50
        away_titgap  = match_row.get("away_title_gap") or 50
        home_missing = match_row.get("home_missing_key") or 0
        away_missing = match_row.get("away_missing_key") or 0
        odds_move_1  = match_row.get("odds_move_1") or 0.0
        odds_move_2  = match_row.get("odds_move_2") or 0.0

        # ── MOTIVATION AMPLIFIER ─────────────────────────────────────────
        # Ev sahibi düşme hattına yakınsa → zorlu savunma → daha fazla kart
        # Deplasman lider peşindeyse → ofansif → daha fazla gol
        home_motivation = min(2.0, 1.0 + max(0, (10 - home_relgap) / 20))
        away_motivation = min(2.0, 1.0 + max(0, (5 - away_titgap) / 20))

        # ── H2H ENHANCEMENT ───────────────────────────────────────────────
        # Backtest: H2H filtresi +%1.8 ROI (baseline +%1.1) → işe yarıyor
        # H2H >= 3 maç + ev oranı >= %50 → sinyal güçlendir
        # H2H < 3 veya zıt yön → sinyali zayıflat (form skoru düşür)
        if h2h_n >= 3 and o1 is not None and o2 is not None:
            h2h_home_rate = h2h_hw / h2h_n
            h2h_away_rate = h2h_aw / h2h_n
            for sig in signals:
                if sig["market"] == "1X2":
                    if sig["pick"] == "1":
                        if h2h_home_rate >= 0.50:
                            sig["signal_score"] = min(1.0, sig["signal_score"] * 1.18)
                            sig["signal_name"] += "_H2H"
                        elif h2h_home_rate <= 0.25:
                            # H2H ev için zayıf → skoru düşür
                            sig["signal_score"] *= 0.80
                    elif sig["pick"] == "2":
                        if h2h_away_rate >= 0.45:
                            sig["signal_score"] = min(1.0, sig["signal_score"] * 1.15)
                            sig["signal_name"] += "_H2H"
                        elif h2h_away_rate <= 0.20:
                            sig["signal_score"] *= 0.80

        # ── KG VAR — H2H BTTS geçmişi ────────────────────────────────────
        if h2h_n >= 3 and h2h_btts >= 0.60 and o_btts_y is not None:
            raw_y2 = 1.0 / o_btts_y if o_btts_y else 0
            mp_h2h_btts = min(0.85, 0.55 + h2h_btts * 0.3)
            if mp_h2h_btts >= 0.60 and o_btts_y >= 1.20:
                signals.append({
                    "market":       "KG_VAR",
                    "pick":         "VAR",
                    "odds":         o_btts_y,
                    "implied_prob": raw_y2,
                    "model_prob":   mp_h2h_btts,
                    "edge":         mp_h2h_btts - raw_y2,
                    "signal_name":  "KG_H2H",
                    "signal_score": min(1.0, h2h_btts * 0.85),
                })

        # ── ODDS HAREKETİ SİNYALİ (Sharp Money) ─────────────────────────
        # Oran kapanışta açılıştan belirgin düştüyse → piyasa o yönü seçiyor
        if o1 is not None and odds_move_1 < -0.15:
            raw1_m = 1.0 / o1
            mp_sharp1 = min(0.80, raw1_m + 0.08)
            if mp_sharp1 >= 0.60:
                signals.append({
                    "market":       "1X2",
                    "pick":         "1",
                    "odds":         o1,
                    "implied_prob": raw1_m,
                    "model_prob":   mp_sharp1,
                    "edge":         mp_sharp1 - raw1_m,
                    "signal_name":  "SHARP_1",
                    "signal_score": min(1.0, abs(odds_move_1) / 0.30 * 0.70),
                })
        if o2 is not None and odds_move_2 < -0.15:
            raw2_m = 1.0 / o2
            mp_sharp2 = min(0.80, raw2_m + 0.08)
            if mp_sharp2 >= 0.55:
                signals.append({
                    "market":       "1X2",
                    "pick":         "2",
                    "odds":         o2,
                    "implied_prob": raw2_m,
                    "model_prob":   mp_sharp2,
                    "edge":         mp_sharp2 - raw2_m,
                    "signal_name":  "SHARP_2",
                    "signal_score": min(1.0, abs(odds_move_2) / 0.30 * 0.70),
                })

        # ── STANDINGS MOTIVASYON: 1X2 sinyallerini filtrele ──────────────
        # Backtest: Standings filtresi +%1.7 ROI (baseline +%1.1) → işe yarıyor
        # Düşme hattına ≤ 4 puan olan takım → defensif oynuyor → piyasa favori bile
        # kazanamaz; bu maçlarda 1X2 sinyallerini iptal et
        if home_relgap is not None and away_relgap is not None:
            if home_relgap <= 4 or away_relgap <= 4:
                # Hayatta kalma modu → 1X2 sinyallerini kaldır
                signals = [s for s in signals if s["market"] != "1X2"]

        # ── DÜŞÜK SKOR / KG YOK — düşme baskısı altındaki maçlar ────────
        # Düşme hattı yakınındaki takımlar defensif oynuyor → alt ve KG yok
        if home_relgap is not None and away_relgap is not None:
            if home_relgap <= 6 and away_relgap <= 6 and o_under is not None:
                raw_un2 = 1.0 / o_under
                mp_survival = min(0.78, 0.58 + (12 - home_relgap - away_relgap) / 40)
                if mp_survival >= 0.60:
                    signals.append({
                        "market":       "ALT_25",
                        "pick":         "ALT",
                        "odds":         o_under,
                        "implied_prob": raw_un2,
                        "model_prob":   mp_survival,
                        "edge":         mp_survival - raw_un2,
                        "signal_name":  "SURV_ALT",
                        "signal_score": min(1.0, mp_survival * 0.90),
                    })

        return signals

    # ----------------------------------------------------------
    # HEDEFLİ PARA YÖNETİMİ
    # ----------------------------------------------------------

    def manage_period(self, portfolio_id: str | None = None) -> dict:
        """
        Aylık hedefli dönem yönetimi.

        Mantık:
          - Dönem başı bankroll kaydedilir (period_start_bankroll)
          - Hedef = dönem_başı × (1 + monthly_target_pct)  [varsayılan +%20]
          - Bankroll hedefe ulaşırsa → kâr KİLİTLENİR, durum 'target_hit'
          - Bankroll stop-loss'a düşerse → durum 'stopped'
          - 30 gün dolarsa veya hedef/stop tetiklenirse → YENİ DÖNEM başlatılır
            (period_start güncellenir, durum 'active', kar locked_profit'e eklenir)

        Returns:
            dict — period_start_bankroll, target, current, status, can_bet,
                   progress_pct, days_elapsed
        """
        pid = portfolio_id or self.portfolio_id
        conn = db.connect()
        try:
            p = conn.execute(
                "SELECT * FROM paper_portfolio WHERE portfolio_id=?", (pid,)
            ).fetchone()
            p = dict(p)

            current   = p["current_bankroll"] or 0.0
            ps_bank   = p.get("period_start_bankroll") or current
            ps_date   = p.get("period_start_date")
            target_pct = p.get("monthly_target_pct") or 0.20
            stop_pct   = p.get("stop_loss_pct") or -0.15
            locked     = p.get("locked_profit") or 0.0
            comp_per   = p.get("completed_periods") or 0
            status     = p.get("period_status") or "active"

            target_bank = ps_bank * (1 + target_pct)
            stop_bank   = ps_bank * (1 + stop_pct)

            # Geçen gün
            days_elapsed = 0
            if ps_date:
                try:
                    sd = datetime.fromisoformat(ps_date.replace("Z", ""))
                    days_elapsed = (datetime.utcnow() - sd).days
                except Exception:
                    days_elapsed = 0

            new_status = status
            reason = ""

            # ── Hedef tutuldu mu? ──
            if current >= target_bank and status == "active":
                new_status = "target_hit"
                reason = f"HEDEF TUTTU: {current:.0f} >= {target_bank:.0f} TL (+%{target_pct*100:.0f})"
            # ── Stop-loss? ──
            elif current <= stop_bank and status == "active":
                new_status = "stopped"
                reason = f"STOP-LOSS: {current:.0f} <= {stop_bank:.0f} TL (%{stop_pct*100:.0f})"

            # ── Yeni dönem başlatma koşulu ──
            # Hedef/stop tetiklendiyse VEYA 30 gün dolduysa → yeni dönem
            start_new = (new_status in ("target_hit", "stopped")) or (days_elapsed >= 30)

            if start_new:
                period_profit = current - ps_bank
                new_locked = locked + max(0.0, period_profit)  # sadece pozitif kâr kilitlenir
                now = _now_iso()
                conn.execute(
                    """
                    UPDATE paper_portfolio
                    SET period_start_bankroll = ?,
                        period_start_date = ?,
                        period_status = 'active',
                        locked_profit = ?,
                        completed_periods = ?,
                        updated_at = ?
                    WHERE portfolio_id = ?
                    """,
                    (current, now, new_locked, comp_per + 1, now, pid),
                )
                conn.commit()
                # Yeni dönem başladı → bahis açılabilir
                return {
                    "period_start_bankroll": current,
                    "target":      current * (1 + target_pct),
                    "current":     current,
                    "status":      "active",
                    "can_bet":     True,
                    "progress_pct": 0.0,
                    "days_elapsed": 0,
                    "locked_profit": new_locked,
                    "completed_periods": comp_per + 1,
                    "event": reason or "Yeni dönem başladı (30 gün doldu)",
                }

            # Durum değiştiyse kaydet (target_hit/stopped ama henüz reset yapılmadıysa
            # — yukarıda zaten reset yaptık, buraya düşmez. Güvenlik için.)
            progress = ((current - ps_bank) / (target_bank - ps_bank) * 100) if target_bank > ps_bank else 0.0
            can_bet = (new_status == "active")

            return {
                "period_start_bankroll": ps_bank,
                "target":      target_bank,
                "current":     current,
                "status":      new_status,
                "can_bet":     can_bet,
                "progress_pct": round(progress, 1),
                "days_elapsed": days_elapsed,
                "locked_profit": locked,
                "completed_periods": comp_per,
                "event": reason,
            }
        finally:
            conn.close()

    # ----------------------------------------------------------
    # OTURUM KUPONU OLUSTUR
    # ----------------------------------------------------------

    def build_session_coupons(self, portfolio_id: str | None = None) -> list[dict]:
        """
        matches_v2'den is_settled=0 olan maclari cek, degerlendir,
        en iyi picks'leri secip kupon listesi dondur.

        Returns:
            list[dict] — her dict bir kupon:
            {
                'coupon_type': str,
                'picks': list[dict],
                'stake': float,
                'combined_odds': float,
                'potential_return': float,
            }
        """
        pid = portfolio_id or self.portfolio_id

        # ── HEDEFLİ PARA YÖNETİMİ: dönem durumunu kontrol et ──────────────
        period = self.manage_period(pid)
        if not period["can_bet"]:
            # Hedef tutuldu veya stop-loss → yeni kupon açma
            return []

        # Stake'ler DÖNEM BAŞI bankroll'a göre (dönem içinde stabil kalır,
        # birkaç galibiyet stake'i şişirmez, birkaç kayıp küçültmez).
        bankroll = period["period_start_bankroll"]

        # ── CANLI iddaa.com trader: lig filtresi YOK ──────────────────────
        # iddaa.com o gün ne sunuyorsa (yaz ligleri dahil) hepsi değerlendirilir.
        # Backtest kanıtlı ligler (SP1/T1/D1/E0) sezon içinde otomatik öne çıkar
        # çünkü orada model_prob daha güçlü. Off-season'da yaz ligleri oynanır.
        BACKTESTED_LEAGUES = ("SP1", "T1", "D1", "E0")

        # Aktif maclari cek — tüm ligler
        # ÖNEMLİ: Zaten AÇIK bir kuponda olan maçları HARİÇ tut.
        # Bu olmadan --run iki kez çalışınca aynı maça mükerrer kupon açılıyor.
        conn = db.connect()
        try:
            rows = conn.execute(
                """
                SELECT *
                FROM matches_v2
                WHERE is_settled = 0
                  AND match_id NOT IN (
                      SELECT pb.match_id
                      FROM paper_bets pb
                      JOIN paper_coupons pc ON pb.coupon_id = pc.coupon_id
                      WHERE pc.status = 'open'
                        AND pc.portfolio_id = ?
                        AND pb.match_id IS NOT NULL
                  )
                ORDER BY kickoff_utc ASC
                LIMIT 200
                """,
                (pid,),
            ).fetchall()
        finally:
            conn.close()

        matches = [dict(r) for r in rows]

        # Tum sinyalleri topla
        all_signals: list[dict] = []
        for m in matches:
            sigs = self.evaluate_match(m)
            for s in sigs:
                s["_match"] = m   # orijinal mac satiri
            all_signals.extend(sigs)

        if not all_signals:
            return []

        # Sinyalleri sinyal skoruna gore sirala
        all_signals.sort(key=lambda x: x["signal_score"], reverse=True)

        coupons: list[dict] = []

        # Bu oturumda kullanılan maçlar — bir maç en fazla 1 kuponda olsun.
        used_match_ids: set = set()

        # ── Yardımcı: farklı maçlardan N pick seç ─────────────────
        def _pick_n(pool: list[dict], n: int) -> list[dict]:
            """pool'dan farklı match_id'li n pick sec.
            Zaten baska kuponda kullanilan maclari (used_match_ids) atlar."""
            result: list[dict] = []
            seen: set = set()
            for s in pool:
                mid = s["_match"].get("match_id")
                if mid in used_match_ids or mid in seen:
                    continue
                result.append(s)
                seen.add(mid)
                if len(result) == n:
                    break
            return result

        def _register(picks: list[dict]):
            """Kuponda kullanilan maclari oturum havuzuna ekle."""
            for p in picks:
                used_match_ids.add(p["_match"].get("match_id"))

        def _combo(picks: list[dict]) -> float:
            odds = 1.0
            for p in picks:
                odds *= p["odds"]
            return round(odds, 3)

        # ── K2_FAVORI: En guclu 2 MS sinyali (farklı maçlar) ──────
        # iddaa.com min 2 ayak — tekli bahis kabul edilmez
        fav_pool = [
            s for s in all_signals
            if s["market"] == "1X2"
            and s["model_prob"] >= 0.65
            and s["odds"] >= 1.25
        ]
        fav_picks = _pick_n(fav_pool, 2)
        if len(fav_picks) == 2:
            stake = round(bankroll * 0.025, 2)
            co = _combo(fav_picks)
            coupons.append({
                "coupon_type":      "K2_FAVORI",
                "picks":            fav_picks,
                "stake":            stake,
                "combined_odds":    co,
                "potential_return": round(stake * co, 2),
            })
            _register(fav_picks)

        # ── K2_VALUE: En guclu 2 value pick (herhangi pazar) ──────
        value_pool = [
            s for s in all_signals
            if s["model_prob"] >= 0.60
            and s["edge"] >= 0.04          # min +4% edge
        ]
        val_picks = _pick_n(value_pool, 2)
        if len(val_picks) == 2:
            stake = round(bankroll * 0.02, 2)
            co = _combo(val_picks)
            coupons.append({
                "coupon_type":      "K2_VALUE",
                "picks":            val_picks,
                "stake":            stake,
                "combined_odds":    co,
                "potential_return": round(stake * co, 2),
            })
            _register(val_picks)

        # ── K2_KARISIK: 1 MS + 1 KG/ALT karışık (farklı maçlar) ──
        ms_pool = [s for s in all_signals if s["market"] == "1X2" and s["model_prob"] >= 0.63]
        alt_pool = [
            s for s in all_signals
            if s["market"] in ("KG_VAR", "ALT_25", "UST_25")
            and s["model_prob"] >= 0.62
        ]
        ms_pick  = _pick_n(ms_pool, 1)
        if ms_pick:
            # alt_pool'dan farklı VE kullanılmamış maçtan bir pick al
            ms_mid = ms_pick[0]["_match"].get("match_id")
            alt_pick = next(
                (s for s in alt_pool
                 if s["_match"].get("match_id") != ms_mid
                 and s["_match"].get("match_id") not in used_match_ids),
                None
            )
            if alt_pick:
                karisik_picks = [ms_pick[0], alt_pick]
                stake = round(bankroll * 0.02, 2)
                co = _combo(karisik_picks)
                coupons.append({
                    "coupon_type":      "K2_KARISIK",
                    "picks":            karisik_picks,
                    "stake":            stake,
                    "combined_odds":    co,
                    "potential_return": round(stake * co, 2),
                })
                _register(karisik_picks)

        # ── K3_KOMBO: 3 güçlü sinyal (farklı maçlar) ──────────────
        kombo_pool = [
            s for s in all_signals
            if s["model_prob"] >= 0.60
        ]
        kombo_picks = _pick_n(kombo_pool, 3)
        if len(kombo_picks) == 3:
            stake = round(bankroll * 0.015, 2)
            co = _combo(kombo_picks)
            coupons.append({
                "coupon_type":      "K3_KOMBO",
                "picks":            kombo_picks,
                "stake":            stake,
                "combined_odds":    co,
                "potential_return": round(stake * co, 2),
            })
            _register(kombo_picks)

        # Max 4 kupon, tekli yok
        return coupons[:4]

    # ----------------------------------------------------------
    # KUPONU DB'YE YAZ
    # ----------------------------------------------------------

    def place_coupons(
        self,
        coupons: list[dict],
        dry_run: bool = False,
    ) -> list[str]:
        """
        paper_coupons ve paper_bets tablolarina yaz.

        Args:
            coupons:  build_session_coupons() ciktisi
            dry_run:  True ise DB'ye yazmaz, sadece ID'leri dondurur

        Returns:
            list[str] — coupon_id listesi
        """
        port = self._load_portfolio()
        coupon_ids: list[str] = []
        today = _today()
        now = _now_iso()

        conn = db.connect()
        try:
            for c in coupons:
                coupon_id = str(uuid.uuid4())
                picks = c["picks"]
                num_legs = len(picks)
                reasoning = self.generate_reasoning(picks, c["coupon_type"])

                if not dry_run:
                    conn.execute(
                        """
                        INSERT INTO paper_coupons (
                            coupon_id, portfolio_id, session_date, created_at,
                            coupon_type, num_legs, combined_odds, stake,
                            potential_return, status, model_version, reasoning
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)
                        """,
                        (
                            coupon_id,
                            self.portfolio_id,
                            today,
                            now,
                            c["coupon_type"],
                            num_legs,
                            c["combined_odds"],
                            c["stake"],
                            c["potential_return"],
                            port.get("strategy_version", "v1"),
                            reasoning,
                        ),
                    )

                    for pick in picks:
                        bet_id = str(uuid.uuid4())
                        m = pick.get("_match", {})
                        conn.execute(
                            """
                            INSERT INTO paper_bets (
                                bet_id, coupon_id, portfolio_id,
                                match_id, iddaa_event_id,
                                league, home_team, away_team, kickoff_utc,
                                market, pick, odds,
                                implied_prob, model_prob, edge,
                                signal_score, signal_name,
                                status
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open')
                            """,
                            (
                                bet_id,
                                coupon_id,
                                self.portfolio_id,
                                m.get("match_id"),
                                m.get("external_id_iddaa"),
                                m.get("league_code"),
                                m.get("home_team"),
                                m.get("away_team"),
                                m.get("kickoff_utc"),
                                pick["market"],
                                pick["pick"],
                                pick["odds"],
                                pick["implied_prob"],
                                pick["model_prob"],
                                pick["edge"],
                                pick["signal_score"],
                                pick["signal_name"],
                            ),
                        )

                coupon_ids.append(coupon_id)

            if not dry_run:
                conn.commit()
                print(f"[OK] {len(coupon_ids)} kupon DB'ye yazildi.")
            else:
                print(f"[DRY RUN] {len(coupon_ids)} kupon yazilmadi (dry_run=True).")

        finally:
            conn.close()

        return coupon_ids

    # ----------------------------------------------------------
    # JOURNAL YAZICI (dahili)
    # ----------------------------------------------------------

    def _write_journal_entry(
        self,
        conn,
        entry_type: str,
        title: str,
        content: str,
        pnl: float = 0.0,
        tags: str = "",
        model_action: str = "",
        signal_name: str = "",
        market: str = "",
        pick: str = "",
        odds: float = 0.0,
        actual_result: str = "",
        portfolio_id: str | None = None,
    ) -> None:
        """Verilen conn uzerinden paper_journal'a giris yaz."""
        pid = portfolio_id or self.portfolio_id
        conn.execute(
            """
            INSERT OR IGNORE INTO paper_journal
            (journal_id, portfolio_id, entry_date, entry_type,
             title, content, signal_name, market, pick, odds,
             actual_result, pnl, tags, model_action, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                str(uuid.uuid4()),
                pid,
                _today(),
                entry_type,
                title,
                content,
                signal_name or "",
                market or "",
                pick or "",
                odds or 0.0,
                actual_result or "",
                round(pnl, 2),
                tags or "",
                model_action or "",
                _now_iso(),
            ),
        )

    # ----------------------------------------------------------
    # KUPONU KAPAT (SETTLE)
    # ----------------------------------------------------------

    def settle_coupons(self, portfolio_id: str | None = None) -> dict:
        """
        Durumu 'open' olan kuponlari kontrol et.
        matches_v2'den home_score/away_score bak (is_settled=1).
        Bitmis macin sonucunu hesapla, status guncelle, bankroll guncelle.

        Returns:
            dict — {'settled': int, 'won': int, 'pnl': float}
        """
        pid = portfolio_id or self.portfolio_id
        conn = db.connect()
        settled_count = 0
        won_count = 0
        total_pnl = 0.0

        try:
            # Acik kuponlar
            open_coupons = conn.execute(
                "SELECT * FROM paper_coupons WHERE portfolio_id=? AND status='open'",
                (pid,),
            ).fetchall()

            for coupon in open_coupons:
                coupon = dict(coupon)
                coupon_id = coupon["coupon_id"]

                # Bu kupona ait betler
                bets = conn.execute(
                    "SELECT * FROM paper_bets WHERE coupon_id=?",
                    (coupon_id,),
                ).fetchall()
                bets = [dict(b) for b in bets]

                if not bets:
                    continue

                # Her bet icin mac sonucunu kontrol et
                all_settled = True
                bet_results: list[dict] = []

                for bet in bets:
                    mid = bet.get("match_id")
                    if mid is None:
                        all_settled = False
                        break

                    match = conn.execute(
                        "SELECT * FROM matches_v2 WHERE match_id=? AND is_settled=1",
                        (mid,),
                    ).fetchone()

                    if match is None:
                        all_settled = False
                        break

                    match = dict(match)
                    hs = match.get("home_score")
                    as_ = match.get("away_score")
                    mstatus = (match.get("status") or "").upper()

                    # is_settled=1 ama skor YOK + status=VOID → takılmış maç (iddaa
                    # event'i sildi). Bu ayağı VOID say (push), kupon diğer ayaklara
                    # göre çözülür. Tek ayaklıysa kupon void → stake iade.
                    if (hs is None or as_ is None):
                        if mstatus == "VOID":
                            bet_results.append({
                                "bet":        bet,
                                "match":      match,
                                "outcome":    "void",
                                "home_score": None,
                                "away_score": None,
                            })
                            continue
                        all_settled = False
                        break

                    outcome = self._determine_outcome(bet, hs, as_)
                    bet_results.append({
                        "bet": bet,
                        "match": match,
                        "outcome": outcome,
                        "home_score": hs,
                        "away_score": as_,
                    })

                if not all_settled:
                    continue

                # Tum ayaklar settlelandi — kupon sonucunu hesapla
                now = _now_iso()
                # VOID ayakları kombinden çıkar: void ayak "push" sayılır,
                # kombine oran sadece kazanan/kaybeden ayaklardan hesaplanır.
                non_void = [r for r in bet_results if r["outcome"] != "void"]
                has_void = len(non_void) < len(bet_results)

                if not non_void:
                    # TÜM ayaklar void → kupon tamamen void → stake iade (PnL=0)
                    coupon_status = "void"
                    actual_return = coupon["stake"]
                    pnl = 0.0
                else:
                    all_won = all(r["outcome"] == "won" for r in non_void)
                    any_lost = any(r["outcome"] == "lost" for r in non_void)
                    if all_won:
                        # Void ayak varsa kombine oranı void'siz yeniden hesapla
                        if has_void:
                            eff_odds = 1.0
                            for r in non_void:
                                eff_odds *= (r["bet"].get("odds") or 1.0)
                            coupon_status = "won"
                            actual_return = round(coupon["stake"] * eff_odds, 2)
                        else:
                            coupon_status = "won"
                            actual_return = coupon["stake"] * coupon["combined_odds"]
                        pnl = actual_return - coupon["stake"]
                    else:
                        coupon_status = "lost"
                        actual_return = 0.0
                        pnl = -coupon["stake"]

                # Her durumda tanımlı olsun (void kuponda da downstream kullanılıyor)
                all_won = (coupon_status == "won")

                # Kupon guncelle
                conn.execute(
                    """
                    UPDATE paper_coupons
                    SET status=?, settled_at=?, actual_return=?, pnl=?
                    WHERE coupon_id=?
                    """,
                    (coupon_status, now, actual_return, pnl, coupon_id),
                )

                # Betleri guncelle
                for r in bet_results:
                    conn.execute(
                        """
                        UPDATE paper_bets
                        SET status=?, result=?, home_score=?, away_score=?, settled_at=?
                        WHERE bet_id=?
                        """,
                        (
                            r["outcome"],
                            self._result_string(r["home_score"], r["away_score"]),
                            r["home_score"],
                            r["away_score"],
                            now,
                            r["bet"]["bet_id"],
                        ),
                    )

                # Portfoy guncelle
                conn.execute(
                    """
                    UPDATE paper_portfolio
                    SET current_bankroll = current_bankroll + ?,
                        total_coupons = total_coupons + 1,
                        won_coupons = won_coupons + ?,
                        total_staked = total_staked + ?,
                        total_return = total_return + ?,
                        peak_bankroll = MAX(peak_bankroll, current_bankroll + ?),
                        updated_at = ?
                    WHERE portfolio_id = ?
                    """,
                    (
                        pnl,
                        1 if all_won else 0,
                        coupon["stake"],
                        actual_return,
                        pnl,
                        now,
                        pid,
                    ),
                )

                # Bahis bazinda total_bets / total_wins guncelle
                bets_won = sum(1 for r in bet_results if r["outcome"] == "won")
                conn.execute(
                    """
                    UPDATE paper_portfolio
                    SET total_bets = total_bets + ?,
                        total_wins = total_wins + ?,
                        updated_at = ?
                    WHERE portfolio_id = ?
                    """,
                    (len(bet_results), bets_won, now, pid),
                )

                # ── Otomatik Journal girisi ──────────────────────
                status_emoji = "✓ KAZANDI" if all_won else "✗ KAYBETTI"
                bet_lines = []
                for r in bet_results:
                    b      = r["bet"]
                    m_r    = r["match"]
                    oc     = r["outcome"].upper()
                    sc     = f"{r['home_score']}-{r['away_score']}"
                    mp     = round((b.get("model_prob")  or 0) * 100, 1)
                    ip     = round((b.get("implied_prob") or 0) * 100, 1)
                    edge_p = round((b.get("edge")         or 0) * 100, 1)
                    sig    = round(b.get("signal_score")  or 0, 2)
                    bet_lines.append(
                        f"{m_r.get('home_team','?')} vs {m_r.get('away_team','?')} "
                        f"| {b.get('market','')} {b.get('pick','')} @{b.get('odds',0):.2f} "
                        f"| Model:%{mp:.0f} Piyasa:%{ip:.0f} Edge:{edge_p:+.1f}% Güven:{sig:.2f} "
                        f"| Skor:{sc} | {oc}"
                    )
                rsn = (coupon.get("reasoning") or "").strip()
                content = (
                    f"Tip: {coupon['coupon_type']} | Oran: {coupon['combined_odds']:.3f} | "
                    f"Stake: {coupon['stake']:.0f} TL | Getiri: {actual_return:.0f} TL\n"
                    + "\n".join(bet_lines)
                )
                if rsn:
                    content += f"\nTrade Notu: {rsn}"
                j_tags = coupon["coupon_type"]
                if all_won:
                    j_tags += ",WON"
                    j_action = "KEEP" if pnl > 0 else "REVIEW"
                else:
                    j_tags += ",LOST"
                    j_action = "REVIEW_SIGNAL"

                self._write_journal_entry(
                    conn=conn,
                    entry_type="RESULT",
                    title=f"{coupon['coupon_type']} — {status_emoji} {pnl:+.0f} TL",
                    content=content,
                    pnl=pnl,
                    tags=j_tags,
                    model_action=j_action,
                    portfolio_id=pid,
                )

                settled_count += 1
                if all_won:
                    won_count += 1
                total_pnl += pnl

            conn.commit()
            self._portfolio = None  # cache'i temizle

        finally:
            conn.close()

        return {
            "settled": settled_count,
            "won": won_count,
            "pnl": round(total_pnl, 2),
        }

    def _determine_outcome(self, bet: dict, home_score: int, away_score: int) -> str:
        """Bir bet icin sonucu hesapla: won / lost / void."""
        market = bet.get("market", "")
        pick = bet.get("pick", "")

        if market == "1X2":
            if home_score > away_score:
                actual = "1"
            elif home_score == away_score:
                actual = "X"
            else:
                actual = "2"
            return "won" if pick == actual else "lost"

        elif market == "KG_VAR":
            btts = home_score > 0 and away_score > 0
            if pick == "VAR":
                return "won" if btts else "lost"
            return "lost"

        elif market == "KG_YOK":
            btts = home_score > 0 and away_score > 0
            if pick == "YOK":
                return "won" if not btts else "lost"
            return "lost"

        elif market == "ALT_25":
            total = home_score + away_score
            if pick == "ALT":
                return "won" if total < 2.5 else "lost"
            return "lost"

        elif market == "UST_25":
            total = home_score + away_score
            if pick == "UST":
                return "won" if total > 2.5 else "lost"
            return "lost"

        return "void"

    @staticmethod
    def _result_string(home_score: int, away_score: int) -> str:
        return f"{home_score}-{away_score}"

    # ----------------------------------------------------------
    # PORTFOY OZETI
    # ----------------------------------------------------------

    def portfolio_status(self, portfolio_id: str | None = None) -> dict:
        """
        Portfoy ozet istatistikleri dondur.

        Returns:
            dict — bankroll, pnl, yield_pct, win_rate,
                   open_coupons, total_coupons, ...
        """
        pid = portfolio_id or self.portfolio_id
        conn = db.connect()
        try:
            port = conn.execute(
                "SELECT * FROM paper_portfolio WHERE portfolio_id=?",
                (pid,),
            ).fetchone()
            if port is None:
                return {"error": f"Portfoy bulunamadi: {pid}"}
            port = dict(port)

            # Acik kuponlar
            open_coupons = conn.execute(
                "SELECT COUNT(*) FROM paper_coupons WHERE portfolio_id=? AND status='open'",
                (pid,),
            ).fetchone()[0]

            # Kazanilan/kaybedilen staked
            staked = port["total_staked"] or 0.0
            total_return = port["total_return"] or 0.0
            total_coupons = port["total_coupons"] or 0
            won_coupons = port["won_coupons"] or 0
            total_bets = port["total_bets"] or 0
            total_wins = port["total_wins"] or 0

            pnl = total_return - staked
            yield_pct = (pnl / staked * 100) if staked > 0 else 0.0
            coupon_win_rate = (won_coupons / total_coupons * 100) if total_coupons > 0 else 0.0
            bet_win_rate = (total_wins / total_bets * 100) if total_bets > 0 else 0.0
            drawdown = port["current_bankroll"] - port["peak_bankroll"]
            drawdown_pct = (drawdown / port["peak_bankroll"] * 100) if port["peak_bankroll"] > 0 else 0.0

            return {
                "portfolio_id":      pid,
                "name":              port["name"],
                "strategy_version":  port["strategy_version"],
                "status":            port["status"],
                "initial_bankroll":  port["initial_bankroll"],
                "current_bankroll":  round(port["current_bankroll"], 2),
                "peak_bankroll":     round(port["peak_bankroll"], 2),
                "pnl":               round(pnl, 2),
                "yield_pct":         round(yield_pct, 2),
                "total_staked":      round(staked, 2),
                "total_return":      round(total_return, 2),
                "total_coupons":     total_coupons,
                "won_coupons":       won_coupons,
                "coupon_win_rate":   round(coupon_win_rate, 1),
                "total_bets":        total_bets,
                "total_wins":        total_wins,
                "bet_win_rate":      round(bet_win_rate, 1),
                "open_coupons":      open_coupons,
                "drawdown":          round(drawdown, 2),
                "drawdown_pct":      round(drawdown_pct, 2),
                "created_at":        port["created_at"],
                "updated_at":        port["updated_at"],
            }
        finally:
            conn.close()

    # ----------------------------------------------------------
    # ACIKLAMA URET
    # ----------------------------------------------------------

    def generate_reasoning(self, picks: list[dict], coupon_type: str) -> str:
        """
        Kupon icin zengin Turkce aciklama uret.
        Enriched data varsa (H2H, standings, sharp money) otomatik olarak dahil eder.
        """
        parts   = []
        context_notes = []
        combined_odds = 1.0

        for pick in picks:
            m      = pick.get("_match", {})
            home   = m.get("home_team", "?")
            away   = m.get("away_team", "?")
            mp_pct = round(pick["model_prob"] * 100, 0)
            market = pick["market"]
            p      = pick["pick"]
            odds   = pick["odds"]
            sname  = pick.get("signal_name", "")
            combined_odds *= odds

            # ── Ana açıklama ──
            if market == "1X2":
                side = "ev sahibi" if p == "1" else "deplasman" if p == "2" else "beraberlik"
                team = home if p == "1" else away if p == "2" else f"{home} vs {away}"
                desc = f"{team} ({side} fav. %{mp_pct:.0f})"
            elif market in ("KG_VAR", "KG_YOK"):
                kg_str = "Var" if market == "KG_VAR" else "Yok"
                desc = f"{home} vs {away} KG {kg_str} (%{mp_pct:.0f})"
            elif market == "ALT_25":
                desc = f"{home} vs {away} Alt 2.5 (%{mp_pct:.0f})"
            elif market == "UST_25":
                desc = f"{home} vs {away} Ust 2.5 (%{mp_pct:.0f})"
            else:
                desc = f"{home} vs {away} {market} {p} (%{mp_pct:.0f})"

            # ── Sinyal etiket notu ──
            if "_H2H" in sname:
                desc += " [H2H guclu]"
            elif "SHARP" in sname:
                desc += " [sharp money]"
            elif "SURV" in sname:
                desc += " [dusme baskisi]"
            elif "KG_H2H" in sname:
                desc += " [H2H BTTS gecmisi]"

            parts.append(desc)

            # ── Bağlam notları (enriched data) ──
            h2h_n    = m.get("h2h_n") or 0
            h2h_hw   = m.get("h2h_home_wins") or 0
            h2h_aw   = m.get("h2h_away_wins") or 0
            h2h_btts = m.get("h2h_btts_rate") or 0.0
            home_pos = m.get("home_league_pos")
            away_pos = m.get("away_league_pos")
            h_relgap = m.get("home_relegation_gap")
            a_relgap = m.get("away_relegation_gap")
            odds_mv  = m.get("odds_move_1") if p == "1" else m.get("odds_move_2") if p == "2" else None

            if h2h_n >= 3:
                context_notes.append(
                    f"H2H son {h2h_n} mac: {h2h_hw}G/{m.get('h2h_draws',0)}B/{h2h_aw}K, "
                    f"BTTS:{h2h_btts:.0%}, ort.gol:{m.get('h2h_avg_goals',0):.1f}"
                )
            if home_pos and away_pos:
                context_notes.append(f"Puan: {home} #{home_pos} vs {away} #{away_pos}")
            if h_relgap is not None and h_relgap <= 8:
                context_notes.append(f"{home} dusme hattina {h_relgap} puan! Savunma baskisi")
            if a_relgap is not None and a_relgap <= 8:
                context_notes.append(f"{away} dusme hattina {a_relgap} puan! Savunma baskisi")
            if odds_mv is not None and odds_mv < -0.15:
                context_notes.append(f"Oran hareketi: {odds_mv:+.2f} (sharp para giriyor)")

        combined_odds = round(combined_odds, 3)
        legs_str = " + ".join(parts)
        result = f"{coupon_type}: {legs_str}. Kombine oran: {combined_odds}."
        if context_notes:
            result += " | " + " | ".join(context_notes)
        return result


# ============================================================
# CLI
# ============================================================

def cmd_run(portfolio_id: str = "PAPER_V1") -> None:
    """Yeni kuponlar olustur ve DB'ye yaz."""
    engine = PaperEngine(portfolio_id)
    port = engine.portfolio_status()

    print(f"\n=== PAPER TRADER — --run ===")
    print(f"Portfoy  : {port['name']} ({portfolio_id})")
    print(f"Bankroll : {port['current_bankroll']:,.2f} TL")

    coupons = engine.build_session_coupons()
    if not coupons:
        print("[INFO] Bu oturum icin sinyal bulunamadi. Kupon olusturulmadi.")
        return

    print(f"\nOlusturulacak {len(coupons)} kupon:")
    for c in coupons:
        picks_str = ", ".join(
            f"{p['market']}:{p['pick']}@{p['odds']}" for p in c["picks"]
        )
        print(
            f"  {c['coupon_type']:15s} | "
            f"Stake:{c['stake']:7.2f} TL | "
            f"Oran:{c['combined_odds']:6.3f} | "
            f"Picks: {picks_str}"
        )

    ids = engine.place_coupons(coupons)
    print(f"\n[OK] {len(ids)} kupon yazildi: {ids}")


def cmd_settle(portfolio_id: str = "PAPER_V1") -> None:
    """Bitmis maclari kapat."""
    engine = PaperEngine(portfolio_id)
    print(f"\n=== PAPER TRADER — --settle ===")
    result = engine.settle_coupons()

    if result["settled"] == 0:
        print("[INFO] Kapatilacak acik kupon bulunamadi.")
    else:
        print(
            f"[OK] {result['settled']} kupon kapatildi: "
            f"{result['won']} kazanildi, "
            f"PnL = {result['pnl']:+.2f} TL"
        )

    status = engine.portfolio_status()
    print(f"\nBankroll : {status['current_bankroll']:,.2f} TL "
          f"(baslangic: {status['initial_bankroll']:,.2f})")
    print(f"PnL      : {status['pnl']:+.2f} TL  "
          f"Yield: {status['yield_pct']:+.1f}%")


def cmd_status(portfolio_id: str = "PAPER_V1") -> None:
    """Portfoy ozetini yazdir."""
    engine = PaperEngine(portfolio_id)
    s = engine.portfolio_status()

    if "error" in s:
        print(f"[HATA] {s['error']}")
        return

    SEP1 = "=" * 55
    SEP2 = "-" * 55
    print(f"\n{SEP1}")
    print(f"  PAPER TRADER - PORTFOY OZETI")
    print(SEP1)
    print(f"  ID            : {s['portfolio_id']}")
    print(f"  Ad            : {s['name']}")
    print(f"  Strateji      : {s['strategy_version']}")
    print(f"  Durum         : {s['status']}")
    print(SEP2)
    print(f"  Baslangic     : {s['initial_bankroll']:>12,.2f} TL")
    print(f"  Guncel        : {s['current_bankroll']:>12,.2f} TL")
    print(f"  Zirve         : {s['peak_bankroll']:>12,.2f} TL")
    print(f"  PnL           : {s['pnl']:>+12,.2f} TL")
    print(f"  Yield         : {s['yield_pct']:>+11.1f} %")
    print(f"  Drawdown      : {s['drawdown']:>+12,.2f} TL  ({s['drawdown_pct']:+.1f}%)")
    print(SEP2)
    print(f"  Toplam bahis  : {s['total_bets']:>4}  (kazanilan: {s['total_wins']}  "
          f"oran: %{s['bet_win_rate']:.1f})")
    print(f"  Toplam kupon  : {s['total_coupons']:>4}  (kazanilan: {s['won_coupons']}  "
          f"oran: %{s['coupon_win_rate']:.1f})")
    print(f"  Acik kupon    : {s['open_coupons']:>4}")
    print(f"  Staked        : {s['total_staked']:>12,.2f} TL")
    print(f"  Return        : {s['total_return']:>12,.2f} TL")
    print(SEP2)
    print(f"  Olusturuldu   : {s['created_at']}")
    print(f"  Son guncelleme: {s['updated_at']}")
    print(f"{SEP1}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Paper Trader Engine v1",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ornekler:\n"
            "  python paper_engine.py --run\n"
            "  python paper_engine.py --settle\n"
            "  python paper_engine.py --status\n"
            "  python paper_engine.py --run --portfolio PAPER_V2\n"
        ),
    )
    parser.add_argument("--run",       action="store_true", help="Yeni kuponlar olustur")
    parser.add_argument("--settle",    action="store_true", help="Bitmis maclari kapat")
    parser.add_argument("--status",    action="store_true", help="Portfoy ozeti")
    parser.add_argument("--portfolio", default="PAPER_V1",  help="Portfoy ID (default: PAPER_V1)")
    parser.add_argument("--dry-run",   action="store_true", help="DB'ye yazma, sadece goster")

    args = parser.parse_args()

    if args.run:
        if args.dry_run:
            engine = PaperEngine(args.portfolio)
            coupons = engine.build_session_coupons()
            if not coupons:
                print("[INFO] Sinyal bulunamadi.")
            else:
                print(f"[DRY RUN] {len(coupons)} kupon olusturulurdu:")
                for c in coupons:
                    reasoning = engine.generate_reasoning(c["picks"], c["coupon_type"])
                    print(f"  {reasoning}")
                    print(f"  Stake: {c['stake']:.2f} TL  |  "
                          f"Oran: {c['combined_odds']}  |  "
                          f"Max getiri: {c['potential_return']:.2f} TL\n")
        else:
            cmd_run(args.portfolio)

    elif args.settle:
        cmd_settle(args.portfolio)

    elif args.status:
        cmd_status(args.portfolio)

    else:
        parser.print_help()
