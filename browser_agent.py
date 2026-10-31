import argparse
import json
import sys
from playwright.sync_api import sync_playwright


def run():
    parser = argparse.ArgumentParser(description="Browser Agent Benchmark Runner")
    parser.add_argument("--base-url", required=True, help="Benchmark base URL")
    parser.add_argument(
        "--scenario",
        required=True,
        choices=["search", "dynamic_dom", "pagination"],
        help="Scenario name to execute",
    )
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    scenario = args.scenario

    result = {
        "scenario": scenario,
        "success": False,
        "extracted_text": None,
        "final_url": "",
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        try:
            if scenario == "search":
                page.goto(f"{base_url}/")
                search_input = page.locator(
                    "#search-input, input[name='q'], input[name='search'], input[type='text'], input"
                ).first
                search_input.fill("browser automation")

                submit_btn = page.locator(
                    "#search-button, #search-submit, button[type='submit'], input[type='submit']"
                ).first
                if submit_btn.count() > 0 and submit_btn.is_visible():
                    submit_btn.click()
                else:
                    search_input.press("Enter")

                page.wait_for_selector(
                    "#search-result:has-text('Found: browser automation')", timeout=10000
                )
                extracted_text = page.locator("#search-result").inner_text().strip()
                result["extracted_text"] = extracted_text
                result["final_url"] = page.url
                if extracted_text == "Found: browser automation":
                    result["success"] = True

            elif scenario == "dynamic_dom":
                page.goto(f"{base_url}/dynamic")
                page.click("#load-record")
                page.wait_for_selector(
                    "#dynamic-result:has-text('Loaded record: DYNAMIC-42')", timeout=10000
                )
                extracted_text = page.locator("#dynamic-result").inner_text().strip()
                result["extracted_text"] = extracted_text
                result["final_url"] = page.url
                if extracted_text == "Loaded record: DYNAMIC-42":
                    result["success"] = True

            elif scenario == "pagination":
                page.goto(f"{base_url}/page/1")
                next_link = page.locator(
                    "a:has-text('Next'), #next-page, a[rel='next']"
                ).first
                next_link.click()

                page.wait_for_selector("text=Page 2 of 2", timeout=10000)
                page.wait_for_selector(
                    "#page-record:has-text('Record 2 of 2: pagination verified')", timeout=10000
                )
                extracted_text = page.locator("#page-record").inner_text().strip()
                result["extracted_text"] = extracted_text
                result["final_url"] = page.url
                if extracted_text == "Record 2 of 2: pagination verified":
                    result["success"] = True

        except Exception:
            if page:
                result["final_url"] = page.url
        finally:
            browser.close()

    print(json.dumps(result))


if __name__ == "__main__":
    run()
