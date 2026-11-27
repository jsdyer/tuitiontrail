"""Exercise the built starter at a project subpath in Chromium."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
import tempfile
import sys
import threading
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build import build


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main():
    screenshots = ROOT / "browser-checks"
    screenshots.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        shutil.copytree(ROOT / "dist", Path(temporary) / "example-tool")
        example = Path(temporary) / "preset-fixture"
        example.mkdir()
        shutil.copytree(ROOT / "web", example / "web")
        shutil.copytree(ROOT / "examples/common-pages", example / "common-pages")
        for name in ("tool.json", "README.md"):
            shutil.copyfile(ROOT / name, example / name)
        build(example)
        server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=temporary))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page(viewport={"width": 1280, "height": 1000})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(f"http://127.0.0.1:{server.server_port}/example-tool/")
                assert page.locator("#input").input_value() == "Halifax\nLangley\nHalifax\nVancouver"
                assert page.locator("#output").input_value() == "Halifax\nLangley\nVancouver"
                assert "1 duplicate removed" in page.locator("#status").inner_text()
                page.locator("#input").fill('<img src=x onerror="alert(1)">\n<img src=x onerror="alert(1)">')
                assert page.locator("#output").input_value() == '<img src=x onerror="alert(1)">'
                assert page.locator("img").count() == 0
                page.locator("#clear").click()
                assert page.locator("#output").input_value() == ""
                assert "Paste one item per line" in page.locator("#status").inner_text()
                page.locator("#sample").click()
                assert page.locator("#output").input_value() == "Halifax\nLangley\nVancouver"
                page.screenshot(path=str(screenshots / "desktop.png"), full_page=True)
                page.set_viewport_size({"width": 390, "height": 844})
                page.goto(f"http://127.0.0.1:{server.server_port}/example-tool/")
                assert page.locator("#input").bounding_box()["y"] < 844
                assert page.locator("#output").input_value() == "Halifax\nLangley\nVancouver"
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                page.screenshot(path=str(screenshots / "mobile.png"), full_page=True)
                page.goto(f"http://127.0.0.1:{server.server_port}/preset-fixture/dist/remove-duplicate-cities/")
                assert page.locator("#output").input_value() == "Vancouver\nHalifax\nCharlottetown"
                page.locator("#input").fill("Surrey\nSurrey\nOttawa")
                assert page.locator("#output").input_value() == "Surrey\nOttawa"
                page.get_by_role("button", name="Restore example").click()
                assert page.locator("#output").input_value() == "Vancouver\nHalifax\nCharlottetown"
                assert not errors, errors
                browser.close()
            print("Browser checks passed: project subpath, sample, clear, safe text and mobile layout")
        finally:
            server.shutdown()


if __name__ == "__main__":
    main()
