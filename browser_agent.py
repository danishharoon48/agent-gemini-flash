import argparse
import json
import sys
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright


def run():
    parser = argparse.ArgumentParser(description="Browser automation agent benchmark")
    parser.add_argument("--base-url", required=True, help="Base URL of benchmark server")
    parser.add_argument("--scenario", required=True, choices=["search", "dynamic_dom", "pagination"], help="Scenario to run")
    args = parser.parse_args()

    result = {
        "scenario": args.scenario,
        "success": False,
        "extracted_text": None,
        "final_url": ""
    }

    base_url = args.base_url
    if not base_url.endswith("/"):
        base_url += "/"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            if args.scenario == "search":
                page.goto(args.base_url)
                page.fill("input#search", "browser automation")
                page.click("button[type=submit]")
                page.wait_for_selector("#search-result")
                text = page.locator("#search-result").inner_text().strip()
                result["extracted_text"] = text
                result["final_url"] = page.url
                if text == "Found: browser automation":
                    result["success"] = True

            elif args.scenario == "dynamic_dom":
                target_url = urljoin(base_url, "dynamic")
                page.goto(target_url)
                page.click("button#load-record")
                page.locator("#dynamic-result", has_text="Loaded record: DYNAMIC-42").wait_for(timeout=10000)
                text = page.locator("#dynamic-result").inner_text().strip()
                result["extracted_text"] = text
                result["final_url"] = page.url
                if text == "Loaded record: DYNAMIC-42":
                    result["success"] = True

            elif args.scenario == "pagination":
                target_url = urljoin(base_url, "page/1")
                page.goto(target_url)
                page.click("a#next")
                page.locator("h1", has_text="Page 2 of 2").wait_for(timeout=10000)
                text = page.locator("#page-record").inner_text().strip()
                result["extracted_text"] = text
                result["final_url"] = page.url
                if text == "Record 2 of 2: pagination verified":
                    result["success"] = True

            browser.close()
    except Exception:
        pass

    print(json.dumps(result))


if __name__ == "__main__":
    run()
