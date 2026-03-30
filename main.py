# main.py

from src.loader import load_config
import argparse
from pathlib import Path
import os
import datetime
from src.renderer import render_html
import src.fetchers
import json


def main() -> None:
    parser = argparse.ArgumentParser(description="VAULT")
    parser.add_argument(
        "--config", default="config.yaml",
        help="Path to the YAML config file (default: config.yaml)",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    src.fetchers.USER_AGENT = config["user_agent"]
    src.fetchers.CACHE_DIR = Path(config["cache_dir"])
    src.fetchers.MAX_WORKERS = config["max_workers"]
    src.fetchers.FORMATS = config["formats"]

    output_dir = Path(config.get("output_dir", "docs"))
    output_dir.mkdir(parents=True, exist_ok=True)
    openalex_key = os.environ.get("OPENALEX_API_KEY", "")
    github_token = os.environ.get("GITHUB_TOKEN", "")
    generated_at = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M UTC")
    results = []

    print("\n── Fetching LOV (scanning all vocabularies) ──")
    lov_results = src.fetchers.fetch_lov_all(config["ontologies"])
 
    for ontology in config["ontologies"]:
        print(f"\n── {ontology['label']} ──")
        print("  Fetching GitHub Code...")
        github_data = src.fetchers.fetch_github(ontology, github_token=github_token)
        print("  Fetching OpenAlex...")
        oax_data = src.fetchers.fetch_openalex(ontology, api_key=openalex_key)
 
        results.append({
            "label": ontology["label"],
            "uri": ontology["uri"],
            "prefix": ontology["prefix"],
            "lov": lov_results[ontology["prefix"]],
            "github": github_data,
            "openalex": oax_data,
        })

    json_file = output_dir / "data.json"
    print(f"\n── Generating report -> {output_dir} ──")
    render_html(results, generated_at, output_dir)
    json_file.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print("Done.")

if __name__ == "__main__":
    main()
