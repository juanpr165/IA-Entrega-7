"""LangGraph adaptation of the Entrega 6 multi-agent orchestrator."""

from __future__ import annotations

import os
import re
import ast
import operator
from typing import Any, Literal, TypedDict

from ddgs import DDGS
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from .config import settings
from .hitl import is_critical_task
from .observability import traced_node

Route = Literal["research", "analyst", "final"]


class OrchestratorState(TypedDict, total=False):
    user_request: str
    next_agent: Route
    iteration: int
    critical: bool
    approval: dict[str, Any]
    research_results: list[dict[str, str]]
    analysis_results: list[dict[str, str]]
    routing_history: list[dict[str, str]]
    final_answer: str


def get_llm() -> ChatGroq:
    """The project intentionally has exactly one LLM provider: Groq."""
    return ChatGroq(
        model=settings.groq_model,
        temperature=0,
        api_key=os.getenv("GROQ_API_KEY"),
    )


def _needs_research(request: str) -> bool:
    return any(term in request.casefold() for term in ("investig", "busc", "fuente", "actual", "noticia", "compar", "tendencia"))


def _needs_analysis(request: str) -> bool:
    return any(term in request.casefold() for term in ("calcul", "porcentaje", "sentimiento", "analiz", "promedio", "variación"))


def _route(state: OrchestratorState) -> tuple[Route, str]:
    if state.get("iteration", 0) >= settings.max_iterations:
        return "final", "Límite de iteraciones alcanzado."
    request = state["user_request"]
    if _needs_research(request) and not state.get("research_results"):
        return "research", "Faltan fuentes para la solicitud."
    if _needs_analysis(request) and not state.get("analysis_results"):
        return "analyst", "Falta el procesamiento especializado."
    return "final", "La evidencia requerida está disponible."


_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def safe_calculate(expression: str) -> float:
    """Evaluate a deliberately tiny arithmetic grammar, never Python source."""
    def visit(node: ast.AST) -> float:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
            return _OPERATORS[type(node.op)](visit(node.left), visit(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPERATORS:
            return _OPERATORS[type(node.op)](visit(node.operand))
        raise ValueError("Sólo se permiten números y operadores aritméticos básicos")
    return visit(ast.parse(expression, mode="eval").body)


@traced_node("classify_criticality")
def classify_criticality(state: OrchestratorState) -> dict[str, Any]:
    return {"critical": is_critical_task(state["user_request"])}


def route_after_classification(state: OrchestratorState) -> str:
    return "approval" if state["critical"] else "supervisor"


@traced_node("human_approval")
def approval_node(state: OrchestratorState) -> dict[str, Any]:
    decision = interrupt({
        "reason": "La tarea fue clasificada como crítica y necesita aprobación humana.",
        "task": state["user_request"],
    })
    if not decision.get("approved", False):
        return {"approval": decision, "final_answer": "Ejecución rechazada por la persona revisora."}
    return {"approval": decision}


def route_after_approval(state: OrchestratorState) -> str:
    return "final" if not state.get("approval", {}).get("approved", False) else "supervisor"


@traced_node("supervisor")
def supervisor_node(state: OrchestratorState) -> dict[str, Any]:
    route, reason = _route(state)
    return {
        "next_agent": route,
        "iteration": state.get("iteration", 0) + 1,
        "routing_history": state.get("routing_history", []) + [{"route": route, "reason": reason}],
    }


@traced_node("research")
def research_node(state: OrchestratorState) -> dict[str, Any]:
    try:
        results = list(DDGS().text(state["user_request"], max_results=3))
        sources = [{"title": item["title"], "url": item["href"], "body": item.get("body", "")} for item in results]
    except Exception as exc:
        sources = [{"title": "Búsqueda no disponible", "url": "", "body": str(exc)}]
    return {"research_results": sources}


@traced_node("analyst")
def analyst_node(state: OrchestratorState) -> dict[str, Any]:
    request = state["user_request"]
    output: list[dict[str, str]] = []
    expression = re.search(r"(?:calcul[áa]|resolver)?\s*([\d\s+*/().,^%-]+)", request, re.IGNORECASE)
    if expression and any(char.isdigit() for char in expression.group(1)):
        # Deliberately restricted arithmetic; no code evaluation or side effects.
        candidate = expression.group(1).strip().replace("^", "**")
        if re.fullmatch(r"[\d\s+*/().%-]+", candidate):
            try:
                output.append({"tool": "arithmetic", "output": str(safe_calculate(candidate))})
            except Exception as exc:
                output.append({"tool": "arithmetic", "output": f"Expresión inválida: {exc}"})
    numbers = [float(item.replace(",", ".")) for item in re.findall(r"\d+(?:[,.]\d+)?", request)]
    if ("porcentual" in request.casefold() or "variación" in request.casefold()) and len(numbers) >= 2 and numbers[0]:
        output.append({"tool": "percentage_change", "output": f"{((numbers[1] - numbers[0]) / numbers[0] * 100):.2f}%"})
    return {"analysis_results": output or [{"tool": "analysis", "output": "No se detectó cálculo específico."}]}


@traced_node("final")
def final_node(state: OrchestratorState) -> dict[str, Any]:
    if state.get("approval") and not state["approval"].get("approved", False):
        return {"final_answer": "Ejecución rechazada por la persona revisora."}
    evidence = f"Fuentes: {state.get('research_results', [])}\nAnálisis: {state.get('analysis_results', [])}"
    messages = [
        SystemMessage(content="Respondé en español de manera clara, usando sólo la evidencia dada."),
        HumanMessage(content=f"Solicitud: {state['user_request']}\n{evidence}"),
    ]
    try:
        answer = get_llm().invoke(messages).content
    except Exception as exc:
        answer = f"No se pudo generar la síntesis con Groq: {exc}"
    return {"final_answer": str(answer)}


def build_graph(checkpointer: Any):
    graph = StateGraph(OrchestratorState)
    graph.add_node("classify", classify_criticality)
    graph.add_node("approval", approval_node)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("research", research_node)
    graph.add_node("analyst", analyst_node)
    graph.add_node("final", final_node)
    graph.add_edge(START, "classify")
    graph.add_conditional_edges("classify", route_after_classification, {"approval": "approval", "supervisor": "supervisor"})
    graph.add_conditional_edges("approval", route_after_approval, {"supervisor": "supervisor", "final": "final"})
    graph.add_conditional_edges("supervisor", lambda state: state["next_agent"], {"research": "research", "analyst": "analyst", "final": "final"})
    graph.add_edge("research", "supervisor")
    graph.add_edge("analyst", "supervisor")
    graph.add_edge("final", END)
    return graph.compile(checkpointer=checkpointer)
