"""Read-only MCP tools for the Campus Customs operations tickets."""

from pathlib import Path
import sqlite3
from typing import Any

from fastmcp import FastMCP


DATABASE_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "campus_customs_new.db"
)
mcp = FastMCP("Campus Customs Operations")


def _connect() -> sqlite3.Connection:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(f"Working database not found: {DATABASE_PATH}")
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _one(connection: sqlite3.Connection, query: str, parameters: tuple[Any, ...]) -> dict[str, Any]:
    row = connection.execute(query, parameters).fetchone()
    if row is None:
        raise ValueError("The requested record was not found in the working database.")
    return dict(row)


def _many(connection: sqlite3.Connection, query: str, parameters: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(query, parameters)]


def _payment_obligation(connection: sqlite3.Connection, ticket_id: int) -> dict[str, Any]:
    ticket = _one(connection, "SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    if ticket["invoice_id"] is not None:
        invoice = _one(connection, "SELECT * FROM invoices WHERE id = ?", (ticket["invoice_id"],))
        return {"ticket": ticket, "kind": "invoice", "ref_id": invoice["id"], "amount": invoice["amount"], "invoice": invoice}
    if ticket["lease_id"] is not None:
        lease = _one(connection, "SELECT * FROM leases WHERE id = ?", (ticket["lease_id"],))
        return {"ticket": ticket, "kind": "lease", "ref_id": lease["id"], "amount": lease["monthly_rent"], "lease": lease}
    raise ValueError("This ticket has no invoice or lease obligation to pay.")


def _checking_account(connection: sqlite3.Connection) -> dict[str, Any]:
    return _one(connection, "SELECT * FROM cash_accounts WHERE name = ?", ("checking",))


@mcp.tool
def inspect_ticket_101_customer_order() -> dict[str, Any]:
    """Inspect ticket 101's tee order, stock, pricing, invoice, and vendor facts."""
    with _connect() as connection:
        ticket = _one(connection, "SELECT * FROM tickets WHERE id = ?", (101,))
        inventory = _one(
            connection,
            "SELECT * FROM inventory WHERE sku = ? AND size = ?",
            (ticket["sku"], ticket["size"]),
        )
        pricing = _one(
            connection, "SELECT * FROM pricing WHERE sku = ?", (ticket["sku"],)
        )
        invoice = _one(
            connection, "SELECT * FROM invoices WHERE id = ?", (ticket["invoice_id"],)
        )
        vendor = _one(
            connection, "SELECT * FROM vendors WHERE id = ?", (invoice["vendor_id"],)
        )
    return {
        "ticket": ticket,
        "inventory": inventory,
        "pricing": pricing,
        "invoice": invoice,
        "vendor": vendor,
        "available": inventory["qty"] >= ticket["qty"],
        "shortfall": max(ticket["qty"] - inventory["qty"], 0),
    }


@mcp.tool
def inspect_ticket_102_rent_notice() -> dict[str, Any]:
    """Inspect ticket 102's lease and compare rent timing with the shop date."""
    with _connect() as connection:
        ticket = _one(connection, "SELECT * FROM tickets WHERE id = ?", (102,))
        lease = _one(
            connection, "SELECT * FROM leases WHERE id = ?", (ticket["lease_id"],)
        )
        desk = _one(connection, "SELECT * FROM desk LIMIT 1", ())
    return {
        "ticket": ticket,
        "lease": lease,
        "desk": desk,
        "is_due_or_overdue": lease["next_due"] <= desk["date_today"],
    }


@mcp.tool
def inspect_ticket_103_bulk_hoodie_request() -> dict[str, Any]:
    """Inspect ticket 103's hoodie quantity, margin, and apparel restock options."""
    with _connect() as connection:
        ticket = _one(connection, "SELECT * FROM tickets WHERE id = ?", (103,))
        inventory = _one(
            connection,
            "SELECT * FROM inventory WHERE sku = ? AND size = ?",
            (ticket["sku"], ticket["size"]),
        )
        pricing = _one(
            connection, "SELECT * FROM pricing WHERE sku = ?", (ticket["sku"],)
        )
        vendors = [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM vendors WHERE lower(specialty) LIKE ? ORDER BY id",
                ("%apparel%",),
            )
        ]
    return {
        "ticket": ticket,
        "inventory": inventory,
        "pricing": pricing,
        "potential_apparel_vendors": vendors,
        "available": inventory["qty"] >= ticket["qty"],
        "shortfall": max(ticket["qty"] - inventory["qty"], 0),
        "unit_margin": pricing["list_price"] - pricing["unit_cost"],
    }


