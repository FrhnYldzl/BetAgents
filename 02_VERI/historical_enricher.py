"""
historical_enricher.py
----------------------
Backfills enriched columns in matches_v2 using only data already in the DB.
No external API calls needed.

Usage:
    python historical_enricher.py
    python historical_enricher.py --force
    python historical_enricher.py --league T1
    python historical_enricher.py --limit 1000
    python historical_enricher.py --force --league E0 --limit 500
"""

import sys
import sqlite3
import argparse
import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

# ---------------------------------------------------------------------------
# DB path
# ---------------------------------------------------------------------------
DB_PATH = Path(__file__).parent / "bahis_agent.db"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def result_char(home_score, away_score, perspective):
    """Return W/D/L from perspective of 'home' or 'away'."""
    if home_score is None or away_score is None:
        return None
    if home_score > away_score:
        return 'W' if perspective == 'home' else 'L'
    elif home_score == away_score:
        return 'D'
    else:
        return 'L' if perspective == 'home' else 'W'


# ---------------------------------------------------------------------------
# H2H features
# ---------------------------------------------------------------------------

def compute_h2h(cur, home_team, away_team, before_dt, limit=10):
    """
    Look across ALL seasons for prior meetings between home_team and away_team
    strictly before before_dt.

    Returns dict with: h2h_n, h2h_home_wins, h2h_draws, h2h_away_wins,
                       h2h_avg_goals, h2h_btts_rate
    """
    cur.execute("""
        SELECT home_score, away_score
        FROM matches_v2
        WHERE (
              (home_team = ? AND away_team = ?)
           OR (home_team = ? AND away_team = ?)
        )
          AND home_score IS NOT NULL
          AND away_score IS NOT NULL
          AND kickoff_utc < ?
        ORDER BY kickoff_utc DESC
        LIMIT ?
    """, (home_team, away_team, away_team, home_team, before_dt, limit))

    rows = cur.fetchall()
    n = len(rows)
    if n == 0:
        return {
            'h2h_n': 0,
            'h2h_home_wins': 0,
            'h2h_draws': 0,
            'h2h_away_wins': 0,
            'h2h_avg_goals': None,
            'h2h_btts_rate': None,
        }

    home_wins = 0
    draws = 0
    away_wins = 0
    total_goals = 0
    btts_count = 0

    for r in rows:
        hs, as_ = r['home_score'], r['away_score']
        total_goals += hs + as_
        if hs > as_:
            home_wins += 1
        elif hs == as_:
            draws += 1
        else:
            away_wins += 1
        if hs > 0 and as_ > 0:
            btts_count += 1

    return {
        'h2h_n': n,
        'h2h_home_wins': home_wins,
        'h2h_draws': draws,
        'h2h_away_wins': away_wins,
        'h2h_avg_goals': round(total_goals / n, 4),
        'h2h_btts_rate': round(btts_count / n, 4),
    }


# ---------------------------------------------------------------------------
# Standings
# ---------------------------------------------------------------------------

def build_standings(cur, league_code, season, before_dt):
    """
    Build a standings dict {team: {pts, gd, gf}} for the given league+season
    using only completed matches strictly before before_dt.

    Returns standings dict.
    """
    cur.execute("""
        SELECT home_team, away_team, home_score, away_score
        FROM matches_v2
        WHERE league_code = ?
          AND season = ?
          AND home_score IS NOT NULL
          AND away_score IS NOT NULL
          AND kickoff_utc < ?
        ORDER BY kickoff_utc
    """, (league_code, season, before_dt))

    rows = cur.fetchall()
    standings = {}  # team -> {pts, gd, gf}

    for r in rows:
        ht, at = r['home_team'], r['away_team']
        hs, as_ = r['home_score'], r['away_score']

        for team in (ht, at):
            if team not in standings:
                standings[team] = {'pts': 0, 'gd': 0, 'gf': 0}

        if hs > as_:
            standings[ht]['pts'] += 3
        elif hs == as_:
            standings[ht]['pts'] += 1
            standings[at]['pts'] += 1
        else:
            standings[at]['pts'] += 3

        standings[ht]['gd'] += hs - as_
        standings[at]['gd'] += as_ - hs
        standings[ht]['gf'] += hs
        standings[at]['gf'] += as_

    return standings


