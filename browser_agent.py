import json
import sys
from playwright.sync_api import sync_playwright


def main():
    target_url = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(target_url, wait_until="domcontentloaded")

            title = page.title()

            h1_element = page.query_selector("h1")
            heading = h1_element.inner_text().strip() if h1_element else None

            data = {
                "url": page.url,
                "title": title,
                "heading": heading,
            }

            print(json.dumps(data))
        finally:
            browser.close()


if __name__ == "__main__":
    main()
