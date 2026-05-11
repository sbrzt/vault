# src/github.py

import json
import time
import io
import urllib.request
import urllib.parse
from pathlib import Path
from collections import Counter
from tqdm import tqdm
from src.http import http_get
from collections import Counter


# https://gist.github.com/aymen-mouelhi/82c93fbcd25f091f2c13faa5e0d61760
FILE_CATEGORIES = {
    "programming": {
        "py",
        "js",
        "java",
        "rs",
        "go",
        "pl",
        "php",
        "rb"
    },
    "documentation": {
        "md",
        "rst",
        "txt",
        "html",
    },
    "data": {
        "rdf",
        "owl",
        "ttl",
        "jsonld",
        "n3",
        "nt",
        "sparql",
        "rq",
        "yml",
        "yaml",
        "toml",
        "json",
    }
}


def _categorize(filename: str) -> str | None:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    for category, extensions in FILE_CATEGORIES.items():
        if ext in extensions:
            return category
    return None


def fetch_github(
    ontology: dict, 
    github_token: str = ""
    ) -> dict:

    result: dict = {
        "repos_count": 0, 
        "repos": [],
        "total_by_category": {cat: 0 for cat in FILE_CATEGORIES},
        "owner_frequencies": Counter()
    }

    if not github_token:
        print("  [GitHub] No token provided, skipping.")
        return result

    extensions = " OR ".join(
        f"extension:{ext}"
        for exts in FILE_CATEGORIES.values()
        for ext in exts
    )

    query= f'"{ontology["uri"]}" {extensions}'
    url = "https://api.github.com/search/code?" + urllib.parse.urlencode({"q": query, "per_page": 100})
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    
    data = http_get(url, headers=headers)
    
    if data and "items" in data:
        repos: dict[str, dict] = {}
        for item in data["items"]:
            repo = item.get("repository", {})
            filename = item.get("name", "")
            if not repo:
                continue
            repo_name = repo.get("full_name", "")
            repo_url = repo.get("html_url", "")
            repo_owner = repo.get("owner")
            repo_description = repo.get("description", "")
            category = _categorize(filename)
            if repo_name not in repos:
                repos[repo_name] = {
                    "name": repo_name,
                    "url": repo_url,
                    "owner": repo_owner,
                    "description": repo_description,
                    "by_category": {cat: 0 for cat in FILE_CATEGORIES},
                }
            if category:
                repos[repo_name]["by_category"][category] += 1
                result["total_by_category"][category] += 1
            result["owner_frequencies"].update([repos[repo_name]["owner"]["type"]])
        result["repos"] = list(repos.values())
        result["repos_count"] = len(result["repos"])
    
    time.sleep(6)
    return result
