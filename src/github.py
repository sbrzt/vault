# src/github.py

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
