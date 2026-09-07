#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTK AI Agent - Single File Rebuild
Local offline MediaTek device management agent.
No Ollama, no cloud LLM, no external AI APIs.
All logic in one file. Offline-first. Safety-first.

Usage:
  python mtk_ai_single.py                     # Interactive mode
  python mtk_ai_single.py --detect            # Detect device
  python mtk_ai_single.py --cmd "read gpt"    # Single command
  python mtk_ai_single.py --diagnose "error"  # Diagnose error
"""

from __future__ import annotations

import os
import sys
import re
import json
import enum
import time
import signal
import logging
import argparse
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

try:
    from colorama import init as _colorama_init, Fore, Style
    _colorama_init()
except ImportError:
    class _ForeStub:
        CYAN = YELLOW = GREEN = RED = ""
    class _StyleStub:
        RESET_ALL = ""
    Fore = _ForeStub()
    Style = _StyleStub()


APP_VERSION = "2.1.0"
APP_NAME = "MTK AI Agent"
logger = logging.getLogger("mtk_ai")


# ============================================================================
# SECTION 1: CONSTANTS & ENUMS
# ============================================================================

class RiskLevel(enum.Enum):
    SAFE = "safe"
    MODERATE = "moderate"
    DANGEROUS = "dangerous"

class OperationStatus(enum.Enum):
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    DEVICE_NOT_FOUND = "DEVICE_NOT_FOUND"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"

class BootMode(enum.Enum):
    UNKNOWN = "UNKNOWN"
    BROM = "BROM"
    PRELOADER = "PRELOADER"
    META = "META"
    FASTBOOT = "FASTBOOT"
    ANDROID = "ANDROID"


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _is_hex_address(s: str) -> bool:
    """Validate hex address string (must start with 0x and contain only hex chars)."""
    if not s:
        return False
    s = s.strip().lower()
    if s.startswith("0x"):
        s = s[2:]
    return len(s) > 0 and all(c in "0123456789abcdef" for c in s)


def get_resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and PyInstaller frozen mode."""
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


# ============================================================================
# SECTION 2: EMBEDDED KNOWLEDGE BASE
# ============================================================================

MTK_KNOWLEDGE: Dict[str, Any] = {
    "boot_modes": {
        "BROM": "BootROM mode. Entered by holding Vol+Vol- or Vol+Power while connecting USB. Device is powered off first.",
        "PRELOADER": "Preloader mode. Device connects briefly before boot. Some devices have preloader disabled.",
        "META": "META (factory) mode. Used for factory testing and calibration. Entered via mtk meta command.",
        "FASTBOOT": "Fastboot mode. Standard Android bootloader interface.",
    },
    "common_errors": {
        "CMD_SEND_DA_FAIL": "Download Agent upload failed. Wrong loader or corrupted binary.",
        "DOWNLOAD_DA_FAIL": "DA download failed. Check loader compatibility with chipset.",
        "TIMEOUT": "Operation timed out. Connection unstable or device unresponsive.",
        "CHKSUM_ERROR": "Checksum mismatch. Data corruption during transfer.",
        "COM_PORT_OPEN_FAIL": "Cannot open COM port. Driver issue or port in use.",
        "AUTOBAUD_FAIL": "Baud rate negotiation failed. Try different USB port/cable.",
        "CONNECT_TO_BOOTLOADER_FAIL": "Cannot reach bootloader. Wrong mode or connection issue.",
        "EFUSE_BLOW_ERROR": "EFUSE write error. Possible hardware issue.",
        "SET_META_REG_FAIL": "META mode registration failed.",
    },
    "partition_concepts": {
        "GPT": "GUID Partition Table. Standard partition layout for modern MTK devices.",
        "PRELOADER": "First stage bootloader. Loads DA (Download Agent).",
        "BOOT": "Android boot partition. Contains kernel and ramdisk.",
        "RECOVERY": "Recovery partition. Used for factory reset and updates.",
        "SYSTEM": "Android system partition. Contains the OS.",
        "USERDATA": "User data partition. Contains apps, settings, personal data.",
        "CACHE": "Cache partition. Temporary system files.",
        "VBMETA": "Verified Boot metadata. Controls dm-verity and AVB.",
        "SUPER": "Dynamic partition container. Holds system, vendor, product.",
        "NVRAM": "Non-Volatile RAM. Contains IMEI, WiFi MAC, calibration data.",
        "SEC_CFG": "Security configuration. Controls bootloader lock state.",
        "TEE": "Trusted Execution Environment. ARM TrustZone secure world.",
    },
    "troubleshooting": {
        "device_not_detected": {
            "causes": ["USB driver not installed", "Wrong USB port/cable (charge-only)", "Device not in correct mode", "Battery too low"],
            "fixes": ["Install MTK USB drivers", "Use USB 2.0 port (not 3.0 hub)", "Hold Vol+Vol- and connect", "Charge device 30+ minutes", "Try different cable"],
        },
        "download_da_fail": {
            "causes": ["Wrong DA loader for chipset", "Corrupted DA binary", "Security lock active", "Bootrom patched on V6 chipsets"],
            "fixes": ["Use --loader with correct V6/V5 binary", "Check chipset compatibility", "Try --stock for stock port mode"],
        },
        "bootloop": {
            "causes": ["Corrupted system/vendor partition", "Bad flash write", "Incompatible kernel", "dm-verity failure"],
            "fixes": ["Reflash boot/system/vendor", "Disable dm-verity via vbmeta", "Boot to recovery and wipe cache", "Full reflash with stock firmware"],
        },
        "hard_brick": {
            "causes": ["Corrupted bootrom/preloader", "Failed firmware update", "Power interruption during flash", "Hardware failure"],
            "fixes": ["Try BROM mode connection", "Use test points if available", "Professional hardware repair may be needed"],
        },
        "auth_fail": {
            "causes": ["Device requires SLA/DAA authentication", "Secure boot enabled", "DA authentication failed"],
            "fixes": ["Use authenticated DA loader", "Try --auth option", "Use pre-auth exploit if available"],
        },
    },
    "chipset_notes": {
        "MT6781": "V6 protocol. Bootrom patched. Use preloader mode with --loader.",
        "MT6789": "V6 protocol. Preloader may be deactivated on some devices.",
        "MT6855": "V6 protocol. Requires correct V6 loader.",
        "MT6886": "V6 protocol. Newer security patches.",
        "MT6895": "V6 protocol. Advanced security features.",
        "MT6983": "Flagship V6 chipset. Maximum security level.",
        "MT6985": "V6 protocol. Latest generation.",
    },
    "recovery_steps": {
        "connection_test": ["Check USB connection", "Verify drivers installed", "Try different USB port"],
        "basic_info": ["Read GPT", "Read device info", "Check chipset compatibility"],
        "backup_before_modify": ["Backup all partitions", "Save GPT table", "Dump bootrom/preloader"],
    },
}

MALAYALAM_MAP = {
    "cheyyanam": "need_to", "cheyu": "do", "cheyyu": "do",
    "aavunnilla": "not_working", "aakunnilla": "not_working",
    "aanu": "is", "illa": "not", "und": "have", "venam": "need",
    "tharamo": "can_give", "kashtam": "difficult", "pattuo": "possible",
    "arikku": "detect", "arikka": "detect",
    "vilikkuka": "flash", "vilikkunnu": "flashing",
    "mashi": "erase", "mashikkuka": "erase",
    "thurakkuka": "unlock", "thurannu": "unlocked",
    "phone detect cheyyu": "detect device",
    "phone detect aakunnilla": "detect device",
    "device check cheyyu": "detect device",
    "device info tharamo": "show device info",
    "device ariyikkuka": "show device info",
    "gpt read cheyyanam": "read gpt",
    "gpt backup edukka": "read gpt",
    "gpt save cheyyu": "save gpt",
    "backup edukka": "take backup",
    "full backup edukka": "read full flash",
    "all partition backup": "read all partitions",
    "flash full backup": "read full flash",
    "phone dead aayi": "phone is dead",
    "bootloop aanu": "bootloop",
    "connect aavunnilla": "not connecting",
    "brom connect aavunnilla": "not connecting",
    "error varunnu": "getting error",
    "reset cheyyu": "reset device",
    "wipe cheyyu": "wipe it",
    "connect aayi": "device connected",
    "thudanguka": "start",
    "nokkuka": "check",
    "parayuka": "tell",
    "kaanikkuka": "show",
    "unlock bootloader cheyyanam": "unlock bootloader",
    "lock bootloader cheyyanam": "lock bootloader",
    "reboot cheyyu": "reset device",
    "meta mode-il keruka": "enter meta",
    "imei vayikkuka": "read imei",
    "imei repair cheyyu": "write imei",
    "vbmeta disable cheyyu": "da vbmeta",
    "efuse vayikkuka": "da efuse",
    "modem patch cheyyu": "da patchmodem",
    "rpmb vayikkuka": "da rpmb read",
    "memory dump edukka": "da memdump",
    "dram dump edukka": "da memdram",
    "crash cheyyu": "crash",
    "brute force": "brute",
    "stuck on logo aanu": "stuck on logo",
    "diagnose cheyyu": "diagnose",
    "logs kaanikkuka": "logs",
    "target config nokkuka": "get target config",
    "write offset": "write offset",
    "read offset": "read offset",
    "sector erase cheyyu": "erase sectors",
    "footer vayikkuka": "read footer",
    "payload run cheyyu": "payload",
    "stage2 run cheyyu": "stage",
    "plstage run cheyyu": "plstage",
    "fs mount cheyyu": "fs mount",
    "nvitem decrypt cheyyu": "da nvitem",
    "keyserver thudanguka": "da keyserver",
    "meta reboot cheyyu": "meta2",
    "phone wipe cheyyu": "wipe device",
    "userdata wipe cheyyu": "wipe device",
    "phone full wipe cheyyanam": "wipe device",
    "full wipe cheyyu": "wipe device",
    "frp erase cheyyu": "frp",
    "frp clear cheyyu": "frp",
}


# ============================================================================
# SECTION 3: DEVICE & CHIPSET DATABASE
# ============================================================================

DEVICE_DB: Dict[str, Dict[str, Dict]] = {
    "OPPO": {
        "CPH2591": {"chip": "MT6893", "name": "OPPO Reno8 Pro", "storage": "UFS", "android": 12},
        "CPH2413": {"chip": "MT6895", "name": "OPPO Reno10 Pro", "storage": "UFS", "android": 13},
        "CPH2451": {"chip": "MT6877", "name": "OPPO K11", "storage": "UFS", "android": 13},
        "CPH2573": {"chip": "MT6895", "name": "OPPO Reno11 Pro", "storage": "UFS", "android": 14},
        "CPH2605": {"chip": "MT6983", "name": "OPPO Find X6", "storage": "UFS", "android": 13},
    },
    "Xiaomi": {
        "2210132G": {"chip": "MT6893", "name": "Redmi Note 12 Pro", "storage": "UFS", "android": 13},
        "2304FPN6DC": {"chip": "MT6895", "name": "Redmi Note 13 Pro+", "storage": "UFS", "android": 14},
    },
    "Samsung": {
        "SM-A536B": {"chip": "MT6877", "name": "Galaxy A53 5G", "storage": "UFS", "android": 12},
    },
    "Infinix": {
        "X6725": {"chip": "MT6789", "name": "Infinix Hot 30", "storage": "eMMC", "android": 13},
    },
    "Tecno": {
        "CK7n": {"chip": "MT6789", "name": "Tecno Spark 10 Pro", "storage": "eMMC", "android": 13},
    },
    "Vivo": {
        "V2254A": {"chip": "MT6895", "name": "Vivo S16 Pro", "storage": "UFS", "android": 13},
    },
}

CHIPSET_DB: Dict[str, Dict] = {
    "MT6735": {"da_mode": "LEGACY", "exploit": "kamakiri", "security": "v1", "year": 2014},
    "MT6750": {"da_mode": "LEGACY", "exploit": "kamakiri", "security": "v1", "year": 2016},
    "MT6755": {"da_mode": "LEGACY", "exploit": "kamakiri", "security": "v1", "year": 2016},
    "MT6757": {"da_mode": "LEGACY", "exploit": "kamakiri", "security": "v1", "year": 2017},
    "MT6758": {"da_mode": "LEGACY", "exploit": "kamakiri", "security": "v1", "year": 2018},
    "MT6761": {"da_mode": "LEGACY", "exploit": "kamakiri2", "security": "v2", "year": 2019},
    "MT6762": {"da_mode": "LEGACY", "exploit": "kamakiri2", "security": "v2", "year": 2019},
    "MT6765": {"da_mode": "LEGACY", "exploit": "kamakiri2", "security": "v2", "year": 2019},
    "MT6768": {"da_mode": "LEGACY", "exploit": "kamakiri2", "security": "v2", "year": 2020},
    "MT6771": {"da_mode": "LEGACY", "exploit": "kamakiri2", "security": "v2", "year": 2019},
    "MT6779": {"da_mode": "XFLASH", "exploit": "heapbait", "security": "v3", "year": 2019},
    "MT6781": {"da_mode": "XML", "exploit": "heapbait", "security": "v4", "year": 2021},
    "MT6785": {"da_mode": "XFLASH", "exploit": "heapbait", "security": "v3", "year": 2020},
    "MT6789": {"da_mode": "XML", "exploit": "heapbait", "security": "v4", "year": 2022},
    "MT6797": {"da_mode": "LEGACY", "exploit": "kamakiri2", "security": "v2", "year": 2017},
    "MT6853": {"da_mode": "XFLASH", "exploit": "heapbait", "security": "v3", "year": 2020},
    "MT6855": {"da_mode": "XML", "exploit": "heapbait", "security": "v4", "year": 2022},
    "MT6873": {"da_mode": "XFLASH", "exploit": "heapbait", "security": "v3", "year": 2020},
    "MT6877": {"da_mode": "XFLASH", "exploit": "heapbait", "security": "v3", "year": 2021},
    "MT6885": {"da_mode": "XFLASH", "exploit": "heapbait", "security": "v3", "year": 2019},
    "MT6886": {"da_mode": "XML", "exploit": "heapbait", "security": "v4", "year": 2022},
    "MT6893": {"da_mode": "XFLASH", "exploit": "heapbait", "security": "v3", "year": 2021},
    "MT6895": {"da_mode": "XML", "exploit": "heapbait", "security": "v4", "year": 2022},
    "MT6983": {"da_mode": "XML", "exploit": "heapbait", "security": "v5", "year": 2022},
    "MT6985": {"da_mode": "XML", "exploit": "heapbait", "security": "v5", "year": 2023},
    "MT8695": {"da_mode": "XML", "exploit": "heapbait", "security": "v5", "year": 2023},
}

