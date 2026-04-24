# src/github.py

import time
import urllib.request
import urllib.parse
import urllib.error
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.http import http_get, http_get_raw
from src.lov import _parse_graph, _check_graph
import logging
import warnings
logging.getLogger("rdflib").setLevel(logging.ERROR)
warnings.filterwarnings("ignore")

RDF_EXTENSIONS = {"ttl", "owl", "rdf", "n3", "nt", "jsonld", "trig"}
MAX_FILE_SIZE = 10 * 1024 * 1024


def fetch_zenodo_all(
    ontologies: list[dict],
    api_key: str = ""
    ) -> dict[str, dict]:
    results: dict[str, dict] = {
        onto["prefix"]: 
            {
                "total_datasets": 0, 
                "by_year": {},
                "by_access": {},
                "by_license": {},
                "keywords": {},
                "communities": {},
                "datasets": [],
            }
        for onto in ontologies
    }
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    monitored_uris = [onto["uri"] for onto in ontologies]
    uri_to_prefix = {onto["uri"]: onto["prefix"] for onto in ontologies}
    seen_ids: set[str] = set()
    completed = 0
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {}
        for ext in RDF_EXTENSIONS:
            page = 1
            while True:
                url = f"https://zenodo.org/api/records?q=filetype:{ext}&size=100&page={page}"
                data = http_get(url, headers=headers, retries=3, delay=5.0)
                if not data or not data.get("hits", {}).get("hits"):
                    break
                for record in data["hits"]["hits"]:
                    rid = record.get("id")
                    resource_type = record.get("metadata", {}).get("resource_type", {}).get("type", "")
                    if rid and rid not in seen_ids and resource_type == "dataset":
                        seen_ids.add(rid)
                        futures[executor.submit(_check_record, record, monitored_uris, headers)] = rid
                total = data["hits"].get("total", 0)
                print(f"  [Zenodo] {ext}: page {page}/{(min(total, 10000) + 99) // 100} ({len(seen_ids)} queued)")
                if page * 100 >= min(total, 10000):
                    break
                page += 1
                time.sleep(1.0)
        total_futures = len(futures)
        for future in as_completed(futures):
            completed += 1
            print(f"  [Zenodo] Checked {completed}/{total_futures}", end="\r")
            try:
                record_result, matched_uris = future.result()
                if record_result:
                    for uri in matched_uris:
                        prefix = uri_to_prefix.get(uri)
                        if prefix and not any(
                            d["id"] == record_result["id"]
                            for d in results[prefix]["datasets"]
                        ):
                            results[prefix]["datasets"].append(record_result)
                            results[prefix]["total_datasets"] += 1
                            year = record_result.get("year")
                            if year and year.isdigit():
                                results[prefix]["by_year"][year] = results[prefix]["by_year"].get(year, 0) + 1
                            access = record_result.get("access_right")
                            if access:
                                results[prefix]["by_access"][access] = results[prefix]["by_access"].get(access, 0) + 1
                            d_license = record_result.get("license")
                            if d_license:
                                results[prefix]["by_license"][d_license] = results[prefix]["by_license"].get(d_license, 0) + 1
                            for keyword in record_result.get("keyword", []):
                                results[prefix]["keyword"][keyword] = results[prefix]["keywords"].get(keyword, 0) + 1
                            for community in record_result.get("communities", []):
                                results[prefix]["communities"][community] = results[prefix]["communities"].get(community, 0) + 1
            except Exception as e:
                print(f"\n  [Zenodo] Error checking record: {e}")
    print()
    return results


def _check_record(
    record: dict,
    monitored_uris: list[str],
    headers: dict
    ):
    files = record.get("files", [])
    rdf_files = [
        f for f in files
        if f.get("key", "").rsplit(".", 1)[-1].lower() in RDF_EXTENSIONS
        and f.get("size", 0) <= MAX_FILE_SIZE
    ]
    if not rdf_files:
        return None, []
    all_matched: set[str] = set()
    for f in rdf_files:
        download_url = f.get("links", "").get("self", "")
        if not download_url:
            continue
        raw = http_get_raw(download_url, headers=headers)
        if raw is None:
            continue
        g = _parse_graph(raw, download_url)
        if g is None:
            continue
        all_matched.update(_check_graph(g, monitored_uris))
    if not all_matched:
        return None, []
    meta = record.get("metadata", {})
    return {
        "id": record.get("id"),
        "title": meta.get("title", ""),
        "doi": record.get("doi", ""),
        "year": (meta.get("publication_date") or "")[:4],
        "access_right": meta.get("access_right", ""),
        "license": (meta.get("license") or {}).get("id", ""),
        "keywords": meta.get("keywords", []),
        "communities": [c.get("id", "") for c in record.get("communities", [])],
    }, list(all_matched)