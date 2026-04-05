# src/opencitations.py

import time
import re
from src.http import http_get
from concurrent.futures import ThreadPoolExecutor, as_completed


def fetch_opencitations(
    ontology: dict,
    api_key: str = "",
    batch_size: int = 5
    ) -> dict:
    result: dict = {
        "total_citations": 0,
        "by_year": {},
        "citing_works": [],
    }
    headers = {}
    if api_key:
        headers["authorization"] = api_key
    all_citations: list[dict] = []
    seen_dois: set[str] = set()
    for doi in ontology.get("papers", []):
        url = f"https://opencitations.net/api/v1/citations/{doi}"
        data = http_get(url, headers=headers)
        if not data:
            continue
        for citation in data:
            citing_doi = citation.get("citing", "")
            if citing_doi and citing_doi not in seen_dois:
                seen_dois.add(citing_doi)
                all_citations.append(citation)
        time.sleep(0.5)
    result["total_citations"] = len(all_citations)
    all_dois = [citation.get("citing", "").split()[0] for citation in all_citations]
    batches = [all_dois[i:i + batch_size] for i in range(0, len(all_dois), batch_size)]
    metadata_map: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {
            executor.submit(_fetch_opencitations_metadata, batch, headers): batch
            for batch in batches
        }
        for future in as_completed(futures):
            try:
                metadata_map.update(future.result())
            except Exception as e:
                print(f"  [OC] Error fetching metadata batch: {e}")
    for citation in all_citations:
        citing_doi = citation.get("citing", "").split()[0]
        meta = metadata_map.get(citing_doi, {})
        creation = citation.get("creation", "")
        year = creation[:4] if creation else None
        if year and year.isdigit():
            result["by_year"][year] = result["by_year"].get(year, 0) + 1
        result["citing_works"].append({
            "doi": citing_doi,
            "year": year,
            "title": meta.get("title", ""),
            "authors": re.sub(r"\s\[.+?\]", "", meta.get("author", "")),
            "venue": re.sub(r"\[.+?\]", "", meta.get("venue", "")),
        })
    return result


def _fetch_opencitations_metadata(
    dois: list[str], 
    headers: dict) -> dict:
    joined_dois = "__".join(f"doi:{doi}" for doi in dois)
    url = f"https://api.opencitations.net/meta/v1/metadata/{joined_dois}"
    data = http_get(url, headers=headers)
    if not data or not isinstance(data, list):
        return {}
    return {
        next((p.replace("doi:", "")for p in item.get("id", "").split() if p.startswith("doi:")), ""): item
        for item in data
        if item.get("id")
    }