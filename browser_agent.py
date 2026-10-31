import argparse
import json
import sys
from playwright.sync_api import sync_playwright

def run():
    parser = argparse.ArgumentParser(description="Browser agent automation script")
    parser.add_argument("--base-url", required=True, help="Base URL for the benchmark")
    parser.add_argument("--scenario", required=True, choices=["search", "dynamic_dom", "pagination"], help="Scenario to execute")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    scenario = args.scenario

    extracted_text = None
    success = False
    final_url = ""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        try:
            if scenario == "search":
                page.goto(base_url, wait_until="networkidle")
                
                input_elem = page.locator("#search-input, input[name='search'], input[name='q'], input[type='text'], input[type='search'], input").first
                input_elem.wait_for(state="visible", timeout=10000)
                input_elem.fill("browser automation")

                submit_btn = page.locator("#search-submit, #search-button, button[type='submit'], input[type='submit'], button:has-text('Search')").first
                if submit_btn.count() > 0 and submit_btn.is_visible():
                    submit_btn.click()
                else:
                    input_elem.press("Enter")

                result_loc = page.locator("#search-result")
                result_loc.wait_for(state="visible", timeout=10000)
                
                page.wait_for_function(
                    "el => el && el.textContent.trim().length > 0",
                    arg=result_loc.element_handle(),
                    timeout=10000
                )
                
                extracted_text = result_loc.text_content().strip()
                if extracted_text == "Found: browser automation":
                    success = True

            elif scenario == "dynamic_dom":
                page.goto(f"{base_url}/dynamic", wait_until="networkidle")
                
                button = page.locator("#load-record")
                button.wait_for(state="visible", timeout=10000)
                button.click()

                result_loc = page.locator("#dynamic-result")
                result_loc.wait_for(state="visible", timeout=10000)
                
                page.wait_for_function(
                    "el => el && el.textContent.includes('DYNAMIC-42')",
                    arg=result_loc.element_handle(),
                    timeout=10000
                )
                
                extracted_text = result_loc.text_content().strip()
                if extracted_text == "Loaded record: DYNAMIC-42":
                    success = True

            elif scenario == "pagination":
                page.goto(f"{base_url}/page/1", wait_until="networkidle")
                
                next_link = page.locator("a:has-text('Next'), #next-page, a[href*='/page/2']").first
                next_link.wait_for(state="visible", timeout=10000)
                next_link.click()

                indicator = page.locator("text=Page 2 of 2")
                indicator.wait_for(state="visible", timeout=10000)

                result_loc = page.locator("#page-record")
                result_loc.wait_for(state="visible", timeout=10000)
                
                extracted_text = result_loc.text_content().strip()
                if extracted_text == "Record 2 of 2: pagination verified" and indicator.is_visible():
                    success = True

            final_url = page.url
        except Exception:
            final_url = page.url if page else ""
        finally:
            context.close()
            browser.close()

    result = {
        "scenario": scenario,
        "success": success,
        "extracted_text": extracted_text,
        "final_url": final_url
    }
    print(json.dumps(result))

if __name__ == "__main__":
    run()
