import argparse
import json
import sys
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright, expect


def main():
    parser = argparse.ArgumentParser(description="Playwright Browser Agent Scenario Runner")
    parser.add_argument("--base-url", required=True, help="Benchmark base URL")
    parser.add_argument(
        "--scenario",
        required=True,
        choices=["search", "dynamic_dom", "pagination"],
        help="Scenario to run",
    )
    args = parser.parse_args()

    base_url = args.base_url
    if not base_url.endswith("/"):
        base_url += "/"

    scenario = args.scenario
    success = False
    extracted_text = None
    final_url = ""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        try:
            if scenario == "search":
                target_url = base_url
                page.goto(target_url)
                page.fill("input#search", "browser automation")
                page.click("button[type=submit]")
                page.wait_for_selector("#search-result")
                result_locator = page.locator("#search-result")
                raw_text = result_locator.inner_text()
                extracted_text = raw_text.strip()
                final_url = page.url
                if extracted_text == "Found: browser automation":
                    success = True

            elif scenario == "dynamic_dom":
                target_url = urljoin(base_url, "dynamic")
                page.goto(target_url)
                page.click("button#load-record")
                result_locator = page.locator("#dynamic-result")
                expect(result_locator).to_have_text("Loaded record: DYNAMIC-42")
                raw_text = result_locator.inner_text()
                extracted_text = raw_text.strip()
                final_url = page.url
                if extracted_text == "Loaded record: DYNAMIC-42":
                    success = True

            elif scenario == "pagination":
                target_url = urljoin(base_url, "page/1")
                page.goto(target_url)
                page.click("a#next")
                h1_locator = page.locator("h1")
                expect(h1_locator).to_have_text("Page 2 of 2")
                record_locator = page.locator("#page-record")
                raw_text = record_locator.inner_text()
                extracted_text = raw_text.strip()
                final_url = page.url
                if extracted_text == "Record 2 of 2: pagination verified":
                    success = True

        except Exception:
            try:
                final_url = page.url
            except Exception:
                final_url = ""
            success = False

        finally:
            context.close()
            browser.close()

    output = {
        "scenario": scenario,
        "success": success,
        "extracted_text": extracted_text,
        "final_url": final_url,
    }

    print(json.dumps(output))


if __name__ == "__main__":
    main()
