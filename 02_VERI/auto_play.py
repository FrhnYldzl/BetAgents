"""
AUTO PLAY — Otomatik canlı iddaa.com kupon oluşturma
=====================================================
8504 CANLI iddaa.com paper trader'ın beyni.
Günde 1-2 kez çalışır. Tam zincir:

  1. fetch_iddaa_live.py  → iddaa.com'un BUGÜN sunduğu maçları çek (tüm ligler)
  2. paper_engine --run   → modeli değerlendir, 5000 TL hesaptan kupon oluştur
  3. (settle ayrı task'ta — auto_settle.py her 90 dk)

Log: YAZILIM/07_LOG_VE_RAPORLAR/auto_play.log

Kullanım:
  python auto_play.py            # tam zincir
  python auto_play.py --no-fetch # sadece kupon oluştur (maçlar zaten DB'de)
"""
from __future__ import annotations
import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
YAZILIM  = THIS_DIR.parent
LOG_FILE = YAZILIM / "07_LOG_VE_RAPORLAR" / "auto_play.log"

sys.path.insert(0, str(THIS_DIR))
sys.stdout.reconfigure(encoding="utf-8")
LOG_FILE.parent.mkdir(exist_ok=True)

import db  # merkezî bağlantı katmanı (SQLite/PostgreSQL)

