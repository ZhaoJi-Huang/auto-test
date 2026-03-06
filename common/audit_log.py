"""
审计日志模块
记录关键业务操作（录制/回放/删除/配置变更等），独立于技术日志
"""

import json
import os
import threading
from datetime import datetime

_lock = threading.Lock()
_data_dir = None


def init_audit_log(data_dir):
    """初始化审计日志目录"""
    global _data_dir
    _data_dir = data_dir


def audit_log(action, case_key="", detail=""):
    """写入一条审计日志

    Args:
        action: 操作类型，如 "录制开始"、"回放完成"、"用例删除"
        case_key: 关联的用例/计划 key
        detail: 补充信息
    """
    if not _data_dir:
        return
    entry = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "action": action,
        "case": case_key,
    }
    if detail:
        entry["detail"] = detail
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    with _lock:
        try:
            path = os.path.join(_data_dir, "audit.log")
            with open(path, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass
