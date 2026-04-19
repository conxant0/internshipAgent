import json
import logging
from pathlib import Path
from agent.llm_client import chat
import agent.tools as tool_fns

logger = logging.getLogger(__name__)

STAGE_ORDER = [
    "filter_expired",
    "fetch_descriptions",
    "enrich_listings",
    "filter_ineligible",
    "score_listing",
    "deduplicate",
    "rank_listings",
]

_CHECKPOINT_DIR = Path(__file__).parent.parent / "data" / "checkpoints"


def _save_checkpoint(stage: str, listings: list) -> None:
    _CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    with open(_CHECKPOINT_DIR / f"{stage}.json", "w", encoding="utf-8") as f:
        json.dump(listings, f, indent=2)


def _load_latest_checkpoint() -> tuple:
    """Return (last_completed_stage, listings) or (None, None)."""
    for stage in reversed(STAGE_ORDER):
        path = _CHECKPOINT_DIR / f"{stage}.json"
        if path.exists():
            with open(path, encoding="utf-8") as f:
                return stage, json.load(f)
    return None, None


SYSTEM_PROMPT = """You are an internship ranking agent.

You have raw internship listings to process. Use your tools in this order:
1. filter_expired — remove listings with past deadlines (raw scraped data)
2. fetch_descriptions — fetch the full description text from each listing's detail page
3. enrich_listings — extract compensation, deadline, location, and requirements from each description
4. filter_ineligible — drop listings with post-enrichment expired deadlines or non-CS/IT course restrictions
5. score_listing — score all remaining listings for relevance
6. deduplicate — merge duplicate listings across sources
7. rank_listings — sort by score
8. write_report — write the final report (call this last)

Always call write_report when you are done. Do not stop before calling it."""

def _no_params(name: str, description: str) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": {}},
        },
    }

TOOLS = [
    _no_params("filter_expired", "Remove listings whose deadline has already passed. Null deadlines are kept."),
    _no_params("fetch_descriptions", "Fetch full description text from each listing's detail page. Call this after filter_expired and before enrich_listings."),
    _no_params("enrich_listings", "Use a small LLM to extract compensation, deadline, location, and requirements from each listing's description. Call this after fetch_descriptions and before filter_ineligible."),
    _no_params("filter_ineligible", "Drop listings with post-enrichment expired deadlines or eligibility constraints that restrict to a non-CS/IT course field. Call this after enrich_listings and before score_listing."),
    _no_params("score_listing", "Score each listing 0-100 for relevance. Adds a 'score' field to each listing."),
    _no_params("deduplicate", "Remove duplicate listings. Keeps the richest version when duplicates are found."),
    _no_params("rank_listings", "Sort listings by score descending."),
    _no_params("write_report", "Write the final ranked report to output/report.md. Call this when all processing is done."),
]

def run(listings: list, profile: dict = None, preferences: dict = None, resume: bool = False):
    current = listings  # we track state; LLM only sees summaries
    completed_stages: set = set()

    if resume:
        last_stage, saved = _load_latest_checkpoint()
        if last_stage:
            current = saved
            completed_stages = set(STAGE_ORDER[: STAGE_ORDER.index(last_stage) + 1])
            logger.info(f"Resuming from checkpoint after '{last_stage}' ({len(current)} listings)")

    _profile = profile or {}
    _preferences = preferences or {}

    tool_map = {
        "filter_expired":     lambda lst: tool_fns.filter_expired(lst),
        "fetch_descriptions": lambda lst: tool_fns.fetch_descriptions(lst),
        "enrich_listings":    lambda lst: tool_fns.enrich_listings(lst),
        "filter_ineligible":  lambda lst: tool_fns.filter_ineligible(lst),
        "score_listing":      lambda lst: tool_fns.score_listing(lst, _profile, _preferences),
        "deduplicate":        lambda lst: tool_fns.deduplicate(lst),
        "rank_listings":      lambda lst: tool_fns.rank_listings(lst),
        "write_report":       lambda lst: tool_fns.write_report(lst),
    }

    for stage in completed_stages:
        if stage in tool_map:
            tool_map[stage] = lambda lst, s=stage: (
                logger.info(f"Skipping '{s}' — already completed (checkpoint)") or lst
            )

    summary = [
        {"title": l.get("title"), "company": l.get("company"), "deadline": l.get("deadline")}
        for l in listings
    ]
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"You have {len(listings)} internship listings to process.\n"
                f"Call tools in order: filter_expired → fetch_descriptions → enrich_listings → filter_ineligible → score_listing → deduplicate → rank_listings → write_report.\n\n"
                f"Listing titles:\n{json.dumps(summary, indent=2)}"
            ),
        },
    ]

    for iteration in range(20):
        response = chat(messages, tools=TOOLS)

        assistant_msg = {"role": "assistant", "content": response.content or ""}
        if response.tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in response.tool_calls
            ]
        messages.append(assistant_msg)

        if not response.tool_calls:
            logger.info("Agent stopped without calling write_report")
            return None

        tool_calls = list(response.tool_calls)
        for idx, tc in enumerate(tool_calls):
            name = tc.function.name
            logger.info(f"[iteration {iteration}] Agent calling: {name}")

            if name not in tool_map:
                logger.warning(f"[iteration {iteration}] Unknown tool: {name!r} — skipping")
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": f"Error: unknown tool '{name}'. Available tools: {', '.join(tool_map)}.",
                })
                continue

            result = tool_map[name](current)

            if name == "write_report":
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": f"Report written to {result}.",
                })
                # Satisfy the message contract for any remaining tool calls in this batch.
                for remaining_tc in tool_calls[idx + 1:]:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": remaining_tc.id,
                        "content": "Not executed — write_report already completed.",
                    })
                logger.info(f"Report written to: {result}")
                return result

            current = result
            if name in STAGE_ORDER:
                _save_checkpoint(name, current)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": f"Done. {len(current)} listings remaining.",
            })

    logger.warning("Agent hit max iterations without finishing")
    return None
