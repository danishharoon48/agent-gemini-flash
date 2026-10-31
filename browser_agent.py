import argparse
import json
import sys
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright, expect


def run():
    parser = argparse.ArgumentParser(description="Playwright browser agent")
    parser.add_argument("--base-url", required=True, help="Base URL of the benchmark")
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
                target_url = base_url + "/"
                page.goto(target_url)
                page.fill("input#search", "browser automation")
                page.click("button[type=submit]")
                search_result = page.locator("#search-result")
                search_result.wait_for(state="visible")
                raw_text = search_result.inner_text().strip()
                result["final_url"] = page.url
                if raw_text == "Found: browser automation":
                    result["extracted_text"] = raw_text
                    result["success"] = True
                else:
                    result["extracted_text"] = raw_text

            elif scenario == "dynamic_dom":
                target_url = urljoin(base_url + "/", "dynamic")
                page.goto(target_url)
                page.click("button#load-record")
                dyn_result = page.locator("#dynamic-result")
                expect(dyn_result).to_have_text("Loaded record: DYNAMIC-42")
                raw_text = dyn_result.inner_text().strip()
                result["final_url"] = page.url
                if raw_text == "Loaded record: DYNAMIC-42":
                    result["extracted_text"] = raw_text
                    result["success"] = True
                else:
                    result["extracted_text"] = raw_text

            elif scenario == "pagination":
                target_url = urljoin(base_url + "/", "page/1")
                page.goto(target_url)
                page.click("a#next")
                h1_locator = page.locator("h1")
                expect(h1_locator).to_have_text("Page 2 of 2")
                page_record = page.locator("#page-record")
                raw_text = page_record.inner_text().strip()
                result["final_url"] = page.url
                if raw_text == "Record 2 of 2: pagination verified":
                    result["extracted_text"] = raw_text
                    result["success"] = True
                else:
                    result["extracted_text"] = raw_text

        except Exception as e:
            if not result["final_url"]:
                try:
                    result["final_url"] = page.url
                except Exception:
                    result["final_url"] = ""
            result["success"] = False
        finally:
            context.close()
            browser.close()

    print(json.dumps(result))


if __name__ == "__main__":
    run()
