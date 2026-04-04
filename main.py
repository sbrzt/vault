# main.py

from src.loader import load_config
import argparse
from pathlib import Path
import os
import datetime
from src.renderer import render_html
import json
import src.github
import src.http
import src.lov
import src.openalex
import src.opencitations


def main() -> None:
    parser = argparse.ArgumentParser(description="VAULT")
    parser.add_argument(
        "--config", default="config.yaml",
        help="Path to the YAML config file (default: config.yaml)",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    src.http.USER_AGENT = config["user_agent"]
    src.lov.USER_AGENT = config["user_agent"]
    src.lov.CACHE_DIR = Path(config["cache_dir"])
    src.lov.MAX_WORKERS = config["max_workers"]
    src.lov.FORMATS = config["formats"]

    output_dir = Path(config.get("output_dir", "docs"))
    output_dir.mkdir(parents=True, exist_ok=True)
    openalex_key = os.environ.get("OPENALEX_API_KEY", "")
    github_token = os.environ.get("GITHUB_TOKEN", "")
    opencitations_token = os.environ.get("OPENCITATIONS_TOKEN", "")
    generated_at = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M UTC")
    results = []

    print("\n── Fetching LOV (scanning all vocabularies) ──")
    lov_data = src.lov.fetch_lov_all(config["ontologies"])
 
    for ontology in config["ontologies"]:
        print(f"\n── {ontology['label']} ──")
        print("  Fetching GitHub Code...")
        github_data = src.github.fetch_github(ontology, github_token=github_token)
        print("  Fetching OpenAlex...")
        oax_data = src.openalex.fetch_openalex(ontology, api_key=openalex_key)
        print("  Fetching OpenCitations...")
        oc_data = src.opencitations.fetch_opencitations(ontology, api_key=opencitations_token)
    
        results.append({
            "label": ontology["label"],
            "uri": ontology["uri"],
            "prefix": ontology["prefix"],
            "lov": lov_data[ontology["prefix"]],
            "github": github_data,
            "openalex": oax_data,
            "opencitations": oc_data,
        })

    json_file = output_dir / "data.json"
    print(f"\n── Generating report -> {output_dir} ──")
    render_html(results, generated_at, output_dir)
    json_file.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print("Done.")

if __name__ == "__main__":
    main()
