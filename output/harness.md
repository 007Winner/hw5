# Campus Customs Operations Harness

## Database setup

- Original database: `data/campus_customs.db`
- Working database: `data/campus_customs_new.db`
- The working database is a copy of the original. The original is kept untouched so a later run can reset the working state.
- The shop's operational date is `desk.date_today`, which is `2026-08-31` in the original data. Agents should use this value when deciding whether rent, invoices, or other obligations are overdue.

## Open-ticket map

There are three tickets whose `status` is `open`:

| Ticket | Type | Important fields and links | Operational significance |
| --- | --- | --- | --- |
| 101 | `customer_order` | `sku=CC-TEE-WHITE`, `size=S`, `qty=1`, `invoice_id=501` | The requested size has zero inventory. The invoice is for a rush reprint, so the inventory agent must check the product and vendor path while accounting checks the unpaid invoice. |
| 102 | `rent_notice` | `lease_id=1` | The facilities agent must inspect lease 1 and compare its `next_due` date with `desk.date_today`; the accounting agent may prepare a payment for human approval. |
| 103 | `price_override` | `sku=CC-HOOD-NAVY`, `size=M`, `qty=20` | The requested bulk quantity exceeds available size-M inventory. The inventory agent should determine the shortfall and vendor option, while accounting or the boss agent evaluates the discount and margin. |

### Cross-table relationships

- `tickets.sku` and `tickets.size` identify rows in `inventory`; the same `sku` identifies a row in `pricing`.
- `tickets.invoice_id` refers to `invoices.id`. `invoices.vendor_id` refers to `vendors.id`.
- `tickets.lease_id` refers to `leases.id`.
- `payments.ref_id` records the related invoice or lease reference, while `payments.account` identifies the cash account used.
- `cash_accounts.name` is the account used by payments; its balance must not become negative.
- `vendors` supplies lead times and vendor capability. An unpaid invoice can prevent a vendor from shipping new product.

## Tables and fields

### `cash_accounts`

| Field | Type | Key/constraint | Why it matters |
| --- | --- | --- | --- |
| `name` | `TEXT` | Primary key | Identifies the cash account from which approved payments are made. |
| `balance` | `REAL` | Required | The accounting agent checks this before payment and must prevent a negative balance. |
| `date` | `TEXT` | Required | Records the date associated with the account balance. |

This table is the accounting agent's source of truth for available cash.

### `desk`

| Field | Type | Key/constraint | Why it matters |
| --- | --- | --- | --- |
| `date_today` | `TEXT` | Required | Defines the shop's current date for overdue and due-date decisions. |
| `notes` | `TEXT` | Optional | Holds general operational notes for the agent team. |

This table provides the shared operational clock and context for every agent.

### `inventory`

| Field | Type | Key/constraint | Why it matters |
| --- | --- | --- | --- |
| `sku` | `TEXT` | Required; composite primary-key part | Identifies the product whose stock is being checked or replenished. |
| `name` | `TEXT` | Required | Gives agents and customer service a readable product name. |
| `size` | `TEXT` | Required; composite primary-key part | Distinguishes stock by size, including `OS` for one-size goods. |
| `qty` | `INTEGER` | Required | Determines availability, shortages, and whether an order can be fulfilled. |
| `location` | `TEXT` | Required | Tells staff where the item is located in the shop. |

The inventory agent must use this table for factual stock answers and shortage calculations.

### `invoices`

| Field | Type | Key/constraint | Why it matters |
| --- | --- | --- | --- |
| `id` | `INTEGER` | Primary key | Identifies an invoice referenced by a ticket or payment. |
| `vendor_id` | `INTEGER` | Required; relates to `vendors.id` | Identifies the vendor that must be paid. |
| `amount` | `REAL` | Required | Specifies the amount accounting may prepare for payment. |
| `due_date` | `TEXT` | Required | Is compared with `desk.date_today` to determine whether payment is overdue. |
| `status` | `TEXT` | Required | Shows whether the invoice remains open or has been paid. |
| `description` | `TEXT` | Optional | Explains the purchase or reprint represented by the invoice. |

This table lets accounting enforce unpaid-invoice rules and prepare database-backed payment proposals.

### `leases`

