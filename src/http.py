# src/http.py

import json
import time
import io
import hashlib
import urllib.request
import urllib.parse
import urllib.error
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDFS, OWL
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path



def http_get(
    url: str, 
    headers: dict | None = None, 
    retries: int = 1, 
    delay: float = 2.0
    ):
    req = urllib.request.Request(url, headers=headers or {})
    req.add_header("User-Agent", USER_AGENT)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    print(f"  [HTTP] Non-JSON response from {url}:")
                    print(f"  {raw[:300]}")
                    return None
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = delay * (2 ** attempt)
                print(f"  [HTTP] Rate limited ({url}), waiting {wait:.0f}s…")
                time.sleep(wait)
            else:
                print(f"  [HTTP] {e.code} for {url}")
                try:
                    print(f"  [HTTP] Body: {e.read().decode('utf-8')[:500]}")
                except:
                    pass
                return None
        except Exception as e:
            print(f"  [HTTP] Error fetching {url}: {e}")
            if attempt < retries - 1:
                time.sleep(delay)
    return None


def http_get_raw(
    url: str,
    headers: dict | None = None,
    retries: int = 3, 
    delay: float = 2.0
    ) -> bytes | None:
    req = urllib.request.Request(
        url,
        headers=headers or {}
    )
    req.add_header("User-Agent", USER_AGENT)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(
                req,
                timeout=60
            ) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            print(f"  [HTTP] {e.code} fetching {url}")
            return None
        except Exception as e:
            print(f"  [HTTP] Error fetching {url}: {e}")
            if attempt < retries - 1:
                time.sleep(delay)
    return None