@mcp.tool
def list_open_tickets() -> dict[str, Any]:
    """List the current open operations tickets and the shop's operational date."""
    with _connect() as connection:
        return {
            "date_today": _one(connection, "SELECT * FROM desk LIMIT 1", ())[
                "date_today"
            ],
            "tickets": _many(
                connection,
                "SELECT * FROM tickets WHERE status = ? ORDER BY id",
                ("open",),
            ),
        }


@mcp.tool
def list_tickets() -> dict[str, Any]:
    """List all three training tickets, including their current statuses."""
    with _connect() as connection:
        return {
            "date_today": _one(connection, "SELECT * FROM desk LIMIT 1", ())["date_today"],
            "tickets": _many(connection, "SELECT * FROM tickets ORDER BY id"),
        }


@mcp.tool
def get_checking_balance() -> dict[str, Any]:
    """Return the current checking-account balance from the working database."""
    with _connect() as connection:
        return _checking_account(connection)


@mcp.tool
def get_ticket_context(ticket_id: int) -> dict[str, Any]:
    """Read a ticket and all database-backed records directly linked to it."""
    with _connect() as connection:
        ticket = _one(connection, "SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        result: dict[str, Any] = {
            "ticket": ticket,
            "desk": _one(connection, "SELECT * FROM desk LIMIT 1", ()),
        }
        if ticket["sku"] is not None:
            result["inventory"] = _many(
                connection, "SELECT * FROM inventory WHERE sku = ? ORDER BY size", (ticket["sku"],)
            )
            result["pricing"] = _one(connection, "SELECT * FROM pricing WHERE sku = ?", (ticket["sku"],))
        if ticket["lease_id"] is not None:
            result["lease"] = _one(connection, "SELECT * FROM leases WHERE id = ?", (ticket["lease_id"],))
        if ticket["invoice_id"] is not None:
            invoice = _one(connection, "SELECT * FROM invoices WHERE id = ?", (ticket["invoice_id"],))
            result["invoice"] = invoice
            result["invoice_vendor"] = _one(connection, "SELECT * FROM vendors WHERE id = ?", (invoice["vendor_id"],))
        return result


