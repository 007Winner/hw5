import { useCallback, useEffect, useMemo, useState } from "react";

const API = "http://localhost:8000/api";

type Ticket = {
  id: number;
  type: string;
  requester: string;
  subject: string;
  sku: string | null;
  size: string | null;
  qty: number | null;
  status: "open" | "resolved" | string;
  notes: string | null;
  created_at: string;
};

type DeskEvent = {
  timestamp: string;
  event: string;
  agent: string | null;
  tool_name: string | null;
  ticket_id: number | null;
  arguments: Record<string, unknown>;
  stop_reason: string | null;
};

type PaymentPreview = {
  ticket_id: number;
  kind: string;
  ref_id: number;
  amount: number;
  account: { name: string; balance: number };
  human_approval_required: boolean;
  can_pay: boolean;
  blocked_reason: string | null;
};

type RunResult = {
  decision: {
    summary: string;
    recommended_action: string;
    requires_human_approval: boolean;
    stop_reason: string;
  };
  steps_used: number;
  max_steps: number;
};

const roleNames: Record<string, string> = {
  boss: "Boss",
  inventory: "Inventory",
  accounting: "Accounting",
  facilities: "Facilities",
  customer_service: "Customer Service",
};

const roleClass = (agent: string | null) => `role-${agent ?? "system"}`;

function formatTime(timestamp: string) {
  return new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit", second: "2-digit" }).format(new Date(timestamp));
}

