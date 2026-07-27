"""
Patch v0.74 - Generic tracker scoring

Apply from the root of the evaluation app project:
    python patch_v74_generic_scoring.py

What it does:
- Adds tracker_evaluation/generic_tracker_scoring_engine.py
- Replaces/overrides get_tracker_metrics(...) in tracker_evaluation/evaluation_service.py
- Keeps logic intern-agnostic: no Bilal/Ume/Haris/Murtaza/Hassan hardcoding
- Counts daily and weekly metrics from the selected intern's sheet only
- Derives weekly due dates from daily tasks by week when weekly due dates are blank
"""
from __future__ import annotations

from pathlib import Path
import shutil
import textwrap

ROOT = Path(__file__).resolve().parent
SERVICE_CANDIDATES = [
    ROOT / "tracker_evaluation" / "evaluation_service.py",
    ROOT / "evaluation_service.py",
]

service = next((p for p in SERVICE_CANDIDATES if p.exists()), None)
if service is None:
    raise SystemExit("Could not find evaluation_service.py. Run this patch from the evaluation app root folder.")

pkg_dir = service.parent
engine_src = ROOT / "generic_tracker_scoring_engine.py"
engine_dst = pkg_dir / "generic_tracker_scoring_engine.py"

if not engine_src.exists():
    raise SystemExit("generic_tracker_scoring_engine.py must be in the same folder as this patch script.")

shutil.copy2(engine_src, engine_dst)

s = service.read_text(encoding="utf-8")

# Make sure needed typing symbols are available for projects that use annotations.
if "from typing import" not in s:
    s = "from typing import Any\n" + s
elif "Any" not in s.split("from typing import", 1)[1].split("\n", 1)[0]:
    s = s.replace("from typing import ", "from typing import Any, ", 1)

# Import the generic engine using package-relative import first, with script fallback.
import_block = """
# v0.74 generic scoring imports
try:
    from .generic_tracker_scoring_engine import calculate_metrics as _v74_calculate_metrics
except Exception:
    from generic_tracker_scoring_engine import calculate_metrics as _v74_calculate_metrics
"""
if "_v74_calculate_metrics" not in s:
    s += "\n" + import_block + "\n"

# Append override rather than trying to surgically edit unknown previous versions.
# In Python, the later function definition with the same name wins.
override = r'''

# v0.74 generic tracker scoring override
# NOTE: This intentionally contains no intern-name hardcoding.
def get_tracker_metrics(tracker_path: str, intern_name: str, evaluation_date: str | None = None, basis: str = "as_of") -> dict[str, Any]:
    """Return selected, till-now, and overall metrics for the selected intern.

    - Uses exact normalized sheet matching. It does not silently switch to another intern.
    - Finds sections and columns by headings, not fixed rows.
    - For weekly projects with blank due dates, derives the due date from the max daily task date in the same week.
    - `basis` controls the selected scoring fields only: "as_of" or "overall".
    """
    from datetime import datetime

    eval_date = evaluation_date or datetime.now().strftime("%Y-%m-%d")
    basis = (basis or "as_of").lower()
    if basis not in {"as_of", "overall"}:
        basis = "as_of"

    m = _v74_calculate_metrics(tracker_path, intern_name, eval_date)

    if basis == "overall":
        daily_done = m.overall_daily_done
        daily_planned = m.overall_daily_planned
        daily_pct = m.overall_daily_pct
        daily_score = m.overall_daily_score
        weekly_done = m.overall_weekly_done
        weekly_planned = m.overall_weekly_planned
        weekly_pct = m.overall_weekly_pct
        weekly_score = m.overall_weekly_score
    else:
        daily_done = m.till_now_daily_done
        daily_planned = m.till_now_daily_planned
        daily_pct = m.till_now_daily_pct
        daily_score = m.till_now_daily_score
        weekly_done = m.till_now_weekly_done
        weekly_planned = m.till_now_weekly_planned
        weekly_pct = m.till_now_weekly_pct
        weekly_score = m.till_now_weekly_score

    return {
        "matched_tracker_name": m.intern_name,
        "sheet_name": m.sheet_name,
        "evaluation_date": m.evaluation_date,
        "basis": basis,

        # Selected basis values used by scoring UI/workbook writer.
        "daily_done": daily_done,
        "daily_planned": daily_planned,
        "daily_pct": daily_pct,
        "daily_score": daily_score,
        "weekly_done": weekly_done,
        "weekly_planned": weekly_planned,
        "weekly_pct": weekly_pct,
        "weekly_score": weekly_score,

        # Daily diagnostics.
        "selected_daily_done": m.selected_daily_done,
        "selected_daily_planned": m.selected_daily_planned,
        "selected_daily_pct": m.selected_daily_pct,
        "selected_daily_score": m.selected_daily_score,
        "asof_daily_done": m.till_now_daily_done,
        "asof_daily_planned": m.till_now_daily_planned,
        "asof_daily_pct": m.till_now_daily_pct,
        "overall_daily_done": m.overall_daily_done,
        "overall_daily_planned": m.overall_daily_planned,
        "overall_daily_pct": m.overall_daily_pct,

        # Weekly diagnostics.
        "asof_weekly_done": m.till_now_weekly_done,
        "asof_weekly_planned": m.till_now_weekly_planned,
        "asof_weekly_pct": m.till_now_weekly_pct,
        "overall_weekly_done": m.overall_weekly_done,
        "overall_weekly_planned": m.overall_weekly_planned,
        "overall_weekly_pct": m.overall_weekly_pct,
        "weekly_projects_without_due_basis": m.weekly_projects_without_due_basis,
    }
'''

if "v0.74 generic tracker scoring override" not in s:
    s += override + "\n"

service.write_text(s, encoding="utf-8")

# Optional README note.
readme = ROOT / "README.md"
if readme.exists() and "v0.74 Generic tracker scoring" not in readme.read_text(encoding="utf-8", errors="ignore"):
    readme.write_text(readme.read_text(encoding="utf-8", errors="ignore") + textwrap.dedent("""

    ## v0.74 Generic tracker scoring

    This patch replaces intern-specific or fixed-row tracker scoring with a generic engine.
    The engine discovers intern tracker sheets, detects sections by headings, detects columns by header labels,
    and calculates selected-date, till-now, and overall daily/weekly metrics for the selected intern only.
    """), encoding="utf-8")

print("v0.74 generic scoring patch applied successfully.")
print(f"Updated: {service}")
print(f"Added:   {engine_dst}")
