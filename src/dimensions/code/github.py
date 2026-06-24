# src/github.py

import json
import time
import urllib.request
import urllib.parse
from collections import Counter
from pathlib import Path
from src.http import http_get


current_dir = Path(__file__).parent
file_path = current_dir / "languages.json"

with open(file_path, "r", encoding="utf-8") as f:
    LANGUAGES_DATA = json.load(f)

EXT_TO_CATEGORY = {
    ext.lstrip(".").lower(): lang["type"]
    for lang in LANGUAGES_DATA
    for ext in lang.get("extensions", [])
}

AVAILABLE_CATEGORIES = set(EXT_TO_CATEGORY.values())


def _categorize(filename: str) -> str | None:
    if "." not in filename:
        return None
    ext = filename.rsplit(".", 1)[-1].lower()
    return EXT_TO_CATEGORY.get(ext)


def fetch_github(
    ontology: dict, 
    github_token: str = ""
    ) -> dict:

    result: dict = {
        "repos_count": 0, 
        "repos": [],
        "total_by_category": {cat: 0 for cat in AVAILABLE_CATEGORIES},
        "owner_frequencies": Counter()
    }

    if not github_token:
        print("  [GitHub] No token provided, skipping.")
        return result

    query= f'"{ontology["uri"]}"'
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
                    "by_category": {cat: 0 for cat in AVAILABLE_CATEGORIES},
                }

            if category:
                repos[repo_name]["by_category"][category] += 1
                result["total_by_category"][category] += 1

            if "type" in repo_owner:
                result["owner_frequencies"].update([repo_owner["type"]])

        result["repos"] = list(repos.values())
        result["repos_count"] = len(result["repos"])
    
    time.sleep(6)
    return result
