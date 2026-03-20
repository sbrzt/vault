# tests/test_fetchers.py

import unittest
from unittest.mock import patch, call
import src.fetchers
 
 
ONTO = {
    "label": "Test Onto",
    "uri": "https://example.org/test/",
    "prefix": "test",
    "openalex_keywords": ["test ontology", "test vocab"],
}


class TestFetchLov(unittest.TestCase):
    
    def _sparql_response(self, vocabs):
        return {
            "results": {
                "bindings": [
                    {"vocab": {"value": v}} for v in vocabs
                ]
            }
        }

    @patch("src.fetchers.http_get")
    def test_found_in_lov(self, mock_get):
        mock_get.side_effect = [
            {"tags": ["iot"], "versions": [{"name": "1.0", "issued": "2020-01-01", "fileURL": []}]},
            self._sparql_response(["http://a.org/", "http://b.org/"]),
        ]
        result = src.fetchers.fetch_lov(ONTO)
        self.assertTrue(result["found"])
        self.assertEqual(result["inlinks"], 2)
        self.assertIn("http://a.org/", result["importing_vocabs"])
        self.assertEqual(result["tags"], ["iot"])
        self.assertIn("test", result["url"])
 
    @patch("src.fetchers.http_get")
    def test_not_found_in_lov(self, mock_get):
        mock_get.side_effect = [
            None,
            self._sparql_response([]),
        ]
        result = src.fetchers.fetch_lov(ONTO)
        self.assertFalse(result["found"])
        self.assertEqual(result["inlinks"], 0)
        self.assertEqual(result["importing_vocabs"], [])
        self.assertIsNone(result["url"])
 
    @patch("src.fetchers.http_get")
    def test_sparql_failure_still_returns_safe_result(self, mock_get):
        mock_get.side_effect = [
            {"tags": [], "versions": []},
            None,
        ]
        result = src.fetchers.fetch_lov(ONTO)
        self.assertTrue(result["found"])
        self.assertEqual(result["inlinks"], 0)
        self.assertEqual(result["importing_vocabs"], [])
 
    @patch("src.fetchers.http_get")
    def test_versions_parsed_correctly(self, mock_get):
        mock_get.side_effect = [
            {
                "tags": [],
                "versions": [
                    {"name": "v1", "issued": "2021-01-01", "fileURL": ["http://x.org/v1.ttl"]},
                    {"name": "v2", "issued": "2022-06-01", "fileURL": []},
                ],
            },
            self._sparql_response([]),
        ]
        result = src.fetchers.fetch_lov(ONTO)
        self.assertEqual(len(result["versions"]), 2)
        self.assertEqual(result["versions"][0]["name"], "v1")


class TestFetchSoftwareHeritage(unittest.TestCase):
    @patch("src.fetchers.http_get")
    def test_list_response(self, mock_get):
        mock_get.return_value = [
            {"url": "https://github.com/org/repo1"},
            {"url": "https://github.com/org/repo2"},
            {"url": ""},
        ]
        result = src.fetchers.fetch_github(ONTO)
        self.assertEqual(result["repos_count"], 2)
        self.assertIn("https://github.com/org/repo1", result["repos"])
 
    @patch("src.fetchers.http_get")
    def test_dict_response_with_results_key(self, mock_get):
        mock_get.return_value = {
            "results": [
                {"url": "https://gitlab.com/org/proj"},
            ]
        }
        result = src.fetchers.fetch_github(ONTO)
        self.assertEqual(result["repos_count"], 1)
        self.assertEqual(result["repos"][0], "https://gitlab.com/org/proj")
 
    @patch("src.fetchers.http_get")
    def test_api_failure_returns_empty(self, mock_get):
        mock_get.return_value = None
        result = src.fetchers.fetch_github(ONTO)
        self.assertEqual(result["repos_count"], 0)
        self.assertEqual(result["repos"], [])
 
    @patch("src.fetchers.http_get")
    def test_token_injected_into_header(self, mock_get):
        mock_get.return_value = []
        src.fetchers.fetch_github(ONTO, github_token="mytoken")
        _, kwargs = mock_get.call_args
        headers = mock_get.call_args[0][1] if len(mock_get.call_args[0]) > 1 else mock_get.call_args[1].get("headers", {})
        self.assertEqual(headers.get("Authorization"), "Bearer mytoken")
 
    @patch("src.fetchers.http_get")
    def test_no_token_sends_no_auth_header(self, mock_get):
        mock_get.return_value = []
        src.fetchers.fetch_github(ONTO, github_token="")
        headers = mock_get.call_args[0][1] if len(mock_get.call_args[0]) > 1 else mock_get.call_args[1].get("headers", {})
        self.assertNotIn("Authorization", headers)


