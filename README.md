# Vibe-Coding Hardware (`vibe-hardware-mcp`)

> **Turn AI-generated schematics, breadboards, and unrouted KiCad layouts (`ESP32`, `RP2040`, `Ergogen` keyboards, `tscircuit`, `atopile`) into `100.0%` routed, `0` native KiCad DRC factory `.ZIP` bundles.**
>
> - **Live Foundry Storefront:** [https://calligraphyeda.com](https://calligraphyeda.com)
> - **Live Remote Streamable-HTTP MCP Endpoint:** `https://calligraphyeda.com/api/v1/mcp`
> - **Machine-Readable LLM Index (`llms.txt`):** [https://calligraphyeda.com/llms.txt](https://calligraphyeda.com/llms.txt)
> - **Model Context Protocol (MCP) Manifest:** [https://calligraphyeda.com/.well-known/mcp.json](https://calligraphyeda.com/.well-known/mcp.json)
> - **OpenAPI 3.1 Specification:** [https://calligraphyeda.com/openapi.json](https://calligraphyeda.com/openapi.json)

---

## Visual Proof: `100.0%` Routed Copper + 3D Raytraced Boards (`0` Native KiCad DRC Errors)

| Benchmark Board | 350-DPI Routed Copper Proof (`0` DRC) | 3D Raytraced Assembly Render |
| :--- | :---: | :---: |
| **`Karabas-Nano` (2-Layer, `738` Pads, `928` Connections)**<br>`100.0%` Completion • `0` Unconnected • `0` KiCad DRC | ![Karabas-Nano 2L Copper Proof](assets/karabas_nano_2layer_738pads_0drc_copper.png) | ![Karabas-Nano 2L 3D Render](assets/karabas_nano_2layer_738pads_0drc_3d.png) |
| **`Decelerator4030` (`908` Pads, `487` Connections, Off-Axis `45°` `LQFP-100`)**<br>`100.0%` Completion • `0` Unconnected • `0` KiCad DRC | ![Decelerator4030 Copper Proof](assets/decelerator4030_908pads_0drc_copper.png) | ![Decelerator4030 3D Render](assets/decelerator4030_908pads_0drc_3d.png) |
| **`Teensy MCU Breakout` (High-Density Through-Hole + SMD)**<br>`100.0%` Completion • `0` Unconnected • `0` KiCad DRC | ![Teensy MCU Breakout Copper Proof](assets/teensy_mcu_breakout_0drc_copper.png) | ![Teensy MCU Breakout 3D Render](assets/teensy_mcu_breakout_0drc_3d.png) |

---

## Why Vibe-Coding Hardware Used to Hit a Brick Wall

With Claude Code, Cursor, Antigravity, `tscircuit`, `atopile`, and `Ergogen`, software engineers can now vibe-code firmware, schematics, and component placements in an afternoon.

Then you open the PCB router—and spend **two weeks** fighting ratsnest hairballs, blocked fine-pitch QFN/USB-C escapes, ground-pour islands, and hundreds of Design Rule Check (DRC) clearance errors.

**Calligraphy EDA ([calligraphyeda.com](https://calligraphyeda.com))** closes the final mile between software-defined hardware and JLCPCB / PCBWay fabrication:

1. **Zero Upfront Risk (`$0.00` Upload & Instant Pre-Flight DFM Audit)**:
   - Upload your unrouted `.kicad_pcb`, Specctra `.dsn`, Altium `.PcbDoc`, Autodesk EAGLE `.brd`, or IPC-2581 `.xml` board file—or click one of the **1-click sample boards** (`RP2040` `$149`, `StickHub 4-Port USB` `$295`, `STM32 RF 4-Layer` `$995`) directly on [calligraphyeda.com](https://calligraphyeda.com).
   - Inspect the **350-DPI Pre-Purchase Copper Proof Loupe** and interactive verification metrics before paying a cent.
2. **Strict `100.0%` Completion + `0` Native KiCad Copper DRC Gate**:
   - Every board is verified against its native `.kicad_pro` / `.kicad_dru` design rules using `kicad-cli pcb drc --severity-all` with fresh copper zone fills (`0` unconnected items, `0` copper DRC violations, `0.00000 mm` coordinate drift).
   - If a board does not close to **`100.0%` geometric completion and `0` copper DRC violations**, checkout is locked at **`$0.00`** (`HTTP 409 Conflict` — we never charge for partial routes).
3. **Turnkey Factory `.ZIP` Bundle**:
   - Instant unlock via **Base L2 `USDC`** (1-Click Coinbase / Web3 Wallet or scannable mobile QR with 5-second on-chain auto-detection) delivers an 18-file manufacturing archive:
     - Native routed `.kicad_pcb` / `.ses` CAD file
     - Fabrication Gerbers (`F.Cu`, `B.Cu`, inner layers, solder mask, silkscreen, `Edge.Cuts`)
     - Excellon PTH/NPTH drill files + IPC-D-356 electrical test netlist
     - Pick-and-Place CPL + BOM CSVs ready for JLCPCB / PCBWay assembly
     - Zero-install interactive 2D/3D HTML5 copper & DFM viewer + 3D Nodal Voltage-Drop & $50\,\Omega$ RF Return-Path Sign-Off Report

---

## Quick Start for Vibe Coders

### Option 1: 1-Line Claude Code CLI Setup (`MCP`)
Register the remote Streamable-HTTP MCP server in Claude Code with a single command:

```bash
claude mcp add --transport http calligraphy-eda https://calligraphyeda.com/api/v1/mcp
```

### Option 2: Cursor / Windsurf / Claude Desktop (`mcp_config.json`)
Copy [`mcp_config.json`](./mcp_config.json) into your IDE or desktop agent's MCP configuration (`.cursor/mcp.json`, `~/.codeium/windsurf/mcp_config.json`, or `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "calligraphy-eda": {
      "url": "https://calligraphyeda.com/api/v1/mcp"
    }
  }
}
```

#### Zero-File First Prompt to Test Immediately
Once connected, paste this prompt into Claude Code or Cursor—no local `.kicad_pcb` file needed:

> *"Use the calligraphy-eda MCP server to list the conquered benchmark boards and run a pre-flight quote on the 2l_rp2040 sample board"*

#### Two Remote HTTP Calling Modes
1. **Mode A (Instant Demo — Zero Local Files Required):**
   - Pass `sample_id="2l_rp2040"` (`$149` 2L RP2040 Breakout), `"2l_stickhub"` (`$295` 2L 4-Port USB Hub), or `"4l_carrier"` (`$995` 4L STM32 RF Carrier) to `calligraphy_preflight_audit` or `calligraphy_compile_board`.
2. **Mode B (Your Local `.kicad_pcb` / `.dsn` / `.ato` / `.tsx` Board):**
   - Ask Claude Code or Cursor to read your local board file from your workspace and pass its text contents in `pcb_text` + `filename` (e.g. `pcb_text="<contents of board.kicad_pcb>"`, `filename="board.kicad_pcb"`).

### Option 3: 1-Click Browser Test Drive (Zero Install)
1. Open **[https://calligraphyeda.com](https://calligraphyeda.com)**.
2. Click **`✨ 60-Second Guided Tour`** or click any of the **3 Live Test-Drive Sample Boards** (`RP2040` 2L, `StickHub` 2L, or `STM32 RF` 4L).
3. Pan around the **350-DPI Pre-Purchase Copper Microscope Loupe** to inspect pad fillets, differential pairs, and clearance corridors.

### Option 4: Terminal CLI Quote & Gallery Inspector (`calligraphy_vibe_cli.py`)
Run the included zero-dependency Python 3 script to inspect the 13-board verified torture gallery or get an instant pre-flight DFM quote on any local `.kicad_pcb` or `.dsn` file:

```bash
# Inspect our 13-board 0-DRC torture gallery from your terminal:
python3 calligraphy_vibe_cli.py --gallery

# Get a free instant pre-flight DFM audit & quote for your local board:
python3 calligraphy_vibe_cli.py --quote path/to/your_board.kicad_pcb
```

---

## Verified 13-Board Zero-DRC Benchmark Gallery

Every showcase board at [`GET https://calligraphyeda.com/api/v1/gallery`](https://calligraphyeda.com/api/v1/gallery) is closed to **`100.0%` connectivity (`0` unconnected items)** and **`0` native KiCad copper DRC violations**, including:

- **2-Layer Custom Mechanical Keyboards & MCU Breakouts**: `Custom_keyboard`, `BluePill_breakout`, `ESP32_breakout`, `FTDI_breakout`, `GameBoy_cartridge`, `Guitar_pedal`
- **Dense 2-Layer & 4-Layer Community Torture Boards**: `KiCad-Library_Teensy_test_layout` (`2,619` pads), `karabas-nano` (`907` pads), `Aleste-520EX` (`1,648` pads), `decelerator4030` (`684` pads, off-axis rotated `45°` `LQFP-100`)
- **Multi-Layer High-Speed & FPGA Reference Designs**: `oskirby_logicbone` (`8L` ECP5 FPGA), `zynq_ddr3_4l` (`4L` DDR3 byte lanes), `coldfire_fpga_4l` (`4L` dense bus routing)

---

## License

MIT License — Copyright (c) 2026 **Calligraphy Systems LLC** ([https://calligraphyeda.com](https://calligraphyeda.com)).
