# MTK AI Agent v2.1.0

Offline MediaTek device management tool with natural language support (English + Malayalam).

## Quick Start

### Standalone EXE (No Python Required)

```
MTK-AI-Agent.exe --cmd "detect device"
```

### With Python

```
python mtk_ai_single.py --cmd "detect device"
```

## Installation

### Option A: Standalone EXE

Copy `MTK-AI-Agent.exe` to any Windows PC. No Python, pip, or MTKClient installation needed.

### Option B: From Source

```bash
git clone https://github.com/bkerler/mtkclient.git
cd mtkclient
pip install pyusb pycryptodome colorama pyserial
```

## Usage

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

### Single Command Mode

```bash
MTK-AI-Agent.exe --cmd "read gpt"
MTK-AI-Agent.exe --cmd "wipe"
MTK-AI-Agent.exe --cmd "search MT6895"
```

### Connection Parameters

```bash
MTK-AI-Agent.exe --loader loader.bin --cmd "detect device"
MTK-AI-Agent.exe --preloader preloader.bin --cmd "read gpt"
MTK-AI-Agent.exe --serialport COM3 --cmd "detect device"
```

### Diagnose Errors

```bash
MTK-AI-Agent.exe --diagnose "S_DA_TIMEOUT"
```

### Detect Only

```bash
MTK-AI-Agent.exe --detect
```

## Commands

### Device

| Command | Description |
|---|---|
| `detect device` | Scan USB and identify connected MTK device |
| `device info` | Show chipset, meid, connection status |
| `diagnose` | Analyze device issues and suggest fixes |
| `diagnose error 0x7D4` | Diagnose specific error code |
| `status` | Show session context and device state |
| `devices list` | Show supported MTK devices |

### Read

| Command | Description |
|---|---|
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
|---|---|
| `write partition <name> <file>` | Flash a partition |
| `write full flash <file>` | Write full flash image |
| `write all partitions <dir>` | Flash all from directory |
| `write offset <hex> <file>` | Write at hex address |
| `flash firmware <file>` | Flash firmware image |

### Erase

| Command | Description |
|---|---|
| `erase partition <name>` | Wipe a partition |
| `erase partition <name> sectors <n>` | Erase N sectors |
| `erase sector <start>` | Erase from sector N |
| `wipe` | Wipe userdata, metadata, md_udc and cache |
| `frp` | Erase FRP partition |

### DA (DA-mode tools)

| Command | Description |
|---|---|
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
|---|---|
| `enter meta mode` | Enter factory META mode |
| `meta2` | Enter META via WDT reboot |
| `payload <file>` | Run kamakiri/DA payload |
| `stage <file>` | Stage2 via bootrom |
| `plstage <file>` | Stage2 via preloader |
| `fs mount` | Mount as FUSE filesystem |

### Advanced

| Command | Description |
|---|---|
| `unlock bootloader` | Unlock via seccfg (DANGEROUS) |
| `lock bootloader` | Lock via seccfg (DANGEROUS) |
| `reboot` | Reboot device |
| `crash` | Crash preloader (advanced) |
| `brute` | Bruteforce kamakiri (experimental) |

### Workflows

| Command | Description |
|---|---|
| `repair <issue>` | Repair dead/bootloop/unbrick |
| `start repair unbrick` | Unbrick workflow |
| `start repair unlock_bootloader` | Unlock bootloader workflow |
| `start repair backup_full` | Full backup workflow |
| `start repair factory_reset` | Factory reset workflow |

### Other

| Command | Description |
|---|---|
| `write imei <numbers>` | Repair IMEI |
| `search <topic>` | Search MTK knowledge base |
| `help` | Show all commands |
| `quit` / `exit` | Exit agent |

## Natural Language

Type commands naturally in English or Malayalam:

```
> phone detect cheyyu          → detect device
> gpt read cheyyanam           → read gpt
> unlock bootloader cheyyanam  → unlock bootloader
> bootloop aanu                → repair
> frp erase cheyyu             → frp
> userdata wipe cheyyu         → wipe
```

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

Type `YES` (exactly) to proceed. Type anything else to cancel.

## Malayalam Phrases

| Phrase | Maps to |
|---|---|
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

## License

MIT License. Based on [bkerler/mtkclient](https://github.com/bkerler/mtkclient).
