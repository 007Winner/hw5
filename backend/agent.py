"""PydanticAI Campus Customs team with bounded, fully connected delegation."""

import asyncio
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai import Agent, RunContext, UsageLimits
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

try:
    from .audit import append_record
    from .mcp_client import ShopMCPClient
    from .models import AgentDecision, AgentRole, TeamRunResult
except ImportError:  # Supports `uvicorn main:app` from inside backend/.
    from audit import append_record
    from mcp_client import ShopMCPClient
    from models import AgentDecision, AgentRole, TeamRunResult


PROJECT_ROOT = Path(__file__).resolve().parents[1]
# Prefer a project-local .env in a clone, while retaining the workspace-level
# fallback used by the existing development setup.
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT.parent / ".env", override=False)

MODEL_NAME = "gpt-6-luna"
MAX_DELEGATION_DEPTH = 4
MAX_LOOP_STEPS = 24
PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
MCP_TOOL_NAMES = (
    "inspect_ticket_101_customer_order",
    "inspect_ticket_102_rent_notice",
    "inspect_ticket_103_bulk_hoodie_request",
    "list_open_tickets",
    "list_tickets",
    "get_checking_balance",
    "get_ticket_context",
    "find_restock_options",
    "prepare_payment",
    "record_approved_payment",
    "save_customer_draft",
    "resolve_ticket",
)


def _portkey_model() -> OpenAIChatModel:
    api_key = os.getenv("PORTKEY_API_KEY")
    if not api_key:
        raise RuntimeError("PORTKEY_API_KEY is required in the root .env")
    client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://api.portkey.ai/v1",
        default_headers={
            "x-portkey-api-key": api_key,
            "x-portkey-provider": "openai",
        },
    )
    # Portkey's gpt-6-luna Chat Completions route rejects tool calls when
    # reasoning_effort is enabled. Explicitly disable it so the agents can
    # use their MCP and delegation tools while retaining the required model.
    return OpenAIChatModel(
        MODEL_NAME,
        provider=OpenAIProvider(openai_client=client),
        settings={"openai_reasoning_effort": "none"},
    )


@dataclass
class TeamRuntime:
    agents: dict[AgentRole, Agent[Any, AgentDecision]] = field(default_factory=dict)
    mcp: ShopMCPClient = field(default_factory=ShopMCPClient)
    steps: int = 0

    async def delegate(
        self,
        source: AgentRole,
        target: AgentRole,
        task: str,
        ticket_id: int | None,
        depth: int,
        approvals: dict[int, str],
    ) -> dict[str, Any]:
        if target not in self.agents:
            return {"blocked": True, "reason": f"Unknown target agent: {target}"}
        if depth >= MAX_DELEGATION_DEPTH:
            append_record(event="delegation_stopped", agent=source.value, ticket_id=ticket_id, stop_reason="max_depth")
            return {"blocked": True, "reason": "Maximum delegation depth reached."}
        if self.steps >= MAX_LOOP_STEPS:
            append_record(event="delegation_stopped", agent=source.value, ticket_id=ticket_id, stop_reason="max_steps")
            return {"blocked": True, "reason": "Maximum team loop steps reached."}
        self.steps += 1
        append_record(
            event="delegation_started",
            agent=source.value,
            ticket_id=ticket_id,
            arguments={"target": target.value, "task": task[:240], "depth": depth + 1},
        )
        deps = TeamDeps(self, source=target, ticket_id=ticket_id, depth=depth + 1, approvals=approvals)
        append_record(
            event="agent_step_started",
            agent=target.value,
            ticket_id=ticket_id,
            arguments={"depth": depth + 1, "task": task[:240]},
        )
        remaining_budget = max(1, MAX_LOOP_STEPS - self.steps)
        result = await self.agents[target].run(
            task,
            deps=deps,
            usage_limits=UsageLimits(
                request_limit=remaining_budget,
                tool_calls_limit=remaining_budget,
            ),
        )
        append_record(
            event="agent_step_completed",
            agent=target.value,
            ticket_id=ticket_id,
            arguments={
                "summary": result.output.summary[:240],
                "recommended_action": result.output.recommended_action[:240],
                "facts": [fact[:160] for fact in result.output.facts[:10]],
            },
            stop_reason=result.output.stop_reason,
        )
        return result.output.model_dump()


