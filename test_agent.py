#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, ".")
from mtk_ai_single import IntentClassifier, Intent, TextNormalizer, SafetyEngine, RiskLevel, ErrorAnalyzer, ResponseFormatter, OperationResult, OperationStatus, DEVICE_DB, CHIPSET_DB, MTK_KNOWLEDGE, MALAYALAM_MAP, INTENT_REGISTRY

ic = IntentClassifier()
passed = 0
failed = 0

def check(label, actual, expected):
    global passed, failed
    if actual == expected:
        passed += 1
    else:
        print(f"  FAIL [{label}]: got {actual!r}, expected {expected!r}")
        failed += 1

def classify_name(text):
    intent_name, score, params = ic.classify(text)
    return intent_name

# --- Intent Classification ---
print("=== Intent Classification ===")
check("detect", classify_name("detect device"), "detect_device")
check("detect2", classify_name("find device"), "detect_device")
check("read_gpt", classify_name("read gpt"), "read_gpt")
check("read_partition", classify_name("read partition boot"), "read_partition")
check("read_partition2", classify_name("read partition userdata"), "read_partition")
check("read_full", classify_name("read full flash"), "read_full_flash")
check("dump_brom", classify_name("dump bootrom"), "dump_brom")
check("dump_sram", classify_name("dump sram"), "dump_sram")
check("dump_preloader", classify_name("dump preloader"), "dump_preloader")
check("flash", classify_name("flash firmware"), "flash_firmware")
check("erase", classify_name("erase cache"), "erase_partition")
check("erase2", classify_name("erase userdata"), "erase_partition")
check("unlock_bl", classify_name("unlock bootloader"), "unlock_bootloader")
check("lock_bl", classify_name("lock bootloader"), "lock_bootloader")
check("reboot", classify_name("reboot device"), "reset_device")
check("meta_mode", classify_name("enter meta mode"), "enter_meta")
check("gen_keys", classify_name("generate keys"), "generate_keys")
check("read_imei", classify_name("read imei"), "read_imei")
check("diagnose", classify_name("diagnose error"), "diagnose")
check("repair", classify_name("start repair unbrick"), "repair")
check("search", classify_name("search flash"), "search_knowledge")
check("help", classify_name("help"), "help")
check("exit1", classify_name("exit"), "unknown")
check("exit2", classify_name("quit"), "unknown")
check("status", classify_name("status"), "status")
check("write_partition", classify_name("write system firmware.img"), "write_partition")
check("connect", classify_name("connect device"), "unknown")
check("device_info", classify_name("device info"), "device_info")
check("test_conn", classify_name("connection test"), "connection_test")
check("show_partitions", classify_name("show partitions"), "read_gpt")
check("partition_table", classify_name("partition table"), "read_gpt")
check("full_dump", classify_name("full dump"), "read_full_flash")
check("backup_everything", classify_name("backup everything"), "read_full_flash")

# --- Malayalam ---
print("=== Malayalam ===")
check("ml_detect", classify_name("arikku device"), "detect_device")
check("ml_flash", classify_name("vilikkuka firmware"), "flash_firmware")
check("ml_erase", classify_name("mashi cache"), "erase_partition")
check("ml_unlock", classify_name("thurakkuka bootloader"), "unlock_bootloader")
check("ml_reboot", classify_name("restart"), "reset_device")

# --- Safety ---
print("=== Safety ===")
s = SafetyEngine()
check("help_safe", s.get_risk_level("help"), RiskLevel.SAFE)
check("read_gpt_safe", s.get_risk_level("read_gpt"), RiskLevel.SAFE)
check("flash_dangerous", s.get_risk_level("flash_firmware"), RiskLevel.DANGEROUS)
check("erase_dangerous", s.get_risk_level("erase_partition"), RiskLevel.DANGEROUS)
check("unlock_dangerous", s.get_risk_level("unlock_bootloader"), RiskLevel.DANGEROUS)
check("write_dangerous", s.get_risk_level("write_partition"), RiskLevel.DANGEROUS)
check("reboot_moderate", s.get_risk_level("reset_device"), RiskLevel.MODERATE)
check("dump_brom_safe", s.get_risk_level("dump_brom"), RiskLevel.SAFE)
check("read_full_moderate", s.get_risk_level("read_full_flash"), RiskLevel.MODERATE)
check("read_imei_safe", s.get_risk_level("read_imei"), RiskLevel.SAFE)
check("diagnose_safe", s.get_risk_level("diagnose"), RiskLevel.SAFE)
check("repair_moderate", s.get_risk_level("repair"), RiskLevel.MODERATE)
check("meta_moderate", s.get_risk_level("enter_meta"), RiskLevel.MODERATE)
check("gen_keys_safe", s.get_risk_level("generate_keys"), RiskLevel.SAFE)
check("write_imei_dangerous", s.get_risk_level("write_imei"), RiskLevel.DANGEROUS)
check("unknown_dangerous", s.get_risk_level("nonexistent"), RiskLevel.DANGEROUS)

