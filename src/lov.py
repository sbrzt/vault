# src/lov.py

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
from src.http import http_get, http_get_raw


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
        PREFIX dcat: <http://www.w3.org/ns/dcat#>
        PREFIX dcterms: <http://purl.org/dc/terms/>
        PREFIX voaf: <http://purl.org/vocommons/voaf#>
        PREFIX vann: <http://purl.org/vocab/vann/>
        SELECT ?vocab ?title ?distribution ?namespaceUri WHERE {
            GRAPH <https://lov.linkeddata.es/dataset/lov> {
                ?vocab a voaf:Vocabulary ;
                    dcterms:title ?title ;
                    dcat:distribution ?distribution .
                ?distribution dcterms:issued ?issued .
                OPTIONAL { ?vocab vann:preferredNamespaceUri ?namespaceUri . }
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
        title = binding.get("title", {}).get("value", "")
        download_url = binding.get("distribution", {}).get("value", "")
        namespace_uri = binding.get("namespaceuri", {}).get("value", "") or vocab
        if (namespace_uri
                and title
                and download_url 
                and namespace_uri not in seen_vocabs
                and download_url.startswith("http")):
            seen_vocabs.add(namespace_uri)
            results.append(
                {
                    "vocab": vocab, 
                    "title": title,
                    "download_url": download_url,
                    "namespace_uri": namespace_uri,
                }
            )
    return results


def _parse_graph(
    raw: bytes,
    url: str
    ) -> Graph | None:
    g = Graph()
    for f in FORMATS:
        try:
            g.parse(
                data=raw.decode("utf-8", errors="replace"), 
                format=f["format"],
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
    for s, p, o in g:
        for uri in monitored_uris:
            if uri in matched:
                continue
            if (str(s).startswith(uri)
                or str(p).startswith(uri)
                or (isinstance(o, URIRef) and str(o).startswith(uri))):
                matched.add(uri)
    return matched


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
    ) -> tuple[str, str, str, list[str]]:
    vocab_uri = vocab["vocab"]
    namespace_uri = vocab["namespace_uri"]
    title = vocab["title"]
    download_url = vocab["download_url"]
    last_modified = _get_last_modified(download_url)
    cached = _load_cache(download_url)
    if cached and last_modified and cached.get("last_modified") == last_modified:
        return namespace_uri, vocab_uri, title, cached["matched"]
    raw = http_get_raw(download_url)
    if raw is None:
        return namespace_uri, vocab_uri, title, []
    g = _parse_graph(raw, download_url)
    if g is None:
        return namespace_uri, vocab_uri, title, []
    
    if "icon" in download_url.lower():
        declared = {str(ns).rstrip("/#") for _, ns in g.namespaces()}
        print(f"  [LOV] DEBUG icon declared namespaces: {declared}")
        for uri in monitored_uris:
            print(f"  [LOV] DEBUG icon checking uri={uri} stripped={uri.rstrip('/#')} in_declared={uri.rstrip('/#') in declared}")

    matched = list(_check_graph(g, monitored_uris))
    _save_cache(download_url, last_modified or "", matched)
    return namespace_uri, vocab_uri, title, matched


def _lov_sparql_inlinks(
    ontologies: list[dict], 
    results: dict[str, dict]
    ) -> None:
    uri_to_prefix = {onto["uri"]: onto["prefix"] for onto in ontologies}
    values = " ".join(f"<{onto['uri']}>" for onto in ontologies)
    sparql_query = f"""
        PREFIX voaf:<http://purl.org/vocommons/voaf#>
        PREFIX owl:<http://www.w3.org/2002/07/owl#>
        PREFIX dcterms:<http://purl.org/dc/terms/>
        PREFIX vann:<http://purl.org/vocab/vann/>
        SELECT ?vocab ?title ?namespaceUri ?target WHERE {{
            GRAPH <https://lov.linkeddata.es/dataset/lov> {{
                VALUES ?target {{ {values} }}
                ?vocab dcterms:title ?title ;
                    vann:preferredNamespaceUri ?namespaceUri .
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
        title = binding.get("title", {}).get("value", "")
        namespace_uri = binding.get("namespaceUri", {}).get("value", "")
        target_uri = binding.get("target", {}).get("value", "")
        prefix = uri_to_prefix.get(target_uri)
        if prefix and vocab_uri and not any(
            v["vocab_uri"] == vocab_uri for v in results[prefix]["using_vocabs"]
            ):
            results[prefix]["using_vocabs"].append({
                "uri": namespace_uri, 
                "vocab_uri": vocab_uri,
                "title": title,
            })
            results[prefix]["inlinks"] += 1


def fetch_lov_all(
    ontologies: list[dict]
    ) -> dict[str, dict]:
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
                namespace_uri, vocab_uri, title, matched_uris = future.result()
                for uri in matched_uris:
                    prefix = uri_to_prefix.get(uri)
                    if prefix and not any(
                        v["uri"] == namespace_uri for v in results[prefix]["using_vocabs"]
                        ):
                        results[prefix]["using_vocabs"].append({
                            "uri": namespace_uri, 
                            "vocab_uri": vocab_uri,
                            "title": title,
                        })
                        results[prefix]["inlinks"] += 1
            except Exception as e:
                vocab = futures[future]
                print(f"\n  [LOV] Error processing {vocab['vocab']}: {e}")
    print()
    return results