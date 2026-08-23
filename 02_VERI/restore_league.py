# -*- coding: utf-8 -*-
"""🩺 TEŞHİS TELAFİSİ — scipy çöküşü yüzünden haksız kesilen cezaları geri al.

22 Ağu 2026 değerlendirmesinde 'pasiflik' gerekçesiyle kadro dışı kalan ajanlar
aslında susmuyordu: Railway runtime'ında scipy olmadığı için _engine_candidates
içindeki koşulsuz `import independent_model` TÜM motor ailesini düşürüyordu.
Ceza sebebi ajanın davranışı değil, sistemin hatasıydı → iade.

GERÇEK performans cezaları KORUNUR (MEMUR rota, JOKER rota, KURUCU performans).
"""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
from datetime import datetime
import db

# journal kayıtlarından birebir devir tutarları (22 Ağu 2026)
UNFAIR = {                 # pasiflik = motor çöküşü kaynaklı → tam iade
    "TEMKINLI_V1": 935.0,
    "AVCI_V1":     932.0,
    "MEMUR_V1":    786.0,   # rota ihtarı ayrıca gerçek → 1 ihtar korunur
    "ERKENKUS_V1": 1000.0,
    "TRIVOX_V1":   1000.0,
    "EUVOX_V1":    1000.0,
}
KEEP_IHTAR = {"MEMUR_V1": 1}          # gerçek (rota) ihtar korunur
CLEAR_IHTAR = ["HOCA_V1", "SIMYACI_V1", "KALECI_V1", "KONSEY_V1"]  # pasiflik kaynaklı
LEADER = "TERS_V1"

conn = db.connect()
now = datetime.utcnow().isoformat()
total = sum(UNFAIR.values())

print("=== ÖNCESİ ===")
for pid in list(UNFAIR) + [LEADER, "KURUCU_V2"]:
    r = conn.execute("SELECT initial_bankroll, current_bankroll, "
                     "COALESCE(ihtar_count,0), COALESCE(benched,0) "
                     "FROM paper_portfolio WHERE portfolio_id=?", (pid,)).fetchone()
    print(f"  {pid:12s} init={r[0]:7.0f} cur={r[1]:7.0f} ihtar={r[2]} bench={r[3]}")

for pid, amt in UNFAIR.items():
    conn.execute(
        "UPDATE paper_portfolio SET benched=0, ihtar_count=?, "
        "initial_bankroll=initial_bankroll+?, updated_at=? WHERE portfolio_id=?",
        (KEEP_IHTAR.get(pid, 0), amt, now, pid))
    conn.execute(
        "INSERT INTO paper_journal (journal_id, portfolio_id, entry_date, entry_type, "
        "title, content, created_at) VALUES (?,?,?,?,?,?,?)",
        (f"fix-{pid}-{now[:10]}", pid, now[:10], "LESSON", "🩺 TEŞHİS TELAFİSİ",
         f"22 Ağu 'pasiflik' cezası İPTAL: sessizliğin sebebi ajan değil, "
         f"Railway'de scipy eksikliğinden çöken sinyal motoruydu "
         f"(_engine_candidates koşulsuz import). Kasa {amt:.0f} TL iade edildi, "
         f"kadro dışılık kaldırıldı. Bundan böyle pasiflik ihtarı yalnız "
         f"🩺 teşhis 'oynayabilirdin' dediğinde kesilir.", now))

conn.execute(
    "UPDATE paper_portfolio SET initial_bankroll=initial_bankroll-?, updated_at=? "
    "WHERE portfolio_id=?", (total, now, LEADER))
conn.execute(
    "INSERT INTO paper_journal (journal_id, portfolio_id, entry_date, entry_type, "
    "title, content, created_at) VALUES (?,?,?,?,?,?,?)",
    (f"fix-{LEADER}-{now[:10]}", LEADER, now[:10], "LESSON", "🩺 DEVİR İADESİ",
     f"Haksız kadro dışı kararları iptal edildiği için devraldığı "
     f"{total:.0f} TL iade edildi. TERS'in kendi kupon P&L'i ve flat becerisi "
     f"etkilenmedi (sabit-100 metrikler kasadan bağımsızdır).", now))

for pid in CLEAR_IHTAR:
    conn.execute("UPDATE paper_portfolio SET ihtar_count=0, updated_at=? "
                 "WHERE portfolio_id=?", (now, pid))
conn.commit()

# sayaç senkronu
try:
    from recompute_portfolio import recompute
    for pid in list(UNFAIR) + [LEADER] + CLEAR_IHTAR:
        recompute(pid, verbose=False)
except Exception as e:
    print("recompute:", e)

print()
print("=== SONRASI ===")
for pid in list(UNFAIR) + [LEADER, "KURUCU_V2"] + CLEAR_IHTAR:
    r = conn.execute("SELECT initial_bankroll, current_bankroll, "
                     "COALESCE(ihtar_count,0), COALESCE(benched,0) "
                     "FROM paper_portfolio WHERE portfolio_id=?", (pid,)).fetchone()
    print(f"  {pid:12s} init={r[0]:7.0f} cur={r[1]:7.0f} ihtar={r[2]} bench={r[3]}")
print(f"\nToplam iade: {total:.0f} TL (TERS'ten geri alındı)")
conn.close()
