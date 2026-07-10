"""
LangGraph investigation workflow.

Graph topology:
  START → agent ⟶ tools ⟶ agent (loop until no tool calls)
                ↘ write_report → END
"""

import os
import json
import re
from typing import Generator
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from mcp_tools.trade_details import get_trade_details
from mcp_tools.execution_logs import get_execution_logs
from mcp_tools.policy_search import search_policies
from workflow.state import InvestigationState, InvestigationReport

load_dotenv()

TOOLS = [get_trade_details, get_execution_logs, search_policies]

SYSTEM_PROMPT = """You are TradeOps AI, an expert trade operations investigator.

When given a Trade ID to investigate, you MUST call all three tools in order:
1. get_trade_details  — retrieve the trade record
2. get_execution_logs — retrieve the full event timeline
3. search_policies    — search for policies relevant to the failure type

Only stop calling tools after you have results from all three.
Do not summarise or explain — just gather the evidence."""

REPORT_PROMPT = """You have finished gathering evidence. Now produce a structured investigation report.

Output a single valid JSON object with exactly these four fields — no markdown, no extra text:

{
  "root_cause": "<one sentence identifying the specific root cause>",
  "evidence": [
    "<evidence point 1: cite log event, timestamp, or system>",
    "<evidence point 2>",
    "<evidence point 3>"
  ],
  "confidence_score": <your assessment as a float 0.0–1.0>,
  "recommended_next_steps": [
    "<actionable step 1>",
    "<actionable step 2>",
    "<actionable step 3>"
  ]
}

Rules:
- root_cause: one sentence, specific to this trade and failure type
- evidence: 3–5 items, each referencing a specific log entry, data field, or policy clause
- confidence_score: your honest assessment of how clearly the gathered evidence supports
  the root cause — use higher values (0.8–1.0) when the log trail is unambiguous,
  lower values (0.4–0.6) when the evidence is circumstantial or incomplete
- recommended_next_steps: 3–5 concrete steps the operations team should take now"""


def _make_llm(temperature: float = 0) -> ChatOpenAI:
    return ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-oss-120b"),
        base_url=os.getenv("OPENAI_BASE_URL"),
        api_key=os.getenv("OPENAI_API_KEY"),
        temperature=temperature,
    )


# Graph nodes

def agent_node(state: InvestigationState) -> dict:
    llm_with_tools = _make_llm().bind_tools(TOOLS)
    response = llm_with_tools.invoke(state["messages"])
    return {"messages": [response]}


def write_report_node(state: InvestigationState) -> dict:
    messages = list(state["messages"]) + [HumanMessage(content=REPORT_PROMPT)]
    response = _make_llm().invoke(messages)

    text = response.content.strip()
    # Strip markdown code fences if the model wraps its output
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```\s*$", "", text, flags=re.MULTILINE)

    try:
        data = json.loads(text)
        report = InvestigationReport(**data)
        return {"report": report.model_dump()}
    except Exception:
        return {
            "report": {
                "root_cause": "Report generation failed — raw evidence available in conversation.",
                "evidence": [text[:600]],
                "confidence_score": 0.0,
                "recommended_next_steps": ["Escalate to senior operations for manual review."],
            }
        }


# Routing 

def should_continue(state: InvestigationState) -> str:
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None):
        return "tools"
    return "write_report"


# Graph assembly 

def _build_graph():
    g = StateGraph(InvestigationState)
    g.add_node("agent", agent_node)
    g.add_node("tools", ToolNode(TOOLS))
    g.add_node("write_report", write_report_node)

    g.set_entry_point("agent")
    g.add_conditional_edges("agent", should_continue, {
        "tools":        "tools",
        "write_report": "write_report",
    })
    g.add_edge("tools", "agent")
    g.add_edge("write_report", END)

    return g.compile()


investigation_graph = _build_graph()


# Public interface 

def _initial_state(trade_id: str) -> InvestigationState:
    return {
        "trade_id": trade_id,
        "messages": [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=f"Investigate failed trade {trade_id.upper()}. "
                        f"Gather all available evidence and determine the root cause."
            ),
        ],
        "report": None,
    }


def investigate(trade_id: str) -> dict:
    result = investigation_graph.invoke(_initial_state(trade_id))
    return result["report"]


def stream_investigate(trade_id: str) -> Generator[dict, None, None]:
    """
    Yield investigation events as they happen.

    Event types emitted:
      {"type": "tool_call",      "tool": str, "args": dict}
      {"type": "tool_result",    "tool": str, "preview": str}  # first 300 chars
      {"type": "writing_report"}
      {"type": "report",         "data": dict}
      {"type": "error",          "message": str}
    """
    try:
        for chunk in investigation_graph.stream(_initial_state(trade_id), stream_mode="updates"):
            node_name = next(iter(chunk))
            node_output = chunk[node_name]

            if node_name == "agent":
                for msg in node_output.get("messages", []):
                    for tc in getattr(msg, "tool_calls", []):
                        yield {"type": "tool_call", "tool": tc["name"], "args": tc["args"]}

            elif node_name == "tools":
                for msg in node_output.get("messages", []):
                    yield {
                        "type": "tool_result",
                        "tool": getattr(msg, "name", "unknown"),
                        "preview": str(msg.content)[:300],
                    }

            elif node_name == "write_report":
                yield {"type": "writing_report"}
                if node_output.get("report"):
                    yield {"type": "report", "data": node_output["report"]}

    except Exception as exc:
        yield {"type": "error", "message": str(exc)}
