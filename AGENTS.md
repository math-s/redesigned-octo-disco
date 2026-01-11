# AGENTS.md

Practical notes for coding agents working in this repository.

## Repository overview

- **Frontend**: static vanilla HTML/JS/CSS in `frontend/` (deployed to GitHub Pages).
- **Backend**: AWS Lambda (Python 3.12) behind API Gateway HTTP API in `backend/`.
- **Storage**: DynamoDB single-table design (created by SAM stack).

There is **no frontend build step** and the Lambda runtime intentionally relies on the AWS-provided runtime libraries (e.g. `boto3` is available in Lambda).

## Quick start (backend)

CI runs on **Python 3.12**.

Install dev dependencies:

```bash
python3 -m pip install -r backend/requirements-dev.txt
```

Run lint:

```bash
cd backend
python3 -m ruff check .
```

Run unit tests:

```bash
cd backend
python3 -m pytest -q
```

## Frontend workflow

- Edit `frontend/index.html`, `frontend/app.js`, `frontend/styles.css`.
- GitHub Pages publishes the `frontend/` directory as-is (see `.github/workflows/pages.yml`).
- To point the UI at your API, update the placeholder base URL in `frontend/app.js` (see `README.md`).

## API + deployment notes (AWS SAM)

Deployment is done via AWS SAM from `backend/`:

```bash
cd backend
sam build
sam deploy --guided
```

Important parameters (see `backend/template.yaml`):
- **AllowedOrigin**: CORS allow-list origin for your Pages site.
- **AdminToken**: compared against the `X-Admin-Token` header (leave empty only for local testing).

Local SAM testing (optional, requires SAM CLI):

```bash
cd backend
sam build
sam local start-api
```

## Codebase map (backend)

- `backend/handler.py`: Lambda entrypoint.
- `backend/app/router.py`: request dispatch by method + path.
- `backend/app/routes/`: route handlers (`goals`, `actions`, `stats`, `books`).
- `backend/app/models.py`: data shapes / helpers.
- `backend/app/db.py`: DynamoDB access.
- `backend/tests/`: pytest unit tests.

## Change guidelines (agent guardrails)

- **Match CI**: prefer changes that keep `python -m ruff check .` and `python -m pytest -q` passing under `backend/`.
- **No secrets**: never add tokens/credentials to the repo; treat `AdminToken` as secret.
- **Avoid deploy side effects**: don’t run real AWS deploys unless explicitly requested; prefer unit tests/local execution.
- **Keep diffs focused**: minimize unrelated reformatting and keep changes scoped to the task.

