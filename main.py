from src.loader import load_config
import argparse
from pathlib import Path
import os
import datetime
from src.renderer import render_html
from src.fetchers import fetch_lov, fetch_software_heritage, fetch_openalex
import json


def main() -> None:
    parser = argparse.ArgumentParser(description="VAULT")
    parser.add_argument(
        "--config", default="config.yaml",
        help="Path to the YAML config file (default: config.yaml)",
    )
    args = parser.parse_args()
 
    config = load_config(args.config)
    output_dir = Path(config.get("output_dir", "docs"))
    output_dir.mkdir(parents=True, exist_ok=True)
 
    openalex_key = os.environ.get("OPENALEX_API_KEY", "")
    swh_token = os.environ.get("SWH_TOKEN", "")
    generated_at = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M UTC")
    results = []
 
    for ontology in config["ontologies"]:
        print(f"\n── {ontology['label']} ──")
        print("  Fetching LOV...")
        lov_data = fetch_lov(ontology)
        print("  Fetching Software Heritage...")
        swh_data = fetch_software_heritage(ontology, swh_token=swh_token)
        print("  Fetching OpenAlex...")
        oax_data = fetch_openalex(ontology, api_key=openalex_key)
 
        results.append({
            "label": ontology["label"],
            "uri": ontology["uri"],
            "prefix": ontology["prefix"],
            "lov": lov_data,
            "swh": swh_data,
            "openalex": oax_data,
        })

    html_file = output_dir / "index.html"
    json_file = output_dir / "data.json"
 
    print(f"\n── Generating report -> {html_file} ──")
    html_file.write_text(render_html(results, generated_at), encoding="utf-8")
    json_file.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print("Done.")

if __name__ == "__main__":
    main()
