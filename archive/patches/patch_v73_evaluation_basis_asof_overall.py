from pathlib import Path

root = Path(__file__).resolve().parent
service = root / 'tracker_evaluation' / 'evaluation_service.py'
web_app = root / 'web_app.py'
page = root / 'web' / 'evaluation.html'
readme = root / 'README.md'

if not service.exists():
    raise SystemExit('tracker_evaluation/evaluation_service.py not found. Apply evaluation workflow first.')
if not web_app.exists():
    raise SystemExit('web_app.py not found.')
if not page.exists():
    raise SystemExit('web/evaluation.html not found. Apply evaluation workflow first.')

# -----------------------------------------------------------------------------
# 1) evaluation_service.py: override get_tracker_metrics with basis support.
# -----------------------------------------------------------------------------
s = service.read_text(encoding='utf-8')
if 'v0.73 evaluation basis override' not in s:
    s += r'''

# v0.73 evaluation basis override
# Supports two fair scoring bases:
# - as_of: count only tasks/projects due up to evaluation_date
# - overall: count full internship tasks/projects

def _v73_parse_date(value):
    if value is None or value == '':
        return None
    if hasattr(value, 'date'):
        return value
    try:
        return datetime.fromisoformat(str(value)[:10])
    except Exception:
        return None


def _v73_row_date(row, idx):
    try:
        return _v73_parse_date(row[idx])
    except Exception:
        return None


def _v73_due_filter(date_value, evaluation_dt, basis: str) -> bool:
    if basis == 'overall' or evaluation_dt is None:
        return True
    if date_value is None:
        return False
    return date_value.date() <= evaluation_dt.date()


def _v73_pct(done: int, planned: int) -> float:
    return done / planned if planned else 0


def get_tracker_metrics(tracker_path: str, intern_name: str, evaluation_date: str | None = None, basis: str = 'as_of') -> dict[str, Any]:
    if parse_workbook is None:
        return {}
    basis = (basis or 'as_of').lower()
    if basis not in {'as_of', 'overall'}:
        basis = 'as_of'
    evaluation_dt = _v73_parse_date(evaluation_date) or datetime.now()

    data = parse_workbook(tracker_path)
    intern = None
    for item in getattr(data, 'interns', []) or []:
        if normalize_name(item.name) == normalize_name(intern_name):
            intern = item
            break
    if not intern:
        best = None
        best_score = 0
        for item in getattr(data, 'interns', []) or []:
            sc = similarity(item.name, intern_name)
            if sc > best_score:
                best = item
                best_score = sc
        intern = best
    if not intern:
        return {}

    tasks = getattr(intern, 'tasks', []) or []
    projects = getattr(intern, 'projects', []) or []

    overall_daily_planned = len(tasks)
    overall_daily_done = sum(1 for row in tasks if len(row) > 4 and status_done(row[4]))
    overall_weekly_planned = len(projects)
    overall_weekly_done = sum(1 for row in projects if len(row) > 5 and status_done(row[5]))

    asof_tasks = [row for row in tasks if _v73_due_filter(_v73_row_date(row, 0), evaluation_dt, 'as_of')]
    asof_projects = []
    for row in projects:
        # Project layout is usually [#, title, description, assigned_date, due_date, status].
        due = _v73_row_date(row, 4)
        if due is None:
            due = _v73_row_date(row, 3)
        if _v73_due_filter(due, evaluation_dt, 'as_of'):
            asof_projects.append(row)

    asof_daily_planned = len(asof_tasks)
    asof_daily_done = sum(1 for row in asof_tasks if len(row) > 4 and status_done(row[4]))
    asof_weekly_planned = len(asof_projects)
    asof_weekly_done = sum(1 for row in asof_projects if len(row) > 5 and status_done(row[5]))

    if basis == 'overall':
        daily_planned = overall_daily_planned
        daily_done = overall_daily_done
        weekly_planned = overall_weekly_planned
        weekly_done = overall_weekly_done
    else:
        daily_planned = asof_daily_planned
        daily_done = asof_daily_done
        weekly_planned = asof_weekly_planned
        weekly_done = asof_weekly_done

    start = intern.main_row[3] if len(intern.main_row) > 3 else ''
    end = intern.main_row[4] if len(intern.main_row) > 4 else ''
    plan = getattr(intern, 'plan_name', '') or ''
    main_project = intern.main_row[0] if len(intern.main_row) > 0 else ''
    scenario = intern.scenario_row[0] if len(intern.scenario_row) > 0 else ''

    return {
        'matched_tracker_name': intern.name,
        'plan': plan,
        'start': start.strftime('%Y-%m-%d') if hasattr(start, 'strftime') else str(start or ''),
        'end': end.strftime('%Y-%m-%d') if hasattr(end, 'strftime') else str(end or ''),
        'evaluation_date': evaluation_dt.strftime('%Y-%m-%d'),
        'basis': basis,

        # Selected basis values used for scoring/writing.
        'daily_done': daily_done,
        'daily_planned': daily_planned,
        'daily_pct': _v73_pct(daily_done, daily_planned),
        'weekly_done': weekly_done,
        'weekly_planned': weekly_planned,
        'weekly_pct': _v73_pct(weekly_done, weekly_planned),
        'daily_score': band_score(daily_done, daily_planned),
        'weekly_score': band_score(weekly_done, weekly_planned),

        # Diagnostic comparison values displayed only on page.
        'asof_daily_done': asof_daily_done,
        'asof_daily_planned': asof_daily_planned,
        'asof_daily_pct': _v73_pct(asof_daily_done, asof_daily_planned),
        'asof_weekly_done': asof_weekly_done,
        'asof_weekly_planned': asof_weekly_planned,
        'asof_weekly_pct': _v73_pct(asof_weekly_done, asof_weekly_planned),
        'overall_daily_done': overall_daily_done,
        'overall_daily_planned': overall_daily_planned,
        'overall_daily_pct': _v73_pct(overall_daily_done, overall_daily_planned),
        'overall_weekly_done': overall_weekly_done,
        'overall_weekly_planned': overall_weekly_planned,
        'overall_weekly_pct': _v73_pct(overall_weekly_done, overall_weekly_planned),

        'main_project': str(main_project or ''),
        'scenario': str(scenario or ''),
    }
'''
service.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# 2) web_app.py: pass evaluation_date and basis into get_tracker_metrics.
# -----------------------------------------------------------------------------
s = web_app.read_text(encoding='utf-8')
old = "metrics = get_tracker_metrics(sess['tracker'], payload.get('intern_name',''))"
new = "metrics = get_tracker_metrics(sess['tracker'], payload.get('intern_name',''), payload.get('evaluation_date'), payload.get('basis', 'as_of'))"
if old in s:
    s = s.replace(old, new, 1)
