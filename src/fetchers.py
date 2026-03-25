# src/fetchers.py

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
 
USER_AGENT = "VAULT/1.0 (https://github.com/sbrzt/vault)"
CACHE_DIR = Path("cache")
MAX_WORKERS = 20


def http_get(
    url: str, 
    headers: dict | None = None, 
    retries: int = 3, 
    delay: float = 2.0
    ):
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

def http_get_raw(
    url: str,
    headers: dict | None = None,
    retries: int = 3, 
    delay: float = 2.0
    ) -> bytes | None:
    req = urllib.request.Request(
        url,
        headers=headers or {}
    )
    req.add_header("User-Agent", USER_AGENT)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(
                req,
                timeout=60
            ) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            print(f"  [HTTP] {e.code} fetching {url}")
            return None
        except Exception as e:
            print(f"  [HTTP] Error fetching {url}: {e}")
            if attempt < retries - 1:
                time.sleep(delay)
    return None


_RDF_FORMATS = [
    ("text/turtle",                "turtle"),
    ("application/rdf+xml",        "xml"),
    ("application/ld+json",        "json-ld"),
    ("text/n3",                    "n3"),
    ("application/n-triples",      "nt"),
]

def _lov_info(ontology: dict) -> dict:
    result: dict = {
        "found": False,
        "inlinks": 0,
        "using_vocabs": [],
        "url": None,
        "tags": [],
        "versions": [],
    }
    info_url = (
        "https://lov.linkeddata.es/dataset/lov/api/v2/vocabulary/info"
        f"?vocab={ontology['prefix']}"
    )
    data = http_get(info_url)
    if data:
        result["found"] = True
        result["url"] = (
            f"https://lov.linkeddata.es/dataset/lov/vocabs/{ontology['prefix']}"
        )
        result["tags"] = data.get("tags", [])
        result["versions"] = [
            {
                "name": v.get("name", ""),
                "issued": v.get("issued", ""),
                "fileURL": v.get("fileURL", [])
            }
            for v in data.get("versions", [])
        ]
    return result

def _lov_all_download_urls() -> list[dict]:
    sparql_query = """
        PREFIX dcat:<http://www.w3.org/ns/dcat#>
        PREFIX dcterms:<http://purl.org/dc/terms/>
        SELECT ?vocab ?distribution WHERE {
            GRAPH <https://lov.linkeddata.es/dataset/lov> {
                ?vocab dcat:distribution ?distribution .
                ?distribution dcterms:issued ?issued .
            }
        }
        ORDER BY ?vocab DESC(?issued)
    """
    sparql_url = (
        "https://lov.linkeddata.es/dataset/lov/sparql?"
        + urllib.parse.urlencode(
            {"query": sparql_query, "format": "json"},
            quote_via=urllib.parse.quote,
        )
    )
    data = http_get(sparql_url, headers={"Accept": "application/sparql-results+json"})
    if not data:
        return []
    results = []
    seen_vocabs: set[str] = set()
    for binding in data.get("results", {}).get("bindings", []):
        vocab = binding.get("vocab", {}).get("value", "")
        download_url = binding.get("distribution", {}).get("value", "")
        if vocab and download_url and vocab not in seen_vocabs and download_url.startswith("http"):
            seen_vocabs.add(vocab)
            results.append(
                {
                    "vocab": vocab, 
                    "download_url": download_url
                }
            )
    return results

def _parse_graph(
    raw: bytes,
    url: str
    ) -> Graph | None:
    g = Graph()
    for _, fmt in _RDF_FORMATS:
        try:
            g.parse(
                data=raw.decode("utf-8", errors="replace"), 
                format=fmt,
                publicID=url
                )
            return g
        except Exception:
            continue
    print(f"  [LOV] Could not parse {url} in any known RDF format, skipping.")
    return None

def _check_graph(
    g: Graph,
    monitored_uris: list[str]) -> set[str]:
    matched: set[str] = set()
    declared_namespaces = {str(ns).rstrip("/#") for _, ns in g.namespaces()}
    for uri in monitored_uris:
        if uri.rstrip("/#") in declared_namespaces:
            matched.add(uri)
    for uri in monitored_uris:
        if uri in matched:
            continue
        uri_ref = URIRef(uri)
        if (None, RDFS.isDefinedBy, uri_ref) in g or (None, OWL.imports, uri_ref) in g:
            matched.add(uri)
    return matched

def fetch_lov_all(ontologies: list[dict]) -> dict[str, dict]:
    results: dict[str, dict] = {}
    for onto in ontologies:
        print(f"  [LOV] Fetching info for {onto['prefix']}…")
        results[onto["prefix"]] = _lov_info(onto)
    print("  [LOV] Querying LOV metadata for inlinks…")
    _lov_sparql_inlinks(ontologies, results)
    print("  [LOV] Fetching all vocabulary download URLs…")
    all_vocabs = _lov_all_download_urls()
    print(f"  [LOV] Found {len(all_vocabs)} vocabularies to scan.")
    monitored_uris = [onto["uri"] for onto in ontologies]
    uri_to_prefix = {onto["uri"]: onto["prefix"] for onto in ontologies}
    vocabs_to_scan = [
        v for v in all_vocabs if v["vocab"] not in monitored_uris
    ]
    completed = 0
    total = len(vocabs_to_scan)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(_process_vocab, vocab, monitored_uris): vocab
            for vocab in vocabs_to_scan
        }
        for future in as_completed(futures):
            completed += 1
            print(f"  [LOV] Scanned {completed}/{total}", end="\r")
            try:
                vocab_uri, matched_uris = future.result()
                for uri in matched_uris:
                    prefix = uri_to_prefix.get(uri)
                    if prefix and vocab_uri not in results[prefix]["using_vocabs"]:
                        results[prefix]["using_vocabs"].append(vocab_uri)
                        results[prefix]["inlinks"] += 1
            except Exception as e:
                vocab = futures[future]
                print(f"\n  [LOV] Error processing {vocab['vocab']}: {e}")
    print()
    return results


