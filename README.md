# Campus Customs Operations Desk

This repository contains the Campus Customs multi-agent operations project:

- a FastMCP server backed by SQLite;
- a FastAPI control plane for the agent team and human approvals; and
- a React/Vite dashboard for watching ticket work.

The original shop database is `data/campus_customs.db`. The application reads and
writes only the resettable working copy, `data/campus_customs_new.db`. Both files
are intentionally included in this repository so the project can be run and
graded without reconstructing the seed data. Never modify the original database.

## Configuration

Copy `.env.example` to `.env` in this project root and put the Portkey key in it:

```text
PORTKEY_API_KEY=your_portkey_api_key
```

The real `.env` is ignored by Git. The agent uses the Portkey-backed
`gpt-6-luna` model, as required by the assignment.

## Install dependencies

Create the local virtual environments if they do not already exist:

```powershell
py -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r requirements.txt

py -m venv mcp_server\.venv
mcp_server\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Install the dashboard dependencies:

```powershell
cd frontend
npm install
cd ..
```

The virtual environments and `node_modules` are local-only and are not committed.

## Start the MCP server

FastMCP runs over stdio for local tool clients. In a terminal, run:

```powershell
cd mcp_server
.\.venv\Scripts\Activate.ps1
python server.py
```

The project-root `.mcp.json` also describes the local MCP connection used by MCP
clients. The server always uses `../data/campus_customs_new.db`.

## Start the FastAPI backend

In a separate terminal:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn main:app --reload --port 8000
```

The API is available at `http://localhost:8000`. The React origin
`http://localhost:5173` is allowed by CORS.

## Start the React board

In a third terminal:

```powershell
cd frontend
npm run dev
```

Open the Vite URL, normally `http://localhost:5173`.

## Reset before a full three-ticket run

Always reset the working database before collecting a fresh run. The reset route
copies the untouched original over the working copy and leaves the append-only
audit trail intact:

```powershell
Invoke-RestMethod -Method Post http://localhost:8000/api/reset
```

The equivalent direct file operation, when the backend is stopped, is:

```powershell
Copy-Item data\campus_customs.db data\campus_customs_new.db -Force
```

After resetting, confirm the checking balance and ticket statuses on the board.
Run tickets 102, 101, and 103 from the dashboard, approve a payment only when a
human approval card is shown, and verify the ending balance against the working
database. Customer and vendor communications remain drafts; nothing is sent to
external parties.

## Useful routes

- `GET /api/health` — health check.
- `GET /api/tickets` — ticket data and current status.
- `POST /api/tickets/{ticket_id}/run` — run the bounded agent team.
- `GET /api/events?limit=100` — recent audit and agent events.
- `GET /api/tickets/{ticket_id}/payment-preview` — show a proposed payment.
- `POST /api/approvals/payment` — record a human-approved payment.
- `GET /api/cash` — current checking balance.
- `POST /api/reset` — restore the working database from the original.

## Evidence

The `output/` directory contains the harness, design documentation, MCP smoke
evidence, append-only audit trail, ticket plans/results, and dashboard evidence.
