import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build import ROOT, build, metadata


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        shutil.copytree(ROOT / "web", self.root / "web")
        shutil.copyfile(ROOT / "tool.json", self.root / "tool.json")
        shutil.copyfile(ROOT / "README.md", self.root / "README.md")

    def edit(self, **changes):
        tool = json.loads((self.root / "tool.json").read_text())
        tool.update(changes)
        (self.root / "tool.json").write_text(json.dumps(tool))

    def test_build_is_scoped_to_web_and_escapes_metadata(self):
        (self.root / "private.txt").write_text("must not publish")
        self.edit(title='<img src=x onerror="bad()">')
        build(self.root)
        page = (self.root / "dist/index.html").read_text()
        self.assertIn('&lt;img', page)
        self.assertNotIn('<img', page)
        self.assertNotIn('{{', page)
        self.assertIn('href="./style.css"', page)
        self.assertFalse((self.root / "dist/private.txt").exists())
        self.assertTrue((self.root / "dist/.nojekyll").exists())

    def test_reporting_is_scoped_to_initialized_coolcode_tools(self):
        for owner, slug, enabled in [
            ("jsdyer", "coolcode-tool-template", False),
            ("another-owner", "my-tool", False),
            ("jsdyer", "my-tool", True),
        ]:
            with self.subTest(owner=owner, slug=slug):
                self.edit(id=slug, url=f"/{slug}/", source=f"https://github.com/{owner}/{slug}")
                build(self.root)
                page = (self.root / "dist/index.html").read_text()
                self.assertEqual('/assets/tool-metrics.js' in page, enabled)
                self.assertEqual(f'https://coolcode.ca/report/?tool={slug}' in page, enabled)
                self.assertNotIn("{{", page)

    def test_common_pages_are_opt_in_and_preserve_root_search_title_and_stats(self):
        self.edit(id="example", url="/example/", source="https://github.com/jsdyer/example")
        build(self.root)
        route = self.root / "dist/remove-duplicate-cities/index.html"
        self.assertFalse(route.exists())
        entry = self.root / "web/index.html"
        entry.write_text(re.sub(r"<title>.*?</title>", "<title>Custom search title · CoolCode</title>",
                                entry.read_text(), count=1, flags=re.S))
        shutil.copytree(ROOT / "examples/common-pages", self.root / "common-pages")
        build(self.root)
        root = (self.root / "dist/index.html").read_text()
        self.assertIn("<title>Custom search title · CoolCode</title>", root)
        self.assertIn('href="./remove-duplicate-cities/"', root)
        self.assertIn('rel="canonical" href="https://coolcode.ca/example/"', root)
        page = route.read_text()
        self.assertIn("<title>Remove duplicate cities from a list · CoolCode</title>", page)
        self.assertIn('rel="canonical" href="https://coolcode.ca/example/remove-duplicate-cities/"', page)
        self.assertIn('src="../app.mjs"', page)
        self.assertIn('data-tool-id="example"', page)
        self.assertIn('src="/assets/tool-metrics.js"', page)
        self.assertIn("Vancouver\nHalifax\nCharlottetown</textarea>", page)

    def test_rejects_invalid_common_page_paths_and_collisions(self):
        directory = self.root / "common-pages"
        directory.mkdir()
        manifest = directory / "manifest.json"
        for slug in ("../escape", "/absolute", "a/b", "x?name=1", ""):
            with self.subTest(slug=slug):
                manifest.write_text(json.dumps([{"slug": slug, "title": "T", "description": "D"}]))
                with self.assertRaises(ValueError):
                    build(self.root)
        manifest.write_text('[{"slug":"data","title":"Data","description":"Some data"}]')
        (self.root / "web/data").mkdir()
        with self.assertRaisesRegex(ValueError, "collides"):
            build(self.root)

    def test_url_matches_tool_id(self):
        self.edit(url="/different/")
        with self.assertRaises(ValueError): metadata(self.root)

    def test_requires_a_source_sentence_and_a_guide_note(self):
        (self.root / "README.md").write_text("# A tool")
        with self.assertRaisesRegex(ValueError, "README note"):
            metadata(self.root)
        self.edit(data_info={"mode": "local", "detail": ""})
        with self.assertRaisesRegex(ValueError, "homepage card"):
            metadata(self.root)

    def test_browser_access_is_explicit(self):
        self.edit(access="install")
        with self.assertRaisesRegex(ValueError, "immediately usable"):
            metadata(self.root)

    def test_failed_build_keeps_existing_output(self):
        build(self.root)
        existing = (self.root / "dist/index.html").read_bytes()
        self.edit(source="javascript:bad()")
        with self.assertRaises(ValueError): build(self.root)
        self.assertEqual((self.root / "dist/index.html").read_bytes(), existing)


if __name__ == "__main__": unittest.main()
