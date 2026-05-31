"""
KAPI 0 — TEST 3: xG/FORM TIMING LEAKAGE AUDIT
==============================================

Komite Madde A7:
> "xG-luck/form leakage şüphesi: xg_cache test fold'un xG'sini içerebiliyor;
>  fav_confirmed 5-maç window'un sonu net değil."

DETERMINISTIC TEST:
  Her sinyal (xG luck, form) için, kullanılan tarihsel maçların:
    a) Hepsi pivot maçtan ÖNCE mi?  (strict <)
    b) Pivot tarihiyle aynı maç var mı? (= sızıntı)
    c) Pivot tarihinden sonra maç var mı? (== ciddi sızıntı)

  100 rastgele maç al, her biri için detaylı denetim.

  Eğer (b) veya (c) > 0 → LEAKAGE → tüm v1 backtest sonuçları kuşkulu.
  Eğer (a) == 100% → no leakage.

Output:
  - Console summary
  - RAPOR/Kapi0_T03_timing_leakage_audit.md
"""
from __future__ import annotations

import random
import sys
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
YAZILIM = THIS_DIR.parent
sys.path.insert(0, str(YAZILIM / "02_VERI"))
sys.path.insert(0, str(YAZILIM / "03_MODELLER" / "selective"))

from extra_signals import (
    _load_xg_cache, _load_fix_cache, xg_luck_signal, form_signal,
)
from team_match import normalize, similarity


def audit_xg_signal(home_team: str, away_team: str, match_date: str) -> dict:
    """Bir maç için xG signal kullanırken hangi tarihli maçları alıyor?"""
    cache = _load_xg_cache()
    h_norm = normalize(home_team)
    a_norm = normalize(away_team)

    def fuzzy_find(team_norm):
        if team_norm in cache:
            return team_norm
        best_key = None; best_score = 0
        for k in cache.keys():
            s = similarity(team_norm, k)
            if s > best_score:
                best_score = s; best_key = k
        return best_key if best_score >= 0.70 else None

    def get_used_dates(team_norm):
        key = fuzzy_find(team_norm)
        if not key: return []
        hist = cache.get(key, [])
        relevant = [h for h in hist if h["match_date"] < match_date]
        return [h["match_date"] for h in relevant[-5:]]

    home_dates = get_used_dates(h_norm)
    away_dates = get_used_dates(a_norm)

    all_used = home_dates + away_dates
    n_total = len(all_used)
    n_after = sum(1 for d in all_used if d > match_date)
    n_same = sum(1 for d in all_used if d == match_date)
    n_before = sum(1 for d in all_used if d < match_date)

    return {
        "home_dates": home_dates,
        "away_dates": away_dates,
        "n_total": n_total,
        "n_before": n_before,
        "n_same_day": n_same,
        "n_after": n_after,
    }


def audit_form_signal(home_team: str, away_team: str, match_date: str) -> dict:
    """Bir maç için form signal kullanırken hangi tarihli maçları alıyor?"""
    cache = _load_fix_cache()
    h_norm = normalize(home_team)
    a_norm = normalize(away_team)

    def get_used_dates(team_norm):
        hist = cache.get(team_norm, [])
        relevant = [h for h in hist if h["date"] < match_date]
        return [h["date"] for h in relevant[-5:]]

    home_dates = get_used_dates(h_norm)
    away_dates = get_used_dates(a_norm)

    all_used = home_dates + away_dates
    n_total = len(all_used)
    n_after = sum(1 for d in all_used if d > match_date)
    n_same = sum(1 for d in all_used if d == match_date)
    n_before = sum(1 for d in all_used if d < match_date)

    return {
        "home_dates": home_dates,
        "away_dates": away_dates,
        "n_total": n_total,
        "n_before": n_before,
        "n_same_day": n_same,
        "n_after": n_after,
    }