@mcp.tool
def find_restock_options(ticket_id: int) -> dict[str, Any]:
    """Use a ticket's database-backed SKU, size, and quantity to identify a restock option."""
    with _connect() as connection:
        ticket = _one(connection, "SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        sku = ticket["sku"]
        size = ticket["size"]
        required_qty = ticket["qty"]
        if sku is None or size is None or required_qty is None or required_qty < 0:
            raise ValueError("The ticket does not contain a valid product restock request.")
        stock = _one(connection, "SELECT * FROM inventory WHERE sku = ? AND size = ?", (sku, size))
        pricing = _one(connection, "SELECT * FROM pricing WHERE sku = ?", (sku,))
        vendors = _many(
            connection,
            "SELECT * FROM vendors WHERE lower(specialty) LIKE ? ORDER BY id",
            ("%apparel%",),
        )
        open_invoices = _many(
            connection,
            "SELECT * FROM invoices WHERE status = ? AND vendor_id IN (SELECT id FROM vendors WHERE lower(specialty) LIKE ?) ORDER BY id",
            ("open", "%apparel%"),
        )
    return {
        "sku": sku,
        "size": size,
        "required_qty": required_qty,
        "ticket": ticket,
        "inventory": stock,
        "pricing": pricing,
        "shortfall": max(required_qty - stock["qty"], 0),
        "vendors": vendors,
        "open_vendor_invoices": open_invoices,
        "vendor_shipping_blocked": bool(open_invoices),
    }


@mcp.tool
def prepare_payment(ticket_id: int) -> dict[str, Any]:
    """Prepare a database-backed payment proposal without changing cash or payment records."""
    with _connect() as connection:
        obligation = _payment_obligation(connection, ticket_id)
        account = _checking_account(connection)
        already_paid = connection.execute(
            "SELECT 1 FROM payments WHERE kind = ? AND ref_id = ? LIMIT 1",
            (obligation["kind"], obligation["ref_id"]),
        ).fetchone() is not None
    blocked_reason = None
    if obligation["kind"] == "invoice" and obligation["invoice"]["status"] != "open":
        blocked_reason = "The invoice is not open."
    elif already_paid:
        blocked_reason = "A payment for this obligation already exists."
    elif account["balance"] < obligation["amount"]:
        blocked_reason = "The checking account does not have enough cash."
    return {
        "ticket_id": ticket_id,
        "kind": obligation["kind"],
        "ref_id": obligation["ref_id"],
        "amount": obligation["amount"],
        "account": account,
        "human_approval_required": True,
        "can_pay": blocked_reason is None,
        "blocked_reason": blocked_reason,
    }


@mcp.tool
def record_approved_payment(ticket_id: int, approved_by: str) -> dict[str, Any]:
    """Record a human-approved payment only when the database permits it and cash stays nonnegative."""
    if not approved_by.strip() or approved_by.strip().lower() in {"agent", "ai", "automatic"}:
        raise ValueError("approved_by must identify a human approver.")
    with _connect() as connection:
        obligation = _payment_obligation(connection, ticket_id)
        account = _checking_account(connection)
        duplicate = connection.execute(
            "SELECT 1 FROM payments WHERE kind = ? AND ref_id = ? LIMIT 1",
            (obligation["kind"], obligation["ref_id"]),
        ).fetchone()
        if obligation["kind"] == "invoice" and obligation["invoice"]["status"] != "open":
            raise ValueError("The invoice is not open and cannot be paid again.")
        if duplicate is not None:
            raise ValueError("A payment for this obligation already exists.")
        if account["balance"] < obligation["amount"]:
            raise ValueError("Payment refused: the checking account would become negative.")
        paid_at = _one(connection, "SELECT date_today FROM desk LIMIT 1", ())[
            "date_today"
        ]
        new_balance = account["balance"] - obligation["amount"]
        connection.execute(
            "INSERT INTO payments(kind, ref_id, amount, account, paid_at, approved_by) VALUES (?, ?, ?, ?, ?, ?)",
            (obligation["kind"], obligation["ref_id"], obligation["amount"], account["name"], paid_at, approved_by.strip()),
        )
        connection.execute(
            "UPDATE cash_accounts SET balance = ?, date = ? WHERE name = ?",
            (new_balance, paid_at, account["name"]),
        )
        if obligation["kind"] == "invoice":
            connection.execute("UPDATE invoices SET status = ? WHERE id = ?", ("paid", obligation["ref_id"]))
        connection.commit()
    return {
        "ticket_id": ticket_id,
        "payment_recorded": True,
        "kind": obligation["kind"],
        "ref_id": obligation["ref_id"],
        "amount": obligation["amount"],
        "account": account["name"],
        "new_balance": new_balance,
        "approved_by": approved_by.strip(),
    }


@mcp.tool
def save_customer_draft(ticket_id: int, draft_message: str) -> dict[str, Any]:
    """Save a customer-service draft on the ticket without sending it externally."""
    if not draft_message.strip():
        raise ValueError("draft_message cannot be empty.")
    with _connect() as connection:
        ticket = _one(connection, "SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        marker = f"Customer-service draft (not sent): {draft_message.strip()}"
        notes = f"{ticket['notes']}\n{marker}" if ticket["notes"] else marker
        connection.execute("UPDATE tickets SET notes = ? WHERE id = ?", (notes, ticket_id))
        connection.commit()
    return {"ticket_id": ticket_id, "saved": True, "sent_externally": False, "notes": notes}


@mcp.tool
def resolve_ticket(ticket_id: int, resolution_note: str) -> dict[str, Any]:
    """Mark a ticket resolved after agents have completed their internal work."""
    if not resolution_note.strip():
        raise ValueError("resolution_note cannot be empty.")
    with _connect() as connection:
        ticket = _one(connection, "SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        notes = f"{ticket['notes']}\nResolution: {resolution_note.strip()}" if ticket["notes"] else f"Resolution: {resolution_note.strip()}"
        connection.execute("UPDATE tickets SET status = ?, notes = ? WHERE id = ?", ("resolved", notes, ticket_id))
        connection.commit()
    return {"ticket_id": ticket_id, "status": "resolved", "notes": notes}


if __name__ == "__main__":
    mcp.run()
