from pathlib import Path

root = Path(".")

# --------------------------
# Dockerfile
# --------------------------

dockerfile = """
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "web_app:app", "--host", "0.0.0.0", "--port", "8000"]
""".strip()

(root / "Dockerfile").write_text(dockerfile, encoding="utf-8")

# --------------------------
# .dockerignore
# --------------------------

dockerignore = """
__pycache__/
*.pyc
*.pyo

.git/
.vscode/

archive/

patch_v*.py

*.bak
*.tmp

venv/
.venv/

.env

outputs/
""".strip()

(root / ".dockerignore").write_text(dockerignore, encoding="utf-8")

print("[OK] Dockerfile created")
print("[OK] .dockerignore created")
print("[OK] Docker setup completed")