from pathlib import Path
import re

root = Path(__file__).resolve().parent
service = root / 'tracker_evaluation' / 'evaluation_service.py'
page = root / 'web' / 'evaluation.html'
web_app = root / 'web_app.py'
readme = root / 'README.md'

if not service.exists():
    raise SystemExit('tracker_evaluation/evaluation_service.py not found. Apply evaluation workflow first.')
if not page.exists():
    raise SystemExit('web/evaluation.html not found. Apply evaluation workflow first.')
if not web_app.exists():
    raise SystemExit('web_app.py not found.')

# -----------------------------------------------------------------------------
# 1) Evaluation service: make score suggestion rationale explicit and useful.
# -----------------------------------------------------------------------------
s = service.read_text(encoding='utf-8')
if 'v0.72 evaluation rationale override' not in s:
    s += r"""

# v0.72 evaluation rationale override
# Each answer should produce a score plus a clear reason for that score.
# If the admin edits the score, the UI marks it as "Set by user". Rationale is
# page-only and is not written to the evaluation workbook.
def _v72_compact_answer(answer: str, limit: int = 160) -> str:
    answer = ' '.join(str(answer or '').split())
    if len(answer) > limit:
        return answer[:limit].rstrip() + '...'
    return answer


def _v72_reason_for_score(criterion: str, answer: str, score: int, tracker_context: dict[str, Any]) -> str:
    ans = _v72_compact_answer(answer)
    if not ans:
        return f'No evaluator evidence was provided for {criterion}; score {score}/5 should be reviewed by the admin.'
    if score >= 5:
        return f'Score 5/5 because the evaluator answer indicates outstanding or independent performance for {criterion}: "{ans}".'
    if score == 4:
        return f'Score 4/5 because the evaluator answer indicates strong performance that exceeds expectations for {criterion}, but admin should confirm evidence before finalizing: "{ans}".'
    if score == 3:
        return f'Score 3/5 because the evaluator answer suggests the intern meets expectations for {criterion}, with no clear evidence for a higher score: "{ans}".'
    if score == 2:
        return f'Score 2/5 because the evaluator answer suggests below-expectation performance or notable support required for {criterion}: "{ans}".'
    if score == 1:
        return f'Score 1/5 because the evaluator answer suggests poor or minimal demonstration for {criterion}: "{ans}".'
    return f'Score 0/5 because there is no demonstrated evidence for {criterion} in the evaluator answer.'


def suggest_score(criterion: str, answer: str, tracker_context: dict[str, Any]) -> dict[str, Any]:
    provider = _llm_provider()
    rubric = RUBRICS.get(criterion, '')
    if provider:
        prompt = f'''
You are assisting an admin with an intern evaluation. Return ONLY JSON.
For this ONE criterion, suggest a score and explain why.
Criterion: {criterion}
Rubric: {rubric}
Tracker context: {json.dumps(tracker_context, default=str)}
Evaluator answer: {answer}

Rules:
- Score must be an integer from 0 to 5.
- Rationale must explain why this score was chosen for this criterion.
- Do not say only "Suggested from evaluator answer".
- If answer is vague, mention that evidence is limited and admin should confirm/edit.

Return shape:
{{"score": 0-5, "rationale": "specific reason for this score"}}
'''
        try:
            data = provider.complete_json(prompt)
            score = int(data.get('score', heuristic_score(answer)))
            score = max(0, min(5, score))
            rationale = str(data.get('rationale', '')).strip()
            if not rationale or rationale.lower() in {'suggested from evaluator answer.', 'suggested from evaluator answer'}:
                rationale = _v72_reason_for_score(criterion, answer, score, tracker_context)
            return {'score': score, 'rationale': rationale, 'source': 'AI suggested'}
        except Exception:
            pass
    score = heuristic_score(answer)
    rationale = _v72_reason_for_score(criterion, answer, score, tracker_context)
    return {'score': score, 'rationale': rationale, 'source': 'AI suggested'}
"""
    service.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# 2) Backend finalize: rationale/comments are page-only, not written to Excel.
# -----------------------------------------------------------------------------
s = web_app.read_text(encoding='utf-8')
# Replace finalize_evaluation call argument for comments with empty dict.
s = s.replace("payload.get('comments') or {}, payload.get('strengths',''), payload.get('development',''), payload.get('remark','')",
              "{}, payload.get('strengths',''), payload.get('development',''), payload.get('remark','')")