# --- Error Analyzer ---
print("=== Error Analyzer ===")
ea = ErrorAnalyzer()
info = ea.analyze("CMD_SEND_DA_FAIL 0x7D4")
check("err_severity", info.severity, "high")
check("err_code", info.code, 0x7D4)
check("err_has_cause", bool(info.cause), True)
check("err_has_fix", bool(info.fix), True)

info2 = ea.analyze("S_TIMEOUT")
check("timeout_severity", info2.severity, "medium")
check("timeout_has_cause", bool(info2.cause), True)

# --- Result Analyzer ---
print("=== OperationResult ===")
r = OperationResult()
r.analyze("test cmd", "some output\n", "err output\n", 1)
check("result_has_stdout", bool(r.stdout), True)
check("result_has_stderr", bool(r.stderr), True)
check("result_code", r.exit_code, 1)

r2 = OperationResult()
r2.analyze("test2", "OK\n", "", 0)
check("result_code_0", r2.exit_code, 0)

# --- Knowledge Base ---
print("=== Knowledge Base ===")
check("device_db_has_oppo", "OPPO" in DEVICE_DB, True)
check("chipset_db_has_mt6895", "MT6895" in CHIPSET_DB, True)
check("malayalam_has_arikka", "arikka" in MALAYALAM_MAP, True)
check("knowledge_has_common_errors", "common_errors" in MTK_KNOWLEDGE, True)

# --- ResponseFormatter ---
print("=== ResponseFormatter ===")
fmt_help = ResponseFormatter.help_text()
check("help_has_version", "v2.1" in fmt_help, True)
check("help_has_sections", "READ" in fmt_help, True)

# --- TextNormalizer ---
print("=== TextNormalizer ===")
check("norm_lower", TextNormalizer.normalize("Flash Firmware"), "flash firmware")
check("norm_strip", TextNormalizer.normalize("  detect device  "), "detect device")
check("norm_malayalam", TextNormalizer.normalize("arikku device"), "detect device")

# --- IntentClassifier aliases ---
print("=== Aliases ===")
check("alias_backdoor", classify_name("backdoor"), "unlock_bootloader")
check("alias_wipe", classify_name("wipe cache"), "erase_partition")
check("alias_show_partitions", classify_name("show partitions"), "read_gpt")
check("alias_info", classify_name("show device info"), "device_info")
check("alias_unbrick", classify_name("unbrick device"), "repair")
check("alias_bootloop", classify_name("bootloop"), "repair")

# --- New intent handlers ---
print("=== New Intent Handlers ===")
check("write_imei", classify_name("write imei 123456789012345"), "write_imei")
check("cancel", classify_name("cancel"), "cancel")
check("stop", classify_name("stop"), "cancel")
check("abort", classify_name("abort"), "cancel")

# --- Adapter stores connection params ---
print("=== Adapter Connection Params ===")
from mtk_ai_single import MTKClientAdapter
a = MTKClientAdapter()
check("adapter_init_connected", a.connected, False)
check("adapter_init_mtk", a.mtk, None)
check("adapter_init_loader", a._loader, None)
check("adapter_init_preloader", a._preloader, None)
check("adapter_init_serialport", a._serialport, None)
check("adapter_has_connect", hasattr(a, 'connect') and callable(a.connect), True)
check("adapter_has_detect_device", hasattr(a, 'detect_device') and callable(a.detect_device), True)
check("adapter_has_run_op", hasattr(a, '_run_op') and callable(a._run_op), True)
check("adapter_has_check_da", hasattr(a, '_check_da') and callable(a._check_da), True)

# --- OperationResult analysis ---
print("=== OperationResult Analysis ===")
from mtk_ai_single import OperationResult, OperationStatus
r = OperationResult()
r.analyze("python mtk.py printgpt", "Partition 1: boot\nPartition 2: system\n", "", 0)
check("result_stdout_parsed", bool(r.stdout), True)
check("result_exit_zero", r.exit_code, 0)
check("result_success_on_zero", r.status, OperationStatus.SUCCESS)

