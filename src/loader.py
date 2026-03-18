import yaml
from pathlib import Path


def load_config(config_path) -> dict:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    _validate_config(config)
    return config

def _validate_config(config: dict) -> None:
    if "ontologies" not in config or not config["ontologies"]:
        raise ValueError("Config must include at least one entry under 'ontologies'.")
    for i, onto in enumerate(config["ontologies"]):
        for field in ("label", "uri", "prefix", "openalex_keywords"):
            if field not in onto:
                raise ValueError(f"Ontology #{i} is missing required field '{field}'.")