| Field | Type | Key/constraint | Why it matters |
| --- | --- | --- | --- |
| `id` | `INTEGER` | Primary key | Identifies the lease referenced by a rent ticket. |
| `space_name` | `TEXT` | Required | Identifies the shop space whose rent is being handled. |
| `landlord` | `TEXT` | Required | Identifies the payee for a rent obligation. |
| `monthly_rent` | `REAL` | Required | Specifies the amount facilities/accounting may propose paying. |
| `next_due` | `TEXT` | Required | Is compared with `desk.date_today` for due-date handling. |
| `notes` | `TEXT` | Optional | Stores lease-specific operational details. |

The facilities agent uses this table for shop-space obligations, with accounting handling any payment proposal.

### `payments`

| Field | Type | Key/constraint | Why it matters |
| --- | --- | --- | --- |
| `id` | `INTEGER` | Primary key | Identifies a completed payment record. |
| `kind` | `TEXT` | Required | Indicates whether the payment concerns an invoice, lease, or another supported obligation. |
| `ref_id` | `INTEGER` | Optional | Links the payment back to the relevant invoice or lease. |
| `amount` | `REAL` | Required | Records how much cash left the account. |
| `account` | `TEXT` | Required | Identifies the `cash_accounts` row that funded the payment. |
| `paid_at` | `TEXT` | Required | Records when the payment was made. |
| `approved_by` | `TEXT` | Required | Provides the human-approval audit trail required before money leaves the shop. |

This is the accounting agent's immutable-looking payment history and must only be updated after human approval and cash validation.

### `pricing`

| Field | Type | Key/constraint | Why it matters |
| --- | --- | --- | --- |
| `sku` | `TEXT` | Primary key; relates to `inventory.sku` | Identifies the product's pricing record. |
| `unit_cost` | `REAL` | Required | Supports margin calculations and discount decisions. |
| `list_price` | `REAL` | Required | Provides the factual selling price before any approved override. |

The boss and accounting agents use this table to evaluate bulk discounts without inventing prices or margins.

### `tickets`

| Field | Type | Key/constraint | Why it matters |
| --- | --- | --- | --- |
| `id` | `INTEGER` | Primary key | Identifies the work item on the operations board. |
| `type` | `TEXT` | Required | Helps the boss agent route the ticket to the appropriate specialist. |
| `requester` | `TEXT` | Required | Identifies the customer, organization, landlord, or other originator. |
| `subject` | `TEXT` | Required | Gives agents a concise description of the request. |
| `sku` | `TEXT` | Optional; relates to `inventory.sku`/`pricing.sku` | Connects product-related tickets to stock and pricing facts. |
| `size` | `TEXT` | Optional | Supplies the size needed for an inventory lookup. |
| `qty` | `INTEGER` | Optional | Supplies the requested quantity for order and shortage calculations. |
| `lease_id` | `INTEGER` | Optional; relates to `leases.id` | Connects rent tickets to the applicable lease. |
| `invoice_id` | `INTEGER` | Optional; relates to `invoices.id` | Connects payment or vendor tickets to the applicable invoice. |
| `status` | `TEXT` | Required | Tracks whether the ticket is still open or resolved. |
| `notes` | `TEXT` | Optional | Contains details that agents need beyond the subject and structured fields. |
| `created_at` | `TEXT` | Required | Records when the ticket entered the board and supports chronological handling. |

This is the central work queue: the boss reads it, specialists resolve it, and customer service uses its requester/details for draft communications.

### `vendors`

| Field | Type | Key/constraint | Why it matters |
| --- | --- | --- | --- |
| `id` | `INTEGER` | Primary key | Identifies a vendor referenced by an invoice or restock decision. |
| `name` | `TEXT` | Required | Names the vendor that could fulfill a purchase or reprint. |
| `specialty` | `TEXT` | Required | Indicates which product or service the vendor can provide. |
| `lead_days` | `INTEGER` | Required | Determines the expected restock timing for an inventory plan. |

The inventory agent uses vendor specialty and lead time to recommend restocking, while unpaid-invoice rules determine whether a vendor may ship.

## Initial observations for later agent work

