"""
Patch v0.77 - Fix weekly score source to overall weekly progress

Apply from the root of the evaluation app project:
    python patch_v77_fix_weekly_score_source_overall.py

Purpose:
- Keep the rubric and scoring method unchanged.
- Fix the bug where Weekly score is still sourced from selected/till-now weekly data.
- Weekly score should use the same scoring method, but with overall weekly progress.
- Daily score behavior is unchanged.
- Workbook remains unchanged until Finalize Evaluation is clicked.
- No intern name is hardcoded.

What this patch does:
1. Scans evaluation app source files for common weekly-score mapping mistakes.
2. Replaces only mappings where `weekly_score` is assigned from selected/till-now weekly score/basis.
3. Adds a small UI guard to the evaluation page that warns if the visible Weekly score still conflicts with visible Weekly progress.
   The guard does NOT invent a new scoring rubric. It only protects against stale selected/till-now values being displayed.
4. Writes a report: v77_weekly_score_source_patch_report.txt
"""
from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
REPORT = ROOT / "v77_weekly_score_source_patch_report.txt"

TEXT_EXTS = {".py", ".js", ".html", ".jinja", ".jinja2", ".ts"}
EXCLUDE_PARTS = {"__pycache__", ".git", ".venv", "venv", "env", "node_modules"}
EXCLUDE_PREFIXES = ("patch_v",)

replacements: list[tuple[str, str, str]] = [
    # Python direct score variable mapping
    (r"weekly_score\s*=\s*selected_weekly_score", "weekly_score = overall_weekly_score", "weekly_score from selected_weekly_score"),
    (r"weekly_score\s*=\s*till_now_weekly_score", "weekly_score = overall_weekly_score", "weekly_score from till_now_weekly_score"),
    (r"weekly_score\s*=\s*weekly_selected_score", "weekly_score = overall_weekly_score", "weekly_score from weekly_selected_score"),
    (r"weekly_score\s*=\s*weekly_till_now_score", "weekly_score = overall_weekly_score", "weekly_score from weekly_till_now_score"),

    # Python dict mappings
    (r"(['\"]weekly_score['\"]\s*:\s*)selected_weekly_score", r"\1overall_weekly_score", "dict weekly_score from selected_weekly_score"),
    (r"(['\"]weekly_score['\"]\s*:\s*)till_now_weekly_score", r"\1overall_weekly_score", "dict weekly_score from till_now_weekly_score"),
    (r"(['\"]weekly_score['\"]\s*:\s*)weekly_selected_score", r"\1overall_weekly_score", "dict weekly_score from weekly_selected_score"),
    (r"(['\"]weekly_score['\"]\s*:\s*)weekly_till_now_score", r"\1overall_weekly_score", "dict weekly_score from weekly_till_now_score"),

    # Python score function called with selected/till-now counts
    (r"weekly_score\s*=\s*([A-Za-z_][A-Za-z0-9_]*score[A-Za-z0-9_]*\()\s*selected_weekly_completed\s*,\s*selected_weekly_total\s*\)", r"weekly_score = \1overall_weekly_completed, overall_weekly_total)", "weekly_score function from selected_weekly counts"),
    (r"weekly_score\s*=\s*([A-Za-z_][A-Za-z0-9_]*score[A-Za-z0-9_]*\()\s*till_now_weekly_completed\s*,\s*till_now_weekly_total\s*\)", r"weekly_score = \1overall_weekly_completed, overall_weekly_total)", "weekly_score function from till_now_weekly counts"),

    # Common camelCase JS variable mappings
    (r"weeklyScore\s*=\s*selectedWeeklyScore", "weeklyScore = overallWeeklyScore", "JS weeklyScore from selectedWeeklyScore"),
    (r"weeklyScore\s*=\s*tillNowWeeklyScore", "weeklyScore = overallWeeklyScore", "JS weeklyScore from tillNowWeeklyScore"),
    (r"(weeklyScore\s*:\s*)selectedWeeklyScore", r"\1overallWeeklyScore", "JS object weeklyScore from selectedWeeklyScore"),
    (r"(weeklyScore\s*:\s*)tillNowWeeklyScore", r"\1overallWeeklyScore", "JS object weeklyScore from tillNowWeeklyScore"),

    # Snake-case JS mappings
    (r"weekly_score\s*=\s*selected_weekly_score", "weekly_score = overall_weekly_score", "JS weekly_score from selected_weekly_score"),
    (r"weekly_score\s*=\s*till_now_weekly_score", "weekly_score = overall_weekly_score", "JS weekly_score from till_now_weekly_score"),
    (r"(weekly_score\s*:\s*)selected_weekly_score", r"\1overall_weekly_score", "JS object weekly_score from selected_weekly_score"),
    (r"(weekly_score\s*:\s*)till_now_weekly_score", r"\1overall_weekly_score", "JS object weekly_score from till_now_weekly_score"),
]

report_lines: list[str] = []
changed_files: list[Path] = []


def should_scan(path: Path) -> bool:
    if path.suffix.lower() not in TEXT_EXTS:
        return False
    if any(part in EXCLUDE_PARTS for part in path.parts):
        return False
    if path.name.startswith(EXCLUDE_PREFIXES):
        return False
    if path.name == REPORT.name:
        return False
    return True


for path in ROOT.rglob("*"):
    if not path.is_file() or not should_scan(path):
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue

    original = text
    file_changes: list[str] = []
    for pattern, repl, desc in replacements:
        text2, count = re.subn(pattern, repl, text)
        if count:
            text = text2
            file_changes.append(f"- {desc}: {count} replacement(s)")

    if text != original:
        backup = path.with_suffix(path.suffix + ".v77.bak")
        if not backup.exists():
            backup.write_text(original, encoding="utf-8")
        path.write_text(text, encoding="utf-8")
        changed_files.append(path)
        report_lines.append(f"UPDATED: {path.relative_to(ROOT)}")
        report_lines.extend(file_changes)
        report_lines.append("")