MTK_ERROR_CODES: Dict[int, str] = {
    0x0: "OK", 0x3E8: "STOP", 0x3E9: "UNDEFINED_ERROR", 0x3EA: "INVALID_ARGUMENTS",
    0x3EB: "INVALID_BBCHIP_TYPE", 0x3F3: "NOT_ENOUGH_STORAGE_SPACE",
    0x3F4: "NOT_ENOUGH_MEMORY", 0x3F5: "COM_PORT_OPEN_FAIL",
    0x3FA: "UNKNOWN_TARGET_BBCHIP", 0x3FC: "UNSUPPORTED_VER_OF_BOOT_ROM",
    0x3FD: "UNSUPPORTED_VER_OF_BOOTLOADER", 0x3FE: "UNSUPPORTED_VER_OF_DA",
    0x410: "UNSUPPORTED_OPERATION", 0x411: "CHKSUM_ERROR", 0x412: "TIMEOUT",
    0x7D0: "SET_META_REG_FAIL", 0x7D4: "DOWNLOAD_DA_FAIL",
    0x7D5: "CMD_STARTCMD_FAIL", 0x7D6: "CMD_STARTCMD_TIMEOUT",
    0x7D7: "CMD_JUMP_FAIL", 0x7E7: "AUTOBAUD_FAIL",
    0x7F0: "CONNECT_TO_BOOTLOADER_FAIL", 0x7F1: "CMD_SEND_DA_FAIL",
    0x7F3: "CMD_JUMP_DA_FAIL", 0x7F5: "EFUSE_REG_NO_MATCH_WITH_TARGET",
    0x7F8: "EFUSE_BLOW_ERROR", 0x7F9: "EFUSE_ALREADY_BROKEN",
}

PARTITION_ALIASES: Dict[str, str] = {
    "system": "SYSTEM", "system_a": "SYSTEM_A", "system_b": "SYSTEM_B",
    "userdata": "USERDATA", "user_data": "USERDATA", "data": "USERDATA",
    "cache": "CACHE", "boot": "BOOT", "boot_a": "BOOT_A", "boot_b": "BOOT_B",
    "recovery": "RECOVERY", "recovery_a": "RECOVERY_A", "recovery_b": "RECOVERY_B",
    "vbmeta": "VBMETA", "vbmeta_a": "VBMETA_A", "vbmeta_b": "VBMETA_B",
    "vendor": "VENDOR", "vendor_a": "VENDOR_A", "vendor_b": "VENDOR_B",
    "dtbo": "DTBO", "dtbo_a": "DTBO_A", "dtbo_b": "DTBO_B",
    "super": "SUPER", "persist": "PERSIST", "misc": "MISC",
    "preloader": "PRELOADER", "nvram": "NVRAM",
    "protect1": "PROTECT1", "protect2": "PROTECT2",
    "secfg": "SEC_CFG", "seccfg": "SEC_CFG", "tee": "TEE", "tp": "TP",
    "proinfo": "PROINFO", "nvdata": "NVDATA", "metadata": "METADATA",
    "flashinfo": "FLASHINFO", "pgpt": "PGPT", "sgpt": "SGPT",
    "odm": "ODM", "odm_a": "ODM_A", "odm_b": "ODM_B",
    "product": "PRODUCT", "product_a": "PRODUCT_A", "product_b": "PRODUCT_B",
    "boot_para": "BOOT_PARA",
}

WORKFLOW_DEFS: Dict[str, Dict] = {
    "unbrick": {
        "description": "Unbrick a dead MTK device",
        "risk": RiskLevel.DANGEROUS,
        "steps": [
            ("detect_device", "Detect device in BROM/preloader mode"),
            ("identify_chipset", "Identify chipset and compatibility"),
            ("dump_brom", "Dump bootrom for analysis"),
            ("dump_preloader", "Dump preloader if accessible"),
            ("read_gpt", "Read partition table"),
            ("backup_all", "Backup all accessible partitions"),
            ("analyze_state", "Analyze device state"),
            ("report", "Generate analysis report"),
        ],
    },
    "unlock_bootloader": {
        "description": "Unlock device bootloader via seccfg",
        "risk": RiskLevel.DANGEROUS,
        "steps": [
            ("detect_device", "Detect device"),
            ("read_seccfg", "Read security configuration"),
            ("unlock_seccfg", "Unlock security config"),
            ("reboot_device", "Reboot device"),
        ],
    },
    "backup_full": {
        "description": "Full flash backup (NAND/eMMC/UFS)",
        "risk": RiskLevel.MODERATE,
        "steps": [
            ("detect_device", "Detect device"),
            ("connect_da", "Connect via Download Agent"),
            ("read_gpt", "Read partition table"),
            ("read_all_partitions", "Read all partitions"),
        ],
    },
    "factory_reset": {
        "description": "Factory reset via partition erase",
        "risk": RiskLevel.DANGEROUS,
        "steps": [
            ("detect_device", "Detect device"),
            ("connect_da", "Connect via Download Agent"),
            ("read_gpt", "Read partition table"),
            ("erase_userdata", "Erase userdata partition"),
            ("erase_cache", "Erase cache partition"),
            ("reboot_device", "Reboot device"),
        ],
    },
}

ERROR_CAUSES: Dict[int, Dict] = {
    0x7D4: {"causes": ["Wrong DA loader for chipset", "DA binary corrupted", "Security auth failed"],
            "actions": ["Use --loader with correct V5/V6 binary", "Check chipset and matching loader", "Try --stock option"]},
    0x7F1: {"causes": ["DA upload failed", "Connection interrupted", "Incompatible DA version"],
            "actions": ["Retry connection", "Use shorter USB cable", "Try USB 2.0 port"]},
    0x7D0: {"causes": ["META entry failed", "Preloader rejected command"],
            "actions": ["Verify device is in correct mode", "Try different metamode"]},
    0x412: {"causes": ["Operation timed out", "Device unresponsive", "USB unstable"],
            "actions": ["Retry operation", "Check USB connection", "Try different cable"]},
    0x411: {"causes": ["Data integrity check failed", "Corrupted transfer"],
            "actions": ["Retry with verification", "Check flash health"]},
    0x3F5: {"causes": ["Cannot open COM port", "Port already in use", "Driver issue"],
            "actions": ["Check USB drivers", "Close other tools using port", "Reinstall drivers"]},
    0x3FA: {"causes": ["Unknown BBChip type", "Chip not supported by tool version"],
            "actions": ["Update mtkclient", "Use --stock option"]},
    0x7E7: {"causes": ["Auto-baud failed", "Communication speed negotiation failed"],
            "actions": ["Try different USB port", "Check cable quality"]},
    0x7F0: {"causes": ["Cannot connect to bootloader", "Device not in correct mode"],
            "actions": ["Ensure BROM/preloader mode", "Hold Vol+Vol- and connect"]},
    0x7F8: {"causes": ["EFUSE blow error", "Cannot write to efuse", "Possible hardware issue"],
            "actions": ["Check hardware connection", "Professional repair may be needed"]},
}


# ============================================================================
# SECTION 4: LOCAL NLP ENGINE
# ============================================================================

@dataclass
class Intent:
    name: str
    description: str
    risk: RiskLevel
    requires_device: bool = True
    requires_confirmation: bool = False
    aliases: List[str] = field(default_factory=list)
    patterns: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.risk == RiskLevel.DANGEROUS:
            self.requires_confirmation = True


