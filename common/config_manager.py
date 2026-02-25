"""
配置管理模块
管理 app_config.json、jira_config.json、device_config.json
"""

import os
import json

# 项目根目录（backend/）
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _resolve_path(path):
    """将相对路径（相对于 BACKEND_DIR）解析为绝对路径"""
    if os.path.isabs(path):
        return path
    return os.path.normpath(os.path.join(BACKEND_DIR, path))


def load_app_config():
    """加载 app_config.json，返回解析后的配置字典

    Returns:
        dict: {
            "data_dir": 绝对路径,
            "scripts_repo_path": 绝对路径,
            "_raw": 原始 JSON 内容
        }
    """
    config_path = os.path.join(BACKEND_DIR, "app_config.json")
    defaults = {
        "data_dir": "./data",
        "scripts_repo_path": "./tv-test-scripts"
    }

    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception:
            raw = defaults.copy()
    else:
        raw = defaults.copy()
        # 写入默认配置
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(raw, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    return {
        "data_dir": _resolve_path(raw.get("data_dir", defaults["data_dir"])),
        "scripts_repo_path": _resolve_path(raw.get("scripts_repo_path", defaults["scripts_repo_path"])),
        "_raw": raw,
    }


# ---------- Jira 配置 ----------

def load_jira_config(data_dir):
    """加载 jira_config.json（位于 data_dir 下）

    Returns:
        dict 或 None
    """
    path = os.path.join(data_dir, "jira_config.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_jira_config(data_dir, config):
    """保存 jira_config.json"""
    path = os.path.join(data_dir, "jira_config.json")
    os.makedirs(data_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


# ---------- 设备配置 ----------

DEFAULT_DEVICE_CONFIG = {
    "tv_ip": "",
    "serial_port": "",
    "remote_port": "",
    "device_id": 0,
    "key_event_device": ""
}


def load_device_config(data_dir):
    """加载 device_config.json（位于 data_dir 下）"""
    path = os.path.join(data_dir, "device_config.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    # 返回默认并写入
    config = DEFAULT_DEVICE_CONFIG.copy()
    save_device_config(data_dir, config)
    return config


def save_device_config(data_dir, config):
    """保存 device_config.json"""
    path = os.path.join(data_dir, "device_config.json")
    os.makedirs(data_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
