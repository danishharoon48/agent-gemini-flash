import argparse
import json
import sys
from playwright.sync_api import sync_playwright

def main():
    parser = argparse.ArgumentParser(description="Playwright Browser Agent")
    parser.add_argument("--base-url", required=True, help="Base URL of the benchmark")
    parser.add_argument("--scenario", required=True, choices=["search", "dynamic_dom", "pagination"], help="Scenario to execute")
    args = parser.parse_args()

    result = {
        "scenario": args.scenario,
        "success": False,
        "extracted_text": None,
        "final_url": ""
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        try:
            if args.scenario == "search":
                page.goto(args.base_url)
                page.fill("input#search", "browser automation")
                page.click("button[type=submit]")
                page.wait_for_selector("#search-result")
                raw_text = page.locator("#search-result").inner_text()
                result["extracted_text"] = raw_text.strip()
                result["final_url"] = page.url
                if result["extracted_text"] == "Found: browser automation":
                    result["success"] = True

            elif args.scenario == "dynamic_dom":
                page.goto(f"{args.base_url}/dynamic")
                page.click("button#load-record")
                
                # Wait until #dynamic-result contains the exact text 'Loaded record: DYNAMIC-42'
                page.wait_for_function(
                    "() => { const el = document.querySelector('#dynamic-result'); return el && el.innerText.trim() === 'Loaded record: DYNAMIC-42'; }"
                )
                
                raw_text = page.locator("#dynamic-result").inner_text()
                result["extracted_text"] = raw_text.strip()
                result["final_url"] = page.url
                if result["extracted_text"] == "Loaded record: DYNAMIC-42":
                    result["success"] = True

            elif args.scenario == "pagination":
                page.goto(f"{args.base_url}/page/1")
                page.click("a#next")
                
                # Wait for h1 to equal 'Page 2 of 2'
                page.wait_for_function(
                    "() => { const el = document.querySelector('h1'); return el && el.innerText.trim() === 'Page 2 of 2'; }"
                )
                
                page.wait_for_selector("#page-record")
                raw_text = page.locator("#page-record").inner_text()
                result["extracted_text"] = raw_text.strip()
                result["final_url"] = page.url
                
                h1_text = page.locator("h1").inner_text().strip()
                if h1_text == "Page 2 of 2" and result["extracted_text"] == "Record 2 of 2: pagination verified":
                    result["success"] = True

        except Exception as e:
            result["success"] = False
            result["extracted_text"] = str(e)
            result["final_url"] = page.url
        finally:
            browser.close()

    print(json.dumps(result))

if __name__ == "__main__":
    main()