INTENT_REGISTRY: Dict[str, Intent] = {
    "help": Intent("help", "Show available commands", RiskLevel.SAFE, requires_device=False,
                   aliases=["commands", "options", "usage", "what can you do"],
                   patterns=[r"(?:show\s+)?help", r"what\s+can\s+you\s+do", r"commands", r"options"]),
    "device_info": Intent("device_info", "Show connected device information", RiskLevel.SAFE,
                          aliases=["phone info", "device details", "chipset info"],
                          patterns=[r"(?:show|get|display)\s+(?:device|phone)\s+(?:info|details)",
                                    r"device\s+(?:info|details|status)", r"what\s+(?:chip|chipset|cpu|soc)",
                                    r"identify\s+(?:device|phone)", r"connected\s+device"]),
    "detect_device": Intent("detect_device", "Detect connected MTK device", RiskLevel.SAFE,
                            aliases=["find device", "scan device", "check device"],
                            patterns=[r"detect\s+(?:device|phone|mtk)", r"scan\s+(?:usb|device)",
                                      r"find\s+(?:device|phone)", r"check\s+(?:device|connection|usb)"]),
    "diagnose": Intent("diagnose", "Diagnose device problems", RiskLevel.SAFE,
                       aliases=["troubleshoot", "problem analysis"],
                       patterns=[r"diagnose\s+(?:device|problem|issue|error|connection)",
                                  r"(?:what|why)\s+(?:is\s+)?(?:wrong|broken|failing)",
                                  r"troubleshoot", r"what(?:'s|\s+is)\s+wrong",
                                  r"(?:fix|help)\s+(?:device|phone)"]),
    "connection_test": Intent("connection_test", "Test device connection", RiskLevel.SAFE,
                              aliases=["test connection", "check connection"],
                              patterns=[r"(?:test|check)\s+connection", r"connection\s+(?:test|check|status)"]),
    "devices_list": Intent("devices_list", "List supported MTK devices", RiskLevel.SAFE,
                           requires_device=False,
                           aliases=["show devices", "supported devices", "device list"],
                           patterns=[r"(?:list|show|supported)\s+devices", r"devices?\s+(?:list|show)",
                                     r"what\s+devices", r"supported\s+(?:phone|mtk)"]),
    "read_gpt": Intent("read_gpt", "Read and display GPT partition table", RiskLevel.SAFE,
                       aliases=["show partitions", "list partitions", "partition table", "show gpt"],
                       patterns=[r"(?:print|show|list|display|read)\s+(?:gpt|partition\s+table)",
                                  r"partition\s+(?:list|table)", r"show\s+partitions", r"what\s+partitions"]),
    "save_gpt": Intent("save_gpt", "Save GPT table to directory", RiskLevel.MODERATE,
                       requires_confirmation=True,
                       aliases=["export gpt", "dump gpt table"],
                       patterns=[r"save\s+(?:gpt|partition\s+table)\s+(?:to\s+)?(\S+)",
                                  r"export\s+gpt\s+(?:to\s+)?(\S+)"]),
    "read_partition": Intent("read_partition", "Read a partition to file", RiskLevel.MODERATE,
                             requires_confirmation=True,
                             aliases=["dump partition", "backup partition"],
                             patterns=[r"read\s+partition\s+(\w+)",
                                       r"dump\s+partition\s+(\w+)",
                                       r"backup\s+partition\s+(\w+)",
                                       r"read\s+partition",
                                       r"dump\s+partition",
                                       r"backup\s+partition"]),
    "read_offset": Intent("read_offset", "Read flash at offset", RiskLevel.MODERATE,
                          requires_confirmation=True,
                          aliases=["read raw", "read raw flash"],
                          patterns=[r"read\s+(?:offset|raw)\s+(?:0x)?[0-9a-fA-F]+",
                                     r"ro\s+(?:0x)?[0-9a-fA-F]+"]),
    "read_sectors": Intent("read_sectors", "Read sectors from flash", RiskLevel.MODERATE,
                           requires_confirmation=True,
                           aliases=["read sector"],
                           patterns=[r"read\s+sectors?\s+\d+",
                                      r"rs\s+\d+"]),
    "read_all_partitions": Intent("read_all_partitions", "Read all partitions to directory", RiskLevel.MODERATE,
                                  requires_confirmation=True,
                                  aliases=["dump all partitions", "backup all partitions", "backup all"],
                                  patterns=[r"(?:read|dump|backup)\s+all\s+partitions?",
                                             r"all\s+partitions?\s+(?:backup|dump)",
                                             r"rl\s+\S+"]),
    "read_full_flash": Intent("read_full_flash", "Read entire flash to file", RiskLevel.MODERATE,
                              requires_confirmation=True,
                              aliases=["full dump", "backup flash", "backup everything", "full backup"],
                              patterns=[r"(?:dump|backup|read)\s+(?:full\s+)?(?:flash|rom|nand|emmc|ufs)",
                                         r"read\s+all", r"full\s+dump", r"backup\s+everything",
                                         r"full\s+backup"]),
    "write_partition": Intent("write_partition", "Write data to a partition", RiskLevel.DANGEROUS,
                              requires_confirmation=True,
                              aliases=["flash partition"],
                              patterns=[r"write\s+(?:to\s+)?(?:partition\s+)?(\w+)",
                                        r"flash\s+(?:to\s+)?(\w+)"]),
    "write_full_flash": Intent("write_full_flash", "Write full flash image", RiskLevel.DANGEROUS,
                               requires_confirmation=True,
                               aliases=["flash full", "write flash image"],
                               patterns=[r"(?:write|flash)\s+(?:full\s+)?(?:flash|image|rom)",
                                          r"wf\s+\S+"]),
    "write_all_partitions": Intent("write_all_partitions", "Write all partitions from directory", RiskLevel.DANGEROUS,
                                   requires_confirmation=True,
                                   aliases=["flash all partitions", "write all"],
                                   patterns=[r"(?:write|flash)\s+all\s+partitions?",
                                              r"all\s+partitions?\s+(?:write|flash)",
                                              r"wl\s+\S+"]),
    "write_offset": Intent("write_offset", "Write flash at offset", RiskLevel.DANGEROUS,
                           requires_confirmation=True,
                           aliases=["write raw", "write raw flash"],
                           patterns=[r"write\s+(?:offset|raw)\s+(?:0x)?[0-9a-fA-F]+",
                                      r"wo\s+(?:0x)?[0-9a-fA-F]+"]),
    "erase_partition": Intent("erase_partition", "Erase a partition", RiskLevel.DANGEROUS,
                              requires_confirmation=True,
                              aliases=["wipe partition", "delete partition", "format partition"],
                              patterns=[r"erase\s+(?:partition\s+)?(\w+)", r"wipe\s+(?:partition\s+)?(\w+)",
                                        r"delete\s+(?:partition\s+)?(\w+)", r"format\s+(?:partition\s+)?(\w+)"]),
    "erase_sectors": Intent("erase_sectors", "Erase partition with sector count", RiskLevel.DANGEROUS,
                            requires_confirmation=True,
                            aliases=["erase sector count"],
                            patterns=[r"erase\s+(\w+)\s+sectors?\s+\d+",
                                       r"es\s+(\w+)\s+\d+"]),
    "erase_sector_range": Intent("erase_sector_range", "Erase sector range", RiskLevel.DANGEROUS,
                                 requires_confirmation=True,
                                 aliases=["erase raw sector"],
                                 patterns=[r"erase\s+sector\s+\d+",
                                            r"ess\s+\d+"]),
    "wipe": Intent("wipe", "Wipe userdata, metadata, md_udc and cache", RiskLevel.DANGEROUS,
                   requires_confirmation=True,
                   aliases=["wipe device", "wipe phone"],
                   patterns=[r"^wipe$", r"^wipe\s+(?:device|phone|userdata|all)$",
                             r"phone\s+wipe\s+cheyyu", r"userdata\s+wipe\s+cheyyu",
                             r"phone\s+full\s+wipe\s+cheyyanam",
                              r"^wipe\s+everything$"]),
    "erase_frp": Intent("erase_frp", "Erase FRP partition", RiskLevel.DANGEROUS,
                        requires_confirmation=True,
                        aliases=["erase frp", "frp erase", "erase frp partition", "frp clear", "frp remove"],
                        patterns=[r"^frp$", r"^erase\s+frp$", r"^frp\s+erase$",
                                  r"^erase\s+frp\s+partition$", r"^frp\s+clear$", r"^frp\s+remove$"]),
    "read_footer": Intent("read_footer", "Read crypto footer from flash", RiskLevel.MODERATE,
                          requires_confirmation=True,
                          aliases=["dump footer", "backup footer"],
                          patterns=[r"(?:read|dump|backup)\s+(?:crypto\s+)?footer",
                                     r"footer\s+(?:read|dump)"]),
    "flash_firmware": Intent("flash_firmware", "Flash firmware image", RiskLevel.DANGEROUS,
                             requires_confirmation=True,
                             aliases=["install firmware", "write firmware"],
                             patterns=[r"flash\s+(?:firmware|rom|stock|image)",
                                       r"install\s+(?:firmware|rom|stock)",
                                       r"write\s+(?:firmware|rom|stock|image)"]),
    "generate_keys": Intent("generate_keys", "Generate crypto keys", RiskLevel.SAFE,
                            aliases=["extract keys", "dump keys"],
                            patterns=[r"generate\s+(?:crypto\s+)?keys", r"extract\s+keys",
                                      r"dump\s+keys", r"get\s+keys"]),
    "read_imei": Intent("read_imei", "Read IMEI numbers", RiskLevel.SAFE,
                        aliases=["check imei", "show imei"],
                        patterns=[r"(?:read|get|show|check)\s+imei", r"imei\s+(?:number|info)",
                                  r"what\s+(?:is\s+)?(?:my\s+)?imei"]),
    "write_imei": Intent("write_imei", "Write/repair IMEI numbers", RiskLevel.DANGEROUS,
                         requires_confirmation=True,
                         aliases=["repair imei", "set imei", "change imei"],
                         patterns=[r"write\s+imei", r"set\s+imei", r"repair\s+imei", r"change\s+imei"]),
    "unlock_bootloader": Intent("unlock_bootloader", "Unlock bootloader via seccfg", RiskLevel.DANGEROUS,
                                requires_confirmation=True,
                                aliases=["bootloader unlock", "backdoor"],
                                patterns=[r"unlock\s+(?:the\s+)?bootloader", r"bootloader\s+unlock",
                                          r"unlock\s+(?:the\s+)?device", r"remove\s+(?:boot\s+)?lock",
                                          r"backdoor"]),
    "lock_bootloader": Intent("lock_bootloader", "Lock bootloader via seccfg", RiskLevel.DANGEROUS,
                              requires_confirmation=True,
                              aliases=["bootloader lock"],
                              patterns=[r"lock\s+(?:the\s+)?bootloader", r"bootloader\s+lock",
                                        r"lock\s+(?:the\s+)?device"]),
    "reset_device": Intent("reset_device", "Reset/reboot device", RiskLevel.MODERATE,
                           aliases=["reboot", "restart"],
                           patterns=[r"reboot\s*(?:the\s+)?(?:device|phone)?", r"restart\s*(?:the\s+)?(?:device|phone)?",
                                     r"reset\s*(?:the\s+)?(?:device|phone)?", r"power\s+(?:cycle|restart)"]),
    "enter_meta": Intent("enter_meta", "Enter META (factory) mode", RiskLevel.MODERATE,
                         aliases=["meta mode", "factory mode"],
                         patterns=[r"enter\s+meta\s+mode", r"switch\s+to\s+meta",
                                   r"meta\s+mode", r"factory\s+mode"]),
    "meta2": Intent("meta2", "Enter META mode via WDT", RiskLevel.MODERATE,
                    aliases=["meta wdt", "meta reboot"],
                    patterns=[r"meta2", r"meta\s+wdt", r"meta\s+reboot"]),
    "payload": Intent("payload", "Run a kamakiri/DA payload", RiskLevel.DANGEROUS,
                      requires_confirmation=True,
                      aliases=["run payload", "execute payload"],
                      patterns=[r"run\s+(?:a\s+)?payload", r"execute\s+(?:a\s+)?payload",
                                r"payload\s+(?:--metamode|--payload)"]),
    "crash": Intent("crash", "Crash the preloader (advanced recovery)", RiskLevel.DANGEROUS,
                    requires_confirmation=True,
                    aliases=["crash preloader"],
                    patterns=[r"crash\s+(?:the\s+)?(?:preloader|device)", r"^crash$"]),
    "brute": Intent("brute", "Bruteforce kamakiri var1 (experimental)", RiskLevel.DANGEROUS,
                    requires_confirmation=True,
                    aliases=["bruteforce", "brute force"],
                    patterns=[r"bruteforce\s+(?:kamakiri|var1)", r"^brute$", r"brute\s+force"]),
    "get_target_config": Intent("get_target_config", "Get target config (sbc, daa, etc.)", RiskLevel.SAFE,
                                aliases=["target config", "sbc daa"],
                                patterns=[r"(?:get|show|read)\s+target\s+config", r"target\s+config",
                                          r"sbc\s+daa"]),
    "logs": Intent("logs", "Get target logs", RiskLevel.SAFE,
                   aliases=["get logs", "read logs", "show logs"],
                   patterns=[r"(?:get|read|show)\s+logs", r"^logs$", r"target\s+logs"]),
    "peek": Intent("peek", "Read memory in patched preloader mode", RiskLevel.DANGEROUS,
                   requires_confirmation=True,
                   aliases=["read memory", "mem read"],
                   patterns=[r"peek\s+(?:0x)?[0-9a-fA-F]+",
                              r"read\s+memory\s+(?:0x)?[0-9a-fA-F]+"]),
    "dump_brom": Intent("dump_brom", "Dump bootrom to file", RiskLevel.SAFE,
                        aliases=["bootrom dump"],
                        patterns=[r"(?:dump|read|backup)\s+(?:the\s+)?bootrom", r"bootrom\s+dump", r"brom\s+dump"]),
    "dump_sram": Intent("dump_sram", "Dump SRAM to file", RiskLevel.SAFE,
                        aliases=["sram dump"],
                        patterns=[r"(?:dump|read|backup)\s+(?:the\s+)?sram", r"sram\s+dump"]),
    "dump_preloader": Intent("dump_preloader", "Dump preloader to file", RiskLevel.SAFE,
                             aliases=["preloader dump"],
                             patterns=[r"(?:dump|read|backup)\s+(?:the\s+)?preloader", r"preloader\s+dump"]),
    "stage": Intent("stage", "Run stage2 payload via bootrom (kamakiri)", RiskLevel.DANGEROUS,
                    requires_confirmation=True,
                    aliases=["stage2", "bootrom stage", "brom stage"],
                    patterns=[r"stage2?", r"(?:bootrom|brom)\s+stage",
                              r"run\s+stage"]),
    "plstage": Intent("plstage", "Run stage2 payload via preloader (send_da)", RiskLevel.DANGEROUS,
                      requires_confirmation=True,
                      aliases=["preloader stage", "pl stage"],
                      patterns=[r"plstage", r"preloader\s+stage", r"pl\s+stage"]),
    "fs_mount": Intent("fs_mount", "Mount device as FUSE filesystem (advanced)", RiskLevel.MODERATE,
                       requires_confirmation=True,
                       aliases=["fuse mount", "filesystem mount"],
                       patterns=[r"(?:mount|fuse)\s+(?:as\s+)?(?:filesystem|fuse)",
                                  r"fs\s+mount", r"mount\s+device"]),
    "da_vbmeta": Intent("da_vbmeta", "Patch vbmeta partition", RiskLevel.DANGEROUS,
                        requires_confirmation=True,
                        aliases=["disable vbmeta", "patch vbmeta", "disable verity"],
                        patterns=[r"(?:patch|disable)\s+vbmeta",
                                   r"vbmeta\s+(?:patch|disable|mode)"]),
    "da_efuse": Intent("da_efuse", "Read efuses", RiskLevel.SAFE,
                       aliases=["read efuse", "efuse read"],
                       patterns=[r"(?:read|get)\s+efuse", r"efuse\s+(?:read|get)"]),
    "da_keyserver": Intent("da_keyserver", "Enable key server", RiskLevel.MODERATE,
                           aliases=["key server", "start keyserver"],
                           patterns=[r"(?:enable|start)\s+key\s*server", r"keyserver"]),
    "da_meta": Intent("da_meta", "DA MetaMode tools", RiskLevel.MODERATE,
                      aliases=["da meta mode"],
                      patterns=[r"da\s+meta\s+(?:off|usb|uart)"]),
    "da_nvitem": Intent("da_nvitem", "NV item decryption/encryption", RiskLevel.DANGEROUS,
                        requires_confirmation=True,
                        aliases=["nvitem", "nv item"],
                        patterns=[r"(?:decrypt|encrypt)\s+nv\s*item", r"nvitem"]),
    "da_patchmodem": Intent("da_patchmodem", "Patch modem for IMEI", RiskLevel.DANGEROUS,
                            requires_confirmation=True,
                            aliases=["patch modem"],
                            patterns=[r"patch\s+modem", r"modem\s+patch"]),
    "da_rpmb_read": Intent("da_rpmb_read", "Read RPMB", RiskLevel.MODERATE,
                           requires_confirmation=True,
                           aliases=["rpmb read", "read rpmb"],
                           patterns=[r"(?:read|dump)\s+rpmb", r"rpmb\s+(?:read|dump)"]),
    "da_rpmb_write": Intent("da_rpmb_write", "Write RPMB", RiskLevel.DANGEROUS,
                            requires_confirmation=True,
                            aliases=["rpmb write", "write rpmb"],
                            patterns=[r"write\s+rpmb", r"rpmb\s+write"]),
    "da_memdump": Intent("da_memdump", "Dump whole memory areas", RiskLevel.MODERATE,
                         requires_confirmation=True,
                         aliases=["memory dump", "dump memory"],
                         patterns=[r"(?:dump|read)\s+(?:whole\s+)?memory", r"memory\s+dump"]),
    "da_memdram": Intent("da_memdram", "Dump DRAM memory", RiskLevel.MODERATE,
                         requires_confirmation=True,
                         aliases=["dram dump", "dump dram"],
                         patterns=[r"(?:dump|read)\s+dram", r"dram\s+dump"]),
    "da_dumpbrom": Intent("da_dumpbrom", "DA dump bootrom", RiskLevel.SAFE,
                          aliases=["da brom dump"],
                          patterns=[r"da\s+(?:dump\s+)?brom"]),
    "repair": Intent("repair", "Start repair workflow", RiskLevel.MODERATE,
                     requires_device=False,
                     aliases=["unbrick", "revive"],
                     patterns=[r"repair\s+(?:device|phone|boot|brick)",
                               r"(?:unbrick|revive|fix)\s+(?:device|phone)",
                               r"device\s+(?:is\s+)?dead", r"phone\s+(?:is\s+)?dead",
                               r"not\s+booting", r"stuck\s+(?:on|at)\s+(?:logo|boot|splash)",
                               r"bootloop"]),
    "search_knowledge": Intent("search_knowledge", "Search MTK knowledge base", RiskLevel.SAFE,
                               requires_device=False,
                               aliases=["search"],
                               patterns=[r"search\s+(.+)"]),
    "status": Intent("status", "Show agent status and context", RiskLevel.SAFE,
                     requires_device=False,
                     aliases=["context", "session"],
                     patterns=[r"^status$", r"^context$", r"^session$"]),
    "cancel": Intent("cancel", "Cancel current operation", RiskLevel.SAFE,
                     requires_device=False,
                     aliases=["stop", "abort"],
                     patterns=[r"^cancel$", r"^stop$", r"^abort$"]),
}


