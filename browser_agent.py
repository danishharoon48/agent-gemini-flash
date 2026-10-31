import argparse
import json
import sys
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright, expect

def main():
    parser = argparse.ArgumentParser(description="Playwright Browser Agent")
    parser.add_argument("--base-url", required=True, help="Base URL for benchmark")
    parser.add_argument("--scenario", required=True, choices=["search", "dynamic_dom", "pagination"], help="Scenario to execute")
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
        page = browser.new_page()
        try:
            if scenario == "search":
                page.goto(base_url)
                page.fill("input#search", "browser automation")
                page.click("button[type=submit]")
                page.wait_for_selector("#search-result")
                extracted = page.locator("#search-result").inner_text().strip()
                result["extracted_text"] = extracted
                result["final_url"] = page.url
                if extracted == "Found: browser automation":
                    result["success"] = True

            elif scenario == "dynamic_dom":
                target_url = urljoin(base_url, "dynamic")
                page.goto(target_url)
                page.click("button#load-record")
                locator = page.locator("#dynamic-result")
                expect(locator).to_have_text("Loaded record: DYNAMIC-42")
                extracted = locator.inner_text().strip()
                result["extracted_text"] = extracted
                result["final_url"] = page.url
                if extracted == "Loaded record: DYNAMIC-42":
                    result["success"] = True

            elif scenario == "pagination":
                target_url = urljoin(base_url, "page/1")
                page.goto(target_url)
                page.click("a#next")
                expect(page.locator("h1")).to_have_text("Page 2 of 2")
                extracted = page.locator("#page-record").inner_text().strip()
                result["extracted_text"] = extracted
                result["final_url"] = page.url
                if extracted == "Record 2 of 2: pagination verified":
                    result["success"] = True

        except Exception as e:
            result["final_url"] = page.url if page else ""
        finally:
            browser.close()

    print(json.dumps(result))

if __name__ == "__main__":
    main()
