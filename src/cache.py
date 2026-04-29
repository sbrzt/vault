# src/cache.py

from pathlib import Path
import json


def save_cache(
    key: str,
    data: dict,
    output_dir: Path
    ) -> None:
    cache_file = output_dir / f"{key}.json"
    cache_file.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def load_cache(
    cache_file: Path,
    key: str | None,
    ) -> dict | None:
    if cache_file.exists():
        if key:
            data = [
                {
                    "label": ontology["label"],
                    "uri": ontology["uri"],
                    "prefix": ontology["prefix"],
                    key: ontology[key]
                }
            for ontology in cache_file.read_text(encoding="utf-8")]
        else:
            data = cache_file.read_text(encoding="utf-8")
        return data
    return None