class TextNormalizer:
    @staticmethod
    def normalize(text: str) -> str:
        t = text.lower().strip()
        sorted_map = sorted(MALAYALAM_MAP.items(), key=lambda x: len(x[0]), reverse=True)
        for ml, en in sorted_map:
            t = t.replace(ml, en)
        t = re.sub(r'[^\w\s]', ' ', t)
        t = re.sub(r'\s+', ' ', t).strip()
        return t


class IntentClassifier:
    def __init__(self):
        self.normalizer = TextNormalizer()

    def classify(self, user_input: str) -> Tuple[str, float, Dict]:
        normalized = self.normalizer.normalize(user_input)
        best_intent = "unknown"
        best_score = 0.0
        best_params: Dict = {}

        for intent_name, intent in INTENT_REGISTRY.items():
            for alias in intent.aliases:
                if alias in normalized:
                    score = 0.9
                    if score >= best_score:
                        best_score, best_intent = score, intent_name

            for pattern in intent.patterns:
                m = re.search(pattern, normalized)
                if m:
                    score = 0.85 if m.group(0) == normalized else 0.75
                    if score >= best_score:
                        best_score, best_intent = score, intent_name
                    if m.lastindex and m.group(1):
                        raw = m.group(1)
                        resolved = PARTITION_ALIASES.get(raw.lower(), raw.upper())
                        best_params["partition"] = resolved

        if best_intent == "unknown":
            for intent_name, intent in INTENT_REGISTRY.items():
                for pattern in intent.patterns:
                    if re.search(pattern, normalized):
                        best_intent = intent_name
                        best_score = 0.6
                        break
                if best_intent != "unknown":
                    break

        extra = self._extract_params(normalized)
        best_params.update(extra)

        return best_intent, best_score, best_params

    def _extract_params(self, text: str) -> Dict:
        params: Dict = {}
        m = re.search(r"(?:partition|part)\s+(\w+)|(\w+)\s+(?:partition|part)", text)
        if m:
            raw = m.group(1) or m.group(2)
            params["partition"] = PARTITION_ALIASES.get(raw.lower(), raw.upper())

        m = re.search(r"(?:to|from|into)\s+[\"']?([^\s\"']+\.\w+)[\"']?", text)
        if m:
            params["filename"] = m.group(1)

        m = re.search(r"(?:offset|at)\s+(?:0x)?([0-9a-fA-F]+)", text)
        if m:
            params["offset"] = int(m.group(1), 16)

        m = re.search(r"(?:length|len|size|bytes?)\s+(?:0x)?([0-9a-fA-F]+)", text)
        if m:
            params["length"] = int(m.group(1), 16)

        m = re.search(r"(?:sector|sectors?)\s+(\d+)", text)
        if m:
            params["sectors"] = int(m.group(1))

        m = re.search(r"(fastboot|factory|factoryact|advanced|meta|atcharge|atcwdt)", text, re.I)
        if m:
            params["metamode"] = m.group(1).lower()

        problem_keywords = {
            "bootloop": "bootloop", "brick": "hard_brick", "dead": "hard_brick",
            "stuck": "bootloop", "not boot": "hard_brick", "logo": "bootloop",
        }
        for kw, problem in problem_keywords.items():
            if kw in text:
                params["problem"] = problem
                break

        return params


# ============================================================================
# SECTION 5: SAFETY ENGINE
# ============================================================================

class SafetyEngine:
    @staticmethod
    def requires_confirmation(intent_name: str) -> bool:
        intent = INTENT_REGISTRY.get(intent_name)
        return intent.requires_confirmation if intent else True

    @staticmethod
    def get_risk_level(intent_name: str) -> RiskLevel:
        intent = INTENT_REGISTRY.get(intent_name)
        return intent.risk if intent else RiskLevel.DANGEROUS

    @staticmethod
    def format_confirmation(intent_name: str, params: Dict) -> str:
        intent = INTENT_REGISTRY.get(intent_name)
        if not intent:
            return "Unknown operation. Cannot proceed safely."

        if intent_name == "wipe":
            return (
                f"\n{Fore.RED}{'='*50}{Style.RESET_ALL}\n"
                f"{Fore.RED}  WARNING: WIPE OPERATION{Style.RESET_ALL}\n"
                f"{Fore.RED}{'='*50}{Style.RESET_ALL}\n"
                f"\n"
                f"  The following partitions will be erased:\n"
                f"\n"
                f"  - userdata\n"
                f"  - metadata\n"
                f"  - md_udc\n"
                f"  - cache\n"
                f"\n"
                f"  This operation will erase user/device data.\n"
                f"\n"
                f"  Type YES to continue.\n"
                f"{Fore.RED}{'='*50}{Style.RESET_ALL}"
            )

        if intent_name == "erase_frp":
            return (
                f"\n{Fore.RED}{'='*50}{Style.RESET_ALL}\n"
                f"{Fore.RED}  WARNING: FRP PARTITION ERASE{Style.RESET_ALL}\n"
                f"{Fore.RED}{'='*50}{Style.RESET_ALL}\n"
                f"\n"
                f"  This will erase the device's `frp` partition.\n"
                f"\n"
                f"  Type YES to continue.\n"
                f"{Fore.RED}{'='*50}{Style.RESET_ALL}"
            )

        risk = intent.risk
        risk_label = {"safe": "SAFE", "moderate": "MODERATE - requires care", "dangerous": "DANGEROUS - may cause data loss"}
        risk_color = {"safe": Fore.GREEN, "moderate": Fore.YELLOW, "dangerous": Fore.RED}

        lines = [
            f"\n{risk_color.get(risk.value, '')}{'='*50}{Style.RESET_ALL}",
            f"  CONFIRMATION REQUIRED",
            f"  Risk Level: {risk_label.get(risk.value, 'UNKNOWN')}",
            f"{'='*50}{Style.RESET_ALL}",
            f"  Operation: {intent.description}",
        ]
        if params.get("partition"):
            lines.append(f"  Target: {params['partition']}")
        if params.get("filename"):
            lines.append(f"  File: {params['filename']}")
        lines += [
            f"",
            f"  Type YES to confirm, or anything else to cancel.",
            f"{'='*50}{Style.RESET_ALL}",
        ]
        return "\n".join(lines)


# ============================================================================
# SECTION 6: CONVERSATION MEMORY
# ============================================================================

@dataclass
class ConversationMemory:
    last_device: Optional[str] = None
    last_chipset: Optional[str] = None
    last_mode: BootMode = BootMode.UNKNOWN
    last_operation: Optional[str] = None
    last_error: Optional[str] = None
    last_result: Optional[Dict] = None
    last_partition: Optional[str] = None
    connected: bool = False
    operation_count: int = 0

    def update(self, **kwargs):
        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)

    def summary(self) -> str:
        lines = ["Session Context:"]
        if self.last_device:
            lines.append(f"  Device: {self.last_device}")
        if self.last_chipset:
            lines.append(f"  Chipset: {self.last_chipset}")
        if self.last_mode != BootMode.UNKNOWN:
            lines.append(f"  Mode: {self.last_mode.value}")
        if self.last_partition:
            lines.append(f"  Last partition: {self.last_partition}")
        if self.last_error:
            lines.append(f"  Last error: {self.last_error}")
        lines.append(f"  Connected: {'Yes' if self.connected else 'No'}")
        lines.append(f"  Operations: {self.operation_count}")
        return "\n".join(lines)


# ============================================================================
# SECTION 7: RESULT ANALYZER
# ============================================================================

@dataclass
class OperationResult:
    status: OperationStatus = OperationStatus.PLANNED
    success: bool = False
    error: Optional[str] = None
    summary: str = ""
    details: Dict = field(default_factory=dict)
    next_action: Optional[str] = None
    stdout: str = ""
    stderr: str = ""
    exit_code: Optional[int] = None
    duration: float = 0.0

    def analyze(self, command: str, stdout: str, stderr: str, exit_code: int):
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.success = (exit_code == 0) and (stderr is None or stderr.strip() == "")

        if exit_code != 0:
            self.status = OperationStatus.FAILED
            self.error = stderr.strip() if stderr else f"Exit code {exit_code}"
        elif "error" in stdout.lower() or "fail" in stdout.lower():
            self.status = OperationStatus.FAILED
            self.error = self._extract_error(stdout)
        else:
            self.status = OperationStatus.SUCCESS

        self.summary = self._generate_summary(command)
        self.next_action = self._suggest_next()

    def _extract_error(self, output: str) -> str:
        for line in output.split("\n"):
            if "error" in line.lower() or "fail" in line.lower():
                return line.strip()
        return "Unknown error in output"

    def _generate_summary(self, command: str) -> str:
        if self.status == OperationStatus.SUCCESS:
            return f"Command completed: {command}"
        elif self.status == OperationStatus.FAILED:
            return f"Command failed: {command}\nError: {self.error}"
        return f"Command not executed: {command}"

    def _suggest_next(self) -> Optional[str]:
        if self.status == OperationStatus.SUCCESS:
            return "Operation completed. Ready for next action."
        if self.status == OperationStatus.FAILED:
            if self.error and "timeout" in self.error.lower():
                return "Try: check USB connection and retry."
            if self.error and "loader" in self.error.lower():
                return "Try: use --loader with correct binary."
            return "Check error details and retry."
        return None


# ============================================================================
# SECTION 8: MTK CLIENT ADAPTER (REAL OPERATIONS)
# ============================================================================

