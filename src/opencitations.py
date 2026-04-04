# src/opencitations.py

import time
from src.http import http_get


def fetch_opencitations(
    ontology: dict,
    api_key: str = ""
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
    for citation in all_citations:
        citing_doi = citation.get("citing", "").split()[0]
        creation = citation.get("creation", "")
        year = creation[:4] if creation else None
        if year and year.isdigit():
            result["by_year"][year] = result["by_year"].get(year, 0) + 1
        meta = _fetch_opencitations_metadata(citing_doi, headers)
        result["citing_works"].append({
            "doi": citing_doi,
            "year": year,
            "title": meta.get("title", ""),
        })
        time.sleep(0.3)
    return result


def _fetch_opencitations_metadata(doi: str, headers: dict) -> dict:
    url = f"https://api.opencitations.net/meta/v1/metadata/doi:{doi}"
    data = http_get(url, headers=headers)
    if not data or not isinstance(data, list) or len(data) == 0:
        return {}
    return data[0]