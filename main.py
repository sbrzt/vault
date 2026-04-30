# main.py

import src.dimensions.vocabularies.lov as lov
from src.loader import load_config
import argparse
from pathlib import Path
import os
import datetime
from src.renderer import render_html
import json
from src.cache import save_cache, load_cache
import src.http
#import src.github
#import src.openalex
#import src.opencitations
#import src.zenodo


def main() -> None:
    parser = argparse.ArgumentParser(description="VAULT")
    parser.add_argument(
        "--config", default="config.yaml",
        help="Path to the YAML config file (default: config.yaml)",
    )
    parser.add_argument(
        "--only", 
        choices=["lov", "zenodo", "github", "openalex", "opencitations", "render"], 
        default=None
    )
    parser.add_argument(
        "--use-cache", 
        action="store_true", 
        help="Load previous results from cache instead of fetching"
    )
    args = parser.parse_args()

    config = load_config(args.config)
    src.http.USER_AGENT = config["user_agent"]
    lov.FORMATS = config["formats"]

    output_dir = Path(config.get("output_dir", "docs"))
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_file = output_dir / config.get("cache_file", "")

    #openalex_token = os.environ.get("OPENALEX_TOKEN", "")
    #github_token = os.environ.get("GITHUB_TOKEN", "")
    #opencitations_token = os.environ.get("OPENCITATIONS_TOKEN", "")
    #zenodo_token = os.environ.get("ZENODO_TOKEN", "")
    
    generated_at = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M UTC")
    
    results = []

    if args.only == "render":
        if args.use_cache:
            if cache_file.exists():
                results = json.loads(cache_file.read_text(encoding="utf-8"))
            print("\nGenerating report...")
            render_html(results, generated_at, output_dir)
            print("Done.")
            return
    '''
    if args.use_cache:
        if cache_file.exists():
            existing = {r["prefix"]: r for r in json.loads(cache_file.read_text(encoding="utf-8"))}
        else:
            existing = {}'''

    if args.only in (None, "lov"):
        print("\n── Fetching LOV ──")
        if args.use_cache:
            lov_data = {p: existing[p]["lov"] for p in existing}
        else:
            lov_data = lov.fetch_lov_all(config["ontologies"])
    
    '''if args.only in (None, "zenodo"):
        print("\n-- Fetching Zenodo --")
        if args.use_cache:
            zenodo_data = {p: existing[p]["zenodo"] for p in existing}
        else:
            zenodo_data = src.zenodo.fetch_zenodo_all(config["ontologies"], api_key=zenodo_token)
            #save_cache("zenodo", zenodo_data, output_dir)'''
        
    for ontology in config["ontologies"]:
        print(f"\n{ontology['label']}")
        prefix = ontology["prefix"]

        '''if args.only in (None, "github"):
            print("\n-- Fetching GitHub Code --")
            if args.use_cache:
                github_data = existing.get(prefix, {}).get("github", {})
            else:
                github_data = src.github.fetch_github(ontology, github_token=github_token)
                #save_cache("github", github_data, output_dir)
        
        print("\n-- Fetching OpenAlex --")
        if args.only in (None, "openalex"):
            if args.use_cache:
                oax_data = existing.get(prefix, {}).get("openalex", {})
            else:
                oax_data = src.openalex.fetch_openalex(ontology, api_key=openalex_token)
                #save_cache("openalex", oax_data, output_dir)
        
        print("  Fetching OpenCitations...")
        if args.only in (None, "opencitations"):
            if args.use_cache:
                oc_data = existing.get(prefix, {}).get("opencitations", {})
            else:
                oc_data = src.opencitations.fetch_opencitations(ontology, api_key=opencitations_token)
                #save_cache("openalex", oc_data, output_dir)'''
        
        results.append({
            "label": ontology["label"],
            "full_name": ontology["full_name"],
            "uri": ontology["uri"],
            "prefix": ontology["prefix"],
            "lov": lov_data.get(prefix, {}),
            #"github": github_data,
            #"openalex": oax_data,
            #"opencitations": oc_data,
            #"zenodo": zenodo_data.get(prefix, {}),
        })

    print(f"\nGenerating report...")
    render_html(results, generated_at, output_dir)
    cache_file.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print("Done.")

if __name__ == "__main__":
    main()