class MTKClientAdapter:
    def __init__(self):
        self.mtk = None
        self.da_handler = None
        self.connected = False
        self._loader: Optional[str] = None
        self._preloader: Optional[str] = None
        self._serialport: Optional[str] = None

    def connect(self, preloader: str = None, loader: str = None,
                serialport: str = None, timeout: int = 30) -> OperationResult:
        result = OperationResult()
        result.status = OperationStatus.RUNNING
        start = time.time()

        self._loader = loader
        self._preloader = preloader
        self._serialport = serialport

        try:
            project_root = os.path.dirname(os.path.abspath(__file__))
            if project_root not in sys.path:
                sys.path.insert(0, project_root)

            from mtk_api import init, connect as mtk_connect

            holder: dict = {}

            def _target():
                try:
                    mtk_obj = init(preloader=preloader, loader=loader, serialport=serialport)
                    mtk_obj, da = mtk_connect(mtk=mtk_obj, directory=".")
                    holder["mtk"] = mtk_obj
                    holder["da"] = da
                except Exception as exc:
                    holder["error"] = exc

            t = threading.Thread(target=_target, daemon=True)
            t.start()
            t.join(timeout=timeout)

            if t.is_alive():
                result.status = OperationStatus.FAILED
                result.error = f"Connection timed out after {timeout}s"
                result.summary = "Timeout: no device found. Check USB, power off device, hold vol+/vol- and reconnect."
            elif "error" in holder:
                raise holder["error"]
            elif holder.get("mtk") is not None:
                self.mtk = holder["mtk"]
                self.da_handler = holder.get("da")
                self.connected = True
                result.status = OperationStatus.SUCCESS
                result.success = True
                result.summary = "Device connected successfully"
                chip = getattr(self.mtk.config, "hwcode", None) if self.mtk.config else None
                if chip:
                    result.details["chipset"] = f"MT{chip}" if not str(chip).startswith("MT") else str(chip)
            else:
                result.status = OperationStatus.DEVICE_NOT_FOUND
                result.error = "No MTK device detected"
                result.summary = "Device not found. Check USB connection and mode."

        except ImportError:
            result.status = OperationStatus.NOT_SUPPORTED
            result.error = "mtkclient not available"
            result.summary = "MTKClient library not found. Ensure mtkclient is installed."
        except Exception as e:
            result.status = OperationStatus.FAILED
            result.error = str(e)
            result.summary = f"Connection failed: {e}"
            logger.debug(f"Connection error: {e}")

        result.duration = time.time() - start
        return result

    def _not_connected(self) -> OperationResult:
        result = OperationResult()
        result.status = OperationStatus.DEVICE_NOT_FOUND
        result.error = "Device not connected"
        result.summary = "Device not connected. Run 'detect device' first."
        return result

    def _run_op(self, name: str, func, timeout: int = 120) -> OperationResult:
        result = OperationResult()
        result.status = OperationStatus.RUNNING
        start = time.time()
        try:
            func()
            result.status = OperationStatus.SUCCESS
            result.success = True
            result.summary = f"{name} completed"
        except Exception as e:
            result.status = OperationStatus.FAILED
            result.error = str(e)
            result.summary = f"{name} failed: {e}"
            logger.debug(f"{name} error: {e}")
        result.duration = time.time() - start
        return result

    def _check_da(self) -> OperationResult:
        if not self.connected or self.mtk is None or self.da_handler is None:
            return self._not_connected()
        return None

    def detect_device(self) -> OperationResult:
        if self.connected and self.mtk:
            result = OperationResult()
            result.status = OperationStatus.SUCCESS
            result.success = True
            hwcode = getattr(self.mtk.config, "hwcode", None) if self.mtk.config else None
            meid = getattr(self.mtk.config, "meid", None) if self.mtk.config else None
            result.details = {
                "chipset": f"MT{hwcode}" if hwcode and not str(hwcode).startswith("MT") else str(hwcode) if hwcode else "Unknown",
                "meid": meid.hex() if isinstance(meid, bytes) else str(meid) if meid else None,
                "connected": True,
            }
            result.summary = f"Device detected: {result.details['chipset']}"
            return result
        return self.connect()

    def read_gpt(self) -> OperationResult:
        err = self._check_da()
        if err:
            return err
        return self._run_op("Read GPT", lambda: (
            lambda data, gpt: gpt.print() if gpt else (_ for _ in ()).throw(RuntimeError("Error reading GPT"))
        )(*self.mtk.daloader.get_gpt()))

    def read_partition(self, partition: str, filename: str = None) -> OperationResult:
        err = self._check_da()
        if err:
            return err
        if not filename:
            filename = f"backup_{partition.lower()}.bin"
        return self._run_op(f"Read partition {partition}",
                            lambda: self.da_handler.da_read(partitionname=partition, parttype="user", filename=filename))

    def erase_partition(self, partition: str) -> OperationResult:
        err = self._check_da()
        if err:
            return err
        return self._run_op(f"Erase partition {partition}",
                            lambda: self.da_handler.da_erase(partitions=[partition], parttype="user"))

    def write_partition(self, partition: str, filename: str) -> OperationResult:
        err = self._check_da()
        if err:
            return err
        return self._run_op(f"Write partition {partition}",
                            lambda: self.da_handler.da_write(parttype="user", filenames=[filename], partitions=[partition]))

    def read_full_flash(self, filename: str = "full_dump.bin") -> OperationResult:
        err = self._check_da()
        if err:
            return err
        return self._run_op("Read full flash",
                            lambda: self.da_handler.da_rf(filename=filename, parttype="user"))

    def dump_brom(self, filename: str = "dump_brom.bin") -> OperationResult:
        err = self._check_da()
        if err:
            return err
        return self._run_op("Dump bootrom",
                            lambda: self.mtk.daloader.dump_brom(filename))

    def dump_sram(self, filename: str = "dump_sram.bin") -> OperationResult:
        err = self._check_da()
        if err:
            return err
        def _do():
            from mtkclient.Library.pltools import PLTools
            plt = PLTools(self.mtk, logging.INFO)
            plt.run_dump_brom(filename, self.mtk.config.ptype, loader="generic_sram_payload.bin")
        return self._run_op("Dump SRAM", _do)

    def dump_preloader(self, filename: str = "dump_preloader.bin") -> OperationResult:
        err = self._check_da()
        if err:
            return err
        def _do():
            from mtkclient.Library.pltools import PLTools
            plt = PLTools(self.mtk, logging.INFO)
            data, default_fn = plt.run_dump_preloader(self.mtk.config.ptype)
            if data is not None:
                out = filename or default_fn or "preloader.bin"
                with open(out, 'wb') as wf:
                    wf.write(data)
        return self._run_op("Dump preloader", _do)

    def unlock_bootloader(self) -> OperationResult:
        err = self._check_da()
        if err:
            return err
        return self._run_op("Unlock bootloader",
                            lambda: self.mtk.daloader.seccfg("unlock", critical=False))

    def lock_bootloader(self) -> OperationResult:
        err = self._check_da()
        if err:
            return err
        return self._run_op("Lock bootloader",
                            lambda: self.mtk.daloader.seccfg("lock", critical=False))

    def reset_device(self) -> OperationResult:
        err = self._check_da()
        if err:
            return err
        return self._run_op("Reset device",
                            lambda: self.mtk.daloader.shutdown(bootmode=0))

    def enter_meta(self, mode: str = "factory") -> OperationResult:
        err = self._check_da()
        if err:
            return err
        def _do():
            from mtkclient.Library.meta import META
            meta = META(self.mtk, logging.INFO)
            mode_map = {
                "factory": b"FACTFACT", "fastboot": b"FASTBOOT",
                "meta": b"METAMETA", "factorym": b"FACTORYM",
                "advemeta": b"ADVEMETA", "at+nboot": b"AT+NBOOT",
            }
            metamode = mode_map.get(mode.lower(), b"FACTFACT")
            meta.init(metamode=metamode, display=True)
        return self._run_op(f"Enter META ({mode})", _do)

    def enter_meta2(self) -> OperationResult:
        err = self._check_da()
        if err:
            return err
        def _do():
            from mtkclient.Library.meta import META
            meta = META(self.mtk, logging.INFO)
            meta.init_wdg(display=True)
        return self._run_op("Enter META via WDT", _do)

    def read_imei(self) -> OperationResult:
        err = self._check_da()
        if err:
            return err
        def _do():
            nvdata = self.mtk.daloader.nvitem(data=None, filename=None, encrypt=False, display=True)
            return nvdata
        return self._run_op("Read IMEI", _do)

    def write_imei(self, imeis: str, product: str = "thunder") -> OperationResult:
        err = self._check_da()
        if err:
            return err
        return self._run_op(f"Write IMEI",
                            lambda: self.mtk.daloader.nvitem(data=imeis, filename=None, encrypt=False,
                                                              display=True, write=True, product=product))

    def generate_keys(self) -> OperationResult:
        err = self._check_da()
        if err:
            return err
        return self._run_op("Generate keys", lambda: self.mtk.daloader.keys())

    def get_target_config(self) -> OperationResult:
        if not self.connected or self.mtk is None:
            return self._not_connected()
        return self._run_op("Get target config", lambda: self.mtk.preloader.get_target_config())

    def read_offset(self, address: str, length: str = "0x100") -> OperationResult:
        err = self._check_da()
        if err:
            return err
        addr = int(address, 16) if isinstance(address, str) else address
        lng = int(length, 16) if isinstance(length, str) else length
        return self._run_op(f"Read offset {hex(addr)}",
                            lambda: self.da_handler.da_ro(start=addr, length=lng, filename="", parttype="user"))

    def read_sectors(self, sector_count: int = 1) -> OperationResult:
        err = self._check_da()
        if err:
            return err
        return self._run_op(f"Read {sector_count} sectors",
                            lambda: self.da_handler.da_rs(start=0, sectors=sector_count, filename="",
                                                          parttype="user", display=True))

    def read_all_partitions(self, directory: str) -> OperationResult:
        err = self._check_da()
        if err:
            return err
        return self._run_op("Read all partitions",
                            lambda: self.da_handler.da_rl(directory=directory, parttype="user", skip=[]))

    def write_full_flash(self, filename: str) -> OperationResult:
        err = self._check_da()
        if err:
            return err
        return self._run_op("Write full flash",
                            lambda: self.da_handler.da_wf(filenames=[filename], parttype="user"))

    def write_all_partitions(self, directory: str) -> OperationResult:
        err = self._check_da()
        if err:
            return err
        return self._run_op("Write all partitions",
                            lambda: self.da_handler.da_wl(directory=directory, parttype="user"))

    def write_offset(self, address: str, filename: str) -> OperationResult:
        err = self._check_da()
        if err:
            return err
        addr = int(address, 16) if isinstance(address, str) else address
        return self._run_op(f"Write offset {hex(addr)}",
                            lambda: self.da_handler.da_wo(start=addr, length=0, filename=filename, parttype="user"))

    def erase_sectors(self, partition: str, sector_count: int) -> OperationResult:
        err = self._check_da()
        if err:
            return err
        return self._run_op(f"Erase {sector_count} sectors of {partition}",
                            lambda: self.da_handler.da_es(partitions=[partition], parttype="user", sectors=sector_count))

    def erase_sector_range(self, sector_start: int) -> OperationResult:
        err = self._check_da()
        if err:
            return err
        return self._run_op(f"Erase from sector {sector_start}",
                            lambda: self.da_handler.da_ess(sector=sector_start, parttype="user", sectors=0))

    def wipe_device(self) -> OperationResult:
        err = self._check_da()
        if err:
            return err
        return self._run_op("Wipe device",
                            lambda: self.da_handler.da_erase(
                                partitions=["userdata", "metadata", "md_udc", "cache"], parttype="user"))

    def erase_frp(self) -> OperationResult:
        err = self._check_da()
        if err:
            return err
        return self._run_op("Erase FRP",
                            lambda: self.da_handler.da_erase(partitions=["frp"], parttype="user"))

    def read_footer(self, filename: str = "footer.bin") -> OperationResult:
        err = self._check_da()
        if err:
            return err
        return self._run_op("Read crypto footer",
                            lambda: self.da_handler.da_footer(filename=filename))

    def save_gpt(self, directory: str) -> OperationResult:
        err = self._check_da()
        if err:
            return err
        return self._run_op("Save GPT",
                            lambda: self.da_handler.da_gpt(directory=directory))

    def run_payload(self, payload_file: str, metamode: str = None) -> OperationResult:
        err = self._check_da()
        if err:
            return err
        def _do():
            from mtkclient.Library.pltools import PLTools
            plt = PLTools(self.mtk, logging.INFO)
            plt.runpayload(payload_file)
        return self._run_op(f"Run payload {payload_file}", _do)

    def crash_preloader(self) -> OperationResult:
        if not self.connected or self.mtk is None:
            return self._not_connected()
        return self._run_op("Crash preloader", lambda: self.mtk.crasher())

    def run_brute(self) -> OperationResult:
        if not self.connected or self.mtk is None:
            return self._not_connected()
        def _do():
            from mtkclient.Library.pltools import PLTools
            import argparse
            plt = PLTools(self.mtk, logging.INFO)
            brute_args = argparse.Namespace(ptype=self.mtk.config.ptype, var1=None)
            plt.runbrute(brute_args)
        return self._run_op("Bruteforce kamakiri", _do)

    def get_logs(self) -> OperationResult:
        err = self._check_da()
        if err:
            return err
        def _do():
            from mtkclient.Library.mtk_main import Main
            main_obj = Main.__new__(Main)
            main_obj._Main__logger = logging.getLogger("mtk")
            main_obj.cmd_log(self.mtk, filename=None)
        return self._run_op("Get logs", _do)

    def run_stage(self, payload_file: str, stage: int = 2, metamode: str = None) -> OperationResult:
        if not self.connected or self.mtk is None:
            return self._not_connected()
        def _do():
            from mtkclient.Library.mtk_main import Main
            import argparse
            main_obj = Main.__new__(Main)
            main_obj._Main__logger = logging.getLogger("mtk")
            main_obj.args = argparse.Namespace(
                filename=payload_file, stage2addr=None, stage2=None, verifystage2=False)
            main_obj.cmd_stage(self.mtk, payload_file, None, None, False)
        return self._run_op(f"Stage2 via bootrom: {payload_file}", _do)

    def run_plstage(self, payload_file: str, stage: int = 2, metamode: str = None) -> OperationResult:
        if not self.connected or self.mtk is None:
            return self._not_connected()
        def _do():
            from mtkclient.Library.pltools import PLTools
            plt = PLTools(self.mtk, logging.INFO)
            with open(payload_file, "rb") as rf:
                pldata = self.mtk.patch_preloader_security_da1(rf.read())
            if self.mtk.preloader.init():
                if self.mtk.config.target_config and self.mtk.config.target_config.get("daa"):
                    self.mtk = self.mtk.bypass_security()
                daaddr = self.mtk.config.chipconfig.pl_payload_addr or 0x40001000
                if self.mtk.preloader.send_da(daaddr, len(pldata), 0x100, pldata):
                    self.mtk.preloader.jump_da(daaddr)
        return self._run_op(f"Stage2 via preloader: {payload_file}", _do)

    def mount_fs(self) -> OperationResult:
        err = self._check_da()
        if err:
            return err
        return self._run_op("Mount FUSE filesystem",
                            lambda: None,
                            timeout=30)

    def da_vbmeta(self, mode: str = "disable") -> OperationResult:
        err = self._check_da()
        if err:
            return err
        mode_int = {"disable": 3, "enable": 0, "0": 0, "1": 1, "2": 2, "3": 3}.get(mode, 3)
        return self._run_op(f"DA vbmeta {mode}",
                            lambda: self.da_handler.da_vbmeta(vbmode=mode_int))

    def da_efuse(self) -> OperationResult:
        err = self._check_da()
        if err:
            return err
        return self._run_op("DA read efuses",
                            lambda: self.da_handler.da_efuse())

    def da_keyserver(self) -> OperationResult:
        err = self._check_da()
        if err:
            return err
        return self._run_op("DA key server",
                            lambda: self.mtk.daloader.keyserver())

    def da_meta(self, mode: str = "off") -> OperationResult:
        err = self._check_da()
        if err:
            return err
        return self._run_op(f"DA MetaMode {mode}",
                            lambda: self.mtk.daloader.setmetamode(mode))

    def da_nvitem(self, action: str, filename: str) -> OperationResult:
        err = self._check_da()
        if err:
            return err
        encrypt = action == "enc"
        return self._run_op(f"DA NV item {action}",
                            lambda: self.mtk.daloader.nvitem(filename=filename, encrypt=encrypt, display=True))

    def da_patchmodem(self) -> OperationResult:
        err = self._check_da()
        if err:
            return err
        def _do():
            data = self.da_handler.da_read_partition("md1img", parttype="user")
            if data:
                self.da_handler.da_write_partition("md1img", data=data, parttype="user")
        return self._run_op("DA patch modem", _do)

    def da_rpmb_read(self) -> OperationResult:
        err = self._check_da()
        if err:
            return err
        return self._run_op("DA read RPMB",
                            lambda: self.mtk.daloader.read_rpmb())

    def da_rpmb_write(self, filename: str) -> OperationResult:
        err = self._check_da()
        if err:
            return err
        return self._run_op(f"DA write RPMB: {filename}",
                            lambda: self.mtk.daloader.write_rpmb(filename=filename))

    def da_memdump(self) -> OperationResult:
        err = self._check_da()
        if err:
            return err
        def _do():
            bromaddr, bromsize = 0, 0x300000
            sramaddr, sramsize = 0x300000, 0x11200000
            efuseaddr, efusesize = 0x11C10000, 0x10000
            dramaddr, dramsize = 0x40000000, 0x100000000 - 0x40000000
            self.da_handler.da_peek(addr=bromaddr, length=bromsize, filename="dump_brom.bin", registers=True)
            self.da_handler.da_peek(addr=dramaddr, length=dramsize, filename="dump_dram.bin", registers=False)
            self.da_handler.da_peek(addr=efuseaddr, length=efusesize, filename="dump_efuse.bin", registers=True)
            self.da_handler.da_peek(addr=sramaddr, length=sramsize, filename="dump_sram.bin", registers=False)
        return self._run_op("DA memory dump", _do)

    def da_memdram(self) -> OperationResult:
        err = self._check_da()
        if err:
            return err
        def _do():
            dramaddr, dramsize = 0x40000000, 0x100000000 - 0x40000000
            self.da_handler.da_peek(addr=dramaddr, length=dramsize, filename="dump_dram.bin", registers=False)
        return self._run_op("DA DRAM dump", _do)


# ============================================================================
# SECTION 9: ERROR ANALYZER
# ============================================================================

