# Campus Customs MCP Server

This FastMCP server provides database-backed tools for the Campus Customs operations agents. It reads `../data/campus_customs_new.db`, the resettable working copy of the shop database. The original `../data/campus_customs.db` is never used for updates and remains untouched.

## Current tools

- `inspect_ticket_101_customer_order`: reads ticket 101, its size-specific inventory, pricing, related invoice, and invoice vendor.
- `inspect_ticket_102_rent_notice`: reads ticket 102, its lease, and `desk.date_today` to determine rent timing.
- `inspect_ticket_103_bulk_hoodie_request`: reads ticket 103, size-specific inventory, pricing, and apparel vendors to calculate the shortage and restock options.
- `list_open_tickets`: lists open tickets and the database's operational date.
- `list_tickets`: lists all training tickets and their current statuses.
- `get_checking_balance`: returns the current checking-account balance.
- `get_ticket_context`: reads a ticket and every directly linked database record.
- `find_restock_options`: derives SKU, size, and requested quantity from a ticket, then checks size-specific stock, pricing, apparel vendors, lead times, and open vendor invoices.
- `prepare_payment`: creates a database-backed payment proposal without changing records and reports whether cash and status checks permit it.
- `record_approved_payment`: records a payment only with a named human approver, sufficient cash, no duplicate payment, and an open invoice when applicable.
- `save_customer_draft`: stores an explicitly marked unsent customer-service draft in the ticket notes.
- `resolve_ticket`: changes a ticket to `resolved` with an internal resolution note.

Read tools return only database values or calculations derived directly from those values. Write tools update only the working database and never contact customers or vendors. Payment tools require human approval and refuse duplicate or unaffordable payments.

## Environment

Install the dependency from `requirements.txt` into this folder's `.venv`. The server is intentionally not started as part of this problem; a later problem will connect it to the agent backend.
