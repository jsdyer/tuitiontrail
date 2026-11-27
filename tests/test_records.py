from copy import deepcopy
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from records import first_view, write_records
from refresh import cell, insert, validate


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.anchors = []
        self.canonicals = []

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "a":
            self.anchors.append(attrs["href"])
        elif tag == "link" and attrs.get("rel") == "canonical":
            self.canonicals.append(attrs["href"])


class RecordsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT / "web/data/edition.json").read_text())
        cls.settings = json.loads((ROOT / "web/settings.json").read_text())
        cls.tool = json.loads((ROOT / "tool.json").read_text())

    def test_amounts_and_unpublished_source_flags(self):
        base = {"SCALAR_FACTOR": "units", "STATUS": "", "SYMBOL": "", "VALUE": "0"}
        self.assertEqual(cell(base), 0)
        self.assertEqual(cell(dict(base, VALUE="", STATUS="x")), "x")
        self.assertEqual(cell(dict(base, VALUE="3100", STATUS="E")), [3100, "E"])
        with self.assertRaises(ValueError):
            cell(dict(base, SCALAR_FACTOR="thousands"))
        with self.assertRaises(ValueError):
            insert({"2012": 100}, "2012", 200)

    def test_check_rejects_incomplete_grad_data_and_empty_fees(self):
        data = deepcopy(self.data)
        data["earnings"]["Health and related fields"]["Canada"]["2010"].pop("5")
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            validate(data)
        data = deepcopy(self.data)
        data["tuition"]["Nursing"]["Nova Scotia"] = {"2026/2027": ".."}
        with self.assertRaisesRegex(ValueError, "nursing"):
            validate(data)

    def test_first_view_uses_source_and_new_settings(self):
        settings = dict(self.settings, field="Education", left="Ontario", right="Alberta")
        result = first_view(self.data, settings)
        series = self.data["tuition"]["Education"]["Ontario"]
        latest = series[max(series)]
        self.assertIn(f"${latest:,}", result["FEE_RESULT"])
        self.assertIn("Ontario", result["FEE_HISTORY"])
        self.assertIn(self.data["income_units"], result["INCOME_RESULT"])

    def test_every_record_is_canonical_linked_and_backed_by_real_files(self):
        with TemporaryDirectory() as temp:
            stage = Path(temp)
            (stage / "data").mkdir()
            (stage / "index.html").touch()
            (stage / "data/edition.json").touch()
            status = write_records(stage, self.tool, self.data)
            prefix = "https://coolcode.ca/tuitiontrail/"
            def local(path):
                p = stage / path
                return p / "index.html" if path.endswith("/") or path == "" else p
            urls = {node.text for node in ET.parse(stage / "sitemap.xml").iterfind(".//{*}loc")}
            self.assertEqual(len(urls), status["sitemap_urls"])
            self.assertIn(prefix + "records/nursing/nova-scotia/", urls)
            self.assertIn(prefix + "records/sources/", urls)
            linked = {prefix + "records/"}
            for url in urls:
                path = url.removeprefix(prefix)
                parser = Links()
                parser.feed(local(path).read_text())
                self.assertEqual(parser.canonicals, [url])
                for href in parser.anchors:
                    target = urlparse(urljoin(url, href))._replace(query="", fragment="").geturl()
                    if target.startswith(prefix):
                        linked.add(target)
                        self.assertTrue(local(target.removeprefix(prefix)).is_file(), (url, href))
            self.assertFalse(urls - linked)