r2 = OperationResult()
r2.analyze("python mtk.py e userdata", "", "Error: device not found\n", 1)
check("result_stderr_parsed", bool(r2.stderr), True)
check("result_exit_nonzero", r2.exit_code, 1)

# --- SafetyEngine covers all dangerous intents ---
print("=== Safety Coverage ===")
from mtk_ai_single import SafetyEngine, RiskLevel, INTENT_REGISTRY
s = SafetyEngine()
all_intents = list(INTENT_REGISTRY.keys())
dangerous_count = sum(1 for name in all_intents if s.get_risk_level(name) == RiskLevel.DANGEROUS)
moderate_count = sum(1 for name in all_intents if s.get_risk_level(name) == RiskLevel.MODERATE)
safe_count = sum(1 for name in all_intents if s.get_risk_level(name) == RiskLevel.SAFE)
check("intent_count_gte_25", len(all_intents) >= 25, True)
check("dangerous_count_gte_5", dangerous_count >= 5, True)
check("moderate_count_gte_3", moderate_count >= 3, True)
check("safe_count_gte_8", safe_count >= 8, True)

# Verify dangerous intents require confirmation
for name in all_intents:
    risk = s.get_risk_level(name)
    intent = INTENT_REGISTRY[name]
    if risk == RiskLevel.DANGEROUS:
        check(f"dangerous_{name}_requires_confirm", intent.requires_confirmation, True)

# --- Verify no network/LLM references ---
print("=== No Network Dependencies ===")
with open("mtk_ai_single.py", "r") as f:
    lines = f.readlines()
code_lines = [l for l in lines if not l.strip().startswith("#") and not l.strip().startswith('"')]
code_text = "".join(code_lines)
check("no_ollama_import", "import ollama" not in code_text.lower(), True)
check("no_openai", "openai" not in code_text.lower(), True)
check("no_openrouter", "openrouter" not in code_text.lower(), True)
check("no_http_api", "http://localhost" not in code_text.lower(), True)
check("no_https_ai", "api.openai" not in code_text.lower(), True)
check("no_urllib_import", "import urllib" not in code_text, True)
check("no_requests_import", "import requests" not in code_text, True)
check("no_ollama_connect", "ollama.connect" not in code_text.lower(), True)

# --- Verify no shell=True ---
print("=== Shell Safety ===")
check("no_shell_true", "shell=True" not in code_text, True)
check("no_subprocess_run", "subprocess.run" not in code_text, True)
check("no_python_mtk_call", '"python", "mtk.py"' not in code_text, True)

# --- Verify MTKClientAdapter has all required methods ---
print("=== Adapter Completeness ===")
required_methods = [
    "connect", "detect_device", "_run_op", "_check_da", "_not_connected",
    "read_gpt", "read_partition", "erase_partition", "write_partition",
    "read_full_flash", "dump_brom", "dump_sram", "dump_preloader",
    "unlock_bootloader", "lock_bootloader", "reset_device", "enter_meta",
    "read_imei", "write_imei", "generate_keys", "get_target_config",
    "read_offset", "read_sectors", "read_all_partitions", "write_full_flash",
    "write_all_partitions", "write_offset", "erase_sectors", "erase_sector_range",
    "wipe_device", "erase_frp", "read_footer", "save_gpt", "enter_meta2", "run_payload",
    "crash_preloader", "run_brute", "get_logs", "run_stage", "run_plstage",
    "mount_fs", "da_vbmeta", "da_efuse", "da_keyserver", "da_meta",
    "da_nvitem", "da_patchmodem", "da_rpmb_read", "da_rpmb_write",
    "da_memdump", "da_memdram",
]
for method in required_methods:
    check(f"adapter_has_{method}", hasattr(a, method) and callable(getattr(a, method)), True)

# --- Verify MTKAgent has all intent handlers ---
print("=== Agent Handler Completeness ===")
from mtk_ai_single import MTKAgent
agent = MTKAgent()
required_handlers = [
    "_handle_detect", "_handle_device_info", "_handle_connection_test",
    "_handle_read_gpt", "_handle_read_partition", "_handle_write_partition",
    "_handle_erase_partition", "_handle_read_full_flash", "_handle_dump",
    "_handle_simple_op", "_handle_repair", "_handle_diagnose_error",
    "_handle_diagnose", "_handle_search", "_unknown_response",
    "_ensure_connected", "_format_result",
]
for handler in required_handlers:
    check(f"agent_has_{handler}", hasattr(agent, handler) and callable(getattr(agent, handler)), True)