function formatMoney(value: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

function EventLine({ event }: { event: DeskEvent }) {
  const role = event.agent ? roleNames[event.agent] ?? event.agent : "Desk";
  let message = "recorded an event";
  if (event.event === "mcp_call_started") message = `opened ${event.tool_name}`;
  if (event.event === "mcp_call_completed") message = `received data from ${event.tool_name}`;
  if (event.event === "delegation_started") message = `delegated work to ${roleNames[String(event.arguments.target)] ?? event.arguments.target}`;
  if (event.event === "agent_step_started") message = "started a focused step";
  if (event.event === "agent_step_completed") message = String(event.arguments.summary ?? "completed its recommendation");
  if (event.event === "agent_loop_completed") message = `finished: ${event.stop_reason ?? "completed"}`;
  return (
    <div className={`event-line ${roleClass(event.agent)}`}>
      <div className="event-dot" />
      <div className="event-copy"><strong>{role}</strong><span>{message}</span></div>
      <time>{formatTime(event.timestamp)}</time>
    </div>
  );
}

function App() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [selectedId, setSelectedId] = useState(101);
  const [events, setEvents] = useState<DeskEvent[]>([]);
  const [cash, setCash] = useState(0);
  const [running, setRunning] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [runResult, setRunResult] = useState<RunResult | null>(null);
  const [payment, setPayment] = useState<PaymentPreview | null>(null);
  const [approver, setApprover] = useState("");
  const [approvalMessage, setApprovalMessage] = useState("");

  const selectedTicket = useMemo(() => tickets.find((ticket) => ticket.id === selectedId), [tickets, selectedId]);
  const selectedEvents = useMemo(() => events.filter((event) => event.ticket_id === selectedId), [events, selectedId]);

  const refresh = useCallback(async () => {
    try {
      const [ticketData, cashData, eventData] = await Promise.all([
        request<{ tickets: Ticket[] }>("/tickets"),
        request<{ balance: number }>("/cash"),
        request<{ events: DeskEvent[] }>("/events?limit=200"),
      ]);
      setTickets(ticketData.tickets);
      setCash(cashData.balance);
      setEvents(eventData.events);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "The operations API is unavailable.");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadPaymentPreview = useCallback(async (ticketId: number) => {
    try {
      setPayment(await request<PaymentPreview>(`/tickets/${ticketId}/payment-preview`));
    } catch {
      setPayment(null);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => { setPayment(null); setRunResult(null); setApprovalMessage(""); }, [selectedId]);
  useEffect(() => {
    const timer = window.setInterval(() => { void refresh(); }, running ? 800 : 5000);
    return () => window.clearInterval(timer);
  }, [refresh, running]);

  async function startRun() {
    setRunning(true); setRunResult(null); setError("");
    try {
      const result = await request<RunResult>(`/tickets/${selectedId}/run`, { method: "POST", body: JSON.stringify({}) });
      setRunResult(result);
      await refresh();
      await loadPaymentPreview(selectedId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "The team run failed.");
    } finally { setRunning(false); }
  }

  async function approvePayment() {
    if (!payment || !approver.trim()) return;
    if (!window.confirm(`Approve ${formatMoney(payment.amount)} from ${payment.account.name}?`)) return;
    try {
      const result = await request<{ new_balance: number }>("/approvals/payment", {
        method: "POST", body: JSON.stringify({ ticket_id: selectedId, approved_by: approver.trim() }),
      });
      setApprovalMessage(`Payment recorded. New balance: ${formatMoney(result.new_balance)}.`);
      setPayment(null); setApprover(""); await refresh();
    } catch (err) { setApprovalMessage(err instanceof Error ? err.message : "Approval failed."); }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-lockup"><div className="crest">CC</div><div><p className="kicker">Yale College Shop</p><h1>Campus Customs <span>Operations Desk</span></h1></div></div>
        <div className="top-meta"><div className="live-pill"><span className="live-dot" /> API LIVE</div><div className="balance"><span>Checking balance</span><strong>{formatMoney(cash)}</strong></div></div>
      </header>
      <main className="desk-layout">
        <aside className="ticket-rail">
          <div className="rail-heading"><div><p className="kicker">Open board</p><h2>Today’s tickets</h2></div><span className="ticket-count">{tickets.length}</span></div>
          <p className="rail-note">Select a case to brief the team and watch the desk move.</p>
          {loading ? <div className="skeleton-list"><div /><div /><div /></div> : tickets.map((ticket) => (
            <button className={`ticket-card ${selectedId === ticket.id ? "selected" : ""}`} key={ticket.id} onClick={() => setSelectedId(ticket.id)}>
              <div className="ticket-card-top"><span className="ticket-id">#{ticket.id}</span><span className={`status ${ticket.status}`}>{ticket.status}</span></div>
              <strong>{ticket.subject}</strong><span>{ticket.type.replaceAll("_", " ")}</span><small>{ticket.requester}</small>
            </button>
          ))}
          {error && <div className="error-box">{error}</div>}
        </aside>

        <section className="command-center">
          {selectedTicket ? <>
            <div className="case-header"><div><p className="kicker">Case file · #{selectedTicket.id}</p><h2>{selectedTicket.subject}</h2><p className="case-requester">Requested by <strong>{selectedTicket.requester}</strong></p></div><span className={`large-status ${selectedTicket.status}`}>{selectedTicket.status === "resolved" ? "Resolved" : "Open"}</span></div>
            <div className="fact-strip"><div><span>Type</span><strong>{selectedTicket.type.replaceAll("_", " ")}</strong></div><div><span>Product</span><strong>{selectedTicket.sku ?? "—"}</strong></div><div><span>Size / quantity</span><strong>{selectedTicket.size ?? "—"} / {selectedTicket.qty ?? "—"}</strong></div></div>
            <div className="run-bar"><div><p className="kicker">Command</p><strong>{running ? "The team is working this case…" : "Ready for the next move"}</strong></div><button className="primary-button" onClick={() => void startRun()} disabled={running || selectedTicket.status === "resolved"}>{running ? <><span className="spinner" /> Running team</> : "Start agent team"}</button></div>
            <div className="activity-card"><div className="section-title"><div><p className="kicker">Live transcript</p><h3>What is happening at the desk</h3></div><span className="event-count">{selectedEvents.length} events</span></div><div className="event-list">{selectedEvents.length ? selectedEvents.slice(-30).map((event, index) => <EventLine event={event} key={`${event.timestamp}-${index}`} />) : <div className="empty-state"><span className="empty-mark">✦</span><p>No activity yet.</p><small>Start the team to see MCP calls, handoffs, and decisions here.</small></div>}</div></div>
            {runResult && <div className="decision-card"><p className="kicker">Team summary</p><h3>{runResult.decision.summary}</h3><p>{runResult.decision.recommended_action}</p><div className="decision-meta"><span>{runResult.steps_used} / {runResult.max_steps} steps used</span><span>{runResult.decision.stop_reason}</span></div></div>}
          </> : <div className="empty-state"><p>Select a ticket to begin.</p></div>}
        </section>

        <aside className="right-rail">
          <div className="side-card approval-card"><div className="side-card-heading"><span className="icon-badge">$</span><div><p className="kicker">Human gate</p><h3>Payment approval</h3></div></div>{payment ? <><p className="approval-copy">The team prepared this payment. Money moves only when you approve it.</p><div className="amount-display"><span>{payment.kind} #{payment.ref_id}</span><strong>{formatMoney(payment.amount)}</strong></div><p className="cash-line">From <strong>{payment.account.name}</strong> · available {formatMoney(payment.account.balance)}</p><label className="field-label" htmlFor="approver">Approver name</label><input id="approver" value={approver} onChange={(event) => setApprover(event.target.value)} placeholder="e.g. Maya Chen" /><button className="approve-button" onClick={() => void approvePayment()} disabled={!payment.can_pay || !approver.trim()}>{payment.can_pay ? "Approve payment" : payment.blocked_reason ?? "Payment blocked"}</button>{approvalMessage && <p className="approval-message">{approvalMessage}</p>}</> : <div className="empty-approval"><span>◌</span><p>No payment is waiting for this ticket.</p><small>Payment proposals will appear here when accounting prepares one.</small></div>}</div>
          <div className="side-card roster-card"><div className="side-card-heading"><span className="icon-badge">✦</span><div><p className="kicker">The crew</p><h3>Agent roster</h3></div></div><ul className="roster">{Object.entries(roleNames).map(([key, name]) => <li key={key}><span className={`agent-avatar ${roleClass(key)}`}>{name[0]}</span><span><strong>{name}</strong><small>{key === "boss" ? "Routes & decides" : key === "customer_service" ? "Drafts replies" : `${name} specialist`}</small></span><i className={running ? "working" : "idle"} /></li>)}</ul></div>
          <div className="side-card protocol-card"><p className="kicker">Desk protocol</p><p>All facts come from the working database through MCP. External messages stay drafts. Payments require your name and approval.</p><span className="protocol-seal">MCP · HUMAN IN THE LOOP</span></div>
        </aside>
      </main>
      <footer><span>Campus Customs Operations Desk</span><span>FastAPI · MCP · PydanticAI</span></footer>
    </div>
  );
}

export default App;
