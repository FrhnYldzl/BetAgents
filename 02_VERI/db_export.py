"""
EKSEN 1 — Database Export Adapters
====================================

Database tablolarını CSV / Excel / Parquet olarak export et.
Başka projelerde, başka araçlarda kullanılabilir.

Kullanım:
    python db_export.py csv                       # tüm tablolar CSV
    python db_export.py csv --table matches_v2    # tek tablo
    python db_export.py excel                     # tek dosya, çoklu sheet
    python db_export.py parquet                   # parquet (büyük data için)
    python db_export.py all                       # tüm formatlar
"""
from __future__ import annotations

import argparse
import sys
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
EXPORTS_DIR = THIS_DIR / "exports"
DB_PATH = THIS_DIR / "bahis_agent.db"

EXPORTS_DIR.mkdir(exist_ok=True)


# Bazı büyük tabloları export hariç tut (cache vs.)
SKIP_TABLES = {"sqlite_sequence", "api_calls"}


def get_tables(conn):
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    return [r[0] for r in rows if r[0] not in SKIP_TABLES and not r[0].startswith("sqlite_")]


def export_csv(target_table: str = None):
    """Tüm tabloları (veya tek tablo) ayrı CSV dosyalarına yaz."""
    date_str = datetime.now().strftime("%Y%m%d_%H%M")
    out_dir = EXPORTS_DIR / f"csv_{date_str}"
    out_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    tables = [target_table] if target_table else get_tables(conn)
    print(f"\n[CSV Export] {len(tables)} tablo -> {out_dir}")

    total = 0
    for t in tables:
        try:
            df = pd.read_sql_query(f"SELECT * FROM {t}", conn)
            out_file = out_dir / f"{t}.csv"
            df.to_csv(out_file, index=False, encoding="utf-8-sig")
            size_kb = out_file.stat().st_size / 1024
            print(f"  {t:<25s} {len(df):>8,} satir  {size_kb:>8.0f} KB")
            total += len(df)
        except Exception as e:
            print(f"  {t:<25s} ERR: {e}")
    conn.close()
    print(f"\n[OK] {len(tables)} tablo, {total:,} satir CSV: {out_dir}")
    return out_dir


def export_excel(target_table: str = None):
    """Tüm tablolar tek Excel dosyasında, ayrı sheet'ler."""
    date_str = datetime.now().strftime("%Y%m%d_%H%M")
    out_file = EXPORTS_DIR / f"bahis_agent_{date_str}.xlsx"

    conn = sqlite3.connect(DB_PATH)
    tables = [target_table] if target_table else get_tables(conn)
    print(f"\n[Excel Export] {len(tables)} tablo -> {out_file}")

    # Excel sheet name limit 31 char + sample limit
    LARGE_TABLE_LIMIT = 100_000  # >100K satır olan tablolar sample

    with pd.ExcelWriter(out_file, engine="openpyxl") as writer:
        # Manifest sheet
        manifest = []
        for t in tables:
            try:
                n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                manifest.append({"table": t, "n_rows": n,
                               "sampled": n > LARGE_TABLE_LIMIT})
            except Exception:
                pass
        pd.DataFrame(manifest).to_excel(writer, sheet_name="_MANIFEST", index=False)

        # Her tablo bir sheet
        for t in tables:
            try:
                n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                if n > LARGE_TABLE_LIMIT:
                    df = pd.read_sql_query(
                        f"SELECT * FROM {t} ORDER BY RANDOM() LIMIT ?",
                        conn, params=(LARGE_TABLE_LIMIT,)
                    )
                    print(f"  {t:<25s} SAMPLED {LARGE_TABLE_LIMIT}/{n:,}")
                else:
                    df = pd.read_sql_query(f"SELECT * FROM {t}", conn)
                    print(f"  {t:<25s} {len(df):>8,} satir")
                sheet_name = t[:31]  # Excel sheet name limit
                df.to_excel(writer, sheet_name=sheet_name, index=False)
            except Exception as e:
                print(f"  {t:<25s} ERR: {e}")

    conn.close()
    size_mb = out_file.stat().st_size / 1024 / 1024
    print(f"\n[OK] Excel: {out_file} ({size_mb:.1f} MB)")
    return out_file


def export_parquet(target_table: str = None):
    """Parquet (büyük data için en verimli format)."""
    date_str = datetime.now().strftime("%Y%m%d_%H%M")
    out_dir = EXPORTS_DIR / f"parquet_{date_str}"
    out_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    tables = [target_table] if target_table else get_tables(conn)
    print(f"\n[Parquet Export] {len(tables)} tablo -> {out_dir}")

    total = 0
    for t in tables:
        try:
            df = pd.read_sql_query(f"SELECT * FROM {t}", conn)
            out_file = out_dir / f"{t}.parquet"
            df.to_parquet(out_file, index=False, compression="snappy")
            size_kb = out_file.stat().st_size / 1024
            print(f"  {t:<25s} {len(df):>8,} satir  {size_kb:>8.0f} KB")
            total += len(df)
        except Exception as e:
            print(f"  {t:<25s} ERR: {e}")
    conn.close()
    print(f"\n[OK] Parquet: {out_dir} ({total:,} satir)")
    return out_dir


def export_all():
    """CSV + Excel + Parquet hep birden."""
    print("=" * 60)
    print("FULL EXPORT — CSV + Excel + Parquet")
    print("=" * 60)
    export_csv()
    export_excel()
    export_parquet()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("format", choices=["csv","excel","parquet","all"])
    parser.add_argument("--table", default=None,
                        help="Sadece bu tabloyu export et")
    args = parser.parse_args()

    if args.format == "csv":
        export_csv(args.table)
    elif args.format == "excel":
        export_excel(args.table)
    elif args.format == "parquet":
        export_parquet(args.table)
    elif args.format == "all":
        export_all()
