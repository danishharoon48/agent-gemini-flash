import argparse
import json
import sys
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright, expect


def main():
    parser = argparse.ArgumentParser(description="Playwright browser automation agent")
    parser.add_argument("--base-url", required=True, help="Benchmark base URL")
    parser.add_argument("--scenario", required=True, choices=["search", "dynamic_dom", "pagination"], help="Scenario to run")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/") + "/"
    scenario = args.scenario

    result = {
        "scenario": scenario,
        "success": False,
        "extracted_text": None,
        "final_url": ""
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        try:
            if scenario == "search":
                page.goto(base_url)
                page.fill("input#search", "browser automation")
                page.click("button[type=submit]")
                search_loc = page.locator("#search-result")
                search_loc.wait_for(state="visible")
                extracted = search_loc.inner_text().strip()
                result["extracted_text"] = extracted
                result["final_url"] = page.url
                if extracted == "Found: browser automation":
                    result["success"] = True

            elif scenario == "dynamic_dom":
                target_url = urljoin(base_url, "dynamic")
                page.goto(target_url)
                page.click("button#load-record")
                dynamic_loc = page.locator("#dynamic-result")
                expect(dynamic_loc).to_have_text("Loaded record: DYNAMIC-42", timeout=10000)
                extracted = dynamic_loc.inner_text().strip()
                result["extracted_text"] = extracted
                result["final_url"] = page.url
                if extracted == "Loaded record: DYNAMIC-42":
                    result["success"] = True

            elif scenario == "pagination":
                target_url = urljoin(base_url, "page/1")
                page.goto(target_url)
                page.click("a#next")
                h1_loc = page.locator("h1")
                expect(h1_loc).to_have_text("Page 2 of 2", timeout=10000)
                record_loc = page.locator("#page-record")
                extracted = record_loc.inner_text().strip()
                result["extracted_text"] = extracted
                result["final_url"] = page.url
                if extracted == "Record 2 of 2: pagination verified":
                    result["success"] = True

        except Exception:
            if page:
                result["final_url"] = page.url
        finally:
            context.close()
            browser.close()

    print(json.dumps(result))


if __name__ == "__main__":
    main()