DB = THIS_DIR / "bahis_agent.db"


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run(no_fetch: bool = False, max_events: int = 40):
    log("=== AUTO PLAY BASLADI ===")

    # ── 1. iddaa.com canlı maçları çek ───────────────────────────
    if not no_fetch:
        try:
            from fetch_iddaa_live import fetch_and_ingest
            log("iddaa.com canlı maçlar çekiliyor (tüm ligler)...")
            fetch_and_ingest(dry_run=False, max_events=max_events,
                             only_target_leagues=False)
            log("Çekim tamamlandı.")
        except Exception as e:
            log(f"FETCH HATA: {e}")
    else:
        log("Fetch atlandı (--no-fetch).")

    # ── 2. Açık kupon limiti kontrolü ────────────────────────────
    conn = db.connect()
    # FIX (coklu-ajan): limit SADECE kendi portfoyunun acik kuponlarina
    # bakmali — eskisi TUM portfoyleri sayiyordu, ajanlarin kuponlari
    # KURUCU'yu blokluyordu (16>=12 -> surekli PAS).
    open_n = conn.execute(
        "SELECT COUNT(*) FROM paper_coupons WHERE status='open' "
        "AND portfolio_id='KURUCU_V2'"
    ).fetchone()[0]
    bankroll = conn.execute(
        "SELECT current_bankroll FROM paper_portfolio WHERE portfolio_id='KURUCU_V2'"
    ).fetchone()
    bankroll = bankroll[0] if bankroll else 0
    conn.close()

    log(f"Mevcut açık kupon: {open_n}  |  Bankroll: {bankroll:,.0f} TL")

    # 🛑 TABAN FRENİ (Era-1 dersi): kasa başlangıcın %50'sinin altına inerse
    # KORUMA MODU — yeni kupon yok (açıklar settle olur). Stop-reset döngüsü
    # felaketi Era-2'de tekrarlayamaz.
    init_row = None
    try:
        conn_f = db.connect()
        init_row = conn_f.execute(
            "SELECT initial_bankroll FROM paper_portfolio "
            "WHERE portfolio_id='KURUCU_V2'").fetchone()
        conn_f.close()
    except Exception:
        pass
    if init_row and bankroll < (init_row[0] or 1000) * 0.50:
        log(f"🛑 TABAN FRENİ: {bankroll:,.0f} < %50 taban — KORUMA MODU, yeni kupon yok.")
        log("=== AUTO PLAY BITTI ===\n")
        return

    # 🌉 AĞUSTOS'A KÖPRÜ (10 Ağu'da otomatik kalkar): KURUCU_V2 için
    # günlük max 2 kupon + stake ×0.5 + Avrupa saat bandı (12-24 UTC).
    # Gerekçe: haftalık özet — off-season'da 36 kupon/hafta israftı.
    bridge = datetime.utcnow().date().isoformat() < "2026-08-10"
    if bridge:
        conn_b = db.connect()
        n_today = conn_b.execute(
            "SELECT COUNT(*) FROM paper_coupons WHERE portfolio_id='KURUCU_V2' "
            "AND session_date=?", (datetime.utcnow().date().isoformat(),)
        ).fetchone()[0]
        conn_b.close()
        if n_today >= 2:
            log(f"🌉 Köprü modu: bugün {n_today}/2 kupon — yeni kurulmadı.")
            log("=== AUTO PLAY BITTI ===\n")
            return

    # Açık kupon çok fazlaysa yeni oluşturma (risk kontrolü)
    MAX_OPEN = 12
    if open_n >= MAX_OPEN:
        log(f"Açık kupon limiti ({MAX_OPEN}) doldu — yeni kupon oluşturulmadı.")
        log("=== AUTO PLAY BITTI ===\n")
        return

    # ── 3. Modeli değerlendir, kupon oluştur ─────────────────────
    try:
        from paper_engine import PaperEngine
        engine = PaperEngine("KURUCU_V2")

        # Hedefli dönem durumu
        per = engine.manage_period()
        log(f"Dönem: {per['status']} | İlerleme: %{per['progress_pct']} "
            f"({per['current']:.0f}/{per['target']:.0f} TL) | Kilitli: {per['locked_profit']:.0f} TL")
        if per.get("event"):
            log(f"  → {per['event']}")
        if not per["can_bet"]:
            log("HEDEF/STOP tetiklendi — bu dönem yeni kupon açılmaz.")
            log("=== AUTO PLAY BITTI ===\n")
            return

        coupons = engine.build_session_coupons()

        if not coupons:
            log("Model uygun sinyal bulamadı — kupon oluşturulmadı.")
            log("=== AUTO PLAY BITTI ===\n")
            return

        log(f"Model {len(coupons)} kupon önerdi:")
        for c in coupons:
            picks_str = ", ".join(
                f"{p.get('_match',{}).get('home_team','?')} {p['market']}:{p['pick']}"
                for p in c["picks"]
            )
            log(f"  {c['coupon_type']}  oran:{c['combined_odds']:.2f}  "
                f"stake:{c['stake']:.0f}TL  → {picks_str}")

        # 🎫 SABİT BIDDING: KURUCU da lige sabit birimle oynar (kıyas adil)
        try:
            import agents as _ag
            conn_l = db.connect()
            _tier, _unit, _f = _ag.license_for(conn_l, "KURUCU_V2")
            conn_l.close()
        except Exception:
            _tier, _unit = "🎫 ÇAYLAK", 100.0
        for c in coupons:
            c["stake"] = round(_unit, 2)
            c["potential_return"] = round(_unit * c["combined_odds"], 2)
        log(f"🎫 Lisans: {_tier} — sabit stake {_unit:.0f} TL/kupon")

        # 🌉 Köprü filtreleri: Avrupa saat bandı + yarım stake + max 2
        if bridge:
            def _eu(c):
                for pck in c["picks"]:
                    ko = str(pck.get("_match", {}).get("kickoff_utc") or "")
                    try:
                        if not (12 <= int(ko[11:13]) < 24):
                            return False
                    except Exception:
                        return False
                return True
            before = len(coupons)
            coupons = [c for c in coupons if _eu(c)][:2]
            for c in coupons:
                c["stake"] = round(c["stake"] * 0.5, 2)
                c["potential_return"] = round(c["stake"] * c["combined_odds"], 2)
            log(f"🌉 Köprü: {before}→{len(coupons)} kupon (saat bandı) · stake ×0.5")
            if not coupons:
                log("=== AUTO PLAY BITTI ===\n")
                return

        # DB'ye yaz (gerçek paper bet)
        ids = engine.place_coupons(coupons, dry_run=False)
        log(f"KUPON OLUŞTURULDU: {len(ids)} adet KURUCU_V2 (Era-2) hesabina kaydedildi.")

    except Exception as e:
        log(f"RUN HATA: {e}")
        import traceback
        log(traceback.format_exc())

    log("=== AUTO PLAY BITTI ===\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-fetch", action="store_true",
                        help="Maç çekme adımını atla")
    parser.add_argument("--max", type=int, default=40)
    args = parser.parse_args()
    run(no_fetch=args.no_fetch, max_events=args.max)