@dataclass
class TeamDeps:
    runtime: TeamRuntime
    source: AgentRole
    ticket_id: int | None
    depth: int
    approvals: dict[int, str]


def _prompt(role: AgentRole) -> str:
    return (PROMPT_DIR / f"{role.value}.md").read_text(encoding="utf-8")


def _register_mcp_tools(agent: Agent[Any, AgentDecision], role: AgentRole) -> None:
    async def invoke(ctx: RunContext[TeamDeps], tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        if tool_name == "record_approved_payment":
            ticket_id = args.get("ticket_id")
            if ticket_id not in ctx.deps.approvals:
                return {"blocked": True, "reason": "Human approval is required before recording payment."}
            args = {**args, "approved_by": ctx.deps.approvals[ticket_id]}
        append_record(
            event="mcp_call_started",
            agent=role.value,
            tool_name=tool_name,
            ticket_id=ctx.deps.ticket_id,
            arguments={k: str(v)[:240] for k, v in args.items()},
        )
        try:
            result = await ctx.deps.runtime.mcp.call(tool_name, args)
        except Exception as exc:
            append_record(
                event="mcp_call_failed",
                agent=role.value,
                tool_name=tool_name,
                ticket_id=ctx.deps.ticket_id,
                arguments={"error": str(exc)[:240]},
                stop_reason=type(exc).__name__,
            )
            return {"tool_error": True, "tool_name": tool_name, "reason": str(exc)[:500]}
        append_record(
            event="mcp_call_completed",
            agent=role.value,
            tool_name=tool_name,
            ticket_id=ctx.deps.ticket_id,
            arguments={"result_keys": list(result)[:20]},
        )
        return result

    no_argument_tools = {
        "inspect_ticket_101_customer_order",
        "inspect_ticket_102_rent_notice",
        "inspect_ticket_103_bulk_hoodie_request",
        "list_open_tickets",
        "list_tickets",
        "get_checking_balance",
    }
    ticket_id_tools = {
        "get_ticket_context",
        "find_restock_options",
        "prepare_payment",
        "record_approved_payment",
    }

    def make_no_args(name: str):
        async def no_args(ctx: RunContext[TeamDeps]) -> dict[str, Any]:
            return await invoke(ctx, name, {})
        return no_args

    def make_one_ticket(name: str):
        async def one_ticket(ctx: RunContext[TeamDeps], ticket_id: int) -> dict[str, Any]:
            return await invoke(ctx, name, {"ticket_id": ticket_id})
        return one_ticket

    for tool_name in MCP_TOOL_NAMES:
        if tool_name in no_argument_tools:
            call_mcp = make_no_args(tool_name)
        elif tool_name in ticket_id_tools:
            call_mcp = make_one_ticket(tool_name)
        elif tool_name == "save_customer_draft":
            async def draft(ctx: RunContext[TeamDeps], ticket_id: int, draft_message: str) -> dict[str, Any]:
                return await invoke(ctx, "save_customer_draft", {"ticket_id": ticket_id, "draft_message": draft_message})
            call_mcp = draft
        elif tool_name == "resolve_ticket":
            async def resolve(ctx: RunContext[TeamDeps], ticket_id: int, resolution_note: str) -> dict[str, Any]:
                return await invoke(ctx, "resolve_ticket", {"ticket_id": ticket_id, "resolution_note": resolution_note})
            call_mcp = resolve
        else:
            raise RuntimeError(f"MCP tool is missing a typed wrapper: {tool_name}")
        call_mcp.__name__ = f"mcp_{tool_name}"
        call_mcp.__doc__ = f"Call authoritative MCP tool {tool_name}; use database facts only."
        agent.tool(call_mcp)


def _register_delegation_tools(agent: Agent[Any, AgentDecision], role: AgentRole, runtime: TeamRuntime) -> None:
    for target in AgentRole:
        if target == role:
            continue

        async def delegate(
            ctx: RunContext[TeamDeps],
            task: str,
            ticket_id: int | None = None,
            *,
            _target: AgentRole = target,
        ) -> dict[str, Any]:
            return await ctx.deps.runtime.delegate(
                role, _target, task, ticket_id or ctx.deps.ticket_id, ctx.deps.depth, ctx.deps.approvals
            )

        delegate.__name__ = f"delegate_to_{target.value}"
        delegate.__doc__ = f"Delegate a bounded task to the {target.value} specialist."
        agent.tool(delegate)


def build_team() -> tuple[dict[AgentRole, Agent[Any, AgentDecision]], TeamRuntime]:
    runtime = TeamRuntime()
    model = _portkey_model()
    for role in AgentRole:
        runtime.agents[role] = Agent(
            model,
            deps_type=TeamDeps,
            output_type=AgentDecision,
            system_prompt=_prompt(role),
            name=f"campus_customs_{role.value}",
        )
    for role, agent in runtime.agents.items():
        _register_mcp_tools(agent, role)
        _register_delegation_tools(agent, role, runtime)
    return runtime.agents, runtime


async def run_operations(
    *, ticket_id: int | None = None, human_approvals: dict[int, str] | None = None
) -> TeamRunResult:
    agents, runtime = build_team()
    prompt = (
        f"Review and coordinate ticket {ticket_id}." if ticket_id is not None else "Review every open ticket and coordinate the team."
    )
    prompt += " Use MCP for all facts, delegate to specialists as needed, and stop after an auditable internal recommendation."
    append_record(event="agent_loop_started", agent=AgentRole.BOSS.value, ticket_id=ticket_id, arguments={"model": MODEL_NAME})
    if runtime.steps >= MAX_LOOP_STEPS:
        raise RuntimeError("Team loop limit reached before starting.")
    runtime.steps += 1
    deps = TeamDeps(runtime, source=AgentRole.BOSS, ticket_id=ticket_id, depth=0, approvals=human_approvals or {})
    append_record(
        event="agent_step_started",
        agent=AgentRole.BOSS.value,
        ticket_id=ticket_id,
        arguments={"depth": 0, "prompt": prompt[:240]},
    )
    try:
        result = await agents[AgentRole.BOSS].run(
            prompt,
            deps=deps,
            usage_limits=UsageLimits(
                request_limit=max(1, MAX_LOOP_STEPS - runtime.steps),
                tool_calls_limit=max(1, MAX_LOOP_STEPS - runtime.steps),
            ),
        )
    except Exception as exc:
        append_record(event="agent_loop_stopped", agent=AgentRole.BOSS.value, ticket_id=ticket_id, stop_reason=type(exc).__name__)
        raise
    append_record(
        event="agent_step_completed",
        agent=AgentRole.BOSS.value,
        ticket_id=ticket_id,
        arguments={
            "summary": result.output.summary[:240],
            "recommended_action": result.output.recommended_action[:240],
            "facts": [fact[:160] for fact in result.output.facts[:10]],
        },
        stop_reason=result.output.stop_reason,
    )
    append_record(event="agent_loop_completed", agent=AgentRole.BOSS.value, ticket_id=ticket_id, stop_reason=result.output.stop_reason)
    return TeamRunResult(
        decision=result.output,
        steps_used=runtime.steps,
        max_steps=MAX_LOOP_STEPS,
        max_depth=MAX_DELEGATION_DEPTH,
    )


if __name__ == "__main__":
    asyncio.run(run_operations())
