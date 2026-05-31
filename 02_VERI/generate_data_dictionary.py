"""
EKSEN 1 — DATA DICTIONARY otomatik üretici
============================================

Tüm tablolar + tüm kolonlar için insan-okur dokümantasyon.
Schema değişikliklerinde tekrar çalıştır.

Output: DATA_DICTIONARY.md
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
DB_PATH = THIS_DIR / "bahis_agent.db"


# Kolon açıklamaları (manuel eklenmiş bilgi)
COLUMN_DOCS = {
    # matches_v2
    "match_id": "Internal primary key",
    "external_id_fd": "Football-Data hash ID (lig+sezon+date+home+away)",
    "external_id_us": "Understat match id",
    "external_id_af": "api-football fixture id",
    "external_id_iddaa": "iddaa.com event id",
    "league_code": "T1/E0/D1/SP1/I1/F1",
    "season": "Canonical sezon kodu (YYYY-YY)",
    "matchday": "Maç tarihi YYYY-MM-DD",
    "kickoff_utc": "Maç başlama saati UTC",
    "home_team": "Ev sahibi takım (canonical isim)",
    "away_team": "Deplasman takım (canonical isim)",
    "home_score": "Ev sahibi tam zaman skor",
    "away_score": "Deplasman tam zaman skor",
    "opening_1": "1X2 açılış oranı home (B365)",
    "opening_X": "1X2 açılış oranı draw",
    "opening_2": "1X2 açılış oranı away",
    "closing_1": "1X2 kapanış oranı home (Pinnacle veya Avg fallback)",
    "closing_X": "1X2 kapanış oranı draw",
    "closing_2": "1X2 kapanış oranı away",
    "closing_over25": "A/Ü 2.5 kapanış oranı Üst",
    "closing_under25": "A/Ü 2.5 kapanış oranı Alt",
    "opening_over25": "A/Ü 2.5 açılış oranı Üst",
    "opening_under25": "A/Ü 2.5 açılış oranı Alt",
    "closing_btts_yes": "KG kapanış oranı Var",
    "closing_btts_no": "KG kapanış oranı Yok",
    "home_xg": "Understat home xG",
    "away_xg": "Understat away xG",
    "home_shots_total": "Total shots home",
    "away_shots_total": "Total shots away",
    "home_corners": "Korner sayısı home",
    "away_corners": "Korner sayısı away",
    "home_yellows": "Sarı kart home",
    "away_yellows": "Sarı kart away",
    "home_reds": "Kırmızı kart home",
    "away_reds": "Kırmızı kart away",
    "referee": "Hakem ismi",
    "has_full_odds": "1X2 closing odds tam mı (1/0)",
    "has_opening_odds": "Opening odds var mı",
    "has_xg": "xG verisi var mı",
    "has_match_stats": "Match stats (shots/corners/cards) var mı",
    "has_clv": "CLV hesaplanmış mı",
    "is_settled": "Maç oynanıp sonuçlandı mı",
    "quality_score": "0-1 arası kalite skoru (sinyal coverage)",
    "clv_home": "CLV home leg = (opening_1 / closing_1) - 1",
    "clv_draw": "CLV draw leg",
    "clv_away": "CLV away leg",
    "clv_avg_1x2": "1X2 ortalama CLV",
    "ingested_at": "İlk ingest zaman damgası",
    "refreshed_at": "Son güncelleme zamanı",
    # signal_snapshots
    "match_uid": "Tabloda unique identifier (lig_sezon_home_away_date)",
    "source": "football_data / iddaa / manual",
    "score_v12": "Eski v1.2 birleşik skor",
    "score_v13": "v1.3 score (anomaly+model+xG+form+sharp+invvar)",
    "score_v14": "v1.4 score (v13 + shots+referee+cards)",
    "s_anomaly": "Cross-market anomaly sinyal gücü 0-1",
    "s_model": "Dixon-Coles model güven sinyali",
    "s_xg": "xG luck (mean reversion) sinyali",
    "s_form": "Rolling 5-maç form sinyali",
    "s_sharp": "Sharp money detection",
    "s_invvar": "Inverse variance (overround)",
    "s_shots": "Shots-form differential sinyal (yeni v14)",
    "s_referee": "Referee bias sinyal (yeni v14)",
    "s_cards": "Cards pressure sinyal (yeni v14)",
    "s_ou_model": "A/Ü 2.5 DC Poisson sinyal gücü",
    "s_btts_model": "KG DC model sinyal gücü",
    "dir_anomaly": "Anomaly yönü HOME/DRAW/AWAY",
    "dir_model": "DC modelin tahminediği yön",
    "dir_xg": "xG sinyalinin yönü",
    "dir_form": "Form sinyalinin yönü",
    "dir_shots": "Shots-form sinyalinin yönü",
    "dir_referee": "Referee bias yönü",
    "dir_cards": "Cards pressure yönü (DRAW)",
    "dir_favorite": "Pinnacle implied favori (en düşük odd)",
    "dir_consensus": "Çoğunluk sinyalin gösterdiği yön",
    "dir_ou_model": "A/Ü 2.5 model yönü Over/Under",
    "dir_btts_model": "KG model yönü Var/Yok",
    "agree_count": "Kaç sinyal favori yönü ile aynı",
    "signal_count": "Kaç sinyal aktif",
    "fp_1": "Vig-stripped fair probability home (closing)",
    "fp_X": "Vig-stripped fair probability draw",
    "fp_2": "Vig-stripped fair probability away",
    "fp_over25": "Fair prob Üst 2.5 (closing)",
    "fp_under25": "Fair prob Alt 2.5",
    "fp_ou_model_over": "Model Üst 2.5 olasılığı (DC Poisson)",
    "fp_ou_model_under": "Model Alt 2.5 olasılığı",
    "fp_btts_model_yes": "Model KG Var olasılığı",
    "fp_btts_model_no": "Model KG Yok olasılığı",
    "ou_model_edge": "Model_p_over - Market_p_over",
    "model_lam_h": "DC home expected goals lambda",
    "model_lam_a": "DC away expected goals mu",
    "model_max_edge": "DC modelin en yüksek edge gördüğü leg",
    "xg_luck_diff": "Home_xg_luck - away_xg_luck",
    "form_delta": "Home_form_pts - away_form_pts",
    "result_1x2": "FT result H/D/A",
    "total_goals": "Toplam gol",
    "ft_btts": "KG gerçekleşti mi (1/0)",
    "settled": "Maç oynanmış mı (1/0)",
    # team_aliases
    "alias": "Alternatif takım ismi (Understat, iddaa vb.)",
    "canonical_name": "Canonical (matches_v2'deki) isim",
    # picks_log_v2
    "pick_id": "Pick unique id",
    "model": "Hangi model üretti (TRIVOX/DUOVOX vb.)",
    "K": "Kupon leg sayısı",
    "leg_no": "Kombin içindeki leg numarası",
    "direction": "HOME/DRAW/AWAY",
    "opening_odd": "Pick yapıldığında oran",
    "closing_odd": "Maç başlangıcında oran",
    "clv_pct": "CLV yüzdesi",
    "stake_tl": "Stake TL",
    "kelly_fraction": "Kelly fraction kullanılan",
    "pnl_gross": "Brüt kar/zarar TL",
    "pnl_net": "Net (vergi sonrası) TL",
}


def get_tables(conn):
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    return [r[0] for r in rows
            if not r[0].startswith("sqlite_") and r[0] != "api_calls"]


def generate():
    conn = sqlite3.connect(DB_PATH)
    tables = get_tables(conn)

    lines = ["# DATA DICTIONARY — BAHIS AGENT DB\n\n"]
    lines.append(f"**Otomatik üretildi:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
    lines.append(f"**Toplam tablo:** {len(tables)}\n\n")
    lines.append("---\n\n## İçindekiler\n\n")
    for t in tables:
        lines.append(f"- [{t}](#{t.replace('_', '-')})\n")
    lines.append("\n---\n\n")

    for t in tables:
        lines.append(f"## {t}\n\n")

        # Description (table level)
        table_desc = {
            "matches_v2": "**MASTER TABLE** — Canonical maç verileri. Tüm "
                         "sezonlar+ligler+pazarlar burada. 19,198 satır.",
            "signal_snapshots": "**MODEL ÇIKTILARI** — Her maç için tüm "
                              "sinyallerin durumu + outcome. Q5+a2 picks bu "
                              "tablodan çıkar.",
            "team_aliases": "Takım isimleri canonical mapping (Understat-FD vs.)",
            "seasons_meta": "Sezon-lig coverage özet metadata",
            "xg_data": "Understat xG verisi (5 lig × 4-5 sezon)",
            "picks_log_v2": "Canlı picks log (gerçek bahisler için)",
            "fixtures": "api-football fixture verisi (canlı sezon için)",
            "iddaa_odds": "iddaa.com odds snapshot'ları (multi-snapshot)",
            "tipster_picks": "Tipster verisi (alternatif sinyal kaynağı)",
            "injuries": "Sakatlık verisi (api-football)",
            "odds_anomaly_signals": "Cross-market anomaly tespitleri",
        }
        desc = table_desc.get(t, "")
        if desc:
            lines.append(f"{desc}\n\n")

        # Schema
        cols = conn.execute(f"PRAGMA table_info({t})").fetchall()
        n_rows = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        lines.append(f"**Satır sayısı:** {n_rows:,}\n\n")
        lines.append("| Kolon | Tip | NN | PK | Default | Açıklama |\n")
        lines.append("|---|---|---|---|---|---|\n")
        for c in cols:
            col_name = c[1]
            col_type = c[2]
            nn = "✓" if c[3] else ""
            pk = "🔑" if c[5] else ""
            default = str(c[4]) if c[4] is not None else ""
            doc = COLUMN_DOCS.get(col_name, "")
            lines.append(f"| `{col_name}` | {col_type} | {nn} | {pk} | "
                         f"{default} | {doc} |\n")
        lines.append("\n---\n\n")

    conn.close()

    out = THIS_DIR / "DATA_DICTIONARY.md"
    out.write_text("".join(lines), encoding="utf-8")
    print(f"[OK] DATA_DICTIONARY.md oluşturuldu ({len(tables)} tablo)")


if __name__ == "__main__":
    generate()
