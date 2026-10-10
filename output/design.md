# Campus Customs Operations Desk Design

The dashboard is designed as a calm, high-trust operations room rather than a generic admin panel. Its visual language draws from a late-night Yale office: espresso charcoal surfaces, warm cream typography, restrained wine-red controls, and brass-gold highlights. The palette gives the desk a memorable identity while keeping status, money, and action controls easy to find.

## Layout

The page uses a three-column desk layout. The left rail is the ticket board: each case has a clear number, subject, requester, type, and open/resolved status. The center is the command area for the selected case. It presents the case facts first, then the team control, live transcript, and final team summary. The right rail holds the human approval gate, agent roster, and operating protocol. This arrangement mirrors the way a real operator works: choose a case, understand it, watch the work, then authorize an irreversible action.

## Agent activity

The live transcript polls the FastAPI event route while a run is in progress. Each role has a distinct accent color so a human can scan the handoffs quickly: gold for the boss, teal for inventory, rose for accounting, violet for facilities, and green for customer service. Events use plain language such as “opened get_ticket_context,” “delegated work,” and “reported,” so the board communicates actions and reasoning without exposing distracting implementation detail.

The roster reinforces this distinction with a compact role label and a live working indicator. The final team summary appears separately from the transcript, making it easy to distinguish an in-progress conversation from the decision the team ultimately returned.

## Resolved tickets and cash

Resolved tickets use a green status treatment in both the left board and the selected case header. The run control disables itself after resolution, preventing an accidental second run. The checking balance is always visible in the top bar, and it refreshes after every dashboard poll and after an approval. This makes a cash change visible as a business consequence rather than burying it inside a tool response.

## Human approval

Payment proposals appear in a dedicated “Human gate” card. The card shows the obligation reference, amount, source account, and available cash before asking for an approver name. The approval button remains disabled until a name is entered and the MCP proposal says the payment is allowed. A confirmation step makes the irreversible action deliberate. Customer messages are treated with the same restraint: the backend stores drafts as unsent, and the interface never implies that an external message was delivered.

## Interaction and accessibility

The interface uses visible focus states, native buttons and inputs, readable contrast, responsive breakpoints, and a reduced-complexity mobile layout. Loading skeletons, an API error message, empty activity states, and disabled actions give the operator feedback at every stage. The visual motion is deliberately small: a live pulse, a working spinner, and subtle card transitions provide orientation without making a serious operations board feel playful.

The frontend talks to `http://localhost:8000/api`, and the backend explicitly allows the Vite origins `http://localhost:5173` and `http://127.0.0.1:5173`.
