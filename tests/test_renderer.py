# tests/test_renderer.py

import unittest
from src.renderer import render_html, _render_link_list, _render_top_works


def _sample_result(prefix="test", label="Test Onto", uri="https://example.org/test/"):
    return {
        "label": label,
        "uri": uri,
        "prefix": prefix,
        "lov": {
            "found": True,
            "inlinks": 5,
            "importing_vocabs": ["http://a.org/", "http://b.org/"],
            "url": f"https://lov.linkeddata.es/dataset/lov/vocabulary/{prefix}",
            "tags": ["sensor"],
            "versions": [],
        },
        "github": {
            "repos_count": 3,
            "repos": ["https://github.com/org/repo1", "https://github.com/org/repo2"],
        },
        "openalex": {
            "total_works": 42,
            "by_year": {"2021": 10, "2022": 20, "2023": 12},
            "top_works": [
                {
                    "title": "A Great Paper",
                    "year": 2022,
                    "cited_by_count": 88,
                    "doi": "10.1234/test",
                    "source_name": "Semantic Web Journal",
                }
            ],
            "sources": {"Semantic Web Journal": 10},
        },
    }
 
 
class TestRenderHtml(unittest.TestCase):
 
    def setUp(self):
        self.result = _sample_result()
        self.html = render_html([self.result], "2025-01-01 08:00 UTC")
 
    def test_returns_string(self):
        self.assertIsInstance(self.html, str)
 
    def test_contains_doctype(self):
        self.assertIn("<!DOCTYPE html>", self.html)
 
    def test_contains_ontology_label(self):
        self.assertIn("Test Onto", self.html)
 
    def test_contains_ontology_uri(self):
        self.assertIn("https://example.org/test/", self.html)
 
    def test_contains_lov_inlinks(self):
        self.assertIn("5", self.html)
 
    def test_contains_github_count(self):
        self.assertIn("3", self.html)
 
    def test_contains_openalex_total(self):
        self.assertIn("42", self.html)
 
    def test_contains_generated_timestamp(self):
        self.assertIn("2025-01-01 08:00 UTC", self.html)
 
    def test_chart_canvas_present(self):
        self.assertIn(f'id="chart-{self.result["prefix"]}"', self.html)
 
    def test_chart_js_loaded(self):
        self.assertIn("chart.umd.min.js", self.html)
 
    def test_year_data_in_chart_script(self):
        for year in ["2021", "2022", "2023"]:
            self.assertIn(year, self.html)
 
    def test_top_paper_title_present(self):
        self.assertIn("A Great Paper", self.html)
 
    def test_top_paper_doi_link(self):
        self.assertIn("10.1234/test", self.html)
 
    def test_lov_link_present(self):
        self.assertIn("lov.linkeddata.es", self.html)
 
    def test_importing_vocab_links(self):
        self.assertIn("http://a.org/", self.html)
 
    def test_nav_contains_prefix_anchor(self):
        self.assertIn(f'href="#onto-{self.result["prefix"]}"', self.html)
 
    def test_multiple_ontologies_all_present(self):
        r1 = _sample_result(prefix="a", label="Onto A")
        r2 = _sample_result(prefix="b", label="Onto B")
        html = render_html([r1, r2], "2025-01-01 08:00 UTC")
        self.assertIn("Onto A", html)
        self.assertIn("Onto B", html)
        self.assertIn('id="onto-a"', html)
        self.assertIn('id="onto-b"', html)
 
    def test_lov_not_found_shows_missing_status(self):
        result = _sample_result()
        result["lov"]["found"] = False
        result["lov"]["url"] = None
        html = render_html([result], "2025-01-01 08:00 UTC")
        self.assertIn('class="status-line status-missing"', html)
        self.assertNotIn('class="status-line status-ok"', html)
 
    def test_lov_found_shows_ok_status(self):
        self.assertIn('class="status-line status-ok"', self.html)
 
    def test_no_papers_fallback_message(self):
        result = _sample_result()
        result["openalex"]["top_works"] = []
        html = render_html([result], "2025-01-01 08:00 UTC")
        self.assertIn("No papers found", html)
 
 
class TestRenderLinkList(unittest.TestCase):
 
    def test_empty_list_returns_none_found(self):
        html = _render_link_list([])
        self.assertIn("None found", html)
 
    def test_items_rendered_as_anchors(self):
        html = _render_link_list(["http://example.org/onto#Foo"])
        self.assertIn('<a href="http://example.org/onto#Foo"', html)
        self.assertIn("Foo", html)
 
    def test_limit_respected(self):
        items = [f"http://example.org/{i}" for i in range(20)]
        html = _render_link_list(items, limit=5)
        self.assertEqual(html.count("<li>"), 5)
 
    def test_slash_uri_uses_last_segment(self):
        html = _render_link_list(["http://example.org/myonto/"])
        self.assertIn("myonto", html)
 
 
class TestRenderTopWorks(unittest.TestCase):
 
    def test_renders_title(self):
        works = [{"title": "My Paper", "year": 2021, "cited_by_count": 5, "doi": "", "source_name": "J"}]
        html = _render_top_works(works)
        self.assertIn("My Paper", html)
 
    def test_doi_link_rendered(self):
        works = [{"title": "X", "year": 2020, "cited_by_count": 1, "doi": "10.1000/xyz", "source_name": "J"}]
        html = _render_top_works(works)
        self.assertIn("10.1000/xyz", html)
        self.assertIn("↗", html)
 
    def test_no_doi_no_link(self):
        works = [{"title": "X", "year": 2020, "cited_by_count": 1, "doi": "", "source_name": "J"}]
        html = _render_top_works(works)
        self.assertNotIn("↗", html)
 
    def test_empty_list_returns_empty_string(self):
        self.assertEqual(_render_top_works([]), "")
 
    def test_year_none_renders_dash(self):
        works = [{"title": "X", "year": None, "cited_by_count": 0, "doi": "", "source_name": "J"}]
        html = _render_top_works(works)
        self.assertIn("—", html)
 
 
if __name__ == "__main__":
    unittest.main()