web_app.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# 3) evaluation.html: add evaluation date + basis selector and better metrics UI.
# -----------------------------------------------------------------------------
h = page.read_text(encoding='utf-8')

# Add controls to match section if not already present.
if 'evaluation_date' not in h:
    marker = '<button onclick="loadQuestions()">Continue to Questions</button>'
    controls = r'''
    <div class="card" style="background:#f8fafc;box-shadow:none;">
      <h4>Evaluation basis</h4>
      <div class="grid">
        <label>Evaluation date<input id="evaluation_date" type="date"></label>
        <label>Scoring basis<select id="evaluation_basis"><option value="as_of">Till now / as of evaluation date</option><option value="overall">Overall full internship</option></select></label>
      </div>
      <p class="muted">Use “Till now” for ongoing internships. Use “Overall” for final evaluations after internship completion.</p>
    </div>
'''
    h = h.replace(marker, controls + '\n    ' + marker, 1)

# Append script override for loadQuestions/renderMetrics/default date.
if 'v73-evaluation-basis-override' not in h:
    script = r'''
<script id="v73-evaluation-basis-override">
function v73Today(){ const d=new Date(); return d.toISOString().slice(0,10); }
setTimeout(()=>{ const el=document.getElementById('evaluation_date'); if(el && !el.value) el.value=v73Today(); }, 100);

async function loadQuestions(){
  const evalDateEl = document.getElementById('evaluation_date');
  const basisEl = document.getElementById('evaluation_basis');
  const evaluationDate = evalDateEl && evalDateEl.value ? evalDateEl.value : v73Today();
  const basis = basisEl && basisEl.value ? basisEl.value : 'as_of';
  const r = await fetch('/api/evaluation/questions', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({session_id:sessionId, intern_name:internSelect.value, eval_sheet:selectedEvalSheet, evaluation_date:evaluationDate, basis:basis})
  });
  const d = await r.json();
  if(!d.ok){ alert(d.error); return; }
  questions = d.questions;
  trackerMetrics = d.metrics;
  qIndex = 0;
  renderMetrics();
  show('questions');
  step(3);
  renderQuestion();
}

function pct(v){ return Math.round((Number(v||0))*100) + '%'; }
function renderMetrics(){
  const basisLabel = trackerMetrics.basis === 'overall' ? 'Overall full internship' : 'Till now / as of ' + (trackerMetrics.evaluation_date || 'today');
  metrics.innerHTML = [
    ['Scoring basis', basisLabel],
    ['Selected daily', (trackerMetrics.daily_done||0)+'/'+(trackerMetrics.daily_planned||0)+' ('+pct(trackerMetrics.daily_pct)+')'],
    ['Selected weekly', (trackerMetrics.weekly_done||0)+'/'+(trackerMetrics.weekly_planned||0)+' ('+pct(trackerMetrics.weekly_pct)+')'],
    ['Daily score', trackerMetrics.daily_score],
    ['Weekly score', trackerMetrics.weekly_score],
    ['Till-now daily', (trackerMetrics.asof_daily_done||0)+'/'+(trackerMetrics.asof_daily_planned||0)+' ('+pct(trackerMetrics.asof_daily_pct)+')'],
    ['Overall daily', (trackerMetrics.overall_daily_done||0)+'/'+(trackerMetrics.overall_daily_planned||0)+' ('+pct(trackerMetrics.overall_daily_pct)+')'],
    ['Till-now weekly', (trackerMetrics.asof_weekly_done||0)+'/'+(trackerMetrics.asof_weekly_planned||0)+' ('+pct(trackerMetrics.asof_weekly_pct)+')'],
    ['Overall weekly', (trackerMetrics.overall_weekly_done||0)+'/'+(trackerMetrics.overall_weekly_planned||0)+' ('+pct(trackerMetrics.overall_weekly_pct)+')']
  ].map(x=>`<div class="metric"><span>${x[0]}</span><b>${x[1]}</b></div>`).join('');
}
</script>
'''
    h = h.replace('</body>', script + '\n</body>')

page.write_text(h, encoding='utf-8')

# Compile checks.
try:
    import py_compile
    py_compile.compile(str(service), doraise=True)
    py_compile.compile(str(web_app), doraise=True)
except Exception as e:
    raise SystemExit(f'Compile check failed: {e}')

if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.73 Evaluation basis: till-now vs overall

- Evaluation page now supports two scoring bases:
  - `Till now / as of evaluation date` for ongoing internships.
  - `Overall full internship` for final evaluations.
- Default basis is `Till now` with today as evaluation date.
- Metrics now show selected scoring values plus comparison values:
  - till-now daily/weekly completion
  - overall daily/weekly completion
- Auto-written delivery scores use the selected basis.
''', encoding='utf-8')

print('v0.73 evaluation basis patch applied successfully.')