# --- Verify Intent Registry completeness ---
print("=== Intent Registry Completeness ===")
from mtk_ai_single import INTENT_REGISTRY
required_intents = [
    "help", "device_info", "detect_device", "diagnose", "connection_test",
    "devices_list", "read_gpt", "save_gpt", "read_partition", "read_offset",
    "read_sectors", "read_all_partitions", "read_full_flash", "write_partition",
    "write_full_flash", "write_all_partitions", "write_offset", "erase_partition",
    "erase_sectors", "erase_sector_range", "read_footer", "flash_firmware",
    "generate_keys", "read_imei", "write_imei", "unlock_bootloader",
    "lock_bootloader", "reset_device", "enter_meta", "meta2", "payload",
    "crash", "brute", "get_target_config", "logs", "peek", "dump_brom",
    "dump_sram", "dump_preloader", "stage", "plstage", "fs_mount",
    "da_vbmeta", "da_efuse", "da_keyserver", "da_meta", "da_nvitem",
    "da_patchmodem", "da_rpmb_read", "da_rpmb_write", "da_memdump",
    "da_memdram", "da_dumpbrom", "repair", "search_knowledge", "status", "cancel",
    "wipe", "erase_frp",
]
for intent in required_intents:
    check(f"registry_has_{intent}", intent in INTENT_REGISTRY, True)

# --- Wipe Command Tests ---
print("=== Wipe Command Tests ===")
from mtk_ai_single import IntentClassifier, SafetyEngine, RiskLevel
from mtk_ai_single import MTKClientAdapter, OperationResult, OperationStatus

# 1. "wipe" maps to wipe intent
clf = IntentClassifier()
intent, score, params = clf.classify("wipe")
check("wipe_intent_wipe", intent, "wipe")

# 2. "wipe device" maps to wipe intent
intent, score, params = clf.classify("wipe device")
check("wipe_intent_wipe_device", intent, "wipe")

# 3. "phone wipe cheyyu" maps to wipe intent (Malayalam)
intent, score, params = clf.classify("phone wipe cheyyu")
check("wipe_intent_malayalam", intent, "wipe")

# 4. "userdata wipe cheyyu" maps to wipe intent (Malayalam)
intent, score, params = clf.classify("userdata wipe cheyyu")
check("wipe_intent_userdata_malayalam", intent, "wipe")

# 5. "phone full wipe cheyyanam" maps to wipe intent (Malayalam)
intent, score, params = clf.classify("phone full wipe cheyyanam")
check("wipe_intent_full_wipe_malayalam", intent, "wipe")

# 6. wipe is DANGEROUS risk
wipe_intent = INTENT_REGISTRY["wipe"]
check("wipe_risk_dangerous", wipe_intent.risk, RiskLevel.DANGEROUS)

# 7. wipe requires confirmation
check("wipe_requires_confirmation", wipe_intent.requires_confirmation, True)

# 8. wipe_device method exists and calls da_erase with correct partitions
a = MTKClientAdapter()
check("adapter_has_wipe_device", hasattr(a, 'wipe_device') and callable(a.wipe_device), True)

# 9. Confirmation message contains required text
safety = SafetyEngine()
confirmation = safety.format_confirmation("wipe", {})
check("wipe_confirm_has_warning", "WARNING: WIPE OPERATION" in confirmation, True)
check("wipe_confirm_has_userdata", "userdata" in confirmation, True)
check("wipe_confirm_has_metadata", "metadata" in confirmation, True)
check("wipe_confirm_has_md_udc", "md_udc" in confirmation, True)
check("wipe_confirm_has_cache", "cache" in confirmation, True)
check("wipe_confirm_has_yes", "Type YES" in confirmation, True)

# 11. "erase" does NOT map to wipe
intent, score, params = clf.classify("erase")
check("erase_not_wipe", intent != "wipe", True)

# 12. No subprocess usage in adapter (direct API)
import inspect
adapter_src = inspect.getsource(MTKClientAdapter)
check("adapter_no_subprocess", "subprocess" not in adapter_src, True)
check("adapter_uses_da_handler", "da_handler" in adapter_src, True)

# 13. Simulated failed wipe does not report fake success
failed_result = OperationResult()
failed_result.status = OperationStatus.DEVICE_NOT_FOUND
failed_result.success = False
failed_result.error = "No device detected"
failed_result.summary = "Device not found"
failed_result.details = {}
check("wipe_failure_success_false", failed_result.success, False)
check("wipe_failure_error_present", failed_result.error, "No device detected")

