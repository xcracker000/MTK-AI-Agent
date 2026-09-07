<div align="center">

# MTK AI Agent

**Offline MediaTek Device Management with Natural Language Support**

No internet. No API keys. No Ollama. Just you and your device.

**Developed by Rasheed** | [GitHub](https://github.com/xcracker000)

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows_10%2F11-lightgrey.svg)](https://github.com/xcracker000/MTK-AI-Agent)
[![Release](https://img.shields.io/badge/Release-v2.0.0-orange.svg)](https://github.com/xcracker000/MTK-AI-Agent/releases/tag/v2.0.0)
[![Tests](https://img.shields.io/badge/Tests-297%2F297-brightgreen.svg)](https://github.com/xcracker000/MTK-AI-Agent)

</div>

---

## What is MTK AI Agent?

MTK AI Agent is a **single-file, offline** MediaTek device management tool. It wraps the full [MTKClient](https://github.com/bkerler/mtkclient) CLI into a natural language interface that understands **English** and **Malayalam**.

- **58 intents** covering every MTKClient command
- **48 adapter methods** calling MTKClient Python API directly
- **No subprocess** — direct API calls, instant responses
- **Built-in safety** — dangerous operations require explicit confirmation
- **Pre-built EXE** — download and run, no Python needed

---

## Download

| File | Size | Description |
|------|------|-------------|
| [MTK-AI-Agent.exe](https://github.com/xcracker000/MTK-AI-Agent/releases/download/v2.0.0/MTK-AI-Agent.exe) | ~35 MB | Standalone EXE, no Python required |

---

## Quick Start

### Standalone EXE

```bash
MTK-AI-Agent.exe --cmd "detect device"
```

### With Python

```bash
git clone https://github.com/xcracker000/MTK-AI-Agent.git
cd MTK-AI-Agent
pip install pyusb pycryptodome colorama pyserial
python mtk_ai_single.py --cmd "detect device"
```

### Interactive Mode

```bash
MTK-AI-Agent.exe
```

Then type commands naturally:

```
> detect device
> read gpt
> wipe
> frp
> unlock bootloader
```

---

## Commands

### Device

| Command | Description |
|---------|-------------|
| `detect device` | Scan USB and identify connected MTK device |
| `device info` | Show chipset, meid, connection status |
| `devices list` | Show supported MTK devices |
| `diagnose` | Analyze device issues and suggest fixes |
| `diagnose error 0x7D4` | Diagnose specific error code |
| `status` | Show session context and device state |

### Read

| Command | Description |
|---------|-------------|
| `read gpt` | Display partition table |
| `save gpt <dir>` | Save GPT table to directory |
| `read partition <name>` | Read partition to backup file |
| `read boot` | Read boot partition |
| `read userdata` | Read userdata partition |
| `read full flash` | Full flash dump to file |
| `read offset <hex> [len]` | Read flash at hex address |
| `read sectors <count>` | Read N sectors from flash |
| `read all partitions` | Backup all partitions |
| `read footer` | Read crypto footer |
| `peek <hex>` | Read memory (patched PL mode) |
| `dump brom` | Dump bootrom |
| `dump sram` | Dump SRAM |
| `dump preloader` | Dump preloader |
| `read imei` | Read IMEI numbers |

### Write

| Command | Description |
|---------|-------------|
| `write partition <name> <file>` | Flash a partition |
| `write full flash <file>` | Write full flash image |
| `write all partitions <dir>` | Flash all from directory |
| `write offset <hex> <file>` | Write at hex address |
| `flash firmware <file>` | Flash firmware image |

### Erase

| Command | Description |
|---------|-------------|
| `erase partition <name>` | Wipe a partition |
| `erase partition <name> sectors <n>` | Erase N sectors |
| `erase sector <start>` | Erase from sector N |
| `wipe` | Wipe userdata, metadata, md_udc and cache |
| `frp` | Erase FRP partition |

### DA (DA-mode tools)

| Command | Description |
|---------|-------------|
| `generate keys` | Extract crypto keys |
| `get target config` | Read SBC/DAA config |
| `logs` | Get target logs |
| `da efuse` | Read efuses |
| `da vbmeta <mode>` | Patch vbmeta (disable/enable) |
| `da keyserver` | Start key server |
| `da meta <mode>` | DA MetaMode (off/usb/uart) |
| `da nvitem <action> <file>` | NV item decrypt/encrypt |
| `da patchmodem` | Patch modem for IMEI |
| `da rpmb read` | Read RPMB |
| `da rpmb write <file>` | Write RPMB |
| `da memdump` | Dump whole memory |
| `da memdram` | Dump DRAM memory |

### META / Payload / Stage

| Command | Description |
|---------|-------------|
| `enter meta mode` | Enter factory META mode |
| `meta2` | Enter META via WDT reboot |
| `payload <file>` | Run kamakiri/DA payload |
| `stage <file>` | Stage2 via bootrom |
| `plstage <file>` | Stage2 via preloader |
| `fs mount` | Mount as FUSE filesystem |

### Advanced

| Command | Description |
|---------|-------------|
| `unlock bootloader` | Unlock via seccfg (DANGEROUS) |
| `lock bootloader` | Lock via seccfg (DANGEROUS) |
| `reboot` | Reboot device |
| `crash` | Crash preloader (advanced) |
| `brute` | Bruteforce kamakiri (experimental) |

### Workflows

| Command | Description |
|---------|-------------|
| `repair <issue>` | Repair dead/bootloop/unbrick |
| `start repair unbrick` | Unbrick workflow |
| `start repair unlock_bootloader` | Unlock bootloader workflow |
| `start repair backup_full` | Full backup workflow |
| `start repair factory_reset` | Factory reset workflow |

### Other

| Command | Description |
|---------|-------------|
| `write imei <numbers>` | Repair IMEI |
| `search <topic>` | Search MTK knowledge base |
| `help` | Show all commands |
| `quit` / `exit` | Exit agent |

---

## Natural Language Support

Type commands naturally in English or Malayalam:

```
> phone detect cheyyu          → detect device
> gpt read cheyyanam           → read gpt
> unlock bootloader cheyyanam  → unlock bootloader
> bootloop aanu                → repair
> frp erase cheyyu             → frp
> userdata wipe cheyyu         → wipe
> full backup edukka           → read full flash
> imei vayikkuka               → read imei
```

### Malayalam Phrase Reference

| Phrase | Maps to |
|--------|---------|
| `phone detect cheyyu` | detect device |
| `gpt read cheyyanam` | read gpt |
| `unlock bootloader cheyyanam` | unlock bootloader |
| `bootloop aanu` | repair |
| `phone dead aayi` | repair |
| `frp erase cheyyu` | frp |
| `userdata wipe cheyyu` | wipe |
| `reset cheyyu` | reset device |
| `imei vayikkuka` | read imei |
| `imei repair cheyyu` | write imei |
| `diagnose cheyyu` | diagnose |
| `full backup edukka` | read full flash |

---

## Safety

Dangerous operations (`wipe`, `frp`, `unlock bootloader`, `erase partition`, etc.) require explicit confirmation:

```
WARNING: WIPE OPERATION
==================================================
The following partitions will be erased:
  - userdata
  - metadata
  - md_udc
  - cache
Type YES to continue.
==================================================
```

Type **`YES`** (exactly) to proceed. Type anything else to cancel.

---

## Connection Options

```bash
# Custom loader
MTK-AI-Agent.exe --loader loader.bin --cmd "detect device"

# Custom preloader
MTK-AI-Agent.exe --preloader preloader.bin --cmd "read gpt"

# Serial port
MTK-AI-Agent.exe --serialport COM3 --cmd "detect device"

# Diagnose specific error
MTK-AI-Agent.exe --diagnose "S_DA_TIMEOUT"

# Detect only
MTK-AI-Agent.exe --detect
```

---

## Chipset Support

| Chipset | Protocol | Mode |
|---------|----------|------|
| MT6781, MT6789, MT6855, MT6886, MT6895, MT6983, MT8985 | V6 | Preloader (use `--loader`) |
| All other MTK chipsets | Standard | BROM mode |

For V6 chipsets: Bootrom is patched. Use `--loader` option with a proper loader file. Preloader mode (no buttons pressed, just connect USB).

---

## Building from Source

### Requirements

- Python 3.8+
- PyInstaller

### Build EXE

```bash
pyinstaller --onefile --console --name MTK-AI-Agent ^
  --add-binary "mtkclient/Library/Filesystem/bin/winfsp-x64.dll;." ^
  --add-binary "mtkclient/Library/Filesystem/bin/winfsp-x86.dll;." ^
  --add-binary "mtkclient/Windows/libusb-1.0.dll;." ^
  --add-binary "mtkclient/Windows/libusb32-1.0.dll;." ^
  --hidden-import mtk_api ^
  --hidden-import mtkclient ^
  --hidden-import mtkclient.Library ^
  --hidden-import mtkclient.Library.mtk_class ^
  --hidden-import mtkclient.Library.mtk_main ^
  --hidden-import mtkclient.Library.mtk_preloader ^
  --hidden-import mtkclient.Library.pltools ^
  --hidden-import mtkclient.Library.meta ^
  --hidden-import mtkclient.Library.Port ^
  --hidden-import mtkclient.Library.error ^
  --hidden-import mtkclient.Library.DA.mtk_da_handler ^
  --hidden-import mtkclient.Library.DA.mtk_daloader ^
  --hidden-import mtkclient.Library.Connection.usblib ^
  --hidden-import mtkclient.Library.Connection.seriallib ^
  --hidden-import mtkclient.Library.Filesystem.mtkdafs ^
  --hidden-import mtkclient.Library.Partitions.gpt ^
  --hidden-import mtkclient.config.mtk_config ^
  --hidden-import mtkclient.config.payloads ^
  --hidden-import mtkclient.config.brom_config ^
  --hidden-import mtkclient.config.devicedb ^
  --hidden-import colorama ^
  --hidden-import usb ^
  --hidden-import usb.core ^
  --hidden-import usb.backend.libusb1 ^
  --hidden-import serial ^
  --noconfirm --clean ^
  mtk_ai_single.py
```

### Run Tests

```bash
python test_agent.py
```

---

## Troubleshooting

### "No device found"

1. Power off device completely
2. Hold Vol+ and Vol- buttons
3. Connect USB cable
4. Run `detect device`

### "Connection timed out"

- Try different USB cable
- Try different USB port
- Ensure device is powered off before connecting
- Try `--loader` option with custom DA file

### "mtkclient not available"

- Ensure `mtkclient/` directory is in the same folder as the script
- Install dependencies: `pip install pyusb pycryptodome colorama pyserial`

### DLL Errors (standalone EXE)

The standalone EXE bundles all required DLLs. If you see DLL errors:
- Ensure you're running `MTK-AI-Agent.exe` (not the Python script)
- The EXE is self-contained — no separate DLL installation needed

---

## Architecture

```
MTK-AI-Agent.exe
  ├── Bundled Python runtime (PyInstaller)
  ├── Bundled MTKClient library
  ├── Bundled native DLLs
  │   ├── libusb-1.0.dll (USB communication)
  │   ├── winfsp-x64.dll (FUSE filesystem)
  │   └── winfsp-x86.dll (32-bit FUSE)
  └── mtk_ai_single.py (single file, all logic)
       ├── IntentClassifier (NLP engine)
       ├── SafetyEngine (confirmation system)
       ├── MTKClientAdapter (direct API calls)
       ├── ErrorAnalyzer (error diagnosis)
       └── MTKAgent (orchestrator)
```

---

## Credits

- **Developed by [Rasheed](https://github.com/xcracker000)**
- [bkerler/mtkclient](https://github.com/bkerler/mtkclient) — Core MTKClient library
- kamakiri [xyzz]
- linecode exploit [chimera]
- heapbait exploit [chimera], creds to [R0rt1z2], [Shomy]
- Chaosmaster
- Geert-Jan Kreileman (GUI, design & fixes)
- All contributors

---

## License

MIT License. Based on [bkerler/mtkclient](https://github.com/bkerler/mtkclient).

---

<div align="center">

### Developed by Rasheed

**Download the latest release:** [MTK-AI-Agent.exe](https://github.com/xcracker000/MTK-AI-Agent/releases/download/v2.0.0/MTK-AI-Agent.exe)

</div>
