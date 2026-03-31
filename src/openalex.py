# src/openalex.py

import json
import time
import io
import hashlib
import urllib.request
import urllib.parse
import urllib.error
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDFS, OWL
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from src.http import http_get


def fetch_openalex(
    ontology: dict, 
    api_key: str = ""
    ) -> dict:
    result: dict = {
        "total_works": 0,
        "by_year": {},
        "top_works": [],
        "sources": {},
    }
    base_params: dict = {
        "per_page": "50",
        "select": "id,title,authorships,publication_year,primary_location,doi",
        "sort": "publication_year:desc",
    }
    if api_key:
        base_params["api_key"] = api_key
    all_works: list[dict] = []
    seen_ids: set[str] = set()
    for keyword in ontology.get("keywords", []):
        search_term = f'"{keyword}"' if " " in keyword else keyword
        params = {**base_params, "search.exact": search_term}
        url = f"https://api.openalex.org/works?{urllib.parse.urlencode(params)}"
        data = http_get(url)
        if data and "results" in data:
            for work in data["results"]:
                wid = work.get("id", "")
                if wid and wid not in seen_ids:
                    seen_ids.add(wid)
                    all_works.append(work)
        time.sleep(0.5)
    result["total_works"] = len(all_works)
    for work in all_works:
        year = str(work.get("publication_year", "")) if work.get("publication_year") else None
        if year:
            result["by_year"][year] = result["by_year"].get(year, 0) + 1
    all_works.sort(key=lambda w: w.get("publication_year", 0), reverse=True)
    for work in all_works[:5]:
        auths_list = []
        auths = work.get("authorships", "")
        for auth in auths:
            auth_name = auth.get("author", "").get("display_name", "")
            auths_list.append(auth_name)
        auths_str = "; ".join(auths_list)
        loc = work.get("primary_location") or {}
        source = loc.get("source") or {}
        result["top_works"].append({
            "title": work.get("title", "Untitled"),
            "authors": auths_str,
            "year": work.get("publication_year"),
            "doi": work.get("doi", ""),
            "source_name": source.get("display_name", ""),
        })
    for work in all_works:
        loc = work.get("primary_location") or {}
        source_name = (loc.get("source") or {}).get("display_name", "Unknown")
        result["sources"][source_name] = result["sources"].get(source_name, 0) + 1
    return result