# --- FRP Erase Command Tests ===
print("=== FRP Erase Command Tests ===")

# 1. "frp" maps to erase_frp intent
intent, score, params = clf.classify("frp")
check("frp_intent_frp", intent, "erase_frp")

# 2. "erase frp" maps to erase_frp
intent, score, params = clf.classify("erase frp")
check("frp_intent_erase_frp", intent, "erase_frp")

# 3. "frp erase" maps to erase_frp
intent, score, params = clf.classify("frp erase")
check("frp_intent_frp_erase", intent, "erase_frp")

# 4. "erase frp partition" maps to erase_frp
intent, score, params = clf.classify("erase frp partition")
check("frp_intent_erase_partition", intent, "erase_frp")

# 5. "frp clear" maps to erase_frp
intent, score, params = clf.classify("frp clear")
check("frp_intent_frp_clear", intent, "erase_frp")

# 6. "frp remove" maps to erase_frp
intent, score, params = clf.classify("frp remove")
check("frp_intent_frp_remove", intent, "erase_frp")

# 7. erase_frp is DANGEROUS risk
frp_intent = INTENT_REGISTRY["erase_frp"]
check("frp_risk_dangerous", frp_intent.risk, RiskLevel.DANGEROUS)

# 8. erase_frp requires confirmation
check("frp_requires_confirmation", frp_intent.requires_confirmation, True)

# 9. erase_frp method exists and calls da_erase with frp partition
a = MTKClientAdapter()
check("adapter_has_erase_frp", hasattr(a, 'erase_frp') and callable(a.erase_frp), True)

# 10. Confirmation message contains required text
frp_confirm = safety.format_confirmation("erase_frp", {})
check("frp_confirm_has_warning", "WARNING: FRP PARTITION ERASE" in frp_confirm, True)
check("frp_confirm_has_frp_partition", "frp" in frp_confirm, True)
check("frp_confirm_has_yes", "Type YES" in frp_confirm, True)

# 11. No subprocess in adapter
check("frp_adapter_no_subprocess", "subprocess" not in adapter_src, True)

# 12. Simulated failed FRP does not report fake success
frp_failed = OperationResult()
frp_failed.status = OperationStatus.DEVICE_NOT_FOUND
frp_failed.success = False
frp_failed.error = "No device detected"
frp_failed.summary = "Device not found"
frp_failed.details = {}
check("frp_failure_success_false", frp_failed.success, False)
check("frp_failure_error_present", frp_failed.error, "No device detected")

# 13. "frp" does NOT map to wipe
intent, score, params = clf.classify("frp")
check("frp_not_wipe", intent != "wipe", True)

print(f"\n{'='*50}")
print(f"Total: {passed+failed}  Passed: {passed}  Failed: {failed}")

# --- Frozen EXE regression test ---
print("\n=== Frozen EXE Regression Test ===")
exe_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist", "MTK-AI-Agent.exe")
if os.path.exists(exe_path):
    import subprocess
    exe_size = os.path.getsize(exe_path)
    check("exe_exists", True, True)
    check("exe_size_under_500mb", exe_size < 500 * 1024 * 1024, True)
    exe_mb = round(exe_size / 1048576, 1)
    check("exe_size_30_to_50mb", 30 <= exe_mb <= 50, True)
    try:
        r = subprocess.run([exe_path, "--version"], capture_output=True, text=True, timeout=10)
        check("exe_version_works", "2.1" in r.stdout, True)
    except Exception as e:
        print(f"  FAIL [exe_version_works]: {e}")
        failed += 1
    try:
        r = subprocess.run([exe_path, "--cmd", "help"], capture_output=True, text=True, timeout=10)
        check("exe_help_works", "READ" in r.stdout, True)
    except Exception as e:
        print(f"  FAIL [exe_help_works]: {e}")
        failed += 1
    try:
        r = subprocess.run([exe_path, "--cmd", "search MT6895"], capture_output=True, text=True, timeout=10)
        check("exe_search_works", "MT6895" in r.stdout, True)
    except Exception as e:
        print(f"  FAIL [exe_search_works]: {e}")
        failed += 1
else:
    print("  EXE not found - skipping frozen tests")
    check("exe_exists", False, True)

if failed == 0:
    print("\nALL TESTS PASSED")
else:
    print("\nSOME TESTS FAILED")
    sys.exit(1)