def standings_features(standings, home_team, away_team):
    """
    Given a standings dict, return position-based features for home/away team.
    Position = rank by pts desc, gd desc (1-based).

    Returns dict with positional columns, or Nones if standings is empty.
    """
    if not standings:
        return {
            'home_league_pos': None, 'away_league_pos': None,
            'home_pts': None, 'away_pts': None,
            'home_gd': None, 'away_gd': None,
            'home_title_gap': None, 'away_title_gap': None,
            'home_relegation_gap': None, 'away_relegation_gap': None,
        }

    # Sort: pts desc, then gd desc
    sorted_teams = sorted(
        standings.items(),
        key=lambda x: (x[1]['pts'], x[1]['gd']),
        reverse=True
    )
    total_teams = len(sorted_teams)

    # Build position map
    pos_map = {}
    for rank, (team, stats) in enumerate(sorted_teams, start=1):
        pos_map[team] = {'pos': rank, 'pts': stats['pts'], 'gd': stats['gd']}

    leader_pts = sorted_teams[0][1]['pts']

    # Relegation: bottom 3 (or bottom 1 if fewer than 4 teams)
    relegation_cutoff = max(1, total_teams - 2)  # position of first relegated team
    # last safe team is at position relegation_cutoff - 1, pts = sorted_teams[relegation_cutoff-2]
    if total_teams >= 4:
        relegation_boundary_pts = sorted_teams[relegation_cutoff - 1][1]['pts']
    else:
        relegation_boundary_pts = 0  # not enough teams for relegation

    def gap_features(team):
        if team not in pos_map:
            return {'pos': None, 'pts': 0, 'gd': 0, 'title_gap': None, 'relg_gap': None}
        info = pos_map[team]
        title_gap = leader_pts - info['pts']
        relg_gap = info['pts'] - relegation_boundary_pts
        return {
            'pos': info['pos'],
            'pts': info['pts'],
            'gd': info['gd'],
            'title_gap': title_gap,
            'relg_gap': relg_gap,
        }

    h = gap_features(home_team)
    a = gap_features(away_team)

    return {
        'home_league_pos': h['pos'],
        'away_league_pos': a['pos'],
        'home_pts': h['pts'],
        'away_pts': a['pts'],
        'home_gd': h['gd'],
        'away_gd': a['gd'],
        'home_title_gap': h['title_gap'],
        'away_title_gap': a['title_gap'],
        'home_relegation_gap': h['relg_gap'],
        'away_relegation_gap': a['relg_gap'],
    }


# ---------------------------------------------------------------------------
# Rolling form (last 5)
# ---------------------------------------------------------------------------

def rolling_form(cur, team, before_dt, n=5):
    """
    Fetch last n matches for team (home or away) before before_dt.
    Returns dict with form_str, avg_goals_scored, clean_sheets,
                        yc_avg, corners_avg.
    """
    cur.execute("""
        SELECT home_team, away_team, home_score, away_score,
               home_yellows, away_yellows,
               home_corners, away_corners
        FROM matches_v2
        WHERE (home_team = ? OR away_team = ?)
          AND home_score IS NOT NULL
          AND away_score IS NOT NULL
          AND kickoff_utc < ?
        ORDER BY kickoff_utc DESC
        LIMIT ?
    """, (team, team, before_dt, n))

    rows = cur.fetchall()

    if not rows:
        return {
            'form_str': None,
            'avg_goals': None,
            'clean_sheets': None,
            'yc_avg': None,
            'corners_avg': None,
        }

    form_chars = []
    goals_scored_list = []
    clean_sheet_count = 0
    yc_list = []
    corners_list = []

    for r in rows:
        is_home = (r['home_team'] == team)
        hs, as_ = r['home_score'], r['away_score']

        # Form character
        if is_home:
            ch = result_char(hs, as_, 'home')
            goals_for = hs
            goals_against = as_
            yc = r['home_yellows']
            corners = r['home_corners']
        else:
            ch = result_char(hs, as_, 'away')
            goals_for = as_
            goals_against = hs
            yc = r['away_yellows']
            corners = r['away_corners']

        if ch:
            form_chars.append(ch)
        goals_scored_list.append(goals_for)
        if goals_against == 0:
            clean_sheet_count += 1
        if yc is not None:
            yc_list.append(yc)
        if corners is not None:
            corners_list.append(corners)

    form_str = ''.join(form_chars) if form_chars else None
    avg_goals = round(sum(goals_scored_list) / len(goals_scored_list), 4) if goals_scored_list else None
    yc_avg = round(sum(yc_list) / len(yc_list), 4) if yc_list else None
    corners_avg = round(sum(corners_list) / len(corners_list), 4) if corners_list else None

    return {
        'form_str': form_str,
        'avg_goals': avg_goals,
        'clean_sheets': clean_sheet_count,
        'yc_avg': yc_avg,
        'corners_avg': corners_avg,
    }


# ---------------------------------------------------------------------------
# Main enrichment loop
# ---------------------------------------------------------------------------

