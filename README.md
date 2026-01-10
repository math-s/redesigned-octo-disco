# Year Goals (AWS Lambda + GitHub Pages)

This repo is a **single-user** year goals + actions tracker:

- **Frontend**: static vanilla HTML/JS in `frontend/` (deploy to GitHub Pages)
- **Backend**: AWS Lambda (Python) + API Gateway HTTP API in `backend/`
- **Storage**: DynamoDB (single table)

No frontend build step, and the Lambda uses only the AWS runtime (`boto3` is included).

## Features

- **Goals per year**: add / edit / mark todo|doing|done / delete
- **Action buttons**: log:
  - **BJJ** session
  - **SAVE** (money saved)
  - **READ** (pages + optional book)
- **Dashboard**: shows yearly totals + recent actions

## Backend deployment (AWS SAM)

Prereqs:
- AWS account + credentials configured (e.g. `aws configure`)
- AWS SAM CLI installed

Deploy:

```bash
cd backend
sam build
sam deploy --guided
```

During `--guided`:
- **AllowedOrigin**: set to your GitHub Pages origin, e.g. `https://YOURUSER.github.io`
- **AdminToken**: choose a strong token (this will be required via `X-Admin-Token`)

After deploy, SAM prints an output **ApiUrl** like:
`https://abc123.execute-api.us-east-1.amazonaws.com`

### API endpoints

- `GET /health`
- `GET /stats?year=2026`
- `GET /goals?year=2026`
- `POST /goals` body `{ "year": 2026, "title": "..." }`
- `PATCH /goals/{goalId}` body `{ "year": 2026, "patch": { "status": "done" } }`
- `DELETE /goals/{goalId}?year=2026`
- `POST /actions` body examples:
  - `{ "year": 2026, "type": "BJJ" }`
  - `{ "year": 2026, "type": "SAVE", "amountCents": 1234 }`
  - `{ "year": 2026, "type": "READ", "pages": 20, "book": "..." }`
- `GET /actions?year=2026&limit=30`

All endpoints (except `OPTIONS` and `GET /health`) require header:
`X-Admin-Token: <your token>`

## Frontend (GitHub Pages)

1) Set your backend URL:
- Edit `frontend/app.js` and replace:
  - `REPLACE_WITH_YOUR_API_BASE_URL`

2) Enable GitHub Pages:
- Repo Settings → Pages → Source: **GitHub Actions**

3) Push to `main`:
- The workflow in `.github/workflows/pages.yml` deploys `frontend/` to Pages.

4) Open your Pages site and **paste your AdminToken** in the Unlock panel (stored in `localStorage`).

## Data model (DynamoDB)

Single table (created by the SAM stack):
- PK: `pk` (always `USER#me`)
- SK prefixes:
  - `GOAL#<year>#<goalId>`
  - `ACTION#<year>#<isoTs>#<actionId>`
  - `STATS#<year>` (fast counters)
