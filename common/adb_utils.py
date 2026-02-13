"""
ADB 工具函数模块
提供 ADB 命令执行、设备检查、Activity 获取等公共功能
"""

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

    通过 dumpsys window 获取 mCurrentFocus

    Returns:
        str: Activity 全限定名，如 "com.example.tv/.MainActivity"，获取失败返回 ""
    """
    try:
        result = run_adb(
            ["shell", "dumpsys", "window", "windows"],
            device_serial=device_serial,
            timeout=5,
        )
        output = result.stdout.decode("utf-8", errors="ignore")
        # 匹配 mCurrentFocus=Window{...  <package>/<activity>}
        match = re.search(r"mCurrentFocus=Window\{[^}]*\s+(\S+/\S+)\}", output)
        if match:
            return match.group(1)
        # 备选：匹配 mFocusedApp
        match = re.search(r"mFocusedApp=.*\{[^}]*\s+(\S+/\S+)\}", output)
        if match:
            return match.group(1)
    except Exception:
        pass
    return ""


def send_keyevent(device_serial, keycode):
    """发送按键事件

    Args:
        keycode: Android keycode 字符串，如 "KEYCODE_HOME"
    """
    return run_adb(["shell", "input", "keyevent", keycode], device_serial=device_serial)


def connect_device(device_serial):
    """连接 ADB 设备（适用于网络 ADB）"""
    try:
        result = run_adb(["connect", device_serial], timeout=10)
        output = result.stdout.decode("utf-8", errors="ignore")
        return "connected" in output.lower() or "already" in output.lower(), output.strip()
    except RuntimeError as e:
        return False, str(e)
