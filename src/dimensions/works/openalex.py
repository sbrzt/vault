# src/openalex.py

import json
import time
import io
import hashlib
from tqdm import tqdm
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
        "works": [],
        "sources": {},
        "avg_works_per_year": 0.0,
        "venues_count": 0,
        "authors_count": 0,
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
    
    if result["by_year"]:
        total_years = len(result["by_year"])
        result["avg_works_per_year"] = round(result["total_works"] / total_years, 2)

    all_works.sort(key = lambda w: w.get("publication_year", 0), reverse = True)

    seen_authors = set()

    for work in all_works:
        auths_list = []
        auths = work.get("authorships", []) or []
        for auth in auths:
            auth_name = auth.get("author", {}).get("display_name", "")
            if auth_name:
                auths_list.append(auth_name)
                author_id = auth.get("author", {}).get("id") or auth_name
                seen_authors.add(author_id)

        auths_str = "; ".join(auths_list)
        loc = work.get("primary_location") or {}
        source = loc.get("source") or {}
        source_name = source.get("display_name", "")

        result["works"].append({
            "title": work.get("title", ""),
            "authors": auths_str,
            "year": work.get("publication_year"),
            "doi": work.get("doi", ""),
            "source_name": source_name,
        })

        result["sources"][source_name] = result["sources"].get(source_name, 0) + 1
    
    result["venues_count"] = len(result["sources"])
    result["authors_count"] = len(seen_authors)

    return result