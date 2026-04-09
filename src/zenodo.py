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
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def fetch_zenodo(
    ontology: dict = {},
    api_key: str = ""
    ) -> dict:
    result: dict = {
        "total_datasets": 0,
        "datasets": [],
    }
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    monitored_uris = [ontology["uri"]]
    records = _search_rdf_datasets(headers)
    matched: list[dict] = []
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {
            executor.submit(_check_record, record, monitored_uris, headers): record
            for record in records
        }
        for future in as_completed(futures):
            try:
                record_result = future.result()
                if record_result:
                    matched.append(record_result)
            except Exception as e:
                print(f"  [Zenodo] Error checking record: {e}")
    result["total_datasets"] = len(matched)
    result["datasets"] = matched
    return result


def _search_rdf_datasets(
    headers: dict
    ) -> list[dict]:
    all_records: list[dict] = []
    seen_ids: set[str] = set()
    lock = threading.Lock()

    def _search_ext(ext: str) -> list[dict]:
        records = []
        page = 1
        while True:
            url = f"https://zenodo.org/api/records?q=filetype:{ext}&size=100&page={page}"
            data = http_get(url, headers=headers)
            if not data or not data.get("hits", {}).get("hits"):
                break
            for record in data["hits"]["hits"]:
                rid = record.get("id")
                resource_type = record.get("metadata", {}).get("resource_type", {}).get("type", "")
                if rid and resource_type == "dataset":
                    records.append(record)
            total = data["hits"].get("total", 0)
            if page * 100 >= min(total, 10000):
                break
            page += 1
            time.sleep(0.1)
        return records

    with ThreadPoolExecutor(max_workers=len(RDF_EXTENSIONS)) as executor:
        futures = {executor.submit(_search_ext, ext): ext for ext in RDF_EXTENSIONS}
        for future in as_completed(futures):
            ext = futures[future]
            try:
                for record in future.result():
                    rid = record.get("id")
                    with lock:
                        if rid and rid not in seen_ids:
                            seen_ids.add(rid)
                            all_records.append(record)
            except Exception as e:
                print(f"  [Zenodo] Search error for {ext}: {e}")
    print(f"  [Zenodo] Found {len(all_records)} candidate RDF dataset records.")
    return all_records


def _check_record(
    record: dict,
    monitored_uris: list[str],
    headers: dict
    ) -> dict | None:
    files = record.get("files", [])
    rdf_files = [
        f for f in files
        if f.get("key", "").rsplit(".", 1)[-1].lower() in RDF_EXTENSIONS
        and f.get("size", 0) <= MAX_FILE_SIZE
    ]
    if not rdf_files:
        return None
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
        if _check_graph(g, monitored_uris):
            meta = record.get("metadata", {})
            return {
                "id": record.get("id"),
                "title": meta.get("title", ""),
                "doi": record.get("doi", "")
            }
    return None