- Ticket 101 requests one `CC-TEE-WHITE` in size `S`, but inventory reports `qty=0`. Its related invoice 501 is open, overdue relative to `desk.date_today`, and belongs to vendor 1, `Bulldog Print Co`.
- Ticket 102 concerns lease 1 for the Chapel Street shop. Rent is due on `2026-09-02`, two days after the shop date in the seed data.
- Ticket 103 requests 20 `CC-HOOD-NAVY` hoodies in size `M`, while inventory has only 8. The shortage is therefore 12 units; pricing gives a $22 unit cost and $58 list price for margin analysis.
- The seed cash balance is $3,400, and the payments table is empty. Any future payment must require human approval, verify available cash, and record the payment in `payments` while updating `cash_accounts`.

## MCP server tools

The FastMCP server is in `mcp_server/server.py`. It uses the resettable working database at `data/campus_customs_new.db`; the original `data/campus_customs.db` remains untouched. These first three tools are read-only and return database-backed facts or calculations derived from those facts.

### `inspect_ticket_101_customer_order`

- Tables read: `tickets`, `inventory`, `pricing`, `invoices`, and `vendors`.
- Ticket unlocked: 101.
- Why this is appropriate: ticket 101 is a size-S Bulldog tee order with zero stock and a related rush-reprint invoice, so the agents need the exact stock, price, invoice, and vendor records together.

### `inspect_ticket_102_rent_notice`

- Tables read: `tickets`, `leases`, and `desk`.
- Ticket unlocked: 102.
- Why this is appropriate: ticket 102 references lease 1, and comparing that lease's due date with `desk.date_today` is the specific fact needed to handle the rent notice.

### `inspect_ticket_103_bulk_hoodie_request`

- Tables read: `tickets`, `inventory`, `pricing`, and `vendors`.
- Ticket unlocked: 103.
- Why this is appropriate: ticket 103 requests 20 size-M hoodies, so the agents need the exact shortfall, unit cost/list price margin data, and apparel vendor lead-time options to evaluate the discount and restock plan.

## Agent team

The five PydanticAI roles are wired in `backend/agent.py`, with one detailed prompt per role in `backend/prompts/`:

- **Boss agent** (`boss.md`) reads the open board, routes each ticket, coordinates delegation, and makes the final internal decision.
- **Inventory agent** (`inventory.md`) checks SKU/size stock, calculates shortfalls, and evaluates database-backed restock options.
- **Accounting agent** (`accounting.md`) checks invoices, cash, margins, and payment proposals; it cannot bypass human approval.
- **Facilities agent** (`facilities.md`) handles leases, rent timing, and shop-space obligations.
- **Customer service agent** (`customer_service.md`) prepares customer-facing drafts and saves them as unsent board notes.

Every agent uses the same Portkey-backed `gpt-6-luna` model and has delegation tools for the other four roles. Delegation is bounded by a maximum depth and step count. Agents receive shop facts through the MCP client bridge only; backend code does not query SQLite directly.

### Structured backend models

- `AgentDecision` contains `role`, optional `ticket_id`, `summary`, `recommended_action`, database-backed `facts`, `delegated_to`, `requires_human_approval`, an optional unsent `external_message_draft`, and `stop_reason`.
- `AuditRecord` contains the UTC `timestamp`, `event`, optional agent and tool names, optional ticket ID, shortened `arguments`, and `stop_reason`.
- `TeamRunResult` contains the final `decision`, `steps_used`, `max_steps`, and `max_depth`, making loop-limit compliance visible to a future API or dashboard.

## Additional MCP tools

| Tool | Tables read or changed | Agent/ticket purpose |
| --- | --- | --- |
| `list_open_tickets` | Reads `desk`, `tickets` | Gives the boss the authoritative open board and shop date before routing tickets. |
| `list_tickets` | Reads `desk`, `tickets` | Gives the dashboard all three training tickets and their current open/resolved statuses. |
| `get_checking_balance` | Reads `cash_accounts` | Gives the dashboard the current checking balance without bypassing MCP. |
| `get_ticket_context` | Reads `desk`, `tickets`, and linked `inventory`, `pricing`, `leases`, `invoices`, and `vendors` records | Gives any specialist the complete database-backed context for a specific ticket without a second backend data layer. |
| `find_restock_options` | Reads `tickets`, `inventory`, `pricing`, `vendors`, and open `invoices` | Derives the SKU, size, and requested quantity from the ticket before evaluating the exact shortfall and whether a vendor is blocked by unpaid invoices. |
| `prepare_payment` | Reads `tickets`, `invoices` or `leases`, `cash_accounts`, and `payments` | Helps accounting create a payment proposal for ticket 101 or 102 while checking invoice state, duplicates, and available cash. |
| `record_approved_payment` | Reads and changes `tickets`, `invoices` or `leases`, `cash_accounts`, `payments`, and `desk` | Executes a payment only after a named human approval, with a cash-floor and duplicate-payment guard. |
| `save_customer_draft` | Reads and changes `tickets` | Keeps customer service messages on the board as explicitly unsent drafts; it cannot contact a customer. |
| `resolve_ticket` | Reads and changes `tickets` | Records the team's internal resolution after the required specialist work is complete. |

