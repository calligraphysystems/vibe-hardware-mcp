"""
Comprehensive unit test suite for `vibe-hardware-mcp` (`calligraphy_mcp_stdio.py`).
Exercises all 15 declared MCP tools individually and verifies that every tool declares
explicit boolean `readOnlyHint`, `destructiveHint`, `idempotentHint`, and `openWorldHint`
annotations matching actual handler behavior.
"""

from __future__ import annotations

import io
import json
import pathlib
import unittest
from typing import Any, Dict
from unittest.mock import patch

import calligraphy_mcp_stdio as mcp_mod

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

SAMPLE_KICAD_PCB = """(kicad_pcb (version 20240108) (generator "pcbnew")
  (layers (0 "F.Cu" signal) (31 "B.Cu" signal) (44 "Edge.Cuts" user))
  (gr_rect (start 0 0) (end 50 40) (layer "Edge.Cuts") (width 0.15))
  (net 0 "") (net 1 "GND") (net 2 "+3V3") (net 3 "SPI_CLK")
  (footprint "Package_QFP:LQFP-48" (layer "F.Cu") (at 25 20)
    (pad "1" smd rect (at 0 0) (size 0.25 0.8) (layers "F.Cu") (net 1 "GND"))
    (pad "2" smd rect (at 0.5 0) (size 0.25 0.8) (layers "F.Cu") (net 2 "+3V3"))
    (pad "3" thru_hole circle (at 2.0 2.0) (size 1.2 1.2) (drill 0.6) (layers "*.Cu") (net 3 "SPI_CLK"))
  )
  (segment (start 25 20) (end 30 20) (width 0.20) (layer "F.Cu") (net 1))
  (arc (start 30 20) (mid 31 21) (end 32 22) (width 0.20) (layer "F.Cu") (net 1))
  (via (at 32 22) (size 0.60) (drill 0.30) (layers "F.Cu" "B.Cu") (net 1))
)
"""

SAMPLE_SPECCTRA_DSN = """(pcb "sensor_node.dsn"
  (parser (string_quote ") (space_in_quoted_tokens on))
  (resolution um 10)
  (unit mm)
  (structure
    (layer F.Cu (type signal))
    (layer B.Cu (type signal))
    (rule (width 150) (clearance 127))
  )
  (network
    (net "GND" (pins U1-1 U2-1 C1-2))
    (net "+3V3" (pins U1-2 C1-1))
  )
)
"""

EXPECTED_15_TOOLS = {
    "analyze_kicad_pcb": (True, False, True, False),
    "analyze_specctra_dsn": (True, False, True, False),
    "calculate_pcb_trace_impedance": (True, False, True, False),
    "audit_pcb_dfm_rules": (True, False, True, False),
    "calligraphy_list_gallery_boards": (True, False, True, True),
    "calligraphy_preflight_audit": (True, False, True, True),
    "calligraphy_compile_board": (False, False, False, True),
    "calligraphy_get_job_status": (True, False, True, True),
    "calligraphy_verify_stablecoin_payment": (False, False, True, True),
    "calligraphy_download_fab_bundle": (True, False, True, True),
    "calligraphy_lookup_b2b_invoice": (True, False, True, True),
    "calligraphy_create_coinbase_checkout": (False, False, False, True),
    "calligraphy_purge_job_vault": (False, True, True, True),
    "calligraphy_route_pcb": (False, False, False, True),
    "calligraphy_request_ip_whitelist": (False, False, False, True),
}


def _call_mcp_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    resp = mcp_mod.handle_jsonrpc_message({
        "jsonrpc": "2.0",
        "id": 99,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    })
    assert resp is not None and "result" in resp
    return resp["result"]


def _mock_remote_response(payload: Dict[str, Any]):
    body = json.dumps({
        "jsonrpc": "2.0",
        "id": 99,
        "result": {
            "content": [{"type": "text", "text": json.dumps(payload)}],
            "structuredContent": payload,
            "isError": False,
        },
    }).encode("utf-8")
    cm = io.BytesIO(body)
    cm.__enter__ = lambda *_: cm
    cm.__exit__ = lambda *_: False
    return cm


