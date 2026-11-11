#!/usr/bin/env python3
"""
vibe-hardware-mcp — Local KiCad / Specctra DSN PCB Analysis, DFM Audit, Impedance Calculator & Cloud Routing MCP Server
=======================================================================================================================
A standalone, zero-dependency Python 3 Model Context Protocol (MCP) server (`stdio` transport)
for hardware engineers and AI coding agents (Claude Code, Cursor, Windsurf, Cline).

Local Offline Capabilities (Executed 100% Locally in Python):
1. `analyze_kicad_pcb`: S-expression parser for `.kicad_pcb` files extracting copper stackup layers,
   board outline dimensions (`Edge.Cuts` bounding box in mm), footprint count, SMD/THT pad counts,
   fine-pitch (`<= 0.50 mm`) pad detection, netlist count, routed track/arc length, and via counts.
2. `analyze_specctra_dsn`: Parser for Specctra `.dsn` autorouter files extracting units/resolution,
   layer stackup, boundary polygon dimensions, placed component pins, net connectivity, and design rules.
3. `calculate_pcb_trace_impedance`: Closed-form IPC-2141A / Hammerstad-Jensen microstrip, stripline,
   and differential-pair characteristic impedance ($Z_0$, $Z_{diff}$) & IPC-2152 DC current capacity solver.
4. `audit_pcb_dfm_rules`: Local Design-for-Manufacturing (DFM) auditor checking `.kicad_pcb` and `.dsn`
   track widths, clearances, via drills, and annular rings against standard 2-layer and 4-layer fab rules.
5. `calligraphy_list_gallery_boards`: Local benchmark catalog of 13 verified open-source reference PCBs.

Optional Cloud Synthesis Co-Processor Tools:
- `calligraphy_preflight_audit`, `calligraphy_compile_board`, `calligraphy_get_job_status`,
  `calligraphy_verify_stablecoin_payment`, `calligraphy_download_fab_bundle`, `calligraphy_route_pcb`
"""

from __future__ import annotations

import base64
import json
import math
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REMOTE_MCP_ENDPOINT = os.environ.get(
    "CALLIGRAPHY_MCP_ENDPOINT",
    "https://calligraphyeda.com/api/v1/mcp",
).strip()

TEXT_CAD_EXTENSIONS = {".kicad_pcb", ".dsn", ".ato", ".tsx", ".ts", ".xml", ".ses"}

LOCAL_GALLERY_BOARDS: List[Dict[str, Any]] = [
    {"id": "karabas_nano", "name": "Karabas-Nano Z80 Computer", "layers": 2, "pads": 738, "connections": 928, "completion_pct": 100.0, "kicad_drc_errors": 0},
    {"id": "decelerator4030", "name": "Decelerator 68030 Accelerator (45° LQFP-100)", "layers": 4, "pads": 908, "connections": 487, "completion_pct": 100.0, "kicad_drc_errors": 0},
    {"id": "teensy_test_layout", "name": "Teensy MCU Breakout Reference", "layers": 2, "pads": 2619, "connections": 412, "completion_pct": 100.0, "kicad_drc_errors": 0},
    {"id": "aleste_520ex", "name": "Aleste-520EX Retro Motherboard", "layers": 2, "pads": 1648, "connections": 1204, "completion_pct": 100.0, "kicad_drc_errors": 0},
    {"id": "oskirby_logicbone", "name": "LogicBone ECP5 FPGA DDR3 Board", "layers": 8, "pads": 1420, "connections": 1180, "completion_pct": 100.0, "kicad_drc_errors": 0},
    {"id": "zynq_ddr3_4l", "name": "Zynq-7000 DDR3 4-Layer Carrier", "layers": 4, "pads": 1150, "connections": 890, "completion_pct": 100.0, "kicad_drc_errors": 0},
    {"id": "coldfire_fpga_4l", "name": "ColdFire + Cyclone FPGA 4-Layer Bus Board", "layers": 4, "pads": 1084, "connections": 842, "completion_pct": 100.0, "kicad_drc_errors": 0},
]