def enrich(args):
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    # Use WAL for concurrent-safe writes
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    cur = conn.cursor()

    # Build WHERE clause for match selection
    where_clauses = []
    params = []

    if not args.force:
        where_clauses.append("stats_enriched_at IS NULL")

    if args.league:
        where_clauses.append("league_code = ?")
        params.append(args.league)

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    limit_sql = f"LIMIT {args.limit}" if args.limit else ""

    query = f"""
        SELECT match_id, league_code, season, kickoff_utc,
               home_team, away_team, home_score, away_score, status
        FROM matches_v2
        {where_sql}
        ORDER BY league_code, season, kickoff_utc
        {limit_sql}
    """

    cur.execute(query, params)
    matches = cur.fetchall()

    total = len(matches)
    print(f"Matches to process: {total}")

    now_str = datetime.datetime.utcnow().isoformat(timespec='seconds') + 'Z'

    updated = 0
    per_league = {}

    # Cache standings per (league_code, season, kickoff_utc) to avoid
    # rebuilding for matches on the same date in the same league+season.
    # Key = (league_code, season, kickoff_utc)
    _standings_cache = {}

    for idx, match in enumerate(matches):
        match_id = match['match_id']
        league_code = match['league_code']
        season = match['season']
        kickoff = match['kickoff_utc']
        home_team = match['home_team']
        away_team = match['away_team']

        # --- H2H ---
        h2h = compute_h2h(cur, home_team, away_team, kickoff)

        # --- Standings (cached) ---
        cache_key = (league_code, season, kickoff)
        if cache_key not in _standings_cache:
            _standings_cache[cache_key] = build_standings(cur, league_code, season, kickoff)
        std = _standings_cache[cache_key]
        stand_feat = standings_features(std, home_team, away_team)

        # --- Rolling form ---
        hf = rolling_form(cur, home_team, kickoff)
        af = rolling_form(cur, away_team, kickoff)

        # --- Build UPDATE ---
        cur2 = conn.cursor()
        cur2.execute("""
            UPDATE matches_v2 SET
                h2h_n               = ?,
                h2h_home_wins       = ?,
                h2h_draws           = ?,
                h2h_away_wins       = ?,
                h2h_avg_goals       = ?,
                h2h_btts_rate       = ?,
                home_league_pos     = ?,
                away_league_pos     = ?,
                home_pts            = ?,
                away_pts            = ?,
                home_gd             = ?,
                away_gd             = ?,
                home_title_gap      = ?,
                away_title_gap      = ?,
                home_relegation_gap = ?,
                away_relegation_gap = ?,
                home_form_5g        = ?,
                away_form_5g        = ?,
                home_avg_goals_5g   = ?,
                away_avg_goals_5g   = ?,
                home_clean_sheet_5g = ?,
                away_clean_sheet_5g = ?,
                home_yc_5g_avg      = ?,
                away_yc_5g_avg      = ?,
                home_corners_5g_avg = ?,
                away_corners_5g_avg = ?,
                stats_enriched_at   = ?,
                stats_source        = 'historical_enricher'
            WHERE match_id = ?
        """, (
            h2h['h2h_n'],
            h2h['h2h_home_wins'],
            h2h['h2h_draws'],
            h2h['h2h_away_wins'],
            h2h['h2h_avg_goals'],
            h2h['h2h_btts_rate'],
            stand_feat['home_league_pos'],
            stand_feat['away_league_pos'],
            stand_feat['home_pts'],
            stand_feat['away_pts'],
            stand_feat['home_gd'],
            stand_feat['away_gd'],
            stand_feat['home_title_gap'],
            stand_feat['away_title_gap'],
            stand_feat['home_relegation_gap'],
            stand_feat['away_relegation_gap'],
            hf['form_str'],
            af['form_str'],
            hf['avg_goals'],
            af['avg_goals'],
            hf['clean_sheets'],
            af['clean_sheets'],
            hf['yc_avg'],
            af['yc_avg'],
            hf['corners_avg'],
            af['corners_avg'],
            now_str,
            match_id,
        ))

        updated += 1
        per_league[league_code] = per_league.get(league_code, 0) + 1

        # Commit every 100 rows
        if updated % 100 == 0:
            conn.commit()
            # Clear standings cache after each commit batch to avoid unbounded growth
            _standings_cache.clear()

        # Progress every 500 matches
        if (idx + 1) % 500 == 0:
            pct = (idx + 1) / total * 100
            print(f"  [{idx+1:>6}/{total}] {pct:.1f}% done — {updated} rows updated so far")

    # Final commit
    conn.commit()
    conn.close()

    # Summary
    print()
    print("=" * 50)
    print(f"DONE — {updated} matches updated out of {total} processed.")
    print("Breakdown by league:")
    for league in sorted(per_league):
        print(f"  {league:>6}: {per_league[league]:>6} matches updated")
    print("=" * 50)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Backfill enriched columns in matches_v2 from existing DB data."
    )
    parser.add_argument(
        '--force',
        action='store_true',
        default=False,
        help='Re-process rows that already have stats_enriched_at set.'
    )
    parser.add_argument(
        '--league',
        type=str,
        default=None,
        metavar='CODE',
        help='Only process matches for this league_code (e.g. T1, E0, SP1).'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        metavar='N',
        help='Stop after processing N matches.'
    )
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()

    print(f"DB path   : {DB_PATH}")
    print(f"Force     : {args.force}")
    print(f"League    : {args.league or '(all)'}")
    print(f"Limit     : {args.limit or '(none)'}")
    print()

    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    enrich(args)