class VibeHardwareMCPTests(unittest.TestCase):
    def test_00_all_15_tools_declare_four_boolean_hints_and_server_json_parity(self) -> None:
        resp = mcp_mod.handle_jsonrpc_message({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        self.assertIsNotNone(resp)
        tools = resp["result"]["tools"]
        self.assertEqual(len(tools), 15)
        by_name = {t["name"]: t for t in tools}
        self.assertEqual(set(by_name.keys()), set(EXPECTED_15_TOOLS.keys()))

        for name, (ro, destr, idemp, open_w) in EXPECTED_15_TOOLS.items():
            ann = by_name[name].get("annotations") or {}
            self.assertTrue(str(ann.get("title") or "").strip(), f"{name} missing title")
            for hint_key, expected_val in (
                ("readOnlyHint", ro),
                ("destructiveHint", destr),
                ("idempotentHint", idemp),
                ("openWorldHint", open_w),
            ):
                val = ann.get(hint_key)
                self.assertIsInstance(val, bool, f"{name}.{hint_key} must be bool")
                self.assertEqual(val, expected_val, f"{name}.{hint_key} mismatch")

        server_json = json.loads((REPO_ROOT / "server.json").read_text(encoding="utf-8"))
        self.assertEqual(server_json["version"], "1.2.1")
        self.assertEqual(len(server_json["tools"]), 15)
        for st in server_json["tools"]:
            s_ann = st.get("annotations") or {}
            for k in ("readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint"):
                self.assertIsInstance(s_ann.get(k), bool)

    def test_01_analyze_kicad_pcb(self) -> None:
        res = _call_mcp_tool("analyze_kicad_pcb", {"pcb_text": SAMPLE_KICAD_PCB})
        self.assertFalse(res["isError"])
        data = res["structuredContent"]
        self.assertEqual(data["format"], "kicad_pcb")
        self.assertEqual(data["layer_count"], 2)
        self.assertEqual(data["total_pads"], 3)
        self.assertEqual(data["routed_segment_count"], 1)
        self.assertEqual(data["routed_arc_count"], 1)
        self.assertEqual(data["via_count"], 1)

    def test_02_analyze_specctra_dsn(self) -> None:
        res = _call_mcp_tool("analyze_specctra_dsn", {"dsn_text": SAMPLE_SPECCTRA_DSN})
        self.assertFalse(res["isError"])
        data = res["structuredContent"]
        self.assertEqual(data["format"], "specctra_dsn")
        self.assertEqual(data["layer_count"], 2)
        self.assertEqual(data["net_count"], 2)

    def test_03_calculate_pcb_trace_impedance(self) -> None:
        res = _call_mcp_tool(
            "calculate_pcb_trace_impedance",
            {"mode": "microstrip", "trace_width_mm": 0.25, "dielectric_height_mm": 0.20, "er": 4.4},
        )
        self.assertFalse(res["isError"])
        data = res["structuredContent"]
        self.assertGreater(data["single_ended_z0_ohm"], 20.0)
        self.assertGreater(data["differential_zdiff_ohm"], 40.0)

    def test_04_audit_pcb_dfm_rules(self) -> None:
        res = _call_mcp_tool("audit_pcb_dfm_rules", {"pcb_text": SAMPLE_KICAD_PCB, "fab_tier": "standard_2l"})
        self.assertFalse(res["isError"])
        self.assertTrue(res["structuredContent"]["dfm_passed"])
        self.assertEqual(res["structuredContent"]["checked_segments"], 2)
        self.assertEqual(res["structuredContent"]["checked_vias"], 1)

    def test_05_calligraphy_list_gallery_boards(self) -> None:
        res = _call_mcp_tool("calligraphy_list_gallery_boards", {})
        self.assertFalse(res["isError"])
        self.assertGreaterEqual(res["structuredContent"]["count"], 7)

    @patch("urllib.request.urlopen")
    def test_06_calligraphy_preflight_audit(self, mock_urlopen: Any) -> None:
        mock_urlopen.return_value = _mock_remote_response({"sku_id": "vibe_micro", "final_price_usd": 149.0})
        res = _call_mcp_tool("calligraphy_preflight_audit", {"sample_id": "2l_rp2040"})
        self.assertFalse(res["isError"])
        self.assertEqual(res["structuredContent"]["sku_id"], "vibe_micro")

    @patch("urllib.request.urlopen")
    def test_07_calligraphy_compile_board(self, mock_urlopen: Any) -> None:
        mock_urlopen.return_value = _mock_remote_response({"job_id": "job_01", "status": "COMPLETED_AWAITING_PAYMENT"})
        res = _call_mcp_tool("calligraphy_compile_board", {"sample_id": "2l_rp2040"})
        self.assertFalse(res["isError"])
        self.assertEqual(res["structuredContent"]["job_id"], "job_01")

    @patch("urllib.request.urlopen")
    def test_08_calligraphy_get_job_status(self, mock_urlopen: Any) -> None:
        mock_urlopen.return_value = _mock_remote_response({"job_id": "job_01", "status": "COMPLETED_AWAITING_PAYMENT"})
        res = _call_mcp_tool("calligraphy_get_job_status", {"job_id": "job_01"})
        self.assertFalse(res["isError"])
        self.assertEqual(res["structuredContent"]["status"], "COMPLETED_AWAITING_PAYMENT")

    @patch("urllib.request.urlopen")
    def test_09_calligraphy_verify_stablecoin_payment(self, mock_urlopen: Any) -> None:
        mock_urlopen.return_value = _mock_remote_response({"job_id": "job_01", "unlocked": True})
        res = _call_mcp_tool("calligraphy_verify_stablecoin_payment", {"job_id": "job_01", "tx_hash": "0x" + "a" * 64})
        self.assertFalse(res["isError"])
        self.assertTrue(res["structuredContent"]["unlocked"])

    @patch("urllib.request.urlopen")
    def test_10_calligraphy_download_fab_bundle(self, mock_urlopen: Any) -> None:
        mock_urlopen.return_value = _mock_remote_response({"job_id": "job_01", "status": "READY_FOR_DOWNLOAD"})
        res = _call_mcp_tool("calligraphy_download_fab_bundle", {"job_id": "job_01"})
        self.assertFalse(res["isError"])
        self.assertEqual(res["structuredContent"]["status"], "READY_FOR_DOWNLOAD")

    @patch("urllib.request.urlopen")
    def test_11_calligraphy_lookup_b2b_invoice(self, mock_urlopen: Any) -> None:
        mock_urlopen.return_value = _mock_remote_response({"job_id": "job_01", "invoice_number": "INV-2026-001"})
        res = _call_mcp_tool("calligraphy_lookup_b2b_invoice", {"job_id": "job_01"})
        self.assertFalse(res["isError"])
        self.assertEqual(res["structuredContent"]["invoice_number"], "INV-2026-001")

    @patch("urllib.request.urlopen")
    def test_12_calligraphy_create_coinbase_checkout(self, mock_urlopen: Any) -> None:
        mock_urlopen.return_value = _mock_remote_response({"job_id": "job_01", "network": "base"})
        res = _call_mcp_tool("calligraphy_create_coinbase_checkout", {"job_id": "job_01"})
        self.assertFalse(res["isError"])
        self.assertEqual(res["structuredContent"]["network"], "base")

    @patch("urllib.request.urlopen")
    def test_13_calligraphy_purge_job_vault(self, mock_urlopen: Any) -> None:
        mock_urlopen.return_value = _mock_remote_response({"job_id": "job_01", "zero_retention_verified": True})
        res = _call_mcp_tool("calligraphy_purge_job_vault", {"job_id": "job_01"})
        self.assertFalse(res["isError"])
        self.assertTrue(res["structuredContent"]["zero_retention_verified"])

    @patch("urllib.request.urlopen")
    def test_14_calligraphy_route_pcb(self, mock_urlopen: Any) -> None:
        mock_urlopen.return_value = _mock_remote_response({"job_id": "job_02", "status": "COMPLETED_AWAITING_PAYMENT"})
        res = _call_mcp_tool("calligraphy_route_pcb", {"sample_id": "2l_stickhub"})
        self.assertFalse(res["isError"])
        self.assertEqual(res["structuredContent"]["job_id"], "job_02")

    @patch("urllib.request.urlopen")
    def test_15_calligraphy_request_ip_whitelist(self, mock_urlopen: Any) -> None:
        mock_urlopen.return_value = _mock_remote_response({"status": "PENDING_REVIEW"})
        res = _call_mcp_tool(
            "calligraphy_request_ip_whitelist",
            {"customer_email": "eng@corp.io", "organization_name": "Corp", "reason": "CI pipeline"},
        )
        self.assertFalse(res["isError"])
        self.assertEqual(res["structuredContent"]["status"], "PENDING_REVIEW")


if __name__ == "__main__":
    unittest.main()