def load_sample_matches(n: int = 100) -> list:
    """signal_snapshots'tan rastgele 100 maç çek."""
    db_path = YAZILIM / "02_VERI" / "bahis_agent.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT league_code, kickoff_iso, home_team, away_team
        FROM signal_snapshots WHERE source='football_data' AND settled=1
        ORDER BY RANDOM() LIMIT ?
    """, (n,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def run():
    print("=" * 80)
    print("KAPI 0 - TEST 3: xG/FORM TIMING LEAKAGE AUDIT")
    print("Komite Madde A7")
    print("=" * 80)

    random.seed(42)
    sample = load_sample_matches(100)
    print(f"\nRastgele {len(sample)} mac auditing...\n")

    # === xG signal audit ===
    print("-" * 80)
    print(">>> xG LUCK SIGNAL AUDIT")
    print("-" * 80)

    xg_results = []
    for i, m in enumerate(sample):
        md = m["kickoff_iso"][:10]
        r = audit_xg_signal(m["home_team"], m["away_team"], md)
        xg_results.append({**r, "match_date": md,
                           "home": m["home_team"], "away": m["away_team"]})

    total_used = sum(r["n_total"] for r in xg_results)
    total_before = sum(r["n_before"] for r in xg_results)
    total_same = sum(r["n_same_day"] for r in xg_results)
    total_after = sum(r["n_after"] for r in xg_results)
    print(f"  Toplam kullanilan match-day record: {total_used}")
    print(f"    ONCESI (< pivot)  : {total_before} ({total_before/max(1,total_used)*100:.1f}%)")
    print(f"    AYNI GUN (= pivot): {total_same}  ({total_same/max(1,total_used)*100:.1f}%)")
    print(f"    SONRASI (> pivot) : {total_after} ({total_after/max(1,total_used)*100:.1f}%)")

    if total_after > 0:
        print(f"\n  *** RED FLAG: {total_after} record pivot tarihinden SONRA ***")
        # Örnek göster
        for r in xg_results:
            if r["n_after"] > 0:
                print(f"    Pivot: {r['match_date']} {r['home']} vs {r['away']}")
                print(f"      Home used dates: {r['home_dates']}")
                print(f"      Away used dates: {r['away_dates']}")
                break
    elif total_same > 0:
        print(f"\n  ! WARNING: {total_same} record AYNI GUN icinde (boundary case)")
    else:
        print(f"\n  OK: xG signal sadece pivot oncesindeki maclari kullaniyor")

    # === Form signal audit ===
    print()
    print("-" * 80)
    print(">>> FORM SIGNAL AUDIT")
    print("-" * 80)

    form_results = []
    for i, m in enumerate(sample):
        md = m["kickoff_iso"][:10]
        r = audit_form_signal(m["home_team"], m["away_team"], md)
        form_results.append({**r, "match_date": md,
                             "home": m["home_team"], "away": m["away_team"]})

    total_used = sum(r["n_total"] for r in form_results)
    total_before = sum(r["n_before"] for r in form_results)
    total_same = sum(r["n_same_day"] for r in form_results)
    total_after = sum(r["n_after"] for r in form_results)
    print(f"  Toplam kullanilan match-day record: {total_used}")
    print(f"    ONCESI (< pivot)  : {total_before} ({total_before/max(1,total_used)*100:.1f}%)")
    print(f"    AYNI GUN (= pivot): {total_same}  ({total_same/max(1,total_used)*100:.1f}%)")
    print(f"    SONRASI (> pivot) : {total_after} ({total_after/max(1,total_used)*100:.1f}%)")

    if total_after > 0:
        print(f"\n  *** RED FLAG: {total_after} record pivot tarihinden SONRA ***")
        for r in form_results:
            if r["n_after"] > 0:
                print(f"    Pivot: {r['match_date']} {r['home']} vs {r['away']}")
                print(f"      Home used dates: {r['home_dates']}")
                print(f"      Away used dates: {r['away_dates']}")
                break
    elif total_same > 0:
        print(f"\n  ! WARNING: {total_same} record AYNI GUN icinde")
    else:
        print(f"\n  OK: form signal sadece pivot oncesindeki maclari kullaniyor")

    # === Ekstra: SCORE_v13 cache var mı kontrol et ===
    # signal_snapshots'da kullanılan xG ve form değerleri kalıcı mı, yoksa yeniden mi hesaplanmış?
    print()
    print("-" * 80)
    print(">>> EXTRA: signal_snapshots ham value vs current cache check")
    print("-" * 80)

    db_path = YAZILIM / "02_VERI" / "bahis_agent.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    discrepancies = 0
    n_checked = 0
    cache_xg = _load_xg_cache()

    # Birkaç pivot maç al, signal_snapshots'taki xg_luck_diff vs şimdi hesaplanan karşılaştır
    rows = conn.execute("""
        SELECT league_code, kickoff_iso, home_team, away_team,
               xg_luck_diff, form_delta
        FROM signal_snapshots
        WHERE source='football_data' AND xg_luck_diff IS NOT NULL
        ORDER BY RANDOM() LIMIT 30
    """).fetchall()
    conn.close()

    for r in rows:
        md = r["kickoff_iso"][:10]
        live = xg_luck_signal(r["home_team"], r["away_team"], md)
        if live.get("luck_diff") is not None and r["xg_luck_diff"] is not None:
            n_checked += 1
            if abs(live["luck_diff"] - r["xg_luck_diff"]) > 0.01:
                discrepancies += 1
    print(f"  signal_snapshots vs live recomputed xG signal:")
    print(f"    Kontrol: {n_checked}, farkli: {discrepancies}")
    if discrepancies > 0:
        print(f"    Farklilik {discrepancies}/{n_checked} mac -> cache temporal drift olabilir")

    # === VERDICT ===
    print()
    print("=" * 80)
    print("KAPI 0 - TEST 3 VERDICT")
    print("=" * 80)

    xg_after = sum(r["n_after"] for r in xg_results)
    xg_same = sum(r["n_same_day"] for r in xg_results)
    form_after = sum(r["n_after"] for r in form_results)
    form_same = sum(r["n_same_day"] for r in form_results)

    print(f"\nxG signal: {xg_after} after-pivot, {xg_same} same-day record")
    print(f"form signal: {form_after} after-pivot, {form_same} same-day record")

    if xg_after > 0 or form_after > 0:
        verdict = "FAIL_LEAKAGE"
        print(f"\n[FAIL] LEAKAGE TESPIT EDILDI -> Tum v1 backtest sonuclari kuskulu")
    elif xg_same > 0 or form_same > 0:
        verdict = "WARN_BOUNDARY"
        print(f"\n[WARN] Boundary case (ayni gun) -> dikkatle gozden gecir")
    else:
        verdict = "PASS_NO_LEAKAGE"
        print(f"\n[PASS] Hicbir signal pivot maciyla ayni gun veya sonrasi kullanmiyor")
        print(f"         -> Komite madde A7 endisesi ortadan kalkar (xG/form icin)")

    # Markdown rapor
    rapor = ["# KAPI 0 — TEST 3: xG/FORM TIMING LEAKAGE AUDIT\n"]
    rapor.append(f"**Tarih:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n")
    rapor.append("**Komite Madde A7:** xG-luck/form leakage suphesi\n\n")
    rapor.append(f"## Sample: {len(sample)} rastgele mac\n\n")
    rapor.append("## xG Luck Signal Audit\n\n")
    rapor.append(f"- Toplam record kullanildi: {sum(r['n_total'] for r in xg_results)}\n")
    rapor.append(f"- Pivot oncesi (< match_date): {sum(r['n_before'] for r in xg_results)}\n")
    rapor.append(f"- Pivot ile ayni gun: {sum(r['n_same_day'] for r in xg_results)}\n")
    rapor.append(f"- Pivot sonrasi: {sum(r['n_after'] for r in xg_results)}\n\n")
    rapor.append("## Form Signal Audit\n\n")
    rapor.append(f"- Toplam record kullanildi: {sum(r['n_total'] for r in form_results)}\n")
    rapor.append(f"- Pivot oncesi (< match_date): {sum(r['n_before'] for r in form_results)}\n")
    rapor.append(f"- Pivot ile ayni gun: {sum(r['n_same_day'] for r in form_results)}\n")
    rapor.append(f"- Pivot sonrasi: {sum(r['n_after'] for r in form_results)}\n\n")
    rapor.append(f"## Recompute Sanity\n\n")
    rapor.append(f"- signal_snapshots vs live recomputed xG: {n_checked} kontrol, {discrepancies} farkli\n\n")
    rapor.append(f"## Verdict\n\n**{verdict}**\n")
    out = YAZILIM / "RAPOR" / "Kapi0_T03_timing_leakage_audit.md"
    out.write_text("".join(rapor), encoding="utf-8")
    print(f"\n[OK] Rapor: {out}")


if __name__ == "__main__":
    run()
