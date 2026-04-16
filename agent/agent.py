import json
import logging
from agent.llm_client import chat
import agent.tools as tool_fns

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an internship ranking agent for a 3rd year CS student based in Cebu, Philippines.
Their skills: Python, Django, React, AWS, Docker.

You have raw internship listings to process. Use your tools in this order:
1. filter_expired — remove listings with past deadlines
2. score_listing — score all remaining listings for relevance
3. deduplicate — merge duplicate listings across sources
4. rank_listings — sort by score
5. write_report — write the final report (call this last)

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
    "filter_expired": lambda args: tool_fns.filter_expired(args["listings"]),
    "score_listing":  lambda args: tool_fns.score_listing(args["listings"]),
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
                f"Call tools in order: filter_expired → score_listing → deduplicate → rank_listings → write_report.\n\n"
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
