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
        "files_count": 0,
        "repos": [],
        "total_by_category": {cat: 0 for cat in AVAILABLE_CATEGORIES},
        "owner_frequencies": Counter()
    }

    if not github_token:
        print("  [GitHub] No token provided, skipping.")
        return result

    query= f'"{ontology["uri"]}"'
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    page = 1
    repos = {}

    while True:
        url = "https://api.github.com/search/code?" + urllib.parse.urlencode({
            "q": query, 
            "per_page": 100,
            "page": page
        })
    
        data = http_get(url, headers=headers)
        if not data or "items" not in data or not data["items"]:
            break

        if page == 1:
            result["files_count"] = data.get("total_count", 0)
    
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
                    "total_files": 0
                }
            
            repos[repo_name]["total_files"] += 1

            if category:
                repos[repo_name]["by_category"][category] += 1
                result["total_by_category"][category] += 1

            if "type" in repo_owner:
                result["owner_frequencies"].update([repo_owner["type"]])
        
        if len(data["items"]) < 100 or page >= 10:
            break
        page += 1
        time.sleep(6)

    result["repos"] = list(repos.values())
    result["repos_count"] = len(result["repos"])

    unique_owners = {repo["owner"].get("id") or repo["owner"].get("login") for repo in result["repos"] if repo.get("owner")}
    result["owners_count"] = len(unique_owners)
    
    if page == 1:
        time.sleep(6)

    return result