web_app.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# 3) Frontend review: show AI reason, mark edited scores as Set by user.
# -----------------------------------------------------------------------------
h = page.read_text(encoding='utf-8')
if 'v72 evaluation reason and user edit override' not in h:
    override = r'''
<script id="v72-evaluation-reason-user-edit">
// v72 evaluation reason and user edit override
// Rationale is page-only. It is not written to Excel.
var scoreSources = window.scoreSources || {};
window.scoreSources = scoreSources;

async function suggestScore(){
  const q = questions[qIndex];
  answers[q.criterion] = ans.value;
  const r = await fetch('/api/evaluation/suggest', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({criterion:q.criterion, answer:ans.value, metrics:trackerMetrics})
  });
  const d = await r.json();
  if(!d.ok){ alert(d.error); return; }
  finalScores[q.criterion] = d.score;
  rationales[q.criterion] = d.rationale || 'AI suggested this score from the evaluator answer.';
  scoreSources[q.criterion] = 'AI suggested';
  suggestion.innerHTML = `<div class="match-card"><b>AI suggested score:</b> ${d.score}/5<br><b>Reason:</b> ${rationales[q.criterion]}<br><button class="success" onclick="nextQuestion()">Accept AI Suggestion & Next</button><button onclick="editSuggestion()">Edit Score</button></div>`;
}

function editSuggestion(){
  const q = questions[qIndex];
  suggestion.innerHTML += `<label>Admin final score<input id="manualScore" type="number" min="0" max="5" value="${finalScores[q.criterion] ?? 0}"></label><p class="muted">If you edit the score, the page will mark this criterion as <b>Set by user</b>. The AI reason is page-only and will not be written to Excel.</p><button class="success" onclick="saveManual()">Save User Score & Next</button>`;
}

function saveManual(){
  const q = questions[qIndex];
  finalScores[q.criterion] = Number(manualScore.value || 0);
  rationales[q.criterion] = 'Set by user';
  scoreSources[q.criterion] = 'Set by user';
  nextQuestion();
}

function renderReview(){
  show('review');
  step(4);
  reviewRows.innerHTML = questions.map(q => {
    const criterion = q.criterion;
    const source = scoreSources[criterion] || 'AI suggested';
    const reason = rationales[criterion] || 'No rationale available. Admin should review/edit.';
    return `<div class="score-row" data-review-row="${criterion}">
      <div><b>${criterion}</b><p class="muted">${q.rubric}</p></div>
      <div>
        <label>Admin Final Score<input type="number" min="0" max="5" value="${finalScores[criterion] ?? 0}" data-score="${criterion}" onchange="markSetByUser('${criterion.replaceAll("'","\\'")}')"></label>
        <span class="pill" data-source="${criterion}">${source}</span>
      </div>
      <div>
        <b>Reason shown on page only</b>
        <p class="muted" data-reason="${criterion}">${reason}</p>
      </div>
    </div>`;
  }).join('');
}

function markSetByUser(criterion){
  scoreSources[criterion] = 'Set by user';
  rationales[criterion] = 'Set by user';
  const src = document.querySelector(`[data-source="${criterion}"]`);
  const reason = document.querySelector(`[data-reason="${criterion}"]`);
  if(src) src.textContent = 'Set by user';
  if(reason) reason.textContent = 'Set by user';
}

async function finalizeEval(){
  document.querySelectorAll('[data-score]').forEach(i => {
    const c = i.dataset.score;
    finalScores[c] = Number(i.value || 0);
  });
  // Do not send AI/user rationale to Excel. Keep as page-only display.
  const r = await fetch('/api/evaluation/finalize', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({
      session_id: sessionId,
      intern_name: internSelect.value,
      eval_sheet: selectedEvalSheet,
      metrics: trackerMetrics,
      scores: finalScores,
      comments: {},
      strengths: strengths.value,
      development: development.value,
      remark: remark.value
    })
  });
  const d = await r.json();
  if(!d.ok){ alert(d.error); return; }
  show('download');
  step(5);
  doneMsg.textContent = 'Evaluation workbook generated.';
  downloadLink.href = d.download;
}
</script>
'''
    h = h.replace('</body>', override + '\n</body>')
    page.write_text(h, encoding='utf-8')

# Compile checks
try:
    import py_compile
    py_compile.compile(str(service), doraise=True)
    py_compile.compile(str(web_app), doraise=True)
except Exception as e:
    raise SystemExit(f'Compile check failed: {e}')

if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.72 Evaluation rationale and user-edit display

- Each evaluation answer now shows an AI suggested score and a specific reason for that number.
- If the admin accepts the AI suggestion, the page keeps and displays the AI reason.
- If the admin edits the score, the page marks the criterion as `Set by user`.
- AI/user rationale is page-only and is not written to the evaluation workbook.
''', encoding='utf-8')

print('v0.72 evaluation rationale/user-edit patch applied successfully.')
