#!/usr/bin/env python3
"""
Calligraphy EDA — Zero-Dependency Python 3 `stdio` MCP Server & HTTPS Bridge (v6.2.38)
======================================================================================
- Handles Model Context Protocol (MCP) JSON-RPC 2.0 introspection (`initialize`, `ping`,
  `tools/list`, `resources/list`, `prompts/list`, and `notifications/*`) 100% locally in <5 ms
  with zero network required (passing Glama.ai / Docker introspection checks cleanly).
- On `tools/call`:
  - If the caller passes a local file path in `arguments["project_path"]` that exists on the
    local filesystem (`Path(project_path).is_file()`) and `pcb_text` / `upload_b64` are not yet
    populated, automatically reads the local file (`pcb_text` for text CAD formats `.kicad_pcb`,
    `.dsn`, `.ato`, `.tsx`, `.xml` or base64 `upload_b64` for binary `.PcbDoc` / `.zip` / `.brd`),
    sets `arguments["filename"] = Path(project_path).name`, removes `project_path`, and forwards
    the JSON-RPC 2.0 `POST` request to `https://calligraphyeda.com/api/v1/mcp`.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

REMOTE_MCP_ENDPOINT = os.environ.get(
    "CALLIGRAPHY_MCP_ENDPOINT",
    "https://calligraphyeda.com/api/v1/mcp",
).strip()

TEXT_CAD_EXTENSIONS = {".kicad_pcb", ".dsn", ".ato", ".tsx", ".ts", ".xml", ".ses"}

MCP_TOOLS_SCHEMA: List[Dict[str, Any]] = [
    {
        "name": "calligraphy_list_gallery_boards",
        "description": (
            "List the 13 conquered open-source PCB benchmark boards (100.0% routed, 0 native KiCad copper DRC violations) "
            "and available 1-click sample demo IDs ('2l_rp2040', '2l_stickhub', '4l_carrier')."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "calligraphy_preflight_audit",
        "description": (
            "Inspect a .kicad_pcb file or .zip project bundle (including atopile/tscircuit/Altium/Allegro builds), "
            "verify outline/pad readiness, and return a deterministic 3-Lever NRE-anchored price quote ($149 vibe_micro "
            "for <=150 pads up to $1,495+ route_3d). "
            "Mode A (Zero-File Demo): Pass `sample_id='2l_rp2040'` (or `'2l_stickhub'`, `'4l_carrier'`). "
            "Mode B (User's Local Board): Pass a local file path in `project_path` (stdio mode) or pass its contents in "
            "`pcb_text` + `filename` (or `upload_b64` for `.PcbDoc`/`.zip`)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "sample_id": {"type": "string", "description": "Optional built-in sample board ID ('2l_rp2040', '2l_stickhub', '4l_carrier')"},
                "pcb_text": {"type": "string", "description": "Raw CAD file contents (.kicad_pcb, .dsn, .ato, .tsx, .xml) for remote HTTP MCP calls"},
                "upload_b64": {"type": "string", "description": "Base64-encoded CAD file or .zip bundle for remote HTTP MCP calls"},
                "filename": {"type": "string", "default": "board.kicad_pcb"},
                "customer_email": {"type": "string", "default": "agent@customer.io", "description": "Engineer email for 30-day ECO license matching"},
                "requested_sku": {
                    "type": "string",
                    "enum": ["vibe_micro", "basic_2l", "intro_trial", "dfm_fix", "route_3d", "premium_hs", "turnkey_full"],
                    "default": "route_3d",
                },
                "include_eco_pass": {"type": "boolean", "default": False, "description": "+50% 30-Day Unlimited ECO Re-Spin Pass"},
                "rush_delivery": {"type": "boolean", "default": False, "description": "+35% Instant <45m Enclave Rush Turnaround"},
                "project_path": {"type": "string", "description": "Local stdio CLI path or built-in sample ID ('2l_rp2040', '2l_stickhub', '4l_carrier')."},
            },
            "required": [],
        },
    },
    {
        "name": "calligraphy_compile_board",
        "description": (
            "Compile a PCB through Calligraphy EDA (3D HDI synthesis + Snowman teardrop pad fillets "
            "+ Zero-VIPPO DFM surgery + 3D nodal G*V=I physics) and return 0-DRC telemetry, preview crops, "
            "a single clickable Stripe Checkout URL, and watch-only per-job USDT/USDC stablecoin payment instructions. "
            "Mode A (Zero-File Demo): Pass `sample_id='2l_rp2040'` (or `'2l_stickhub'`, `'4l_carrier'`). "
            "Mode B (User's Local Board): Pass a local file path in `project_path` (stdio mode) or pass its contents in "
            "`pcb_text` + `filename` (or `upload_b64` for `.PcbDoc`/`.zip`)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "sample_id": {"type": "string", "description": "Optional built-in sample board ID ('2l_rp2040', '2l_stickhub', '4l_carrier')"},
                "pcb_text": {"type": "string", "description": "Raw CAD file contents (.kicad_pcb, .dsn, .ato, .tsx, .xml) for remote HTTP MCP calls"},
                "upload_b64": {"type": "string", "description": "Base64-encoded CAD file or .zip bundle for remote HTTP MCP calls"},
                "filename": {"type": "string", "default": "board.kicad_pcb"},
                "customer_email": {"type": "string", "default": "agent@customer.io"},
                "requested_sku": {
                    "type": "string",
                    "enum": ["vibe_micro", "basic_2l", "intro_trial", "dfm_fix", "route_3d", "premium_hs", "turnkey_full"],
                    "default": "route_3d",
                },
                "include_eco_pass": {"type": "boolean", "default": False},
                "rush_delivery": {"type": "boolean", "default": False},
                "tos_accepted": {"type": "boolean", "default": True},
                "no_itar_certified": {"type": "boolean", "default": True},
                "export_control_certified": {"type": "boolean", "default": True},
                "retention_policy": {
                    "type": "string",
                    "enum": ["auto_purge_on_download", "expire_24h"],
                    "default": "auto_purge_on_download",
                },
                "project_path": {"type": "string", "description": "Local stdio CLI path or built-in sample ID ('2l_rp2040', '2l_stickhub', '4l_carrier')."},
            },
            "required": [],
        },
    },
    {
        "name": "calligraphy_get_job_status",
        "description": (
            "Query the compilation and payment status of a Calligraphy EDA job (`job_id`). "
            "When `status` is `COMPLETED_AWAITING_PAYMENT`, returns `stablecoin_payment_instructions` "
            "with the job's unique watch-only `deposit_address` (`0x...`) for autonomous USDT/USDC checkout."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "Job ID returned by calligraphy_compile_board"},
            },
            "required": ["job_id"],
        },
    },
    {
        "name": "calligraphy_verify_stablecoin_payment",
        "description": (
            "Submit an on-chain `USDT` or `USDC` transaction hash (`tx_hash`) sent to the job's unique "
            "watch-only `deposit_address` on `base`, `arbitrum`, `polygon`, or `ethereum` to receive a "
            "private HMAC-SHA256 payment receipt (`receipt_hmac_sha256`) and immediately unlock "
            "`calligraphy_download_fab_bundle` with zero human browser intervention."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "Job ID returned by calligraphy_compile_board"},
                "tx_hash": {"type": "string", "description": "0x-prefixed 64-character hex EVM transaction hash"},
                "token": {
                    "type": "string",
                    "enum": ["USDT", "USDC"],
                    "default": "USDT",
                    "description": "Stablecoin symbol (`USDT` or `USDC`)",
                },
                "network": {
                    "type": "string",
                    "enum": ["base", "arbitrum", "polygon", "ethereum"],
                    "default": "base",
                    "description": "EVM settlement network (`base` recommended for near-zero gas & Coinbase treasury)",
                },
            },
            "required": ["job_id", "tx_hash"],
        },
    },
    {
        "name": "calligraphy_download_fab_bundle",
        "description": (
            "Download the unlocked routed .kicad_pcb and turnkey JLCPCB/PCBWay .zip bundle "
            "(Gerbers, Excellon drills, IPC-D-356, BOM, CPL, and 3D HTML5 viewer) once paid via "
            "Stripe Checkout, autonomous USDT/USDC stablecoin verification, or active 30-day board license."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "Job ID returned by calligraphy_compile_board"},
                "include_bundle_b64": {
                    "type": "boolean",
                    "default": False,
                    "description": "Set True over remote HTTP to inline the base64 .zip bytes and trigger auto-purge immediately; defaults to False so the returned download_zip_url remains active for browser/curl download.",
                },
                "output_dir": {"type": "string", "description": "Local directory to save unlocked files (stdio CLI mode)"},
            },
            "required": ["job_id"],
        },
    },
    {
        "name": "calligraphy_lookup_b2b_invoice",
        "description": (
            "Look up a Calligraphy EDA job and generate a B2B Tax Invoice & Chain-of-Custody Certificate "
            "with custom PO number and company name."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "Job ID returned by calligraphy_compile_board"},
                "customer_email": {"type": "string", "default": "agent@customer.io"},
                "po_number": {"type": "string", "default": ""},
                "company_name": {"type": "string", "default": ""},
            },
            "required": ["job_id"],
        },
    },
    {
        "name": "calligraphy_create_coinbase_checkout",
        "description": (
            "Create a 1-Click Coinbase Pay / Coinbase Onchain Payment Protocol checkout session "
            "(and x402 AI-agent payment URL) settling in USDC on Base (chain_id=8453) with automatic "
            "DEX token conversion and zero gas-dust sweeping."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["job_id"],
            "properties": {
                "job_id": {"type": "string", "description": "Job ID returned by calligraphy_compile_board."},
                "currency": {"type": "string", "default": "USDC"},
                "network": {"type": "string", "default": "base"},
            },
        },
    },
    {
        "name": "calligraphy_purge_job_vault",
        "description": (
            "Immediately shred all enclave CAD and synthesis artifacts for job_id and return a "
            "cryptographically signed CertificateOfDestruction (zero_retention_verified=True)."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["job_id"],
            "properties": {
                "job_id": {"type": "string", "description": "Job ID to shred immediately."},
            },
        },
    },
    {
        "name": "calligraphy_route_pcb",
        "description": (
            "Alias for calligraphy_compile_board: synthesize and route a PCB through Calligraphy EDA "
            "(0 opens, 0 DRC) and return Stripe, Coinbase Pay (x402), and watch-only USDT/USDC payment instructions. "
            "Mode A (Zero-File Demo): Pass `sample_id='2l_rp2040'` (or `'2l_stickhub'`, `'4l_carrier'`). "
            "Mode B (User's Local Board): Pass a local file path in `project_path` (stdio mode) or pass its contents in "
            "`pcb_text` + `filename` (or `upload_b64` for `.PcbDoc`/`.zip`)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "sample_id": {"type": "string", "description": "Optional built-in sample board ID ('2l_rp2040', '2l_stickhub', '4l_carrier')"},
                "pcb_text": {"type": "string", "description": "Raw CAD file contents (.kicad_pcb, .dsn, .ato, .tsx, .xml) for remote HTTP MCP calls"},
                "upload_b64": {"type": "string", "description": "Base64-encoded CAD file or .zip bundle for remote HTTP MCP calls"},
                "filename": {"type": "string", "default": "board.kicad_pcb"},
                "customer_email": {"type": "string", "default": "agent@customer.io"},
                "requested_sku": {
                    "type": "string",
                    "enum": ["vibe_micro", "basic_2l", "intro_trial", "dfm_fix", "route_3d", "premium_hs", "turnkey_full"],
                    "default": "route_3d",
                },
                "project_path": {"type": "string", "description": "Local stdio CLI path or built-in sample ID ('2l_rp2040', '2l_stickhub', '4l_carrier')."},
            },
            "required": [],
        },
    },
    {
        "name": "calligraphy_request_ip_whitelist",
        "description": (
            "Submit a Support Whitelist Request for an engineering team, corporate NAT IP, or PCB layout "
            "agency that needs higher daily compilation write limits (e.g. 25–100 compiles/day)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "customer_email": {"type": "string", "description": "Work or agency email address"},
                "organization_name": {"type": "string", "description": "Company or PCB layout agency name"},
                "reason": {"type": "string", "description": "Brief description of multi-board or team workflow"},
                "requested_daily_limit": {"type": "integer", "default": 25},
                "client_ip": {"type": "string", "default": "127.0.0.1"},
            },
            "required": ["customer_email", "organization_name", "reason"],
        },
    },
]


def _bridge_local_file_arguments(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """If `project_path` points to a real file on the local machine, inline it as `pcb_text` or `upload_b64`."""
    args = dict(arguments or {})
    proj_path_str = str(args.get("project_path") or "").strip()
    if proj_path_str and not args.get("pcb_text") and not args.get("upload_b64"):
        p = Path(proj_path_str).expanduser()
        if p.is_file():
            args["filename"] = p.name
            if p.suffix.lower() in TEXT_CAD_EXTENSIONS:
                args["pcb_text"] = p.read_text(encoding="utf-8", errors="replace")
            else:
                args["upload_b64"] = base64.b64encode(p.read_bytes()).decode("ascii")
            args.pop("project_path", None)
    return args


def _forward_tools_call_to_remote(req_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    tool_name = str(params.get("name") or "").strip()
    raw_args = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
    bridged_args = _bridge_local_file_arguments(raw_args)

    rpc_payload = {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": bridged_args,
        },
    }
    req = urllib.request.Request(
        REMOTE_MCP_ENDPOINT,
        data=json.dumps(rpc_payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Calligraphy-MCP-Stdio/6.2.38",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        err_msg = f"Remote MCP bridge error calling {REMOTE_MCP_ENDPOINT}: {exc}"
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [{"type": "text", "text": json.dumps({"error": err_msg})}],
                "structuredContent": {"error": err_msg},
                "isError": True,
            },
        }


def handle_jsonrpc_message(msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    req_id = msg.get("id")
    method = str(msg.get("method") or "").strip()
    params = msg.get("params") if isinstance(msg.get("params"), dict) else {}

    # Notifications (no id or notifications/*) produce no stdout output in stdio MCP
    if req_id is None or method.startswith("notifications/") or method == "initialized":
        return None

    if method == "initialize":
        client_proto = str(params.get("protocolVersion") or "2024-11-05")
        proto_ver = client_proto if client_proto in ("2025-11-05", "2025-03-26", "2024-11-05") else "2024-11-05"
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": proto_ver,
                "capabilities": {
                    "tools": {"listChanged": False},
                    "resources": {},
                    "prompts": {},
                },
                "serverInfo": {
                    "name": "@calligraphysystems/mcp",
                    "title": "Calligraphy EDA Autonomous PCB Physical Synthesis & Turnkey Foundry MCP",
                    "version": "6.2.38",
                },
                "instructions": (
                    "Phase 1 (2L & 4L PCBs) is LIVE. Mode A (Zero-File Demo): call `calligraphy_preflight_audit` "
                    "with `sample_id='2l_rp2040'` (or `'2l_stickhub'`, `'4l_carrier'`). Mode B (User's Local Board): "
                    "pass a local file path in `project_path` (stdio mode) or pass its contents in `pcb_text` + `filename` "
                    "(or `upload_b64` up to 50 MB for `.PcbDoc`/`.zip`), then call `calligraphy_compile_board`."
                ),
            },
        }

    if method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": MCP_TOOLS_SCHEMA}}

    if method == "resources/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"resources": []}}

    if method == "prompts/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"prompts": []}}

    if method == "tools/call":
        return _forward_tools_call_to_remote(req_id, params)

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def main() -> int:
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue

        if isinstance(payload, dict):
            resp = handle_jsonrpc_message(payload)
            if resp is not None:
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
