# src/renderer.html

import json
 
 
def render_html(data: list[dict], generated_at: str) -> str:
    onto_sections = ""
    summary_cards = ""
    for onto in data:
        label = onto["label"]
        uri = onto["uri"]
        lov = onto["lov"]
        github = onto["github"]
        oax = onto["openalex"]
        years = sorted(oax["by_year"].keys())
        year_counts = [oax["by_year"][y] for y in years]
        top_works_rows = _render_top_works(oax["top_works"])
        importing_list = _render_link_list(lov.get("importing_vocabs", []), limit=10)
        repos_list = _render_link_list(github.get("repos", []), domain="https://github.com/", limit=8)
        lov_status = "✓ Listed" if lov["found"] else "✗ Not listed"
        lov_class = "status-ok" if lov["found"] else "status-missing"
        summary_cards += f"""
        <div class="summary-card">
            <h3>{label}</h3>
            <div class="uri">{uri}</div>
            <div class="metrics">
                <div class="metric">
                    <span class="metric-value">{oax['total_works']}</span>
                    <span class="metric-label">Papers (OpenAlex)</span>
                </div>
                <div class="metric">
                    <span class="metric-value">{lov['inlinks']}</span>
                    <span class="metric-label">Imports (LOV)</span>
                </div>
                <div class="metric">
                    <span class="metric-value">{github['repos_count']}</span>
                    <span class="metric-label">Repos (github)</span>
                </div>
            </div>
        </div>"""

        onto_sections += f"""
        <section class="onto-section" id="onto-{onto['prefix']}">
            <div class="section-header">
                <h2>{label}</h2>
                <span class="uri-badge">{uri}</span>
            </div>
            <div class="grid-3">
 
                <div class="card">
                    <div class="card-header">
                        <span class="source-tag lov-tag">LOV</span>
                        <h3>Ontology Imports</h3>
                    </div>
                    <div class="card-stat">
                        <span class="big-num">{lov['inlinks']}</span>
                        <span class="stat-label">vocabularies import this ontology</span>
                    </div>
                    <div class="card-detail">
                        <div class="status-line {lov_class}">{lov_status} in LOV catalogue</div>
                        <p class="sub">Vocabularies importing or extending <strong>{label}</strong>:</p>
                        <ul class="compact-list">{importing_list}</ul>
                        {f'<a class="lov-link" href="{lov["url"]}" target="_blank">View in LOV →</a>' if lov.get("url") else ""}
                    </div>
                </div>
 
                <div class="card">
                    <div class="card-header">
                        <span class="source-tag github-tag">github</span>
                        <h3>Code Usage</h3>
                    </div>
                    <div class="card-stat">
                        <span class="big-num">{github['repos_count']}</span>
                        <span class="stat-label">archived repos reference this namespace</span>
                    </div>
                    <div class="card-detail">
                        <p class="sub">Repositories:</p>
                        <ul class="compact-list">{repos_list}</ul>
                    </div>
                </div>
 
                <div class="card">
                    <div class="card-header">
                        <span class="source-tag oax-tag">OpenAlex</span>
                        <h3>Academic Citations</h3>
                    </div>
                    <div class="card-stat">
                        <span class="big-num">{oax['total_works']}</span>
                        <span class="stat-label">works found across all keywords</span>
                    </div>
                    <div class="card-detail">
                        <canvas id="chart-{onto['prefix']}" height="120"></canvas>
                    </div>
                </div>
            </div>
 
            <div class="card full-width">
                <div class="card-header">
                    <span class="source-tag oax-tag">OpenAlex</span>
                    <h3>Most Cited Papers</h3>
                </div>
                <table class="papers-table">
                    <thead><tr>
                        <th>Title</th><th>Year</th><th>Citations</th><th>Venue</th>
                    </tr></thead>
                    <tbody>{top_works_rows if top_works_rows else '<tr><td colspan="4">No papers found</td></tr>'}</tbody>
                </table>
            </div>
        </section>
 
        <script>
        (function() {{
            var ctx = document.getElementById('chart-{onto['prefix']}');
            if (!ctx) return;
            new Chart(ctx, {{
                type: 'bar',
                data: {{
                    labels: {json.dumps(years)},
                    datasets: [{{
                        label: 'Papers per year',
                        data: {json.dumps(year_counts)},
                        backgroundColor: 'rgba(99,179,237,0.7)',
                        borderColor: 'rgba(99,179,237,1)',
                        borderWidth: 1,
                        borderRadius: 3,
                    }}]
                }},
                options: {{
                    responsive: true,
                    plugins: {{ legend: {{ display: false }} }},
                    scales: {{
                        y: {{ beginAtZero: true, ticks: {{ stepSize: 1 }}, grid: {{ color: 'rgba(255,255,255,0.05)' }} }},
                        x: {{ grid: {{ display: false }} }}
                    }}
                }}
            }});
        }})();
        </script>
        """
 
    nav_links = "".join(
        f'<a href="#onto-{o["prefix"]}">{o["label"]}</a>' for o in data
    )
 
    return _html_shell(summary_cards, onto_sections, nav_links, generated_at)

 
