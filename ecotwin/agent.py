"""EcoTwin-X planning agent, built with the AWS open-source Strands Agents SDK.

The agent answers questions from planners and workers by calling EcoTwin-X's
own analysis functions as tools (routing, cooling-stop ranking, budget plans).

Model choice (env var ECOTWIN_MODEL):
  bedrock (default)  Amazon Bedrock  - needs AWS credentials
  ollama             local open model - no AWS account needed
If no model can be reached, ask_offline() answers the same questions by calling
the same tools directly, so the app always works. The UI says which mode ran.
"""
from __future__ import annotations
import os
import re

from . import core

SYSTEM_PROMPT = """You are the EcoTwin-X planning assistant for a city environment team.
You help outdoor workers (delivery riders, street vendors) and city planners cut
exposure to heat and air pollution.

Rules:
- ALWAYS call a tool to get numbers. Never invent figures.
- Hours are 9, 11, 13, 15, 17 (24h). Worker types: rider, vendor, child.
- Budgets are in Indian rupees (INR).
- Answer in plain language a non-expert understands, in under 120 words.
- End with one clear recommended action.
- Say these are planning simulations built on assumed intervention effects."""


def _tools():
    from strands import tool

    @tool
    def compare_routes(worker_type: str = "rider", hour: int = 13) -> dict:
        """Compare the shortest route with the CoolPath (less heat/pollution)
        route for a worker type (rider, vendor, child) at an hour (9, 11, 13,
        15 or 17). Returns distance, time, heat dose, pollution dose and the
        percent exposure reduction."""
        return core.compare_routes(worker_type, hour)

    @tool
    def top_cooling_stop_locations(n: int = 5) -> list:
        """Best real places (parks, schools, hospitals) to build cooling stops."""
        return core.top_priority_locations(n)

    @tool
    def best_plan_for_budget(budget_inr: int) -> dict:
        """Best mix of cooling stops, trees and green corridors for a budget."""
        return core.best_plan_for_budget(budget_inr)

    @tool
    def intervention_options() -> list:
        """Cost, heat/pollution reduction and time-to-benefit of each intervention."""
        return core.intervention_options()

    return [compare_routes, top_cooling_stop_locations,
            best_plan_for_budget, intervention_options]


def build_agent():
    """Return a Strands Agent, or None if the SDK/model is unavailable."""
    try:
        from strands import Agent
        kind = os.getenv("ECOTWIN_MODEL", "bedrock").lower()
        if kind == "ollama":
            from strands.models.ollama import OllamaModel
            model = OllamaModel(
                host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
                model_id=os.getenv("OLLAMA_MODEL", "llama3.1"))
        else:
            from strands.models import BedrockModel
            model = BedrockModel(
                model_id=os.getenv("BEDROCK_MODEL_ID",
                                   "us.anthropic.claude-sonnet-4-20250514-v1:0"),
                region_name=os.getenv("AWS_REGION", "us-east-1"))
        return Agent(model=model, tools=_tools(), system_prompt=SYSTEM_PROMPT)
    except Exception:
        return None


def ask(question: str, agent=None) -> tuple[str, str]:
    """Returns (answer, mode). mode is 'strands-agent' or 'offline'."""
    agent = agent or build_agent()
    if agent is not None:
        try:
            return str(agent(question)), "strands-agent"
        except Exception:
            pass  # no credentials / model down -> fall back
    return ask_offline(question), "offline"


# ---------------- offline fallback (same tools, rule-based) ----------------
def ask_offline(question: str) -> str:
    q = question.lower()
    worker = next((w for w in ("vendor", "child", "rider") if w in q), "rider")
    hm = re.search(r"(\d{1,2})\s*(am|pm)", q)
    hour = 13
    if hm:
        h = int(hm.group(1)) % 12 + (12 if hm.group(2) == "pm" else 0)
        hour = min(core.HOURS, key=lambda x: abs(x - h))
    bm = re.search(r"(\d[\d,\.]*)\s*(lakh|lac|l\b|k\b|crore)?", q) if re.search(
        r"budget|₹|rs|inr|lakh|crore", q) else None

    if bm:
        n = float(bm.group(1).replace(",", ""))
        mult = {"lakh": 1e5, "lac": 1e5, "l": 1e5, "k": 1e3, "crore": 1e7}.get(bm.group(2), 1)
        r = core.best_plan_for_budget(int(n * mult))
        if "error" in r:
            return r["error"]
        return (f"With that budget, the best plan is **{r['strategy']}**, costing "
                f"₹{r['cost_inr']:,} (₹{r['unused_budget_inr']:,} left over). "
                f"It scores {r['total_benefit_index']} on our benefit index. "
                f"{r['note']}")
    if any(k in q for k in ("where", "stop", "location", "place", "build")):
        rows = core.top_priority_locations(3)
        lst = "; ".join(f"{r['name']} ({r['stop_type']})" for r in rows)
        return (f"The three best places for cooling stops are: {lst}. They have "
                f"little shade and many connected roads, so they protect the most "
                f"workers. Recommended action: start with {rows[0]['name']}.")
    r = core.compare_routes(worker, hour)
    return (f"For a {worker} at {r['hour']}, the CoolPath route cuts heat and "
            f"pollution exposure by **{r['exposure_reduction_pct']}%** compared "
            f"with the shortest route, adding only {r['extra_minutes']} minutes "
            f"({r['shortest']['distance_m']} m vs {r['cool']['distance_m']} m). "
            f"Recommended action: take the CoolPath route.")
