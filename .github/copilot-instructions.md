# Year Goals Copilot Instructions

## Overview
This is a single-user year goals + actions tracker with a serverless Python backend (AWS Lambda + API Gateway + DynamoDB) and vanilla JS frontend deployed to GitHub Pages.

## Architecture
- **Backend** (`backend/`): Python Lambda handler in `handler.py`, SAM template in `template.yaml` for deployment.
- **Frontend** (`frontend/`): Static HTML/JS/CSS, no build step.
- **Data Model**: Single DynamoDB table with PK `USER#me`, SK prefixes `GOAL#{year}#{id}`, `ACTION#{year}#{ts}#{id}`, `STATS#{year}`.
- **Auth**: X-Admin-Token header required for all API calls except health check.

## Key Patterns
- All API endpoints require `?year=2026` query param.
- Actions: `BJJ` (count), `SAVE` (amountCents), `READ` (pages, optional book).
- Goals: title, status (`todo`/`doing`/`done`), optional target.
- Stats aggregated atomically in `STATS#{year}` row using DynamoDB ADD operations.
- CORS allows only configured GitHub Pages origin.
- Frontend stores token in `localStorage`, fetches from API_BASE_URL (set in `app.js`).
- Error responses: `{"error": "message"}`.

## Deployment
- **Backend**: `cd backend && sam build && sam deploy --guided` (set AllowedOrigin to GitHub Pages URL, choose AdminToken).
- **Frontend**: Push to `main`, GitHub Actions deploys `frontend/` to Pages.
- After backend deploy, update `API_BASE_URL` in `frontend/app.js` with SAM output ApiUrl.

## Development Tips
- Test locally: Set `API_BASE_URL` to deployed backend, paste AdminToken in frontend unlock panel.
- No tests or linting configured; add if needed.
- Frontend uses vanilla JS with fetch; no frameworks.
- Backend uses boto3 (included in AWS runtime); no pip installs required.