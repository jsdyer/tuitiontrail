"""Exercise the real tuition comparison and crawlable records in Chromium."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import tempfile
import threading

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main():
    screenshots = ROOT / "browser-checks"
    screenshots.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        (Path(temp) / "tuitiontrail").symlink_to(ROOT / "dist", target_is_directory=True)
        server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=temp))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        home = f"http://127.0.0.1:{server.server_port}/tuitiontrail/"
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(executable_path=os.getenv("CHROMIUM_PATH"))
                errors = []
                page = browser.new_page(viewport={"width": 1280, "height": 960})
                page.route("**/assets/tool-metrics.js", lambda route: route.fulfill(body=""))
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(home)
                page.locator("#fees").wait_for()
                default = page.locator("#tuition-output").inner_text()
                assert "Nursing" in default and "Nova Scotia" in default and "British Columbia" in default
                assert "$" in default
                page.screenshot(path=str(screenshots / "desktop.png"), full_page=True)
                fees = page.locator("#fees")
                fees.get_by_label("Field of study").select_option("Education")
                fees.get_by_label("First place").select_option("Ontario")
                fees.get_by_label("Academic year").select_option("2019/2020")
                assert "2019/2020" in page.locator("#tuition-output").inner_text()
                page.locator("#income").get_by_label("Graduation year").select_option("2010")
                assert "10 years (2020)" in page.locator("#income-output").inner_text()
                page.reload()
                fees.wait_for()
                assert fees.get_by_label("Field of study").input_value() == "Education"
                assert fees.get_by_label("First place").input_value() == "Ontario"
                assert fees.get_by_label("Academic year").input_value() == "2019/2020"
                page.locator("summary").click()
                assert page.locator("#fee-history th").count() > 8
                page.get_by_role("link", name="Ontario tuition history").click()
                assert page.locator("h1").inner_text() == "Education undergraduate tuition in Ontario"
                assert page.locator("tbody tr").count() > 10
                for width in [390, 320]:
                    page.set_viewport_size({"width": width, "height": 844})
                    page.goto(home)
                    fees.wait_for()
                    assert fees.bounding_box()["y"] < 844
                    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                    fees.get_by_label("First place").select_option("Ontario")
                    assert "Ontario" in page.locator("#tuition-output").inner_text()
                    if width == 390:
                        page.screenshot(path=str(screenshots / "mobile.png"), full_page=True)
                offline = browser.new_context(java_script_enabled=False)
                static = offline.new_page()
                static.goto(home)
                assert static.locator("#tuition-output").inner_text() == default
                assert "$" in static.locator("#income-output").inner_text()
                static.get_by_role("link", name="Nova Scotia tuition history").click()
                assert static.locator("tbody tr").count() > 10
                static.get_by_role("link", name="All records").click()
                static.get_by_role("link", name="Sources and interpretation").click()
                assert static.locator("h1").inner_text() == "How to read tuition and graduate income"
                assert not errors, errors
                browser.close()
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
