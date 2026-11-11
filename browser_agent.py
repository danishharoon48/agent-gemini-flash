import argparse
import json
import sys
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright


def run():
    parser = argparse.ArgumentParser(description="Browser automation agent")
    parser.add_argument("--base-url", required=True, help="Base URL for the benchmark target")
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
        context = browser.new_context()
        page = context.new_page()

        try:
            if scenario == "search":
                target_url = urljoin(base_url, "/")
                page.goto(target_url)
                page.fill("input#search", "browser automation")
                page.click("button[type=submit]")
                page.wait_for_selector("#search-result")
                text = page.inner_text("#search-result").strip()
                result["extracted_text"] = text
                result["final_url"] = page.url
                if text == "Found: browser automation":
                    result["success"] = True

            elif scenario == "dynamic_dom":
                target_url = urljoin(base_url, "/dynamic")
                page.goto(target_url)
                page.click("button#load-record")
                page.wait_for_function(
                    "document.querySelector('#dynamic-result')?.textContent.trim() === 'Loaded record: DYNAMIC-42'",
                    timeout=10000
                )
                text = page.inner_text("#dynamic-result").strip()
                result["extracted_text"] = text
                result["final_url"] = page.url
                if text == "Loaded record: DYNAMIC-42":
                    result["success"] = True

            elif scenario == "pagination":
                target_url = urljoin(base_url, "/page/1")
                page.goto(target_url)
                page.click("a#next")
                page.wait_for_function(
                    "document.querySelector('h1')?.textContent.trim() === 'Page 2 of 2'",
                    timeout=10000
                )
                page.wait_for_selector("#page-record")
                text = page.inner_text("#page-record").strip()
                result["extracted_text"] = text
                result["final_url"] = page.url
                if text == "Record 2 of 2: pagination verified":
                    result["success"] = True

        except Exception as e:
            result["final_url"] = page.url if page else ""
            result["success"] = False

        finally:
            context.close()
            browser.close()

    print(json.dumps(result))


if __name__ == "__main__":
    run()
