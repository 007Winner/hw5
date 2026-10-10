# Campus Customs Operations Desk

This React/Vite/TypeScript dashboard talks to the FastAPI backend at `http://localhost:8000/api`. Start the backend from `../backend` with `uvicorn main:app --reload --port 8000`, then start this folder with `npm run dev`.

The interface polls ticket status, checking cash, and append-only agent events. Ticket runs stay visible while the team works, and payment proposals appear in the human approval panel before any money is moved.