def _oax_work(wid, title, year, citations, source="Journal A", doi=""):
    return {
        "id": f"https://openalex.org/W{wid}",
        "title": title,
        "publication_year": year,
        "cited_by_count": citations,
        "doi": doi,
        "primary_location": {"source": {"display_name": source}},
    }

class TestFetchOpenAlex(unittest.TestCase):
 
    @patch("src.fetchers.time.sleep")
    @patch("src.fetchers.http_get")
    def test_basic_results_aggregated(self, mock_get, _sleep):
        works_page = {
            "meta": {"count": 2},
            "results": [
                _oax_work(1, "Paper A", 2021, 50),
                _oax_work(2, "Paper B", 2022, 30),
            ],
        }
        mock_get.return_value = works_page
        result = src.fetchers.fetch_openalex(ONTO)
        self.assertGreaterEqual(result["total_works"], 2)
        self.assertIn("2021", result["by_year"])
        self.assertIn("2022", result["by_year"])
 
    @patch("src.fetchers.time.sleep")
    @patch("src.fetchers.http_get")
    def test_deduplication_across_keywords(self, mock_get, _sleep):
        shared_work = _oax_work(99, "Shared Paper", 2020, 100)
        mock_get.return_value = {"meta": {"count": 1}, "results": [shared_work]}
        result = src.fetchers.fetch_openalex(ONTO)
        ids = [w["title"] for w in result["top_works"]]
        self.assertEqual(len(ids), len(set(ids)))
 
    @patch("src.fetchers.time.sleep")
    @patch("src.fetchers.http_get")
    def test_top_works_sorted_by_citations(self, mock_get, _sleep):
        mock_get.side_effect = [
            {
                "meta": {"count": 3},
                "results": [
                    _oax_work(1, "High", 2021, 200),
                    _oax_work(2, "Low",  2021, 10),
                    _oax_work(3, "Mid",  2021, 80),
                ],
            },
            {"meta": {"count": 0}, "results": []},  # second keyword empty
        ]
        result = src.fetchers.fetch_openalex(ONTO)
        citations = [w["cited_by_count"] for w in result["top_works"]]
        self.assertEqual(citations, sorted(citations, reverse=True))
 
    @patch("src.fetchers.time.sleep")
    @patch("src.fetchers.http_get")
    def test_api_failure_returns_safe_empty(self, mock_get, _sleep):
        mock_get.return_value = None
        result = src.fetchers.fetch_openalex(ONTO)
        self.assertEqual(result["total_works"], 0)
        self.assertEqual(result["by_year"], {})
        self.assertEqual(result["top_works"], [])
 
    @patch("src.fetchers.time.sleep")
    @patch("src.fetchers.http_get")
    def test_year_aggregation(self, mock_get, _sleep):
        mock_get.side_effect = [
            {
                "meta": {"count": 3},
                "results": [
                    _oax_work(1, "A", 2020, 5),
                    _oax_work(2, "B", 2020, 3),
                    _oax_work(3, "C", 2021, 1),
                ],
            },
            {"meta": {"count": 0}, "results": []},
        ]
        result = src.fetchers.fetch_openalex(ONTO)
        self.assertEqual(result["by_year"].get("2020"), 2)
        self.assertEqual(result["by_year"].get("2021"), 1)
 
    @patch("src.fetchers.time.sleep")
    @patch("src.fetchers.http_get")
    def test_api_key_included_in_url(self, mock_get, _sleep):
        mock_get.return_value = {"meta": {"count": 0}, "results": []}
        src.fetchers.fetch_openalex(ONTO, api_key="testkey123")
        first_url = mock_get.call_args_list[0][0][0]
        self.assertIn("api_key=testkey123", first_url)
 
    @patch("src.fetchers.time.sleep")
    @patch("src.fetchers.http_get")
    def test_top_works_capped_at_five(self, mock_get, _sleep):
        many_works = [_oax_work(i, f"Paper {i}", 2021, i * 10) for i in range(1, 12)]
        mock_get.side_effect = [
            {"meta": {"count": 11}, "results": many_works},
            {"meta": {"count": 0}, "results": []},
        ]
        result = src.fetchers.fetch_openalex(ONTO)
        self.assertLessEqual(len(result["top_works"]), 5)
 
 
if __name__ == "__main__":
    unittest.main()