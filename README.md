# Vocabulary and Artifact Uptake Locator and Tracker (VAULT)

A tool that fetches usage data for ontologies across diverse sources, and generates a self-contained HTML report.

## To-Do

- [x] `fetch_lov`: add another heuristic based on the use of `rdfs:isDefinedBy` **within** the single ontology
- [ ] `fetch_lov`: refine heuristics and eventually integrate additional resources
- [x] `fetch_openalex`: the intuition is correct (fulltext search is a strong signal), but it needs more work on how it deals with keywords
- [x] `fetch_opencitations`: add `papers` in configuration parameters
- [ ] `fetch_opencitations`: add more meaningful paper metadata
- [ ] add uptake statistics at general level (including all ontologies taken into consideration)
- [ ] `report.html.j2` and `style.css`: add better UX and information visualization
- [x] add license
- [ ] add citation file
- [ ] add PDF download
- [ ] add proper configuration for sources that can be used in the report


## Data Sources

| Source | What it measures |
|---|---|
| **[LOV](https://lov.linkeddata.es)** | Vocabularies that import or extend the ontologies |
| **[GitHub](https://github.com)** | Repos whose metadata references the ontologies' namespaces |
| **[OpenAlex](https://openalex.org)** | Academic papers that cite or discuss the ontologies |

## Project structure

```
.
├── config.yaml          ← edit this to configure your ontologies
├── main.py               ← orchestrator (reads config, calls fetchers, writes output)
├── fetchers.py              ← all API logic (LOV, GitHub, OpenAlex)
├── renderer.py              ← pure HTML generation (no I/O)
├── tests/
│   ├── test_config.py       ← config loading and validation
│   ├── test_fetchers.py     ← mocked fetcher logic
│   └── test_renderer.py     ← HTML output correctness
├── docs/
│   ├── index.html           ← generated report
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
| `GITHUB_TOKEN` | **Required.** Free at [github.com](https://github.com) after signup |

### 3. Enable GitHub Pages

**Settings → Pages** → source: `docs/` folder on `main`.
Report will be live at `https://<you>.github.io/vault/`.

## Running locally

Create a `.env` file at the root of the project:

```
GITHUB_TOKEN="<YOUR_GITHUB_TOKEN>"
OPENALEX_API_KEY="<YOUR_OPENALEX_API_KEY>"
```

Then run `main.py` in the terminal:

```bash
# Install dependencies and sync the virtualenv
uv sync

# Run with .env loaded
uv run --env-file .env main.py
```

## Running tests

 All external calls are mocked, so no API keys or network access is needed.

```bash
uv run python -m unittest discover -s tests -v
```