## Safety and operating limits

- The original database is never modified; all writes target `data/campus_customs_new.db`.
- Agents must use MCP for shop facts and must not invent stock, price, cash, invoice, lease, vendor, or date values.
- No tool sends email, calls a vendor, contacts a customer, or performs an external side effect.
- Payment execution requires a named human approver, an open obligation, no prior payment, and enough cash; negative balances are refused.
- Customer communications remain marked as unsent drafts until a later human workflow explicitly handles them.
- Agent calls use only `gpt-6-luna` through Portkey and read `PORTKEY_API_KEY` from the root `.env`; the key is never written to source or logs.
- Delegation is capped at 4 levels of depth and 24 team loop steps per run. MCP results are bounded to the requested ticket/context, and audit arguments are shortened to avoid leaking secrets or consuming unnecessary tokens.
- `output/audit_trail.json` is append-only: each agent step, delegation, MCP call, stop reason, and write action records a UTC timestamp, role, tool/event name, ticket, and short arguments.

## FastAPI dashboard routes

- `GET /api/tickets` — returns all three training tickets, their current open/resolved status, and the shop date through MCP.
- `POST /api/tickets/{ticket_id}/run` — runs the bounded PydanticAI team for one ticket and returns its structured decision and loop limits.
- `GET /api/events?limit=100` — returns recent audit events, including agent summaries, delegation steps, stop reasons, and MCP tools used.
- `GET /api/tickets/{ticket_id}/payment-preview` — returns the database-backed payment proposal and approval state before a human decides.
- `POST /api/approvals/payment` — records a payment only after a human supplies `ticket_id` and `approved_by`; the MCP payment guard still checks status, duplicates, and cash.
- `GET /api/cash` — returns the current checking-account record through MCP.
- `POST /api/reset` — copies untouched `data/campus_customs.db` over `data/campus_customs_new.db` and leaves the audit trail intact.

Run from the `backend` folder with `uvicorn main:app --reload --port 8000`.

## Final bounded run evidence

Before the final run, the API reset copied the untouched seed database to `data/campus_customs_new.db`. The checking balance was `$3,400.00`. Tickets were attempted in the requested order: 102, 101, and 103. The team reached valid database-backed recommendations for all three, but correctly left them open when resolution would require an unrecorded restock, price, or due-date action. The actual agent/tool/delegation notes are recorded in `output/desk_tickets.html` and the machine-readable outcomes are in `output/resolved_tickets.json`.

The only recorded cash movement was the explicit human-approved payment of invoice 501 for ticket 101: `$3,400.00 - $840.00 = $2,560.00`. The ending balance was read from `cash_accounts` through MCP and matches that calculation. Ticket 102 did not trigger payment because rent is due on `2026-09-02`, after `desk.date_today` (`2026-08-31`). Ticket 103 has no payment obligation.

During live testing, Portkey required `openai_reasoning_effort="none"` for function tools on `gpt-6-luna`; this setting is now explicit in `backend/agent.py`. MCP tools are registered with typed schemas (`ticket_id`, `draft_message`, and `resolution_note`) so model calls match the FastMCP contracts. Malformed MCP calls are recorded as failures and returned as recoverable tool errors instead of terminating the entire team run. The append-only run history remains in `output/audit_trail.json`.

The project-root `.mcp.json` connects the local `mcp_server/.venv/Scripts/python.exe` process to `mcp_server/server.py`. PydanticAI also applies `UsageLimits` to each agent run, using the shared 24-step budget for model requests and tool calls; delegation remains capped at depth 4.
