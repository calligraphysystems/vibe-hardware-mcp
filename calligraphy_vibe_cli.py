#!/usr/bin/env python3
"""
Calligraphy EDA — Vibe-Coding Hardware CLI (`calligraphy_vibe_cli.py`)
Zero-dependency Python 3 client for inspecting the 0-DRC Benchmark Gallery
and running free instant Pre-Flight DFM Quotes against https://calligraphyeda.com.
"""

import argparse
import base64
import json
import pathlib
import sys
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "https://calligraphyeda.com"


def fetch_gallery(base_url: str) -> None:
    url = f"{base_url.rstrip('/')}/api/v1/gallery"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "CalligraphyVibeCLI/1.0 (+https://calligraphyeda.com)"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=15.0) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    items = data.get("showcase_boards") or data.get("items") or []
    print(f"=== Calligraphy EDA Verified 0-DRC Gallery ({len(items)} boards) ===")
    for idx, item in enumerate(items, 1):
        title = item.get("title") or item.get("board_id") or f"Board #{idx}"
        layers = item.get("layer_count") or item.get("layers") or "?"
        unconn = item.get("unconnected_after", 0)
        drc = item.get("drc_after", 0)
        print(f"  {idx:2d}. {title} [{layers}L] -> Unconnected: {unconn}, Native KiCad DRC: {drc}")


def request_quote(base_url: str, board_path: pathlib.Path, sku: str) -> None:
    if not board_path.is_file():
        print(f"Error: File not found: {board_path}", file=sys.stderr)
        sys.exit(1)
    raw_bytes = board_path.read_bytes()
    payload = {
        "filename": board_path.name,
        "requested_sku": sku,
        "storefront_domain": "calligraphyeda.com",
        "upload_b64": base64.b64encode(raw_bytes).decode("ascii"),
    }
    url = f"{base_url.rstrip('/')}/api/v1/quote"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "CalligraphyVibeCLI/1.0 (+https://calligraphyeda.com)",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20.0) as resp:
            quote = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code} from {url}:\n{err_body}", file=sys.stderr)
        sys.exit(1)

    print("=== Calligraphy EDA Instant Pre-Flight DFM Quote ===")
    print(f"  Board File      : {board_path.name}")
    print(f"  Assigned Tier   : {quote.get('sku_id') or sku}")
    print(f"  Quoted Price    : ${quote.get('final_price_usd', quote.get('quoted_price_usd', 'N/A'))} USD")
    print(f"  Layer Count     : {quote.get('layer_count', 'N/A')}")
    print(f"  Pad Count       : {quote.get('pad_count', 'N/A')}")
    dfm = quote.get("free_instant_dfm_audit") or {}
    if dfm:
        print(f"  Pre-Flight DFM  : {json.dumps(dfm, indent=2)}")
    print(f"\nUpload & inspect 350-DPI copper proof at: {base_url}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calligraphy EDA — Vibe-Coding Hardware CLI (https://calligraphyeda.com)"
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Foundry base URL")
    parser.add_argument("--gallery", action="store_true", help="List the verified 0-DRC benchmark gallery")
    parser.add_argument("--quote", type=pathlib.Path, help="Path to .kicad_pcb, .dsn, .PcbDoc, or .brd file")
    parser.add_argument("--sku", default="vibe_micro", help="Target SKU (vibe_micro, basic_2l, route_3d)")
    args = parser.parse_args()

    if args.gallery:
        fetch_gallery(args.base_url)
    elif args.quote:
        request_quote(args.base_url, args.quote, args.sku)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