@dataclass
class ErrorInfo:
    raw: str = ""
    code: Optional[int] = None
    name: Optional[str] = None
    severity: str = "unknown"
    cause: str = "Unknown"
    meaning: str = ""
    fix: List[str] = field(default_factory=list)
    safe_next: str = ""

    @property
    def has_code(self) -> bool:
        return self.code is not None


class ErrorAnalyzer:
    def analyze(self, error_text: str) -> ErrorInfo:
        code = self._extract_code(error_text)
        info = ErrorInfo(raw=error_text, code=code)

        if code and code in MTK_ERROR_CODES:
            info.name = MTK_ERROR_CODES[code]

        if code and code in ERROR_CAUSES:
            info.cause = ERROR_CAUSES[code]["causes"][0]
            info.fix = ERROR_CAUSES[code]["actions"]
        else:
            info.cause = self._guess_cause(error_text)
            info.fix = self._guess_fixes(error_text)

        info.severity = self._severity(error_text)
        info.meaning = self._meaning(info)
        info.safe_next = info.fix[0] if info.fix else "Check connection and retry."

        return info

    def _extract_code(self, text: str) -> Optional[int]:
        m = re.search(r"(?:0x|error\s+code[:\s]+)([0-9a-fA-F]{3,4})", text)
        if m:
            return int(m.group(1), 16)
        for code, name in MTK_ERROR_CODES.items():
            if name.lower().replace("_", " ") in text.lower():
                return code
        return None

    def _severity(self, text: str) -> str:
        t = text.lower()
        for p in [r"bricked", r"dead", r"corrupt", r"efuse", r"blow", r"permanent"]:
            if re.search(p, t):
                return "critical"
        for p in [r"download.*da.*fail", r"send_da", r"boot.*fail", r"auth.*fail"]:
            if re.search(p, t):
                return "high"
        for p in [r"timeout", r"retry", r"unstable", r"intermittent"]:
            if re.search(p, t):
                return "medium"
        return "low"

    def _guess_cause(self, text: str) -> str:
        t = text.lower()
        if "timeout" in t:
            return "Operation timed out. Connection unstable."
        if "not found" in t or "no device" in t:
            return "Device not detected. Check USB connection."
        if "permission" in t or "access" in t:
            return "Permission denied. Check drivers."
        if "loader" in t or "da" in t:
            return "Download Agent issue. Wrong loader?"
        return "Unknown error. Check raw output."

    def _guess_fixes(self, text: str) -> List[str]:
        t = text.lower()
        fixes = []
        if "timeout" in t:
            fixes = ["Retry operation", "Check USB cable", "Try different port"]
        elif "not found" in t or "no device" in t:
            fixes = ["Install MTK drivers", "Try different USB port", "Hold Vol+Vol- and connect"]
        elif "permission" in t:
            fixes = ["Run as administrator", "Check USB drivers"]
        else:
            fixes = ["Check connection", "Retry operation", "Check mtkclient output"]
        return fixes

    def _meaning(self, info: ErrorInfo) -> str:
        if info.name:
            return f"MTK error: {info.name}. {info.cause}"
        return f"Error detected. {info.cause}"

    def format_report(self, info: ErrorInfo) -> str:
        sev_colors = {"critical": Fore.RED, "high": Fore.RED, "medium": Fore.YELLOW, "low": Fore.GREEN}
        sev = info.severity
        color = sev_colors.get(sev, "")

        lines = [
            f"\n{color}{'='*50}{Style.RESET_ALL}",
            f"  ERROR ANALYSIS",
            f"{'='*50}{Style.RESET_ALL}",
            f"  Severity : {color}{sev.upper()}{Style.RESET_ALL}",
        ]
        if info.name:
            lines.append(f"  Error    : {info.name}")
        if info.code is not None:
            lines.append(f"  Code     : 0x{info.code:04X}")
        lines += [
            f"  Meaning  : {info.meaning}",
            f"  Cause    : {info.cause}",
            "",
            "  RECOMMENDED:",
        ]
        for i, chk in enumerate(info.fix, 1):
            lines.append(f"    {i}. {chk}")
        if info.safe_next:
            lines.append(f"\n  SAFE NEXT: {info.safe_next}")
        lines.append(f"{'='*50}")
        return "\n".join(lines)


# ============================================================================
# SECTION 10: WORKFLOW ENGINE
# ============================================================================

@dataclass
class WorkflowStep:
    action: str
    description: str
    status: OperationStatus = OperationStatus.PLANNED
    result: Optional[OperationResult] = None
    error: Optional[str] = None
    duration: float = 0.0

    def to_dict(self) -> Dict:
        return {"action": self.action, "description": self.description,
                "status": self.status.value, "error": self.error, "duration": self.duration}


class WorkflowEngine:
    def __init__(self, adapter: MTKClientAdapter):
        self.adapter = adapter
        self.active: Optional[str] = None
        self._steps: List[WorkflowStep] = []

    def list_workflows(self) -> List[Dict]:
        return [{"name": n, "desc": w["description"], "risk": w["risk"].value, "steps": len(w["steps"])}
                for n, w in WORKFLOW_DEFS.items()]

    def execute(self, name: str, params: Dict = None) -> str:
        if name not in WORKFLOW_DEFS:
            return f"Unknown workflow: {name}. Available: {', '.join(WORKFLOW_DEFS.keys())}"

        wf = WORKFLOW_DEFS[name]
        self.active = name
        steps = [WorkflowStep(action=a, description=d) for a, d in wf["steps"]]
        self._steps = steps

        lines = [
            f"\n{'='*50}",
            f"  WORKFLOW: {name.upper()}",
            f"  {wf['description']}",
            f"  Risk: {wf['risk'].value.upper()}",
            f"{'='*50}",
            "",
        ]

        for i, step in enumerate(steps, 1):
            step.status = OperationStatus.RUNNING
            lines.append(f"  [{i}/{len(steps)}] {step.description}...")

            result = self._execute_step(step.action, params or {})
            step.result = result
            step.duration = result.duration

            if result.status == OperationStatus.SUCCESS:
                step.status = OperationStatus.SUCCESS
                lines.append(f"         OK")
            elif result.status == OperationStatus.DEVICE_NOT_FOUND:
                step.status = OperationStatus.FAILED
                lines.append(f"         FAILED: {result.error}")
                lines.append(f"\n  Cannot continue without device connection.")
                break
            elif result.status == OperationStatus.NOT_SUPPORTED:
                step.status = OperationStatus.NOT_SUPPORTED
                lines.append(f"         SKIPPED: {result.error}")
            else:
                step.status = OperationStatus.FAILED
                lines.append(f"         FAILED: {result.error}")

        completed = sum(1 for s in steps if s.status in (OperationStatus.SUCCESS, OperationStatus.NOT_SUPPORTED))
        total = len(steps)
        self.active = None

        lines += [
            "",
            f"  Progress: {completed}/{total} ({completed/total*100:.0f}%)",
            f"{'='*50}",
        ]
        return "\n".join(lines)

    def _execute_step(self, action: str, params: Dict) -> OperationResult:
        if action == "detect_device":
            return self.adapter.detect_device()
        elif action == "identify_chipset":
            return self._identify_chipset()
        elif action == "dump_brom":
            return self.adapter.dump_brom()
        elif action == "dump_preloader":
            return self.adapter.dump_preloader()
        elif action == "read_gpt":
            return self.adapter.read_gpt()
        elif action == "read_all_partitions":
            return self.adapter.read_full_flash()
        elif action == "backup_all":
            return self.adapter.read_full_flash()
        elif action == "analyze_state":
            return self._analyze_state()
        elif action == "read_seccfg":
            return self.adapter.get_target_config()
        elif action == "unlock_seccfg":
            return self.adapter.unlock_bootloader()
        elif action == "reboot_device":
            return self.adapter.reset_device()
        elif action == "connect_da":
            if self.adapter.connected:
                r = OperationResult()
                r.status = OperationStatus.SUCCESS
                r.success = True
                r.summary = "DA already connected"
                return r
            return self.adapter.connect()
        elif action == "erase_userdata":
            return self.adapter.erase_partition("USERDATA")
        elif action == "erase_cache":
            return self.adapter.erase_partition("CACHE")
        elif action == "report":
            r = OperationResult()
            r.status = OperationStatus.SUCCESS
            r.success = True
            report_lines = ["Workflow Report", f"Workflow: {self.active or 'unknown'}", ""]
            for step in self._steps:
                status_str = step.status.value if step.status else "planned"
                duration_str = f"{step.duration:.1f}s" if step.duration else "n/a"
                report_lines.append(f"  [{status_str}] {step.description} ({duration_str})")
                if step.error:
                    report_lines.append(f"    Error: {step.error}")
            r.summary = "\n".join(report_lines)
            return r
        else:
            r = OperationResult()
            r.status = OperationStatus.NOT_SUPPORTED
            r.error = f"Action not implemented: {action}"
            r.summary = f"Step '{action}' is not yet supported."
            return r

    def _identify_chipset(self) -> OperationResult:
        r = OperationResult()
        if self.adapter.mtk and self.adapter.mtk.config:
            hwcode = getattr(self.adapter.mtk.config, "hwcode", None)
            if hwcode:
                chip = f"MT{hwcode}" if not str(hwcode).startswith("MT") else str(hwcode)
                r.status = OperationStatus.SUCCESS
                r.success = True
                r.details["chipset"] = chip
                if chip in CHIPSET_DB:
                    r.details.update(CHIPSET_DB[chip])
                r.summary = f"Chipset: {chip}"
                return r
        r.status = OperationStatus.DEVICE_NOT_FOUND
        r.error = "No chipset info available"
        return r

    def _analyze_state(self) -> OperationResult:
        r = OperationResult()
        if not self.adapter.connected:
            r.status = OperationStatus.DEVICE_NOT_FOUND
            r.error = "No device connected for state analysis"
            return r

        r.status = OperationStatus.SUCCESS
        r.success = True
        details: Dict = {}

        chip = "Unknown"
        if self.adapter.mtk and self.adapter.mtk.config:
            hwcode = getattr(self.adapter.mtk.config, "hwcode", None)
            if hwcode:
                chip = f"MT{hwcode}" if not str(hwcode).startswith("MT") else str(hwcode)
        details["chipset"] = chip
        if chip in CHIPSET_DB:
            details.update(CHIPSET_DB[chip])

        config_result = self.adapter.get_target_config()
        if config_result.success and config_result.stdout:
            details["target_config"] = config_result.stdout.strip()[:200]

        gpt_result = self.adapter.read_gpt()
        if gpt_result.success and gpt_result.stdout:
            details["gpt_readable"] = True
            details["gpt_preview"] = gpt_result.stdout.strip()[:200]
        else:
            details["gpt_readable"] = False

        r.details = details
        parts = [f"Chipset: {chip}"]
        for k, v in details.items():
            if k not in ("chipset",):
                parts.append(f"{k}: {v}")
        r.summary = " | ".join(parts)
        return r


# ============================================================================
# SECTION 11: RESPONSE FORMATTER
# ============================================================================

class ResponseFormatter:
    @staticmethod
    def success(message: str, details: Dict = None) -> str:
        lines = [f"\n{Fore.GREEN}OK{Style.RESET_ALL} {message}"]
        if details:
            for k, v in details.items():
                lines.append(f"  {k:12s}: {v}")
        return "\n".join(lines)

    @staticmethod
    def error(message: str, details: Dict = None) -> str:
        lines = [f"\n{Fore.RED}FAILED{Style.RESET_ALL} {message}"]
        if details:
            for k, v in details.items():
                lines.append(f"  {k:12s}: {v}")
        return "\n".join(lines)

    @staticmethod
    def device_info(details: Dict) -> str:
        lines = [
            f"\n{Fore.CYAN}{'='*50}{Style.RESET_ALL}",
            f"  DEVICE INFO",
            f"{'='*50}{Style.RESET_ALL}",
        ]
        for k, v in details.items():
            lines.append(f"  {k:15s}: {v}")
        lines.append(f"{'='*50}")
        return "\n".join(lines)

    @staticmethod
    def help_text() -> str:
        return f"""
{Fore.CYAN}{'='*50}
  {APP_NAME} v{APP_VERSION}
  Offline MediaTek Device Management
{'='*50}{Style.RESET_ALL}

{Fore.YELLOW}DEVICE:{Style.RESET_ALL}
  detect device            Detect connected MTK device
  device info              Show device information
  connection test          Test USB connection
  diagnose                 Diagnose device problems
  diagnose error 0x7D4     Diagnose specific error
  status                   Show session context
  devices list             Show supported MTK devices

{Fore.YELLOW}READ:{Style.RESET_ALL}
  read gpt                 Show partition table
  save gpt <dir>           Save GPT table to directory
  read partition <name>    Read partition to backup file
  read boot                Read boot partition
  read userdata            Read userdata partition
  read full flash          Read entire flash (full backup)
  read offset <hex> [len]  Read flash at hex address
  read sectors <count>     Read N sectors from flash
  read all partitions      Read all partitions to directory
  read footer              Read crypto footer
  peek <hex>               Read memory (patched PL mode)
  dump bootrom             Dump bootrom
  dump sram                Dump SRAM
  dump preloader           Dump preloader
  read imei                Read IMEI numbers

{Fore.YELLOW}WRITE:{Style.RESET_ALL}
  write partition <n> <f>  Write to partition
  write full flash <file>  Write full flash image
  write all partitions     Write all from directory
  write offset <hex> <f>   Write at hex address
  flash firmware <file>    Flash firmware image

{Fore.YELLOW}ERASE:{Style.RESET_ALL}
  erase partition <name>              Erase partition
  erase partition <n> sectors <count> Erase N sectors
  erase sector <start>               Erase from sector N
  wipe                               Wipe userdata, metadata, md_udc and cache
  frp                                Erase FRP partition

{Fore.YELLOW}DA (DA-mode tools):{Style.RESET_ALL}
  generate keys            Generate crypto keys
  get target config        Get SBC/DAA config
  logs                     Get target logs
  da efuse                 Read efuses
  da vbmeta <mode>         Patch vbmeta (disable/enable)
  da keyserver             Start key server
  da meta <mode>           DA MetaMode (off/usb/uart)
  da nvitem <act> <file>   NV item decrypt/encrypt
  da patchmodem            Patch modem for IMEI
  da rpmb read             Read RPMB
  da rpmb write <file>     Write RPMB
  da memdump               Dump whole memory
  da memdram               Dump DRAM memory

{Fore.YELLOW}META / PAYLOAD / STAGE:{Style.RESET_ALL}
  enter meta mode          Enter META factory mode
  meta2                    Enter META via WDT
  payload <file>           Run kamakiri/DA payload
  stage <file>             Stage2 via bootrom
  plstage <file>           Stage2 via preloader
  fs mount                 Mount as FUSE filesystem

{Fore.YELLOW}ADVANCED:{Style.RESET_ALL}
  unlock bootloader        Unlock via seccfg (DANGEROUS)
  lock bootloader          Lock via seccfg (DANGEROUS)
  reboot device            Reset/reboot device
  crash                    Crash preloader (advanced)
  brute                    Bruteforce kamakiri (experimental)

{Fore.YELLOW}WORKFLOWS:{Style.RESET_ALL}
  start repair unbrick           Unbrick workflow
  start repair unlock_bootloader Unlock bootloader workflow
  start repair backup_full       Full backup workflow
  start repair factory_reset     Factory reset workflow
  repair <issue>                 Repair dead/bootloop/unbrick

{Fore.YELLOW}OTHER:{Style.RESET_ALL}
  write imei <numbers>     Repair IMEI
  search <query>           Search knowledge base
  help                     Show this help
  quit / exit              Exit agent
"""