def _render_top_works(works: list[dict]) -> str:
    rows = ""
    for w in works:
        doi_link = ""
        if w.get("doi"):
            clean = w["doi"].replace("https://doi.org/", "")
            doi_link = f' <a href="https://doi.org/{clean}" target="_blank">↗</a>'
        rows += f"""
            <tr>
                <td class="title-cell">{w['title']}{doi_link}</td>
                <td class="center">{w['year'] or '—'}</td>
                <td class="center">{w['cited_by_count']}</td>
                <td>{w['source_name']}</td>
            </tr>"""
    return rows
 
 
def _render_link_list(items: list[str], domain: str = "", limit: int = 10) -> str:
    if not items:
        return "<li><em>None found</em></li>"
    html = ""
    for item in items[:limit]:
        name = item.rstrip("/").split("/")[-1].split("#")[-1] or item
        html += f'<li><a href="{domain}{item}" target="_blank">{name}</a></li>'
    return html
 
 
def _html_shell(summary_cards: str, onto_sections: str, nav_links: str, generated_at: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Ontology Usage Monitor</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');
  :root {{
    --bg:#0d1117;--bg2:#161b22;--bg3:#1c2330;--border:#30363d;
    --text:#e6edf3;--muted:#7d8590;
    --accent-lov:#58a6ff;--accent-github:#3fb950;--accent-oax:#d2a8ff;--accent-warn:#f78166;
    --font-mono:'IBM Plex Mono',monospace;--font-sans:'IBM Plex Sans',sans-serif;
  }}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:var(--bg);color:var(--text);font-family:var(--font-sans);font-weight:300;line-height:1.6}}
  header{{background:var(--bg2);border-bottom:1px solid var(--border);padding:20px 40px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100}}
  .logo{{font-family:var(--font-mono);font-size:.85rem;font-weight:600;color:var(--accent-lov);letter-spacing:.08em;text-transform:uppercase}}
  .header-meta{{font-family:var(--font-mono);font-size:.75rem;color:var(--muted)}}
  nav a{{color:var(--muted);text-decoration:none;font-size:.82rem;margin-left:20px;transition:color .15s}}
  nav a:hover{{color:var(--text)}}
  main{{max-width:1200px;margin:0 auto;padding:40px 32px}}
  .summary-strip{{display:flex;gap:20px;margin-bottom:48px;flex-wrap:wrap}}
  .summary-card{{background:var(--bg2);border:1px solid var(--border);border-radius:8px;padding:24px;flex:1;min-width:260px}}
  .summary-card h3{{font-size:1rem;font-weight:600;margin-bottom:4px}}
  .summary-card .uri{{font-family:var(--font-mono);font-size:.7rem;color:var(--muted);margin-bottom:16px;word-break:break-all}}
  .metrics{{display:flex;gap:16px}}
  .metric{{display:flex;flex-direction:column;align-items:center;flex:1}}
  .metric-value{{font-family:var(--font-mono);font-size:1.6rem;font-weight:600;line-height:1.1}}
  .metric-label{{font-size:.68rem;color:var(--muted);text-align:center;margin-top:4px}}
  .onto-section{{margin-bottom:64px;scroll-margin-top:80px}}
  .section-header{{display:flex;align-items:baseline;gap:16px;margin-bottom:24px;padding-bottom:12px;border-bottom:1px solid var(--border)}}
  .section-header h2{{font-size:1.4rem;font-weight:600}}
  .uri-badge{{font-family:var(--font-mono);font-size:.72rem;color:var(--muted);background:var(--bg3);padding:3px 8px;border-radius:4px;border:1px solid var(--border)}}
  .grid-3{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:16px}}
  @media(max-width:900px){{.grid-3{{grid-template-columns:1fr 1fr}}}}
  @media(max-width:600px){{.grid-3{{grid-template-columns:1fr}}main{{padding:24px 16px}}header{{flex-direction:column;gap:12px;padding:16px}}}}
  .card{{background:var(--bg2);border:1px solid var(--border);border-radius:8px;padding:20px;transition:border-color .15s}}
  .card:hover{{border-color:#444c56}}
  .full-width{{grid-column:1/-1}}
  .card-header{{display:flex;align-items:center;gap:10px;margin-bottom:16px}}
  .card-header h3{{font-size:.9rem;font-weight:600}}
  .source-tag{{font-family:var(--font-mono);font-size:.65rem;font-weight:600;padding:2px 7px;border-radius:3px;text-transform:uppercase;letter-spacing:.05em}}
  .lov-tag{{background:rgba(88,166,255,.15);color:var(--accent-lov)}}
  .github-tag{{background:rgba(63,185,80,.15);color:var(--accent-github)}}
  .oax-tag{{background:rgba(210,168,255,.15);color:var(--accent-oax)}}
  .card-stat{{margin-bottom:16px}}
  .big-num{{display:block;font-family:var(--font-mono);font-size:2.4rem;font-weight:600;line-height:1.1}}
  .stat-label{{font-size:.78rem;color:var(--muted)}}
  .status-line{{font-size:.8rem;margin-bottom:12px;padding:4px 8px;border-radius:4px;display:inline-block}}
  .status-ok{{background:rgba(63,185,80,.1);color:var(--accent-github)}}
  .status-missing{{background:rgba(247,129,102,.1);color:var(--accent-warn)}}
  .sub{{font-size:.78rem;color:var(--muted);margin-bottom:6px}}
  .compact-list{{list-style:none;padding:0}}
  .compact-list li{{font-size:.78rem;padding:3px 0;border-bottom:1px solid var(--border)}}
  .compact-list li:last-child{{border-bottom:none}}
  .compact-list a{{color:var(--accent-lov);text-decoration:none}}
  .compact-list a:hover{{text-decoration:underline}}
  .lov-link{{display:inline-block;margin-top:12px;font-size:.78rem;color:var(--accent-lov);text-decoration:none}}
  .lov-link:hover{{text-decoration:underline}}
  .papers-table{{width:100%;border-collapse:collapse;font-size:.82rem}}
  .papers-table th{{text-align:left;padding:8px 12px;font-weight:600;font-size:.75rem;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid var(--border)}}
  .papers-table td{{padding:10px 12px;border-bottom:1px solid var(--bg3);vertical-align:top}}
  .papers-table tr:last-child td{{border-bottom:none}}
  .papers-table tr:hover td{{background:var(--bg3)}}
  .title-cell{{max-width:400px}}
  .title-cell a{{color:var(--accent-oax);text-decoration:none;font-size:.8rem}}
  .center{{text-align:center}}
  footer{{margin-top:80px;padding:24px 32px;border-top:1px solid var(--border);font-family:var(--font-mono);font-size:.72rem;color:var(--muted);display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px}}
</style>
</head>
<body>
<header>
  <div class="logo">VAULT</div>
  <nav>{nav_links}</nav>
  <div class="header-meta">Generated: {generated_at}</div>
</header>
<main>
  <div class="summary-strip">{summary_cards}</div>
  {onto_sections}
</main>
<footer>
  <span>Sources: LOV · GitHub · OpenAlex</span>
  <span>Generated automatically via GitHub Actions · {generated_at}</span>
</footer>
</body>
</html>"""