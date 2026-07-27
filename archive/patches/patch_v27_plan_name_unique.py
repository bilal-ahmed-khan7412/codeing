from pathlib import Path

root = Path(__file__).resolve().parent
chat_service = root / 'tracker_chat' / 'chat_service.py'
plan_service = root / 'tracker_services' / 'plan_service.py'
chat_html = root / 'web' / 'chat.html'
readme = root / 'README.md'

if not chat_service.exists():
    raise SystemExit('tracker_chat/chat_service.py not found. Run this patch inside intern_tracker_system_v0.')
if not plan_service.exists():
    raise SystemExit('tracker_services/plan_service.py not found. Run this patch inside intern_tracker_system_v0.')

# -----------------------------------------------------------------------------
# 1) ChatService: better plan name extraction and topic fallback for Deep Learning.
# -----------------------------------------------------------------------------
s = chat_service.read_text(encoding='utf-8')

old = """        if 'infosec' in lower or 'information security' in lower or 'cyber security' in lower or 'cybersecurity' in lower:\n            return 'Information Security Foundation'\n        if 'soc' in lower and 'plan' in lower:\n            return 'SOC Analyst Foundation'\n        if 'kubernetes' in lower or 'k8s' in lower:\n            return 'Kubernetes Foundation'\n"""
new = """        if 'infosec' in lower or 'information security' in lower or 'cyber security' in lower or 'cybersecurity' in lower:\n            return 'Information Security Foundation'\n        if 'deep learning' in lower or 'deeplearning' in lower:\n            return 'Deep Learning Foundation'\n        if 'machine learning' in lower or ' ml ' in f' {lower} ':\n            return 'Machine Learning Foundation'\n        if 'ai ' in f' {lower} ' or 'artificial intelligence' in lower:\n            return 'AI Foundation'\n        if 'soc' in lower and 'plan' in lower:\n            return 'SOC Analyst Foundation'\n        if 'kubernetes' in lower or 'k8s' in lower:\n            return 'Kubernetes Foundation'\n"""
if old in s:
    s = s.replace(old, new)
else:
    print('Warning: topic name block not matched. Continuing with other fixes.')

# Replace generic "create an X plan" extraction to strip duration words like "8 week".
old = """        m2 = re.search(r'create\\s+(?:an?|the)?\\s*([A-Za-z0-9 ._+-]+?)\\s+plan', text, re.I)\n        if m2:\n            topic = m2.group(1).strip().rstrip('.')\n            if topic and topic.lower() not in {'week', 'weeks', '8 week', 'eight week'}:\n                return topic.title() + ' Foundation'\n        return None\n"""
new = """        m2 = re.search(r'(?:create|make|draft|generate|build)\\s+(?:an?|the)?\\s*([A-Za-z0-9 ._+-]+?)\\s+plan', text, re.I)\n        if m2:\n            topic = m2.group(1).strip().rstrip('.')\n            # Remove duration/level filler from topic, e.g. "8 week Deep learning" -> "Deep learning".\n            topic = re.sub(r'^(?:\\d+|one|two|three|four|five|six|seven|eight|nine|ten)\\s*-?\\s*weeks?\\s+', '', topic, flags=re.I).strip()\n            topic = re.sub(r'^(?:beginner|intermediate|advanced)\\s+', '', topic, flags=re.I).strip()\n            if topic and topic.lower() not in {'week', 'weeks', 'plan'}:\n                if topic.lower().replace(' ', '') == 'deeplearning':\n                    return 'Deep Learning Foundation'\n                return topic.title() + ' Foundation'\n        return None\n"""
if old in s:
    s = s.replace(old, new)
else:
    print('Warning: generic plan extraction block not matched. Continuing with other fixes.')

# Add Deep Learning fallback weeks before the generic fallback.
needle = """        elif 'security' in lower or 'infosec' in lower or 'cyber' in lower or 'soc analyst' in lower:\n            base = [\n"""
insert = """        elif 'deep learning' in lower or 'deeplearning' in lower:\n            base = [\n                ('Python, Math, and ML Refresh', 'Review Python notebooks, NumPy, Pandas, matrices, gradients, train/test splits, and model evaluation basics.', 'Build a small supervised learning baseline and document metrics.'),\n                ('Neural Network Foundations', 'Learn perceptrons, activation functions, loss functions, backpropagation intuition, and optimization basics.', 'Train a simple neural network on a tabular or image dataset.'),\n                ('Deep Learning Framework Basics', 'Practice PyTorch or TensorFlow tensors, datasets, dataloaders, model classes, training loops, and checkpoints.', 'Create a reusable training loop with validation tracking.'),\n                ('Computer Vision Fundamentals', 'Explore CNNs, image preprocessing, augmentation, transfer learning, and model evaluation.', 'Fine-tune an image classifier and summarize performance.'),\n                ('NLP and Embeddings Basics', 'Learn tokenization, embeddings, sequence models, transformer concepts, and text classification workflows.', 'Build a small text classification or embedding similarity demo.'),\n                ('Model Tuning and Experiment Tracking', 'Practice hyperparameter tuning, overfitting control, regularization, learning-rate schedules, and experiment notes.', 'Run multiple experiments and compare results in a short report.'),\n                ('Deployment and Inference Basics', 'Learn model export, inference scripts, batching, latency basics, and simple API serving patterns.', 'Create a simple inference endpoint or batch prediction script.'),\n                ('Final Deep Learning Project', 'Combine dataset preparation, model training, evaluation, and inference into a complete final demo.', 'Deliver a final model demo, metrics report, and brief technical write-up.'),\n            ]\n        elif 'security' in lower or 'infosec' in lower or 'cyber' in lower or 'soc analyst' in lower:\n            base = [\n"""
if needle in s and 'Neural Network Foundations' not in s:
    s = s.replace(needle, insert)

