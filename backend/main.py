"""FastAPI control plane for the Campus Customs operations dashboard."""

import json
import shutil
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    from .audit import AUDIT_PATH, append_record
    from .agent import run_operations
    from .mcp_client import ShopMCPClient
except ImportError:  # Supports `uvicorn main:app` from inside backend/.
    from audit import AUDIT_PATH, append_record
    from agent import run_operations
    from mcp_client import ShopMCPClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_DATABASE = PROJECT_ROOT / "data" / "campus_customs.db"
WORKING_DATABASE = PROJECT_ROOT / "data" / "campus_customs_new.db"

app = FastAPI(title="Campus Customs Operations API", version="1.0.0")
shop_mcp = ShopMCPClient()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunTicketRequest(BaseModel):
    human_approvals: dict[int, str] = Field(default_factory=dict)


class PaymentApprovalRequest(BaseModel):
    ticket_id: int
    approved_by: str = Field(min_length=1, max_length=120)


def _read_events(limit: int) -> list[dict]:
    if not AUDIT_PATH.exists():
        return []
    try:
        events = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Audit trail is not valid JSON") from exc
    if not isinstance(events, list):
        raise HTTPException(status_code=500, detail="Audit trail must be a JSON array")
    return events[-limit:]


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/tickets")
async def tickets() -> dict:
    """Return all training tickets and their current open/resolved status."""
    return await shop_mcp.call("list_tickets")


@app.post("/api/tickets/{ticket_id}/run")
async def run_ticket(ticket_id: int, request: RunTicketRequest | None = None) -> dict:
    """Run the bounded agent team for one ticket."""
    try:
        result = await run_operations(
            ticket_id=ticket_id,
            human_approvals=request.human_approvals if request else {},
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return result.model_dump(mode="json")


@app.get("/api/events")
async def events(limit: int = Query(default=100, ge=1, le=500)) -> dict:
    """Return recent agent steps, decisions, delegation, and MCP tool events."""
    return {"events": _read_events(limit)}


@app.get("/api/tickets/{ticket_id}/payment-preview")
async def payment_preview(ticket_id: int) -> dict:
    """Show a database-backed payment proposal before the human approves it."""
    try:
        return await shop_mcp.call("prepare_payment", {"ticket_id": ticket_id})
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/approvals/payment")
async def approve_payment(request: PaymentApprovalRequest) -> dict:
    """Execute a payment only after a human approval reaches this route."""
    if request.approved_by.strip().lower() in {"agent", "ai", "automatic"}:
        raise HTTPException(status_code=400, detail="approved_by must identify a human approver")
    try:
        result = await shop_mcp.call(
            "record_approved_payment",
            {"ticket_id": request.ticket_id, "approved_by": request.approved_by.strip()},
        )
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    append_record(
        event="human_payment_approval",
        tool_name="record_approved_payment",
        ticket_id=request.ticket_id,
        arguments={"approved_by": request.approved_by.strip()[:120]},
        stop_reason="payment_recorded",
    )
    return result


@app.get("/api/cash")
async def cash() -> dict:
    """Return the current checking balance through MCP."""
    return await shop_mcp.call("get_checking_balance")


@app.post("/api/reset")
async def reset_database() -> dict[str, str]:
    """Restore the working database from the untouched original seed database."""
    if not ORIGINAL_DATABASE.exists():
        raise HTTPException(status_code=500, detail="Original database is missing")
    shutil.copy2(ORIGINAL_DATABASE, WORKING_DATABASE)
    append_record(
        event="database_reset",
        arguments={"source": "data/campus_customs.db", "target": "data/campus_customs_new.db"},
        stop_reason="restored_seed_copy",
    )
    return {"status": "reset", "working_database": "data/campus_customs_new.db"}
