# Vocabulary and Artifact Usage Locator and Tracker (VAULT)

A GitHub Actions-powered tool that runs monthly, fetches usage data for one or more ontologies across three sources, and generates a self-contained HTML report — no backend required.

## To-Do

- [] `fetch_lov`: add another heuristic based on the use of `rdfs:isDefinedBy` **within** the single ontology


## Data Sources

| Source | What it measures |
|---|---|
| **[LOV](https://lov.linkeddata.es)** | Vocabularies that import or extend your ontology |
| **[Software Heritage](https://archive.softwareheritage.org)** | Archived repos whose metadata references your namespace |
| **[OpenAlex](https://openalex.org)** | Academic papers that cite or discuss your ontology |

## Project structure

```
.
├── config.yaml          ← edit this to configure your ontologies
├── main.py               ← orchestrator (reads config, calls fetchers, writes output)
├── fetchers.py              ← all API logic (LOV, SWH, OpenAlex)
├── renderer.py              ← pure HTML generation (no I/O)
├── tests/
│   ├── test_config.py       ← config loading and validation
│   ├── test_fetchers.py     ← fetcher logic (all mocked, no real API calls)
│   └── test_renderer.py     ← HTML output correctness
├── docs/
│   ├── index.html           ← generated report (served via GitHub Pages)
│   └── data.json            ← raw JSON snapshot for auditing
└── .github/workflows/
    └── monitor.yml          ← monthly GitHub Actions schedule
```

## Quick Start

### 1. Configure your ontologies

Edit `config.yaml`:

```yaml
output_dir: docs

ontologies:
  - label: "My Ontology"
    uri: "https://example.org/myonto/"
    prefix: "myonto"
    openalex_keywords:
      - "My Ontology"
      - "myonto vocabulary"
```

### 2. Set GitHub Secrets

Go to **Settings → Secrets and variables → Actions**:

| Secret | Notes |
|---|---|
| `OPENALEX_API_KEY` | **Required.** Free at [openalex.org](https://openalex.org) after signup |
| `SWH_TOKEN` | *Optional.* Lifts SWH rate limits |

### 3. Enable GitHub Pages

**Settings → Pages** → source: `docs/` folder on `main`.
Report will be live at `https://<you>.github.io/<repo>/`.

## Running locally

```bash
# Install dependencies and sync the virtualenv
uv sync

# Run with API keys
OPENALEX_API_KEY=your_key uv run main.py

# Custom config file
uv run main.py --config config.yaml
```

## Running tests

No API keys or network access needed — all external calls are mocked.

```bash
uv run python -m unittest discover -s tests -v
```

