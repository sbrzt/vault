# src/lov.py

import os
import json
import time
import io
import hashlib
import urllib.request
import urllib.parse
import urllib.error
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDFS, OWL
from concurrent.futures import ProcessPoolExecutor, as_completed
from collections import Counter
from pathlib import Path
from src.http import http_get, http_get_raw
from tqdm import tqdm


def _lov_info(
    ontology: dict
    ) -> dict:

    result: dict = {
        "found": False,
        "inlinks": 0,
        "using_vocabs": [],
        "url": None,
        "tags": [],
        "versions": [],
        "keyword_counter": Counter(),
        "year_counter": Counter(),
    }

    info_url = (
        "https://lov.linkeddata.es/dataset/api/v2/vocabulary/info"
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
        SELECT ?vocab ?title (GROUP_CONCAT(?keyword; separator="|") AS ?keywords) ?distribution ?namespaceUri ?issued WHERE {
            GRAPH <https://lov.linkeddata.es/dataset/lov> {
                ?vocab a voaf:Vocabulary ;
                    dcterms:title ?title ;
                    dcat:distribution ?distribution .
                OPTIONAL { ?vocab dcat:keyword ?keyword . }
                ?distribution dcterms:issued ?issued .
                OPTIONAL { ?vocab vann:preferredNamespaceUri ?namespaceUri . }
            }
        }
        GROUP BY ?vocab ?title ?distribution ?namespaceUri ?issued
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
        
        keywords = binding.get("keywords", {}).get("value", "")
        keywords_list = [k.strip() for k in keywords.split("|") if k.strip()]

        issued = binding.get("issued", {}).get("value", "")
        issued_year = issued[:4] if issued else ""

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
                    "keywords": keywords_list,
                    "download_url": download_url,
                    "namespace_uri": namespace_uri,
                    "issued": issued_year,
                }
            )
    return results


def _parse_graph(
    raw: bytes,
    url: str
    ) -> Graph | None:

    g = Graph()

    for f in FORMATS:
        g.parse(
            data = raw.decode("utf-8", errors="replace"), 
            format = f["format"],
            publicID = url
        )
        return g

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

    remaining_uris = [uri for uri in monitored_uris if uri not in matched]
    if not remaining_uris:
        return matched

    unique_graph_uris: set[str] = set()

    for s, p, o in g:
        if isinstance(s, URIRef): unique_graph_uris.add(str(s))
        if isinstance(p, URIRef): unique_graph_uris.add(str(p))
        if isinstance(o, URIRef): unique_graph_uris.add(str(o))

    for uri in remaining_uris:
        if any(graph_uri.startswith(uri) for graph_uri in unique_graph_uris):
            matched.add(uri)

    return matched


def _process_vocab(
    vocab: dict, 
    monitored_uris: list[str]
    ) -> tuple[str, str, str, list[str]]:

    vocab_uri = vocab.get("vocab", "")
    namespace_uri = vocab.get("namespace_uri", "")
    title = vocab.get("title", "")
    keywords = vocab.get("keywords", "")
    download_url = vocab.get("download_url", "")
    issued = vocab.get("issued", "")

    raw = http_get_raw(download_url)

    if raw is None:
        return namespace_uri, vocab_uri, title, keywords, issued, []

    found_any = any(uri.encode('utf-8') in raw for uri in monitored_uris)
    if not found_any:
        return namespace_uri, vocab_uri, title, keywords, issued, []

    g = _parse_graph(raw, download_url)
    if g is None:
        return namespace_uri, vocab_uri, title, keywords, issued, []
    
    matched = list(_check_graph(g, monitored_uris))

    return namespace_uri, vocab_uri, title, keywords, issued, matched


def _lov_sparql_inlinks(
    ontologies: list[dict], 
    results: dict[str, dict]
    ) -> None:
    uri_to_prefix = {onto["uri"]: onto["prefix"] for onto in ontologies}
    values = " ".join(f"<{onto['uri']}>" for onto in ontologies)
    sparql_query = f"""
        PREFIX voaf: <http://purl.org/vocommons/voaf#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX dcterms: <http://purl.org/dc/terms/>
        PREFIX vann: <http://purl.org/vocab/vann/>
        
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
                "dependency_type": "explicit",
            })
            results[prefix]["inlinks"] += 1


def fetch_data(
    ontologies: list[dict]
    ) -> dict[str, str | dict]:

    results: dict[str, str | dict] = {}

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

    with ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
        futures = {
            executor.submit(_process_vocab, vocab, monitored_uris): vocab
            for vocab in vocabs_to_scan
        }
        for future in tqdm(as_completed(futures)):
            try:
                namespace_uri, vocab_uri, title, keywords, issued, matched_uris = future.result()
                for uri in matched_uris:
                    prefix = uri_to_prefix.get(uri)
                    if prefix and not any(
                        v["uri"] == namespace_uri for v in results[prefix]["using_vocabs"]
                        ):
                        results[prefix]["using_vocabs"].append({
                            "uri": namespace_uri, 
                            "vocab_uri": vocab_uri,
                            "title": title,
                            "keywords": keywords,
                            "issued": issued,
                            "dependency_type": "implicit",
                        })
                        results[prefix]["inlinks"] += 1
                        results[prefix]["keyword_counter"].update(keywords)
                        if issued:
                            results[prefix]["year_counter"].update([issued])
            except Exception as e:
                vocab = futures[future]
                print(f"\n  [LOV] Error processing {vocab['vocab']}: {e}")

    for prefix in results:

        results[prefix]["keyword_frequencies"] = dict(results[prefix].pop("keyword_counter").most_common(5))
        
        year_counter = results[prefix].pop("year_counter")
        timeline = {}
        cumulative = 0
        for year in sorted(year_counter.keys()):
            cumulative += year_counter[year]
            timeline[year] = cumulative
        results[prefix]["adoption_timeline"] = timeline

        explicit_count = 0
        implicit_count = 0
        for vocab in results[prefix]["using_vocabs"]:
            if vocab.get("dependency_type") == "explicit":
                explicit_count += 1
            elif vocab.get("dependency_type") == "implicit":
                implicit_count += 1
        results[prefix]["dependency_frequencies"] = {
            "Explicit": explicit_count,
            "Implicit": implicit_count
        }

    return results