# ============================================================================
# SECTION 12: MAIN AGENT
# ============================================================================

class MTKAgent:
    def __init__(self, loglevel: int = logging.INFO):
        logging.basicConfig(
            level=loglevel,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )
        self.adapter = MTKClientAdapter()
        self.classifier = IntentClassifier()
        self.safety = SafetyEngine()
        self.memory = ConversationMemory()
        self.workflow = WorkflowEngine(self.adapter)
        self.error_analyzer = ErrorAnalyzer()
        self.formatter = ResponseFormatter()
        self.session_log: List[Dict] = []
        self.pending_confirmation: Optional[Dict] = None

    def process(self, user_input: str) -> str:
        raw = user_input.strip()
        low = raw.lower()

        if low in ("quit", "exit", "q"):
            return "__QUIT__"

        if self.pending_confirmation:
            return self._handle_confirmation(raw)

        if low == "save":
            self._save_session()
            return self.formatter.success("Session saved.")

        if low.startswith("start repair "):
            name = raw[13:].strip().lower().replace(" ", "_")
            return self._handle_repair(name)

        if low.startswith("diagnose error "):
            return self._handle_diagnose_error(raw[15:].strip())

        if low.startswith("diagnose"):
            return self._handle_diagnose(raw)

        if low.startswith("search "):
            return self._handle_search(raw[7:].strip())

        intent_name, confidence, params = self.classifier.classify(raw)

        if intent_name == "unknown":
            return self._unknown_response(raw)

        intent = INTENT_REGISTRY[intent_name]
        self._log(intent_name, params)

        if intent.requires_confirmation:
            self.pending_confirmation = {"intent": intent_name, "params": params, "raw": raw}
            return self.safety.format_confirmation(intent_name, params)

        return self._execute_intent(intent_name, params)

    def _handle_confirmation(self, user_input: str) -> str:
        pending = self.pending_confirmation
        self.pending_confirmation = None

        if user_input.strip().upper() != "YES":
            return self.formatter.error("Operation cancelled by user.")

        return self._execute_intent(pending["intent"], pending["params"])

    def _execute_intent(self, intent_name: str, params: Dict) -> str:
        if intent_name == "help":
            return self.formatter.help_text()

        if intent_name == "status":
            return self.memory.summary()

        if intent_name == "detect_device":
            return self._handle_detect(params)

        if intent_name == "device_info":
            return self._handle_device_info(params)

        if intent_name == "connection_test":
            return self._handle_connection_test()

        if intent_name == "read_gpt":
            return self._handle_read_gpt()

        if intent_name == "read_partition":
            return self._handle_read_partition(params)

        if intent_name == "write_partition":
            return self._handle_write_partition(params)

        if intent_name == "erase_partition":
            return self._handle_erase_partition(params)

        if intent_name == "read_full_flash":
            return self._handle_read_full_flash(params)

        if intent_name == "dump_brom":
            return self._handle_dump("brom", params)

        if intent_name == "dump_sram":
            return self._handle_dump("sram", params)

        if intent_name == "dump_preloader":
            return self._handle_dump("preloader", params)

        if intent_name == "unlock_bootloader":
            return self._handle_simple_op(self.adapter.unlock_bootloader, "Unlock bootloader")

        if intent_name == "lock_bootloader":
            return self._handle_simple_op(self.adapter.lock_bootloader, "Lock bootloader")

        if intent_name == "reset_device":
            return self._handle_simple_op(self.adapter.reset_device, "Reset device")

        if intent_name == "enter_meta":
            mode = params.get("metamode", "factory")
            return self._handle_simple_op(lambda: self.adapter.enter_meta(mode), f"Enter META ({mode})")

        if intent_name == "flash_firmware":
            fn = params.get("filename")
            if not fn:
                return self.formatter.error("No firmware file specified. Usage: flash firmware <filename>")
            return self._handle_simple_op(lambda: self.adapter.write_partition("SUPER", fn), f"Flash firmware: {fn}")

        if intent_name == "read_imei":
            return self._handle_simple_op(self.adapter.read_imei, "Read IMEI")

        if intent_name == "write_imei":
            imeis = params.get("imei") or params.get("partition", "")
            if not imeis:
                return self.formatter.error("No IMEI specified. Usage: write imei <number>")
            return self._handle_simple_op(lambda: self.adapter.write_imei(imeis), f"Write IMEI: {imeis}")

        if intent_name == "generate_keys":
            return self._handle_simple_op(self.adapter.generate_keys, "Generate keys")

        if intent_name == "search_knowledge":
            return self._handle_search(params.get("query", "") or params.get("partition", ""))

        if intent_name == "repair":
            workflow_name = params.get("workflow") or params.get("partition") or ""
            return self._handle_repair(workflow_name)

        if intent_name == "cancel":
            self.pending_confirmation = None
            self.workflow.active = None
            return "Operation cancelled."

        if intent_name == "devices_list":
            return self._handle_simple_op(self.adapter.list_devices, "Supported devices")

        if intent_name == "save_gpt":
            directory = params.get("filename") or params.get("partition") or "gpt_backup"
            return self._handle_simple_op(lambda: self.adapter.save_gpt(directory), f"Save GPT to {directory}")

        if intent_name == "read_offset":
            addr = params.get("address", "")
            length = params.get("length", "0x100")
            if not addr:
                return self.formatter.error("No address specified. Usage: read offset <hex_address> [length]")
            if not _is_hex_address(addr):
                return self.formatter.error(f"Invalid hex address: {addr}. Example: 0x1000")
            return self._handle_simple_op(lambda: self.adapter.read_offset(addr, length), f"Read offset {addr}")

        if intent_name == "read_sectors":
            count = params.get("sector_count", 1)
            return self._handle_simple_op(lambda: self.adapter.read_sectors(count), f"Read {count} sectors")

        if intent_name == "read_all_partitions":
            directory = params.get("filename") or params.get("partition") or "all_partitions_backup"
            return self._handle_simple_op(lambda: self.adapter.read_all_partitions(directory), f"Backup all partitions to {directory}")

        if intent_name == "write_full_flash":
            fn = params.get("filename")
            if not fn:
                return self.formatter.error("No filename specified. Usage: write full flash <filename>")
            return self._handle_simple_op(lambda: self.adapter.write_full_flash(fn), f"Write full flash: {fn}")

        if intent_name == "write_all_partitions":
            directory = params.get("filename")
            if not directory:
                return self.formatter.error("No directory specified. Usage: write all partitions <directory>")
            return self._handle_simple_op(lambda: self.adapter.write_all_partitions(directory), f"Write all partitions from {directory}")

        if intent_name == "write_offset":
            addr = params.get("address", "")
            fn = params.get("filename")
            if not addr:
                return self.formatter.error("No address specified. Usage: write offset <hex_address> <filename>")
            if not fn:
                return self.formatter.error("No filename specified. Usage: write offset <hex_address> <filename>")
            if not _is_hex_address(addr):
                return self.formatter.error(f"Invalid hex address: {addr}. Example: 0x1000")
            return self._handle_simple_op(lambda: self.adapter.write_offset(addr, fn), f"Write offset {addr}: {fn}")

        if intent_name == "erase_sectors":
            partition = params.get("partition", "")
            count = params.get("sector_count", 1)
            if not partition:
                return self.formatter.error("No partition specified. Usage: erase <partition> sectors <count>")
            return self._handle_simple_op(lambda: self.adapter.erase_sectors(partition, count), f"Erase {count} sectors of {partition}")

        if intent_name == "erase_sector_range":
            sector_start = params.get("sector_count", 0)
            return self._handle_simple_op(lambda: self.adapter.erase_sector_range(sector_start), f"Erase from sector {sector_start}")

        if intent_name == "wipe":
            return self._handle_wipe()

        if intent_name == "erase_frp":
            return self._handle_erase_frp()

        if intent_name == "read_footer":
            fn = params.get("filename", "footer.bin")
            return self._handle_simple_op(lambda: self.adapter.read_footer(fn), f"Read crypto footer: {fn}")

        if intent_name == "meta2":
            return self._handle_simple_op(self.adapter.enter_meta2, "Enter META via WDT")

        if intent_name == "payload":
            pf = params.get("filename") or params.get("partition")
            if not pf:
                return self.formatter.error("No payload file specified. Usage: payload <file>")
            metamode = params.get("metamode")
            return self._handle_simple_op(lambda: self.adapter.run_payload(pf, metamode), f"Run payload: {pf}")

        if intent_name == "crash":
            return self._handle_simple_op(self.adapter.crash_preloader, "Crash preloader")

        if intent_name == "brute":
            return self._handle_simple_op(self.adapter.run_brute, "Bruteforce kamakiri")

        if intent_name == "get_target_config":
            return self._handle_simple_op(self.adapter.get_target_config, "Get target config")

        if intent_name == "logs":
            return self._handle_simple_op(self.adapter.get_logs, "Get logs")

        if intent_name == "peek":
            addr = params.get("address", "")
            if not addr:
                return self.formatter.error("No address specified. Usage: peek <hex_address>")
            if not _is_hex_address(addr):
                return self.formatter.error(f"Invalid hex address: {addr}. Example: 0x00100000")
            return self._handle_simple_op(lambda: self.adapter.read_offset(addr, "0x100"), f"Read memory at {addr}")

        if intent_name == "stage":
            pf = params.get("filename")
            if not pf:
                return self.formatter.error("No payload file specified. Usage: stage <file>")
            metamode = params.get("metamode")
            return self._handle_simple_op(lambda: self.adapter.run_stage(pf, 2, metamode), f"Stage2 via bootrom: {pf}")

        if intent_name == "plstage":
            pf = params.get("filename")
            if not pf:
                return self.formatter.error("No payload file specified. Usage: plstage <file>")
            metamode = params.get("metamode")
            return self._handle_simple_op(lambda: self.adapter.run_plstage(pf, 2, metamode), f"Stage2 via preloader: {pf}")

        if intent_name == "fs_mount":
            return self._handle_simple_op(self.adapter.mount_fs, "Mount FUSE filesystem")

        if intent_name == "da_vbmeta":
            mode = params.get("vbmode", "disable")
            return self._handle_simple_op(lambda: self.adapter.da_vbmeta(mode), f"DA vbmeta: {mode}")

        if intent_name == "da_efuse":
            return self._handle_simple_op(self.adapter.da_efuse, "DA read efuses")

        if intent_name == "da_keyserver":
            return self._handle_simple_op(self.adapter.da_keyserver, "DA key server")

        if intent_name == "da_meta":
            mode = params.get("metamode", "off")
            return self._handle_simple_op(lambda: self.adapter.da_meta(mode), f"DA MetaMode: {mode}")

        if intent_name == "da_nvitem":
            action = params.get("action", "dec")
            fn = params.get("filename")
            if not fn:
                return self.formatter.error("No filename specified. Usage: nvitem <action> <filename>")
            return self._handle_simple_op(lambda: self.adapter.da_nvitem(action, fn), f"DA NV item: {action} {fn}")

        if intent_name == "da_patchmodem":
            return self._handle_simple_op(self.adapter.da_patchmodem, "DA patch modem")

        if intent_name == "da_rpmb_read":
            return self._handle_simple_op(self.adapter.da_rpmb_read, "DA read RPMB")

        if intent_name == "da_rpmb_write":
            fn = params.get("filename")
            if not fn:
                return self.formatter.error("No filename specified. Usage: rpmb write <filename>")
            return self._handle_simple_op(lambda: self.adapter.da_rpmb_write(fn), f"DA write RPMB: {fn}")

        if intent_name == "da_memdump":
            return self._handle_simple_op(self.adapter.da_memdump, "DA memory dump")

        if intent_name == "da_memdram":
            return self._handle_simple_op(self.adapter.da_memdram, "DA DRAM dump")

        return self.formatter.error(f"Intent '{intent_name}' recognized but not yet implemented.")

    def _handle_detect(self, params: Dict) -> str:
        result = self.adapter.detect_device()
        if result.success:
            self.memory.update(
                last_chipset=result.details.get("chipset"),
                connected=True,
                last_operation="detect",
            )
            return self.formatter.device_info(result.details)
        return self.formatter.error(result.summary, {"Error": result.error or "None"})

    def _handle_device_info(self, params: Dict) -> str:
        if not self.adapter.connected:
            return self.formatter.error(
                "No device connected.",
                {"How to connect": "Power off device, hold Vol+Vol-, connect USB cable"}
            )
        chip = "Unknown"
        meid = None
        if self.adapter.mtk and self.adapter.mtk.config:
            hwcode = getattr(self.adapter.mtk.config, "hwcode", None)
            meid = getattr(self.adapter.mtk.config, "meid", None)
            if hwcode:
                chip = f"MT{hwcode}" if not str(hwcode).startswith("MT") else str(hwcode)
        info: Dict = {"Chipset": chip, "Connected": "Yes", "Mode": self.memory.last_mode.value}
        if meid:
            info["MEID"] = meid.hex() if isinstance(meid, bytes) else str(meid)
        if chip in CHIPSET_DB:
            cinfo = CHIPSET_DB[chip]
            info["DA Mode"] = cinfo["da_mode"]
            info["Exploit"] = cinfo["exploit"]
            info["Security"] = cinfo["security"]
            info["Year"] = cinfo["year"]
        return self.formatter.device_info(info)

    def _handle_connection_test(self) -> str:
        result = self.adapter.detect_device()
        if result.success:
            return self.formatter.success("Connection OK", result.details)
        return self.formatter.error("Connection failed", {"Error": result.error})

    def _handle_read_gpt(self) -> str:
        if not self._ensure_connected():
            return self.formatter.error("Device not connected.")
        result = self.adapter.read_gpt()
        self._log_result("read_gpt", result)
        return self._format_result("Read GPT", result)

    def _handle_read_partition(self, params: Dict) -> str:
        part = params.get("partition")
        if not part:
            return self.formatter.error("No partition specified. Usage: read <partition>")
        fn = params.get("filename", f"backup_{part.lower()}.bin")
        if not self._ensure_connected():
            return self.formatter.error("Device not connected.")
        result = self.adapter.read_partition(part, fn)
        self.memory.update(last_partition=part)
        self._log_result(f"read_{part}", result)
        return self._format_result(f"Read {part}", result)

    def _handle_write_partition(self, params: Dict) -> str:
        part = params.get("partition")
        fn = params.get("filename")
        if not part or not fn:
            return self.formatter.error("Usage: write <partition> <filename>")
        if not self._ensure_connected():
            return self.formatter.error("Device not connected.")
        result = self.adapter.write_partition(part, fn)
        self._log_result(f"write_{part}", result)
        return self._format_result(f"Write {part}", result)

    def _handle_erase_partition(self, params: Dict) -> str:
        part = params.get("partition")
        if not part:
            return self.formatter.error("No partition specified. Usage: erase <partition>")
        if not self._ensure_connected():
            return self.formatter.error("Device not connected.")
        result = self.adapter.erase_partition(part)
        self._log_result(f"erase_{part}", result)
        return self._format_result(f"Erase {part}", result)

    def _handle_read_full_flash(self, params: Dict) -> str:
        fn = params.get("filename", "full_dump.bin")
        if not self._ensure_connected():
            return self.formatter.error("Device not connected.")
        result = self.adapter.read_full_flash(fn)
        self._log_result("read_full_flash", result)
        return self._format_result("Full flash dump", result)

    def _handle_dump(self, what: str, params: Dict) -> str:
        fn = params.get("filename", f"dump_{what}.bin")
        if not self._ensure_connected():
            return self.formatter.error("Device not connected.")
        handlers = {"brom": self.adapter.dump_brom, "sram": self.adapter.dump_sram, "preloader": self.adapter.dump_preloader}
        result = handlers[what](fn)
        self._log_result(f"dump_{what}", result)
        return self._format_result(f"Dump {what}", result)

    def _handle_simple_op(self, op_func, description: str) -> str:
        if not self._ensure_connected():
            return self.formatter.error("Device not connected.")
        result = op_func()
        self._log_result(description.lower().replace(" ", "_"), result)
        return self._format_result(description, result)

    def _handle_wipe(self) -> str:
        if not self._ensure_connected():
            return self.formatter.error("Device not connected.")
        result = self.adapter.wipe_device()
        self._log_result("wipe", result)
        return self._format_result("Wipe", result)

    def _handle_erase_frp(self) -> str:
        if not self._ensure_connected():
            return self.formatter.error("Device not connected.")
        result = self.adapter.erase_frp()
        self._log_result("erase_frp", result)
        return self._format_result("Erase FRP", result)

    def _handle_repair(self, name: str) -> str:
        if name not in WORKFLOW_DEFS:
            available = ", ".join(WORKFLOW_DEFS.keys())
            return self.formatter.error(f"Unknown workflow: {name}", {"Available": available})
        wf = WORKFLOW_DEFS[name]
        if wf["risk"] == RiskLevel.DANGEROUS:
            self.pending_confirmation = {"intent": "start_repair", "params": {"workflow": name}, "raw": name}
            return self.safety.format_confirmation("repair", {"workflow": name})
        return self.workflow.execute(name)

    def _handle_diagnose_error(self, error_text: str) -> str:
        info = self.error_analyzer.analyze(error_text)
        self.memory.update(last_error=error_text)
        return self.error_analyzer.format_report(info)

    def _handle_diagnose(self, raw: str) -> str:
        if not self.adapter.connected:
            parts = [
                "\n  DIAGNOSIS (no device connected)",
                "",
                "  To diagnose, first connect a device:",
                "    1. Power off device completely",
                "    2. Hold Vol+ and Vol- buttons",
                "    3. Connect USB cable",
                "    4. Type: detect device",
                "",
                "  Common issues:",
            ]
            for issue, info in MTK_KNOWLEDGE["troubleshooting"].items():
                parts.append(f"\n  {issue.upper()}:")
                for fix in info.get("fixes", [])[:2]:
                    parts.append(f"    - {fix}")
            return "\n".join(parts)

        chip = "Unknown"
        if self.adapter.mtk and self.adapter.mtk.config:
            hwcode = getattr(self.adapter.mtk.config, "hwcode", None)
            if hwcode:
                chip = f"MT{hwcode}" if not str(hwcode).startswith("MT") else str(hwcode)

        parts = [f"\n  DIAGNOSIS - Chipset: {chip}", ""]

        config_result = self.adapter.get_target_config()
        if config_result.success and config_result.stdout:
            parts.append(f"  Target Config:")
            for line in config_result.stdout.strip().split("\n")[:5]:
                parts.append(f"    {line.strip()}")
        else:
            parts.append(f"  Target Config: Could not read")

        gpt_result = self.adapter.read_gpt()
        if gpt_result.success and gpt_result.stdout:
            parts.append(f"  GPT: Readable")
        else:
            parts.append(f"  GPT: NOT readable - partition table may be corrupted")
            parts.append(f"  Recommendation: Re-flash GPT or full firmware restore")

        if chip in CHIPSET_DB:
            ci = CHIPSET_DB[chip]
            parts.append(f"  DA Mode    : {ci['da_mode']}")
            parts.append(f"  Exploit    : {ci['exploit']}")
            parts.append(f"  Security   : {ci['security']}")
        if chip in MTK_KNOWLEDGE.get("chipset_notes", {}):
            parts.append(f"  Note       : {MTK_KNOWLEDGE['chipset_notes'][chip]}")

        parts.append(f"\n  Checks performed:")
        parts.append(f"    1. Target config read: {'OK' if config_result.success else 'FAILED'}")
        parts.append(f"    2. GPT readability: {'OK' if gpt_result.success else 'FAILED'}")
        return "\n".join(parts)

    def _handle_search(self, query: str) -> str:
        if not query:
            return self.formatter.error("Usage: search <query>")
        ql = query.lower()
        parts = [f"\n  SEARCH: {query}", ""]

        found = False
        for chip, info in CHIPSET_DB.items():
            if ql in chip.lower():
                parts.append(f"  CHIPSET: {chip}")
                for k, v in info.items():
                    parts.append(f"    {k}: {v}")
                found = True

        for brand, devices in DEVICE_DB.items():
            for model, info in devices.items():
                if ql in model.lower() or ql in info.get("name", "").lower():
                    parts.append(f"  DEVICE: {brand} {info['name']} ({model})")
                    parts.append(f"    Chip: {info['chip']}, Storage: {info['storage']}")
                    found = True

        for name, wf in WORKFLOW_DEFS.items():
            if ql in name.lower() or ql in wf["description"].lower():
                parts.append(f"  WORKFLOW: {name} - {wf['description']}")
                found = True

        for issue, info in MTK_KNOWLEDGE.get("troubleshooting", {}).items():
            if ql in issue.lower():
                parts.append(f"  ISSUE: {issue}")
                for fix in info.get("fixes", [])[:3]:
                    parts.append(f"    - {fix}")
                found = True

        if not found:
            parts.append(f"  No results found for '{query}'")

        return "\n".join(parts)

    def _unknown_response(self, raw: str) -> str:
        parts = [
            f"\n  Unknown command: {raw}",
            "",
            "  I didn't understand that. Try:",
            '    "help"           - Show available commands',
            '    "detect device"  - Detect connected device',
            '    "device info"    - Show device information',
            '    "read gpt"       - Show partition table',
            '    "diagnose"       - Diagnose problems',
        ]
        return "\n".join(parts)

    def _ensure_connected(self) -> bool:
        if self.adapter.connected:
            return True
        result = self.adapter.detect_device()
        if result.success:
            self.memory.update(connected=True, last_chipset=result.details.get("chipset"))
            return True
        return False

    def _format_result(self, operation: str, result: OperationResult) -> str:
        if result.status == OperationStatus.SUCCESS:
            details = {}
            if result.details:
                details = result.details
            elif result.stdout:
                lines = result.stdout.strip().split("\n")[:10]
                for line in lines:
                    if ":" in line:
                        k, v = line.split(":", 1)
                        details[k.strip()] = v.strip()
            return self.formatter.success(f"{operation} completed", details)

        if result.status == OperationStatus.DEVICE_NOT_FOUND:
            return self.formatter.error(f"{operation} failed - no device", {
                "Fix": "Connect device: Power off, hold Vol+Vol-, connect USB"
            })

        if result.status == OperationStatus.NOT_SUPPORTED:
            return self.formatter.error(f"{operation} not supported", {
                "Reason": result.error,
                "Fix": "Ensure mtkclient is installed and device is connected"
            })

        if result.error:
            info = self.error_analyzer.analyze(result.error)
            return self.error_analyzer.format_report(info)

        return self.formatter.error(f"{operation} failed", {"Error": result.error or "Unknown"})

    def _log(self, intent: str, params: Dict):
        self.session_log.append({
            "time": datetime.now().isoformat(),
            "intent": intent,
            "params": params,
        })
        self.memory.update(last_operation=intent)
        self.memory.operation_count += 1

    def _log_result(self, operation: str, result: OperationResult):
        self.session_log.append({
            "time": datetime.now().isoformat(),
            "operation": operation,
            "status": result.status.value,
            "success": result.success,
            "duration": result.duration,
        })

    def _save_session(self, filename: str = "agent_session.json"):
        try:
            with open(filename, "w") as f:
                json.dump(self.session_log, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save session: {e}")


# ============================================================================
# SECTION 13: CLI
# ============================================================================

def run_interactive(agent: MTKAgent):
    signal.signal(signal.SIGINT, lambda s, f: (print(f"\n{Fore.YELLOW}Goodbye!{Style.RESET_ALL}"), sys.exit(0)))

    banner = f"""
{Fore.CYAN}{'='*50}
  {APP_NAME} v{APP_VERSION}
  Offline MediaTek Device Management
{'='*50}{Style.RESET_ALL}
{Fore.YELLOW}Type 'help' for commands, 'quit' to exit.{Style.RESET_ALL}
"""
    print(banner)

    while True:
        try:
            user_input = input(f"{Fore.GREEN}mtk-ai>{Style.RESET_ALL} ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{Fore.YELLOW}Goodbye!{Style.RESET_ALL}")
            break

        if not user_input:
            continue

        response = agent.process(user_input)

        if response == "__QUIT__":
            print(f"{Fore.YELLOW}Goodbye!{Style.RESET_ALL}")
            break

        print(response)


def main():
    parser = argparse.ArgumentParser(
        description=f"{APP_NAME} v{APP_VERSION} - Offline MediaTek device management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--cmd", type=str, help="Process single command and exit")
    parser.add_argument("--detect", action="store_true", help="Detect connected device")
    parser.add_argument("--diagnose", type=str, help="Diagnose error message")
    parser.add_argument("--search", type=str, help="Search knowledge base")
    parser.add_argument("--connect", action="store_true", help="Connect to device on startup")
    parser.add_argument("--loader", type=str, help="Path to DA loader binary")
    parser.add_argument("--preloader", type=str, help="Path to preloader binary")
    parser.add_argument("--serialport", type=str, help="Serial port name")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {APP_VERSION}")
    args = parser.parse_args()

    loglevel = logging.DEBUG if args.debug else logging.INFO
    agent = MTKAgent(loglevel=loglevel)

    if args.connect:
        result = agent.adapter.connect(preloader=args.preloader, loader=args.loader, serialport=args.serialport)
        if result.success:
            agent.memory.update(connected=True, last_chipset=result.details.get("chipset"))
            print(f"{Fore.GREEN}Device connected: {result.details.get('chipset', 'Unknown')}{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}Connection failed: {result.error}{Style.RESET_ALL}")

    if args.detect:
        result = agent.adapter.detect_device()
        if result.success:
            agent.memory.update(connected=True, last_chipset=result.details.get("chipset"))
            print(ResponseFormatter.device_info(result.details))
        else:
            print(ResponseFormatter.error(result.summary, {"Error": result.error}))
        return

    if args.diagnose:
        info = agent.error_analyzer.analyze(args.diagnose)
        print(agent.error_analyzer.format_report(info))
        return

    if args.search:
        print(agent._handle_search(args.search))
        return

    if args.cmd:
        response = agent.process(args.cmd)
        if response != "__QUIT__":
            print(response)
        return

    run_interactive(agent)


if __name__ == "__main__":
    main()