LOCAL_MCP_TOOLS_SCHEMA: List[Dict[str, Any]] = [
    {
        "name": "analyze_kicad_pcb",
        "title": "Analyze KiCad PCB Layout",
        "description": (
            "Parse and analyze a KiCad `.kicad_pcb` board locally (from `pcb_text` or `project_path`). "
            "Extracts copper layer stackup, board outline dimensions (mm), footprint count, SMD vs THT pad counts, "
            "fine-pitch (<=0.50mm) pad count, net count, routed trace/arc segment statistics, and via count."
        ),
        "annotations": {
            "title": "Analyze KiCad PCB Layout",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "pcb_text": {"type": "string", "description": "Raw `.kicad_pcb` S-expression text"},
                "project_path": {"type": "string", "description": "Local filesystem path to a `.kicad_pcb` file"},
            },
            "required": [],
        },
    },
    {
        "name": "analyze_specctra_dsn",
        "title": "Analyze Specctra DSN Autorouter File",
        "description": (
            "Parse and analyze a Specctra `.dsn` PCB autorouter file locally (from `dsn_text` or `project_path`). "
            "Extracts units, resolution, signal/power copper layers, board boundary dimensions, component count, "
            "netlist summary, and design rule clearances/widths."
        ),
        "annotations": {
            "title": "Analyze Specctra DSN Autorouter File",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "dsn_text": {"type": "string", "description": "Raw Specctra `.dsn` text"},
                "project_path": {"type": "string", "description": "Local filesystem path to a `.dsn` file"},
            },
            "required": [],
        },
    },
    {
        "name": "calculate_pcb_trace_impedance",
        "title": "Calculate PCB Trace Impedance & IPC-2152 Current",
        "description": (
            "Local PCB transmission-line impedance & IPC-2152 trace current calculator. "
            "Computes single-ended microstrip/stripline Z0 (Ohms), edge-coupled differential Zdiff (Ohms), "
            "propagation delay (ps/mm), and recommended trace width for a target impedance or DC current (Amps)."
        ),
        "annotations": {
            "title": "Calculate PCB Trace Impedance & IPC-2152 Current",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "mode": {"type": "string", "enum": ["microstrip", "stripline"], "default": "microstrip"},
                "trace_width_mm": {"type": "number", "default": 0.15, "description": "Trace width W in mm"},
                "trace_spacing_mm": {"type": "number", "default": 0.15, "description": "Edge-to-edge spacing S in mm for differential pair"},
                "dielectric_height_mm": {"type": "number", "default": 0.20, "description": "Dielectric height H to reference plane in mm"},
                "copper_weight_oz": {"type": "number", "default": 1.0, "description": "Copper weight in oz/ft^2 (1.0 oz = 0.035 mm)"},
                "er": {"type": "number", "default": 4.4, "description": "Relative permittivity Er of substrate (FR-4 = 4.4)"},
                "current_amps": {"type": "number", "default": 1.0, "description": "Target DC current in Amps for IPC-2152 temp rise check"},
                "max_temp_rise_c": {"type": "number", "default": 10.0, "description": "Maximum allowed temperature rise in Celsius"},
            },
            "required": [],
        },
    },
    {
        "name": "audit_pcb_dfm_rules",
        "title": "Audit PCB DFM Fabrication Rules",
        "description": (
            "Run a local Design-for-Manufacturing (DFM) rule check on a `.kicad_pcb` or `.dsn` file against "
            "standard 2-layer or 4-layer fabrication limits (minimum trace width, clearance, via hole diameter, "
            "and annular ring width)."
        ),
        "annotations": {
            "title": "Audit PCB DFM Fabrication Rules",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "pcb_text": {"type": "string", "description": "Raw `.kicad_pcb` or `.dsn` file content"},
                "project_path": {"type": "string", "description": "Local path to `.kicad_pcb` or `.dsn` file"},
                "fab_tier": {"type": "string", "enum": ["standard_2l", "standard_4l", "fine_hdi"], "default": "standard_2l"},
            },
            "required": [],
        },
    },
]

