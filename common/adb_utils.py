"""
ADB 工具函数模块
提供 ADB 命令执行、设备检查、Activity 获取等公共功能
"""
import datetime
import subprocess
import re
from .utils import ADB_PATH


def run_adb(cmd_list, device_serial=None, timeout=30):
    """执行 ADB 命令

    Args:
        cmd_list: 命令参数列表，如 ["shell", "input", "keyevent", "KEYCODE_HOME"]
        device_serial: 设备序列号（TV IP:port），为 None 时不指定设备
        timeout: 超时秒数

    Returns:
        subprocess.CompletedProcess
    """
    prefix = [ADB_PATH]
    if device_serial:
        prefix.extend(["-s", device_serial])
    try:
        flags = 0
        import platform
        if platform.system() == "Windows":
            flags = subprocess.CREATE_NO_WINDOW
        return subprocess.run(
            prefix + cmd_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            creationflags=flags,
        )
    except FileNotFoundError:
        raise RuntimeError("ADB 工具未找到，请检查安装路径")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"ADB 命令超时（{timeout}s）")


def check_adb_device(device_serial):
    """检查 ADB 设备连接状态

    Returns:
        (bool, str): (是否可用, 错误信息)
    """
    # 1. 执行 adb devices
    try:
        result = run_adb(["devices"], timeout=10)
    except RuntimeError as e:
        return False, str(e)

    if result.returncode != 0:
        return False, "adb devices 命令执行失败"

    output = result.stdout.decode("utf-8", errors="ignore")
    lines = output.strip().split("\n")

    # 2. 检查设备是否在列表中
    found = False
    status = None
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0].strip() == device_serial:
            found = True
            status = parts[1].strip()
            break

    if not found:
        return False, f"设备 {device_serial} 未连接，请检查 ADB 连接或 USB/网络"

    if status == "offline":
        return False, f"设备 {device_serial} 处于离线状态"
    if status == "unauthorized":
        return False, f"设备 {device_serial} 未授权，请在设备上确认调试授权"
    if status != "device":
        return False, f"设备 {device_serial} 状态异常: {status}"

    # 3. 验证 shell 可执行
    try:
        result = run_adb(["shell", "echo", "ok"], device_serial=device_serial, timeout=10)
        output = result.stdout.decode("utf-8", errors="ignore").strip()
        if output != "ok":
            return False, "ADB 命令无法执行，请检查设备授权"
    except RuntimeError as e:
        return False, str(e)

    return True, ""


def get_current_activity(device_serial):
    """获取当前 Activity

    通过 dumpsys window | grep mCurrentFocus 获取（设备端 grep，速度更快）

    Returns:
        str: Activity 全限定名，如 "com.example.tv/.MainActivity"，获取失败返回 ""
    """
    import logging
    logger = logging.getLogger(__name__)
    try:
        current = datetime.datetime.now()
        result = run_adb(
            ["shell", "dumpsys window | grep mCurrentFocus"],
            device_serial=device_serial,
            timeout=5,
        )
        output = result.stdout.decode("utf-8", errors="ignore").strip()
        stderr = result.stderr.decode("utf-8", errors="ignore").strip()
        logger.info(f"get_current_activity: time = {datetime.datetime.now()-current},rc={result.returncode}, stdout='{output[:200]}', stderr='{stderr[:100]}'")
        if output:
            # 匹配两种格式：
            # 1. com.tcl.cyberui/com.tcl.cyberui.MainActivity （包名/Activity）
            # 2. com.tcl.settings （仅包名，无 Activity）
            match = re.search(r"mCurrentFocus=Window\{[^}]*\s+(\S+)\}", output)
            if match:
                return match.group(1)
            else:
                logger.warning(f"get_current_activity: 输出不匹配正则: '{output}'")
        else:
            logger.warning(f"get_current_activity: 输出为空, rc={result.returncode}, stderr='{stderr}'")
    except Exception as e:
        logger.warning(f"get_current_activity 异常: {e}")
    return ""


def send_keyevent(device_serial, keycode):
    """发送按键事件

    Args:
        keycode: Android keycode 字符串，如 "KEYCODE_HOME"
    """
    return run_adb(["shell", "input", "keyevent", keycode], device_serial=device_serial)


def list_adb_devices():
    """列出所有已连接的 ADB 设备

    Returns:
        list[dict]: 设备列表，每项包含 serial, status, type (usb/network)
    """
    try:
        result = run_adb(["devices"], timeout=10)
    except RuntimeError:
        return []

    if result.returncode != 0:
        return []

    output = result.stdout.decode("utf-8", errors="ignore")
    devices = []
    for line in output.strip().split("\n")[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            serial = parts[0].strip()
            status = parts[1].strip()
            # 判断连接类型：包含冒号的是网络连接，否则是 USB
            conn_type = "network" if ":" in serial else "usb"
            devices.append({
                "serial": serial,
                "status": status,
                "type": conn_type,
            })
    return devices


def ensure_device_serial(device_config, data_dir=None):
    """确保获取到有效的设备序列号，未配置时自动检测已连接设备

    Args:
        device_config: 设备配置字典（含 tv_ip 字段）
        data_dir: 数据目录（非 None 时自动保存检测到的设备到配置）

    Returns:
        (str, str): (device_serial, message)
            - device_serial 为空字符串表示未找到设备
            - message 包含自动检测信息或错误提示
    """
    serial = device_config.get("tv_ip", "")
    if serial:
        return serial, ""

    # 未配置，尝试自动检测
    devices = list_adb_devices()
    available = [d for d in devices if d["status"] == "device"]
    if not available:
        return "", "未检测到已连接的 ADB 设备，请通过 USB 连接设备或配置设备地址"

    serial = available[0]["serial"]
    conn_type = available[0]["type"]
    type_label = "USB" if conn_type == "usb" else "网络"

    # 自动保存到配置
    device_config["tv_ip"] = serial
    if data_dir:
        try:
            from common.config_manager import save_device_config
            save_device_config(data_dir, device_config)
        except Exception:
            pass

    return serial, f"已自动检测到{type_label}设备 {serial}"


def connect_device(device_serial):
    """连接 ADB 设备（适用于网络 ADB）"""
    try:
        result = run_adb(["connect", device_serial], timeout=10)
        output = result.stdout.decode("utf-8", errors="ignore")
        return "connected" in output.lower() or "already" in output.lower(), output.strip()
    except RuntimeError as e:
        return False, str(e)
