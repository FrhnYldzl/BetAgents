"""🛡 TIKANIKLIK KALKANI — DEPLOY ÖNCESİ ZORUNLU TEST

Kök neden dersi (2026-08): Railway runtime SLIM'dir (scipy/sklearn/lightgbm
YOK). Yerelde bu paketler kurulu olduğu için kod "çalışıyor" görünüyordu;
canlıda ise motor ailesinin TAMAMI ModuleNotFoundError ile çöküyor, ajanlar
haftalarca 'pasiflik'ten ceza yiyordu.

Bu test canlı ortamı YERELDE taklit eder: ağır paketleri import edilemez hâle
getirir ve her ajanın aday üretebildiğini doğrular. Çıkış kodu != 0 ise
DEPLOY ETME.

Kullanım:
    python selftest_agents.py            # slim taklidi (varsayılan)
    python selftest_agents.py --full     # yerel tam ortam
"""
from __future__ import annotations

import builtins
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# Railway'de OLMAYAN paketler (requirements-railway.txt SLIM setidir)
SLIM_BLOCKED = ("scipy", "sklearn", "lightgbm", "xgboost", "playwright",
                "statsmodels", "matplotlib", "bs4", "selenium")


def _block_heavy() -> None:
    real_import = builtins.__import__

    def guarded(name, *args, **kwargs):
        root = name.split(".")[0]
        if root in SLIM_BLOCKED:
            raise ModuleNotFoundError(f"No module named '{root}'")
        return real_import(name, *args, **kwargs)

    builtins.__import__ = guarded
    for mod in list(sys.modules):
        if mod.split(".")[0] in SLIM_BLOCKED:
            del sys.modules[mod]


def main() -> int:
    slim = "--full" not in sys.argv
    if slim:
        _block_heavy()
        print("🛡 SLIM TAKLİDİ AÇIK — bloklu: " + ", ".join(SLIM_BLOCKED))
    else:
        print("🛡 TAM ORTAM (yerel paketler açık)")

    import agents

    problems = agents.preflight()

    # Ek kanıt: her profil gerçekten kupon montajı yapabiliyor mu?
    import db
    from paper_engine import PaperEngine
    conn = db.connect()
    rows = conn.execute(
        "SELECT * FROM matches_v2 WHERE is_settled=0 AND kickoff_utc > ? "
        "AND closing_1 IS NOT NULL ORDER BY kickoff_utc LIMIT 200",
        (agents._now(),)).fetchall()
    matches = [dict(r) for r in rows]
    conn.close()
    print(f"\n🩺 MONTAJ TESTİ ({len(matches)} maç):")
    for pid, prof in agents.PROFILES.items():
        if prof.get("dormant"):
            print(f"  {pid:12s} 😴 dormant — atlandı")
            continue
        try:
            eng = PaperEngine(pid)
            mode = prof.get("mode")
            if mode == "council":
                picks = agents._council_candidates(prof, f"[t:{pid}]", matches, eng)
            elif mode == "midband":
                picks = agents._midband_candidates(prof, f"[t:{pid}]", matches)
            elif mode == "joker":
                picks = agents._joker_candidates(prof, f"[t:{pid}]", matches)
            elif mode == "fade":
                picks = agents._fade_candidates(prof, f"[t:{pid}]")
            elif mode == "popular":
                picks = agents._popular_candidates(prof, f"[t:{pid}]")
            else:
                picks = agents._engine_candidates(prof, f"[t:{pid}]", matches, eng)
            picks.sort(key=agents._sort_key(prof), reverse=True)
            cps = agents._assemble_coupons(prof, 1000.0, picks, 100.0)
            print(f"  {pid:12s} ✅ aday={len(picks):<3d} kupon={len(cps)}")
        except Exception as e:
            problems.append(f"{pid} montaj → {type(e).__name__}: {e}")
            print(f"  {pid:12s} 🔴 ÇÖKTÜ: {type(e).__name__}: {e}")

    print()
    if problems:
        print(f"🔴 {len(problems)} TIKANIKLIK — DEPLOY ETME:")
        for x in problems:
            print(f"   - {x}")
        return 1
    print("✅ TÜM AJANLAR TEMİZ — canlı ortamda tıkanıklık beklenmiyor.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