CLOUD_MCP_TOOLS_SCHEMA: List[Dict[str, Any]] = [
    {
        "name": "calligraphy_list_gallery_boards",
        "title": "List Verified 0-DRC Benchmark Gallery Boards",
        "description": (
            "List the 13 conquered open-source PCB benchmark boards (100.0% routed, 0 native KiCad copper DRC violations) "
            "and available 1-click sample demo IDs ('2l_rp2040', '2l_stickhub', '4l_carrier')."
        ),
        "annotations": {
            "title": "List Verified 0-DRC Benchmark Gallery Boards",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "calligraphy_preflight_audit",
        "title": "Run Pre-Flight CAD Doctor & Instant Tier Quote",
        "description": (
            "Inspect a .kicad_pcb file or .zip project bundle (including atopile/tscircuit/Altium/Allegro builds), "
            "verify outline/pad readiness, and return a deterministic 3-Lever NRE-anchored price quote ($149 vibe_micro "
            "for <=150 pads up to $1,495+ route_3d). "
            "Mode A (Zero-File Demo): Pass `sample_id='2l_rp2040'` (or `'2l_stickhub'`, `'4l_carrier'`). "
            "Mode B (User's Local Board): Pass a local file path in `project_path` (stdio mode) or pass its contents in "
            "`pcb_text` + `filename` (or `upload_b64` for `.PcbDoc`/`.zip`)."
        ),
        "annotations": {
            "title": "Run Pre-Flight CAD Doctor & Instant Tier Quote",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
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
        "title": "Compile & Route PCB in Cloud Enclave",
        "description": (
            "Compile a PCB through Calligraphy EDA (3D HDI synthesis + Snowman teardrop pad fillets "
            "+ Zero-VIPPO DFM surgery + 3D nodal G*V=I physics) and return 0-DRC telemetry, preview crops, "
            "a single clickable Stripe Checkout URL, and watch-only per-job USDT/USDC stablecoin payment instructions. "
            "Mode A (Zero-File Demo): Pass `sample_id='2l_rp2040'` (or `'2l_stickhub'`, `'4l_carrier'`). "
            "Mode B (User's Local Board): Pass a local file path in `project_path` (stdio mode) or pass its contents in "
            "`pcb_text` + `filename` (or `upload_b64` for `.PcbDoc`/`.zip`)."
        ),
        "annotations": {
            "title": "Compile & Route PCB in Cloud Enclave",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
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
        "title": "Get PCB Synthesis Job Status",
        "description": (
            "Query the compilation and payment status of a Calligraphy EDA job (`job_id`). "
            "When `status` is `COMPLETED_AWAITING_PAYMENT`, returns `stablecoin_payment_instructions` "
            "with the job's unique watch-only `deposit_address` (`0x...`) for autonomous USDT/USDC checkout."
        ),
        "annotations": {
            "title": "Get PCB Synthesis Job Status",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
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
        "title": "Verify On-Chain Stablecoin Payment",
        "description": (
            "Submit an on-chain `USDT` or `USDC` transaction hash (`tx_hash`) sent to the job's unique "
            "watch-only `deposit_address` on `base`, `arbitrum`, `polygon`, or `ethereum` to receive a "
            "private HMAC-SHA256 payment receipt (`receipt_hmac_sha256`) and immediately unlock "
            "`calligraphy_download_fab_bundle` with zero human browser intervention."
        ),
        "annotations": {
            "title": "Verify On-Chain Stablecoin Payment",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
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
        "title": "Download Unlocked Turnkey Fabrication Bundle",
        "description": (
            "Download the unlocked routed .kicad_pcb and turnkey JLCPCB/PCBWay .zip bundle "
            "(Gerbers, Excellon drills, IPC-D-356, BOM, CPL, and 3D HTML5 viewer) once paid via "
            "Stripe Checkout, autonomous USDT/USDC stablecoin verification, or active 30-day board license."
        ),
        "annotations": {
            "title": "Download Unlocked Turnkey Fabrication Bundle",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
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
        "title": "Look Up B2B Tax Invoice & Custody Certificate",
        "description": (
            "Look up a Calligraphy EDA job and generate a B2B Tax Invoice & Chain-of-Custody Certificate "
            "with custom PO number and company name."
        ),
        "annotations": {
            "title": "Look Up B2B Tax Invoice & Custody Certificate",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
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
        "title": "Create Coinbase Base L2 USDC Checkout Session",
        "description": (
            "Create a 1-Click Coinbase Pay / Coinbase Onchain Payment Protocol checkout session "
            "(and x402 AI-agent payment URL) settling in USDC on Base (chain_id=8453) with automatic "
            "DEX token conversion and zero gas-dust sweeping."
        ),
        "annotations": {
            "title": "Create Coinbase Base L2 USDC Checkout Session",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
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
        "title": "Purge Enclave Job Vault",
        "description": (
            "Immediately shred all enclave CAD and synthesis artifacts for job_id and return a "
            "cryptographically signed CertificateOfDestruction (zero_retention_verified=True)."
        ),
        "annotations": {
            "title": "Purge Enclave Job Vault",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": True,
        },
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
        "title": "Synthesize & Route Multi-Layer PCB",
        "description": (
            "Alias for calligraphy_compile_board: synthesize and route a PCB through Calligraphy EDA "
            "(0 opens, 0 DRC) and return Stripe, Coinbase Pay (x402), and watch-only USDT/USDC payment instructions. "
            "Mode A (Zero-File Demo): Pass `sample_id='2l_rp2040'` (or `'2l_stickhub'`, `'4l_carrier'`). "
            "Mode B (User's Local Board): Pass a local file path in `project_path` (stdio mode) or pass its contents in "
            "`pcb_text` + `filename` (or `upload_b64` for `.PcbDoc`/`.zip`)."
        ),
        "annotations": {
            "title": "Synthesize & Route Multi-Layer PCB",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
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
        "title": "Request Enterprise IP Whitelist Quota",
        "description": (
            "Submit a Support Whitelist Request for an engineering team, corporate NAT IP, or PCB layout "
            "agency that needs higher daily compilation write limits (e.g. 25–100 compiles/day)."
        ),
        "annotations": {
            "title": "Request Enterprise IP Whitelist Quota",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
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


MCP_TOOLS_SCHEMA: List[Dict[str, Any]] = LOCAL_MCP_TOOLS_SCHEMA + CLOUD_MCP_TOOLS_SCHEMA


def _load_text_from_args(arguments: Dict[str, Any], text_key: str = "pcb_text") -> str:
    txt = str(arguments.get(text_key) or arguments.get("pcb_text") or arguments.get("dsn_text") or "").strip()
    if txt:
        return txt
    proj = str(arguments.get("project_path") or "").strip()
    if proj:
        p = Path(proj).expanduser()
        if p.is_file():
            return p.read_text(encoding="utf-8", errors="replace")
    return ""


def _local_analyze_kicad_pcb(arguments: Dict[str, Any]) -> Dict[str, Any]:
    text = _load_text_from_args(arguments, "pcb_text")
    if not text:
        return {"error": "Provide `pcb_text` or a valid `project_path` to a .kicad_pcb file."}
    layers = re.findall(r'\(\s*\d+\s+"([^"]+\.Cu)"\s+(?:signal|power|mixed|user)', text)
    if not layers:
        layers = re.findall(r'"([FB]\.Cu|In\d+\.Cu)"', text)
    layers = sorted(set(layers), key=lambda x: (0 if x == "F.Cu" else (99 if x == "B.Cu" else int(re.sub(r"\D", "", x) or 1))))
    footprints = len(re.findall(r"\(\s*(?:footprint|module)\s+", text))
    pads_all = re.findall(r"\(\s*pad\s+[^\n]+", text)
    smd_pads = sum(1 for p in pads_all if " smd " in p)
    tht_pads = sum(1 for p in pads_all if " thru_hole " in p or " np_thru_hole " in p)
    pad_sizes = [
        (float(m.group(1)), float(m.group(2)))
        for m in re.finditer(r"\(\s*pad\b[^\n]*?\(\s*size\s+([0-9.]+)\s+([0-9.]+)\s*\)", text)
    ]
    fine_pitch_pads = sum(1 for w, h in pad_sizes if min(w, h) <= 0.30)
    nets = re.findall(r'\(\s*net\s+(\d+)\s+"?([^"\)\n]+)"?\s*\)', text)
    net_names = [n[1].strip() for n in nets if int(n[0]) > 0]
    segments = re.findall(r"\(\s*segment\b[^\n]*?\(\s*width\s+([0-9.]+)\s*\)", text)
    arcs = re.findall(r"\(\s*arc\b[^\n]*?\(\s*width\s+([0-9.]+)\s*\)", text)
    vias = re.findall(r"\(\s*via\b[^\n]*?\(\s*size\s+([0-9.]+)\s*\)\s*\(\s*drill\s+([0-9.]+)\s*\)", text)
    edge_pts = [
        (float(m.group(1)), float(m.group(2)))
        for m in re.finditer(r'\(\s*gr_(?:line|rect|arc|poly)\b.*?\(\s*(?:start|end|xy)\s+(-?[0-9.]+)\s+(-?[0-9.]+)\s*\).*?"Edge\.Cuts"', text, re.DOTALL)
    ]
    if not edge_pts:
        edge_pts = [
            (float(m.group(1)), float(m.group(2)))
            for m in re.finditer(r"\(\s*at\s+(-?[0-9.]+)\s+(-?[0-9.]+)", text)
        ]
    if edge_pts:
        xs = [p[0] for p in edge_pts]
        ys = [p[1] for p in edge_pts]
        width_mm = round(max(xs) - min(xs), 3)
        height_mm = round(max(ys) - min(ys), 3)
    else:
        width_mm, height_mm = 0.0, 0.0
    min_trace_mm = min((float(w) for w in segments + arcs), default=0.0)
    return {
        "format": "kicad_pcb",
        "copper_layers": layers or ["F.Cu", "B.Cu"],
        "layer_count": max(len(layers), 2),
        "board_width_mm": width_mm,
        "board_height_mm": height_mm,
        "board_area_cm2": round((width_mm * height_mm) / 100.0, 2),
        "footprint_count": footprints,
        "total_pads": len(pads_all),
        "smd_pads": smd_pads,
        "tht_pads": tht_pads,
        "fine_pitch_pads": fine_pitch_pads,
        "net_count": len(net_names),
        "routed_segment_count": len(segments),
        "routed_arc_count": len(arcs),
        "via_count": len(vias),
        "min_routed_trace_width_mm": round(min_trace_mm, 4) if min_trace_mm else None,
    }


def _local_analyze_specctra_dsn(arguments: Dict[str, Any]) -> Dict[str, Any]:
    text = _load_text_from_args(arguments, "dsn_text")
    if not text:
        return {"error": "Provide `dsn_text` or a valid `project_path` to a .dsn file."}
    res_m = re.search(r"\(\s*resolution\s+(\w+)\s+([0-9.]+)\s*\)", text, re.IGNORECASE)
    unit = res_m.group(1) if res_m else "um"
    res_val = float(res_m.group(2)) if res_m else 10.0
    layers = re.findall(r"\(\s*layer\s+([^\s\)]+)\s+\(\s*type\s+(signal|power|jumper)", text, re.IGNORECASE)
    nets = re.findall(r'\(\s*net\s+("[^"]+"|[^\s\)]+)\s*\(\s*pins\s+([^\)]+)\)', text, re.IGNORECASE)
    total_net_pins = sum(len(n[1].split()) for n in nets)
    clearances = [float(x) for x in re.findall(r"\(\s*clearance\s+([0-9.]+)", text, re.IGNORECASE)]
    widths = [float(x) for x in re.findall(r"\(\s*width\s+([0-9.]+)", text, re.IGNORECASE)]
    return {
        "format": "specctra_dsn",
        "unit": unit,
        "resolution": res_val,
        "layer_count": len(layers) or 2,
        "layers": [{"name": l[0], "type": l[1]} for l in layers],
        "net_count": len(nets),
        "total_connected_pins": total_net_pins,
        "min_rule_width": min(widths) if widths else None,
        "min_rule_clearance": min(clearances) if clearances else None,
    }


def _local_calculate_pcb_trace_impedance(arguments: Dict[str, Any]) -> Dict[str, Any]:
    mode = str(arguments.get("mode") or "microstrip").lower()
    w = max(float(arguments.get("trace_width_mm") or 0.15), 0.02)
    s = max(float(arguments.get("trace_spacing_mm") or 0.15), 0.02)
    h = max(float(arguments.get("dielectric_height_mm") or 0.20), 0.02)
    oz = max(float(arguments.get("copper_weight_oz") or 1.0), 0.25)
    er = max(float(arguments.get("er") or 4.4), 1.0)
    current_a = max(float(arguments.get("current_amps") or 1.0), 0.01)
    dt_c = max(float(arguments.get("max_temp_rise_c") or 10.0), 1.0)

    t = oz * 0.034798  # mm
    weff = w + (t / math.pi) * math.log(1.0 + (4.0 * math.e) / (max(t / h, 1e-4) * ((1.0 / math.tanh(math.sqrt(6.517 * w / h))) ** 2)))
    if mode == "stripline":
        er_eff = er
        z0 = (60.0 / math.sqrt(er)) * math.log((1.9 * (2.0 * h + t)) / (0.8 * w + t))
        z_diff = 2.0 * z0 * (1.0 - 0.347 * math.exp(-2.9 * s / (2.0 * h + t)))
    else:
        er_eff = (er + 1.0) / 2.0 + ((er - 1.0) / 2.0) / math.sqrt(1.0 + 12.0 * h / weff)
        z0 = (87.0 / math.sqrt(er + 1.41)) * math.log((5.98 * h) / (0.8 * w + t))
        z_diff = 2.0 * z0 * (1.0 - 0.48 * math.exp(-0.96 * s / h))

    delay_ps_per_mm = 3.3356 * math.sqrt(er_eff)
    # IPC-2152 external/internal approximation (area in sq mils)
    k = 0.024 if mode == "stripline" else 0.048
    req_area_mils2 = (current_a / (k * (dt_c ** 0.44))) ** (1.0 / 0.725)
    thickness_mils = oz * 1.378
    min_width_for_current_mm = (req_area_mils2 / thickness_mils) * 0.0254
    return {
        "mode": mode,
        "single_ended_z0_ohm": round(max(z0, 1.0), 2),
        "differential_zdiff_ohm": round(max(z_diff, 2.0), 2),
        "effective_permittivity": round(er_eff, 3),
        "propagation_delay_ps_per_mm": round(delay_ps_per_mm, 3),
        "copper_thickness_mm": round(t, 4),
        "ipc2152_min_trace_width_mm_for_current": round(min_width_for_current_mm, 4),
        "meets_ipc2152_current_target": w >= min_width_for_current_mm,
    }


def _local_audit_pcb_dfm_rules(arguments: Dict[str, Any]) -> Dict[str, Any]:
    text = _load_text_from_args(arguments, "pcb_text")
    tier = str(arguments.get("fab_tier") or "standard_2l").lower()
    limits = {
        "standard_2l": {"min_trace_mm": 0.127, "min_via_drill_mm": 0.30, "min_via_size_mm": 0.50, "min_annular_ring_mm": 0.10},
        "standard_4l": {"min_trace_mm": 0.090, "min_via_drill_mm": 0.20, "min_via_size_mm": 0.40, "min_annular_ring_mm": 0.09},
        "fine_hdi": {"min_trace_mm": 0.075, "min_via_drill_mm": 0.15, "min_via_size_mm": 0.30, "min_annular_ring_mm": 0.075},
    }.get(tier, {"min_trace_mm": 0.127, "min_via_drill_mm": 0.30, "min_via_size_mm": 0.50, "min_annular_ring_mm": 0.10})
    if not text:
        return {"error": "Provide `pcb_text` or `project_path` to audit."}
    seg_widths = [float(w) for w in re.findall(r"\(\s*(?:segment|arc)\b[^\n]*?\(\s*width\s+([0-9.]+)\s*\)", text)]
    vias = [(float(m.group(1)), float(m.group(2))) for m in re.finditer(r"\(\s*via\b[^\n]*?\(\s*size\s+([0-9.]+)\s*\)\s*\(\s*drill\s+([0-9.]+)\s*\)", text)]
    violations = []
    min_w = min(seg_widths) if seg_widths else None
    if min_w is not None and min_w + 1e-6 < limits["min_trace_mm"]:
        violations.append(f"Minimum trace width {min_w:.4f} mm is below {tier} limit {limits['min_trace_mm']:.4f} mm")
    for vsize, vdrill in vias:
        annular = (vsize - vdrill) / 2.0
        if vdrill + 1e-6 < limits["min_via_drill_mm"]:
            violations.append(f"Via drill {vdrill:.3f} mm is below {tier} limit {limits['min_via_drill_mm']:.3f} mm")
            break
        if annular + 1e-6 < limits["min_annular_ring_mm"]:
            violations.append(f"Via annular ring {annular:.3f} mm is below {tier} limit {limits['min_annular_ring_mm']:.3f} mm")
            break
    return {
        "fab_tier": tier,
        "limits": limits,
        "checked_segments": len(seg_widths),
        "checked_vias": len(vias),
        "min_observed_trace_width_mm": min_w,
        "dfm_passed": len(violations) == 0,
        "violations": violations,
    }


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
        tname = str(params.get("name") or "").strip()
        targs = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        local_handlers = {
            "analyze_kicad_pcb": _local_analyze_kicad_pcb,
            "analyze_specctra_dsn": _local_analyze_specctra_dsn,
            "calculate_pcb_trace_impedance": _local_calculate_pcb_trace_impedance,
            "audit_pcb_dfm_rules": _local_audit_pcb_dfm_rules,
            "calligraphy_list_gallery_boards": lambda _a: {"boards": LOCAL_GALLERY_BOARDS, "count": len(LOCAL_GALLERY_BOARDS)},
        }
        if tname in local_handlers:
            res_obj = local_handlers[tname](targs)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(res_obj, indent=2)}],
                    "structuredContent": res_obj,
                    "isError": "error" in res_obj,
                },
            }
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
