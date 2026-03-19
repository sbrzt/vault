# src/fetchers.py

import json
import time
import urllib.request
import urllib.parse
import urllib.error
 
USER_AGENT = "VAULT/1.0 (https://github.com/sbrzt/vault)"


def http_get(url: str, headers: dict | None = None, retries: int = 3, delay: float = 2.0):
    req = urllib.request.Request(url, headers=headers or {})
    req.add_header("User-Agent", USER_AGENT)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    print(f"  [HTTP] Non-JSON response from {url}:")
                    print(f"  {raw[:300]}")
                    return None
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = delay * (2 ** attempt)
                print(f"  [HTTP] Rate limited ({url}), waiting {wait:.0f}s…")
                time.sleep(wait)
            else:
                print(f"  [HTTP] {e.code} for {url}")
                return None
        except Exception as e:
            print(f"  [HTTP] Error fetching {url}: {e}")
            if attempt < retries - 1:
                time.sleep(delay)
    return None


def fetch_lov(ontology: dict) -> dict:
    result: dict = {
        "found": False,
        "inlinks": 0,
        "importing_vocabs": [],
        "url": None,
        "tags": [],
        "versions": [],
    }
 
    info_url = (
        f"https://lov.linkeddata.es/dataset/lov/api/v2/vocabulary/info"
        f"?vocab={ontology['prefix']}"
    )
    data = http_get(info_url)
    if data:
        result["found"] = True
        result["url"] = (
            data.get("uri", "")
        )
        result["tags"] = data.get("tags", [])
        result["versions"] = [
            {
                "name": v.get("name", ""),
                "issued": v.get("issued", ""),
                "fileURL": v.get("fileURL", []),
            }
            for v in data.get("versions", [])
        ]
    sparql_query = f"""
        PREFIX voaf:<http://purl.org/vocommons/voaf#>
        PREFIX dcat:<http://www.w3.org/ns/dcat#>
        PREFIX owl:<http://www.w3.org/2002/07/owl#>
        SELECT ?vocab WHERE {{
             GRAPH <https://lov.linkeddata.es/dataset/lov> {{
            {{ ?vocab voaf:metadataVoc <{ontology['uri']}> . }}
            UNION
            {{ ?vocab voaf:hasEquivalencesWith <{ontology['uri']}> . }}
            UNION
            {{ ?vocab owl:imports <{ontology['uri']}> . }}
            UNION
            {{ ?vocab voaf:specializes <{ontology['uri']}> . }}
        }}
        }}
    """
    sparql_url = (
        "https://lov.linkeddata.es/dataset/lov/sparql?"
        + urllib.parse.urlencode({"query": sparql_query, "format": "json"}, quote_via=urllib.parse.quote)
    )
    sparql_data = http_get(sparql_url, headers={"Accept": "application/sparql-results+json"})
    print(sparql_data)
    if sparql_data:
        bindings = sparql_data.get("results", {}).get("bindings", [])
        result["importing_vocabs"] = [
            b.get("vocab", {}).get("value", "") for b in bindings
        ]
        result["inlinks"] = len(result["importing_vocabs"])
    return result


def fetch_software_heritage(ontology: dict, swh_token: str = "") -> dict:
    result: dict = {"origins_count": 0, "origins": []}
    headers = {}
    if swh_token:
        headers["Authorization"] = f"Bearer {swh_token}"
    namespace = ontology["uri"].rstrip("/#")
    encoded = urllib.parse.quote(namespace)
    url = (
        f"https://archive.softwareheritage.org/api/1/origin/metadata-search/"
        f"?fulltext={encoded}&limit=10"
    )
    data = http_get(url, headers=headers)
    if isinstance(data, list):
        result["origins"] = [i.get("url", "") for i in data if i.get("url")]
    elif isinstance(data, dict) and "results" in data:
        result["origins"] = [i.get("url", "") for i in data["results"] if i.get("url")]
    result["origins_count"] = len(result["origins"])
    return result


def fetch_openalex(ontology: dict, api_key: str = "") -> dict:
    result: dict = {
        "total_works": 0,
        "by_year": {},
        "top_works": [],
        "sources": {},
    }
    base_params: dict = {
        "per_page": "50",
        "select": "id,title,publication_year,cited_by_count,primary_location,doi",
        "sort": "cited_by_count:desc",
    }
    if api_key:
        base_params["api_key"] = api_key
    all_works: list[dict] = []
    seen_ids: set[str] = set()
    for keyword in ontology.get("openalex_keywords", []):
        params = {**base_params, "search": keyword}
        url = f"https://api.openalex.org/works?{urllib.parse.urlencode(params)}"
        data = http_get(url)
        if data and "results" in data:
            for work in data["results"]:
                wid = work.get("id", "")
                if wid and wid not in seen_ids:
                    seen_ids.add(wid)
                    all_works.append(work)
            if not result["total_works"]:
                result["total_works"] = data.get("meta", {}).get("count", 0)
        time.sleep(0.5)
    result["total_works"] = max(result["total_works"], len(all_works))
    for work in all_works:
        year = str(work.get("publication_year", "")) if work.get("publication_year") else None
        if year:
            result["by_year"][year] = result["by_year"].get(year, 0) + 1
    all_works.sort(key=lambda w: w.get("cited_by_count", 0), reverse=True)
    for work in all_works[:5]:
        loc = work.get("primary_location") or {}
        source = loc.get("source") or {}
        result["top_works"].append({
            "title": work.get("title", "Untitled"),
            "year": work.get("publication_year"),
            "cited_by_count": work.get("cited_by_count", 0),
            "doi": work.get("doi", ""),
            "source_name": source.get("display_name", ""),
        })
    for work in all_works:
        loc = work.get("primary_location") or {}
        source_name = (loc.get("source") or {}).get("display_name", "Unknown")
        result["sources"][source_name] = result["sources"].get(source_name, 0) + 1
    return result