# If Groq returns LLM Generated Plan, force fallback name from prompt.
old = """                plan_name = data.get('plan_name') or fallback_name\n                description = data.get('description') or text\n                weeks = data.get('weeks') or []\n"""
new = """                plan_name = data.get('plan_name') or fallback_name\n                if not plan_name or plan_name.strip().lower() in {'llm generated plan', 'generated plan', 'custom plan'}:\n                    plan_name = fallback_name\n                description = data.get('description') or text\n                weeks = data.get('weeks') or []\n"""
if old in s:
    s = s.replace(old, new)

old = """                if ('infosec' in lower_text or 'information security' in lower_text or 'cybersecurity' in lower_text or 'cyber security' in lower_text) and all(x not in plan_name.lower() for x in ['security', 'infosec', 'cyber']):\n                    plan_name = 'Information Security Foundation'\n                    weeks = self._fallback_weeks(plan_name, weeks_count, 'Adjusted to Information Security based on user request.')\n"""
new = """                if ('infosec' in lower_text or 'information security' in lower_text or 'cybersecurity' in lower_text or 'cyber security' in lower_text) and all(x not in plan_name.lower() for x in ['security', 'infosec', 'cyber']):\n                    plan_name = 'Information Security Foundation'\n                    weeks = self._fallback_weeks(plan_name, weeks_count, 'Adjusted to Information Security based on user request.')\n                if ('deep learning' in lower_text or 'deeplearning' in lower_text) and 'deep learning' not in plan_name.lower():\n                    plan_name = 'Deep Learning Foundation'\n                    weeks = self._fallback_weeks(plan_name, weeks_count, 'Adjusted to Deep Learning based on user request.')\n"""
if old in s:
    s = s.replace(old, new)

chat_service.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# 2) PlanService: avoid hard failure on duplicate plan names. Auto-suffix copy.
# -----------------------------------------------------------------------------
s = plan_service.read_text(encoding='utf-8')

# Add helper if missing.
if 'def _unique_plan_name' not in s:
    helper = r'''
    def _unique_plan_name(self, data, plan_name: str) -> str:
        """Return a non-conflicting plan name by adding Copy suffix if needed."""
        base = (plan_name or 'Plan').strip()
        if not self._find_plan(data, base):
            return base
        i = 2
        while True:
            candidate = f'{base} Copy {i}'
            if not self._find_plan(data, candidate):
                return candidate
            i += 1

'''
    marker = '    def _safe_sheet_name'
    if marker in s:
        s = s.replace(marker, helper + marker)
    else:
        print('Warning: could not insert _unique_plan_name helper.')

# Patch create_plan_from_draft duplicate hard fail.
old = """        if self._find_plan(data, plan_name):\n            return CommandResult(False, f'Plan already exists: {plan_name}')\n        weeks = weeks or []\n"""
new = """        plan_name = self._unique_plan_name(data, plan_name)\n        weeks = weeks or []\n"""
if old in s:
    s = s.replace(old, new, 1)
else:
    print('Warning: create_plan_from_draft duplicate block not matched. Continuing.')

plan_service.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# 3) Chat UI: cleaner duplicate/copy wording already handled by service; no change required.
# -----------------------------------------------------------------------------
if chat_html.exists():
    hs = chat_html.read_text(encoding='utf-8')
    hs = hs.replace('LLM Generated Plan', 'AI-Drafted Plan')
    chat_html.write_text(hs, encoding='utf-8')

# README
if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.27 Plan name quality and duplicate handling

- Prompts like `create a 8 week Deep learning plan` now infer `Deep Learning Foundation` instead of `LLM Generated Plan`.
- Added topic-aware fallback weeks for Deep Learning plans.
- If a plan name already exists, creating another plan automatically uses a safe copy name such as `Deep Learning Foundation Copy 2` instead of failing.
- Generic LLM names like `LLM Generated Plan` are replaced with the inferred topic name when possible.
''', encoding='utf-8')

print('v0.27 plan name and duplicate handling patch applied successfully.')
