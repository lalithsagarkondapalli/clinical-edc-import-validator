"""Regenerate the synthetic DM site-upload workbook.

The workbook is committed so the pipeline runs without this script; it exists so
reviewers can see exactly what is in the binary file (and which errors are seeded).
"""
from pathlib import Path

from openpyxl import Workbook

ROWS = [
    # SUBJID,   SITE,  BIRTH_DATE,    SEX,      RACE                          seeded issue
    ("S01-001", "S01", "1968-04-12", "M", "WHITE"),
    ("S01-002", "S01", "03/22/1971", "Female", "BLACK OR AFRICAN AMERICAN"),  # US date -> ISO
    ("S01-003", "S01", "19750809", "F", "ASIAN"),                           # compact date -> ISO
    ("S01-004", "S01", "02-Jan-1980", "Male", "WHITE"),                     # DD-Mon-YYYY -> ISO
    ("S02-001", "S02", "1962-11-30", "M", ""),
    ("S02-002", "S02", "1959-06-05", "F", "WHITE"),
    ("S02-003", "S02", "1970-01-15", "X", "WHITE"),                         # invalid codelist value
    ("S03-001", "S03", "1966-07-21", "M", "ASIAN"),
    ("S03-002", "S03", "", "F", "WHITE"),                                    # missing required
    ("S01-002", "S01", "03/22/1971", "Female", "BLACK OR AFRICAN AMERICAN"),  # duplicate key
    ("S03-003", "S02", "1981-09-09", "F", "WHITE"),                         # site/subject mismatch
]

def main() -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "DM"
    ws.append(["SUBJID", "SITE", "BIRTH_DATE", "SEX", "RACE"])
    for row in ROWS:
        ws.append(list(row))
    out = Path(__file__).resolve().parents[1] / "data/source/CARD301_DM_site_upload.xlsx"
    wb.save(out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
