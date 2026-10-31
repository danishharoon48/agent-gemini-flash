import argparse
import json
import sys
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright, expect


def run_scenario(base_url: str, scenario: str) -> dict:
    result = {
        "scenario": scenario,
        "success": False,
        "extracted_text": None,
        "final_url": ""
    }

    normalized_base = base_url if base_url.endswith("/") else base_url + "/"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        try:
            if scenario == "search":
                page.goto(normalized_base)
                page.locator("input#search").fill("browser automation")
                page.locator("button[type=submit]").click()
                search_result = page.locator("#search-result")
                search_result.wait_for(state="visible", timeout=10000)
                extracted = search_result.inner_text().strip()
                result["extracted_text"] = extracted
                result["final_url"] = page.url
                if extracted == "Found: browser automation":
                    result["success"] = True

            elif scenario == "dynamic_dom":
                target_url = urljoin(normalized_base, "dynamic")
                page.goto(target_url)
                page.locator("button#load-record").click()
                dynamic_elem = page.locator("#dynamic-result")
                expect(dynamic_elem).to_have_text("Loaded record: DYNAMIC-42", timeout=10000)
                extracted = dynamic_elem.inner_text().strip()
                result["extracted_text"] = extracted
                result["final_url"] = page.url
                if extracted == "Loaded record: DYNAMIC-42":
                    result["success"] = True

            elif scenario == "pagination":
                target_url = urljoin(normalized_base, "page/1")
                page.goto(target_url)
                page.locator("a#next").click()
                expect(page.locator("h1")).to_have_text("Page 2 of 2", timeout=10000)
                page_record = page.locator("#page-record")
                page_record.wait_for(state="visible", timeout=10000)
                extracted = page_record.inner_text().strip()
                result["extracted_text"] = extracted
                result["final_url"] = page.url
                if extracted == "Record 2 of 2: pagination verified":
                    result["success"] = True

            else:
                result["final_url"] = page.url

        except Exception as e:
            try:
                result["final_url"] = page.url
            except Exception:
                pass
        finally:
            context.close()
            browser.close()

    return result


def main():
    parser = argparse.ArgumentParser(description="Playwright browser automation agent")
    parser.add_argument("--base-url", required=True, help="Base URL of the benchmark application")
    parser.add_argument("--scenario", required=True, choices=["search", "dynamic_dom", "pagination"], help="Scenario to run")
    args = parser.parse_args()

    result = run_scenario(args.base_url, args.scenario)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
