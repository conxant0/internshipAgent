"""Diagnostic script: intercept GraphQL requests+responses on JobStreet listing page."""
import json
from playwright.sync_api import sync_playwright

URL = "https://ph.jobstreet.com/Intern-jobs-in-information-communication-technology/in-Philippines"
graphql_calls = []  # {operation, request_body, response_body}


def handle_response(response):
    if "graphql" not in response.url:
        return
    try:
        req_body = response.request.post_data_json
        op = req_body.get("operationName", "?") if isinstance(req_body, dict) else "?"
        resp_body = response.json()
        graphql_calls.append({"operation": op, "request": req_body, "response": resp_body})
    except Exception:
        pass


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    )
    page = context.new_page()
    page.on("response", handle_response)
    print(f"Navigating to {URL} ...")
    page.goto(URL, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(3000)
    browser.close()

print(f"\n--- Captured {len(graphql_calls)} GraphQL operations ---\n")
for call in graphql_calls:
    op = call["operation"]
    resp = call["response"]
    data_keys = list(resp["data"].keys()) if resp and isinstance(resp.get("data"), dict) else []
    print(f"Operation: {op}  →  data keys: {data_keys}")

print("\n\n=== FULL DUMP of each operation ===")
for call in graphql_calls:
    op = call["operation"]
    resp = call["response"]
    print(f"\n{'='*60}")
    print(f"OPERATION: {op}")
    print(f"--- Request variables ---")
    req = call["request"]
    if isinstance(req, dict):
        print(json.dumps(req.get("variables", {}), indent=2))
    print(f"--- Response data ---")
    if resp and isinstance(resp.get("data"), dict):
        print(json.dumps(resp["data"], indent=2)[:4000])
    else:
        print(str(resp)[:500])