# Add UI diagnostic/guard to evaluation.html. The guard does not change rubric.
# It only warns if the source mapping still appears inconsistent after source patching.
PAGE_CANDIDATES = [
    ROOT / "web" / "evaluation.html",
    ROOT / "evaluation.html",
    ROOT / "templates" / "evaluation.html",
]
page = next((p for p in PAGE_CANDIDATES if p.exists()), None)
if page:
    html = page.read_text(encoding="utf-8")
    guard = r'''

<!-- v0.77 weekly score source guard: overall weekly should feed weekly score -->
<style id="v77-weekly-source-guard-style">
  .v77-weekly-source-warning {
    border: 1px solid #f59e0b;
    background: #fffbeb;
    color: #92400e;
    padding: 10px 12px;
    border-radius: 10px;
    margin: 10px 0;
    font-size: 13px;
  }
</style>
<script id="v77-weekly-source-guard-script">
(function(){
  function norm(t){ return String(t || '').replace(/\s+/g, ' ').trim().toLowerCase(); }
  function txt(el){ return String((el && el.textContent) || '').trim(); }
  function parseProgress(value){
    const m = String(value || '').match(/(\d+)\s*\/\s*(\d+)\s*\(\s*(\d+)%\s*\)/);
    if (!m) return null;
    return {done:Number(m[1]), total:Number(m[2]), pct:Number(m[3])};
  }
  function findValueAfterLabel(labelText){
    const all = Array.from(document.querySelectorAll('body *'));
    for (const el of all) {
      const own = Array.from(el.childNodes).filter(n => n.nodeType === Node.TEXT_NODE).map(n => n.textContent).join(' ').trim();
      if (norm(own) === norm(labelText) || norm(el.textContent) === norm(labelText)) {
        const row = el.closest('tr, .row, .score-row, .basis-row, .field-row, li, p, div');
        if (row) {
          const m = txt(row).match(/\d+\s*\/\s*\d+\s*\(\s*\d+%\s*\)/);
          if (m) return m[0];
          const score = txt(row).match(/\b[0-5]\b/);
          if ((labelText || '').toLowerCase().includes('score') && score) return score[0];
        }
        let next = el.nextElementSibling;
        let guard = 0;
        while (next && guard < 4) {
          const t = txt(next);
          const pm = t.match(/\d+\s*\/\s*\d+\s*\(\s*\d+%\s*\)/);
          if (pm) return pm[0];
          if ((labelText || '').toLowerCase().includes('score')) {
            const sm = t.match(/\b[0-5]\b/);
            if (sm) return sm[0];
          }
          next = next.nextElementSibling;
          guard++;
        }
      }
    }
    return '';
  }
  function removeOldWarnings(){
    document.querySelectorAll('.v77-weekly-source-warning').forEach(el => el.remove());
  }
  function addWarning(message){
    removeOldWarnings();
    const box = document.createElement('div');
    box.className = 'v77-weekly-source-warning';
    box.textContent = message;
    const target = Array.from(document.querySelectorAll('body *')).find(el => norm(el.textContent) === 'scoring basis') || document.querySelector('main') || document.body;
    if (target.parentElement) target.parentElement.insertBefore(box, target.nextSibling);
    else document.body.insertBefore(box, document.body.firstChild);
  }
  function guardWeeklyScoreSource(){
    const weeklyProgressText = findValueAfterLabel('Weekly progress') || findValueAfterLabel('Overall weekly');
    const weeklyScoreText = findValueAfterLabel('Weekly score');
    const progress = parseProgress(weeklyProgressText);
    const score = Number(String(weeklyScoreText || '').match(/\b[0-5]\b/)?.[0] || NaN);
    // This guard does not alter the score because the rubric must remain unchanged.
    // It only detects the exact stale-source bug: non-zero/high overall weekly progress but score remains 0.
    if (progress && progress.total > 0 && progress.pct >= 70 && score === 0) {
      addWarning('Weekly score appears to be using old selected/till-now weekly data instead of overall weekly progress. Apply/verify v0.77 backend/source mapping replacements.');
    } else {
      removeOldWarnings();
    }
  }
  document.addEventListener('DOMContentLoaded', guardWeeklyScoreSource);
  setTimeout(guardWeeklyScoreSource, 200);
  setTimeout(guardWeeklyScoreSource, 800);
  const mo = new MutationObserver(function(){
    clearTimeout(window.__v77WeeklySourceGuardTimer);
    window.__v77WeeklySourceGuardTimer = setTimeout(guardWeeklyScoreSource, 100);
  });
  mo.observe(document.documentElement, {childList:true, subtree:true});
})();
</script>
'''
    if "v77-weekly-source-guard-script" not in html:
        if "</body>" in html:
            html = html.replace("</body>", guard + "\n</body>", 1)
        else:
            html += guard
        page.write_text(html, encoding="utf-8")
        report_lines.append(f"UPDATED: {page.relative_to(ROOT)}")
        report_lines.append("- Added weekly score source guard/warning script")
        report_lines.append("")

if not report_lines:
    report_lines.append("No source mapping replacements were applied.")
    report_lines.append("This means the weekly_score mapping uses different variable names or is generated server-side in code not matched by this generic patch.")
    report_lines.append("Search manually for weekly_score / weeklyScore and verify it uses overall_weekly, not selected/till_now weekly.")

REPORT.write_text("\n".join(report_lines), encoding="utf-8")

print("v0.77 patch completed.")
print(f"Changed files: {len(changed_files)}")
print(f"Report: {REPORT}")
for line in report_lines[:20]:
    print(line)
