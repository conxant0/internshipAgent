import json
import logging
from agent.llm_client import chat
import agent.tools as tool_fns

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an internship ranking agent for a 3rd year CS student based in Cebu, Philippines.
Their skills: Python, Django, React, AWS, Docker.

You have raw internship listings to process. Use your tools in this order:
1. filter_expired — remove listings with past deadlines
2. fetch_descriptions — fetch the full description text from each listing's detail page
3. enrich_listings — extract compensation, deadline, location, and requirements from each description
4. score_listing — score all remaining listings for relevance
5. deduplicate — merge duplicate listings across sources
6. rank_listings — sort by score
7. write_report — write the final report (call this last)

Always call write_report when you are done. Do not stop before calling it."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "filter_expired",
            "description": "Remove listings whose deadline has already passed. Null deadlines are kept.",
            "parameters": {
                "type": "object",
                "properties": {"listings": {"type": "array", "items": {"type": "object"}}},
                "required": ["listings"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_descriptions",
            "description": "Fetch full description text from each listing's detail page. Call this after filter_expired and before score_listing.",
            "parameters": {
                "type": "object",
                "properties": {"listings": {"type": "array", "items": {"type": "object"}}},
                "required": ["listings"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "enrich_listings",
            "description": "Use a small LLM to extract compensation, deadline, location, and specific skill requirements from each listing's description. Overwrites existing fields with more specific values. Call this after fetch_descriptions and before score_listing.",
            "parameters": {
                "type": "object",
                "properties": {"listings": {"type": "array", "items": {"type": "object"}}},
                "required": ["listings"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "score_listing",
            "description": "Score each listing 0-100 for relevance. Adds a 'score' field to each listing.",
            "parameters": {
                "type": "object",
                "properties": {"listings": {"type": "array", "items": {"type": "object"}}},
                "required": ["listings"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "deduplicate",
            "description": "Remove duplicate listings. Keeps the richest version when duplicates are found.",
            "parameters": {
                "type": "object",
                "properties": {"listings": {"type": "array", "items": {"type": "object"}}},
                "required": ["listings"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rank_listings",
            "description": "Sort listings by score descending.",
            "parameters": {
                "type": "object",
                "properties": {"listings": {"type": "array", "items": {"type": "object"}}},
                "required": ["listings"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_report",
            "description": "Write the final ranked report to output/report.md. Call this when all processing is done.",
            "parameters": {
                "type": "object",
                "properties": {"listings": {"type": "array", "items": {"type": "object"}}},
                "required": ["listings"],
            },
        },
    },
]

TOOL_MAP = {
    "filter_expired":    lambda args: tool_fns.filter_expired(args["listings"]),
    "fetch_descriptions": lambda args: tool_fns.fetch_descriptions(args["listings"]),
    "enrich_listings":    lambda args: tool_fns.enrich_listings(args["listings"]),
    "score_listing":     lambda args: tool_fns.score_listing(args["listings"]),
    "deduplicate":    lambda args: tool_fns.deduplicate(args["listings"]),
    "rank_listings":  lambda args: tool_fns.rank_listings(args["listings"]),
    "write_report":   lambda args: tool_fns.write_report(args["listings"]),
}


def run(listings: list):
    current = listings  # we track state; LLM only sees summaries

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
                f"Call tools in order: filter_expired → fetch_descriptions → enrich_listings → score_listing → deduplicate → rank_listings → write_report.\n\n"
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

        for tc in response.tool_calls:
            name = tc.function.name
            logger.info(f"[iteration {iteration}] Agent calling: {name}")

            result = TOOL_MAP[name]({"listings": current})

            if name == "write_report":
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": f"Report written to {result}.",
                })
                logger.info(f"Report written to: {result}")
                return result

            current = result
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": f"Done. {len(current)} listings remaining.",
            })

    logger.warning("Agent hit max iterations without finishing")
    return None