def fetch_github(
    ontology: dict, 
    github_token: str = ""
    ) -> dict:
    result: dict = {"repos_count": 0, "repos": []}
    if not github_token:
        print("  [GitHub] No token provided, skipping.")
        return result
    extensions = """
        extension:ttl OR extension:rdf or extension:owl OR extension:jsonld
        OR extension:sparql OR extension:rq OR extension:md OR extension:rst
        OR extension:py OR extension:js OR extension:java
        """
    query= f'"{ontology["uri"]}" {extensions}'
    url = "https://api.github.com/search/code?" + urllib.parse.urlencode({"q": query, "per_page": 100})
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    data = http_get(url, headers=headers)
    if data and "items" in data:
        seen = set()
        for item in data["items"]:
            repo = item.get("repository", {}).get("full_name", "")
            if repo and repo not in seen:
                seen.add(repo)
                result["repos"].append(repo)
        result["repos_count"] = len(result["repos"])
    time.sleep(6)
    return result


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
    for keyword in ontology.get("openalex_keywords", []):
        params = {**base_params, "search.exact": keyword}
        url = f'https://api.openalex.org/works?search.exact="{keyword}"'
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


def _cache_path(url: str) -> Path:
    url_hash = hashlib.sha1(url.encode()).hexdigest()
    return CACHE_DIR / f"{url_hash}.json"

def _load_cache(url: str) -> dict | None:
    path = _cache_path(url)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

def _save_cache(
    url: str, 
    last_modified: str, 
    matched: list[str]
    ) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(url)
    path.write_text(
        json.dumps(
            {
                "last_modified": last_modified, 
                "matched": matched
            }
        ),
        encoding="utf-8",
    )

def _get_last_modified(url: str) -> str | None:
    req = urllib.request.Request(url, method="HEAD", headers={})
    req.add_header("User-Agent", USER_AGENT)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.headers.get("Last-Modified", None)
    except Exception:
        return None

def _process_vocab(
    vocab: dict, 
    monitored_uris: list[str]
    ) -> tuple[str, list[str]]:
    vocab_uri = vocab["vocab"]
    download_url = vocab["download_url"]
    last_modified = _get_last_modified(download_url)
    cached = _load_cache(download_url)
    if cached and last_modified and cached.get("last_modified") == last_modified:
        return vocab_uri, cached["matched"]
    raw = http_get_raw(download_url)
    if raw is None:
        return vocab_uri, []
    g = _parse_graph(raw, download_url)
    if g is None:
        return vocab_uri, []
    matched = list(_check_graph(g, monitored_uris))
    _save_cache(download_url, last_modified or "", matched)
    return vocab_uri, matched

def _lov_sparql_inlinks(ontologies: list[dict], results: dict[str, dict]):
    uri_to_prefix = {onto["uri"]: onto["prefix"] for onto in ontologies}
    values = " ".join(f"<{onto['uri']}>" for onto in ontologies)
    sparql_query = f"""
        PREFIX voaf:<http://purl.org/vocommons/voaf#>
        PREFIX owl:<http://www.w3.org/2002/07/owl#>
        SELECT ?vocab ?target WHERE {{
            GRAPH <https://lov.linkeddata.es/dataset/lov> {{
                VALUES ?target {{ {values} }}
                {{ ?vocab voaf:metadataVoc ?target . }}
                UNION
                {{ ?vocab voaf:specializes ?target . }}
                UNION
                {{ ?vocab voaf:extends ?target . }}
                UNION
                {{ ?vocab voaf:reliesOn ?target . }}
                UNION
                {{ ?vocab owl:imports ?target . }}
            }}
        }}
    """
    sparql_url = (
        "https://lov.linkeddata.es/dataset/lov/sparql?"
        + urllib.parse.urlencode(
            {"query": sparql_query, "format": "json"},
            quote_via=urllib.parse.quote,
        )
    )
    data = http_get(sparql_url, headers={"Accept": "application/sparql-results+json"})
    if not data:
        print("  [LOV] SPARQL metadata query returned no data.")
        return
    for binding in data.get("results", {}).get("bindings", []):
        vocab_uri = binding.get("vocab", {}).get("value", "")
        target_uri = binding.get("target", {}).get("value", "")
        prefix = uri_to_prefix.get(target_uri)
        if prefix and vocab_uri and vocab_uri not in results[prefix]["using_vocabs"]:
            results[prefix]["using_vocabs"].append(vocab_uri)
            results[prefix]["inlinks"] += 1