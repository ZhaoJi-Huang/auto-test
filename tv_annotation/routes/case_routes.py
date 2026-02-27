"""
用例管理路由
支持 Jira 导入、自定义创建、索引管理等操作
"""

import os
import json
import socket
import tempfile
import logging
from datetime import datetime

from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)


def load_index(scripts_repo_path):
    """读取 index.json，不存在则返回空列表"""
    path = os.path.join(scripts_repo_path, "index.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_index(scripts_repo_path, index_data):
    """原子写入 index.json"""
    path = os.path.join(scripts_repo_path, "index.json")
    os.makedirs(scripts_repo_path, exist_ok=True)
    # 写入临时文件再 rename，保证原子性
    fd, tmp_path = tempfile.mkstemp(dir=scripts_repo_path, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(index_data, f, ensure_ascii=False, indent=2)
        # Windows 上 rename 目标存在时会失败，需要先删除
        if os.path.exists(path):
            os.replace(tmp_path, path)
        else:
            os.rename(tmp_path, path)
    except Exception:
        # 清理临时文件
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def update_index_entry(scripts_repo_path, entry):
    """更新或新增索引条目"""
    index = load_index(scripts_repo_path)
    # 查找已有条目
    for i, item in enumerate(index):
        if item.get("key") == entry.get("key"):
            index[i] = entry
            save_index(scripts_repo_path, index)
            return
    # 新增
    index.append(entry)
    save_index(scripts_repo_path, index)


def _check_has_recording(scripts_repo_path, key):
    """检查用例是否有录制数据"""
    steps_path = os.path.join(scripts_repo_path, key, "steps.json")
    return os.path.exists(steps_path)


def _build_index_entry(scripts_repo_path, case_data):
    """从 case.json 数据构建索引条目"""
    key = case_data.get("key", "")
    source = case_data.get("source", "")

    # 用例名称：Jira 用例用 summary，自定义用例用 name
    if source == "jira":
        name = case_data.get("summary", "")
    else:
        name = case_data.get("name", "")

    entry = {
        "key": key,
        "name": name,
        "source": source,
        "has_recording": _check_has_recording(scripts_repo_path, key),
        "last_replay": None,
        "last_replay_result": None,
    }

    if source == "jira":
        entry["priority"] = case_data.get("priority", "")
        entry["imported_at"] = case_data.get("imported_at", "")

    return entry


def _next_local_key(scripts_repo_path):
    """生成下一个 LOCAL 自增序号"""
    index = load_index(scripts_repo_path)
    max_num = 0
    for item in index:
        if item.get("source") == "custom":
            key = item.get("key", "")
            if key.startswith("LOCAL-"):
                try:
                    num = int(key[6:])
                    if num > max_num:
                        max_num = num
                except ValueError:
                    pass
    return f"LOCAL-{max_num + 1:03d}"


def _save_case(scripts_repo_path, key, case_data):
    """保存 case.json 到用例目录"""
    case_dir = os.path.join(scripts_repo_path, key)
    os.makedirs(case_dir, exist_ok=True)
    path = os.path.join(case_dir, "case.json")
    # 原子写入
    fd, tmp_path = tempfile.mkstemp(dir=case_dir, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(case_data, f, ensure_ascii=False, indent=2)
        if os.path.exists(path):
            os.replace(tmp_path, path)
        else:
            os.rename(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def _load_case(scripts_repo_path, key):
    """读取用例的 case.json"""
    path = os.path.join(scripts_repo_path, key, "case.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def create_case_routes(data_dir, scripts_repo_path):
    """创建用例管理路由蓝图

    Args:
        data_dir: 数据根目录
        scripts_repo_path: 脚本仓库路径
    """

    bp = Blueprint("tv_cases", __name__)

    # ========== 用例列表 ==========

    @bp.route("/api/tv/cases", methods=["GET"])
    def list_cases():
        """获取用例列表（从 index.json）"""
        index = load_index(scripts_repo_path)

        # 筛选参数
        keyword = request.args.get("keyword", "").strip()
        source = request.args.get("source", "").strip()
        key_prefix = request.args.get("key_prefix", "").strip()

        result = []
        for item in index:
            # 来源筛选
            if source and item.get("source") != source:
                continue
            # 前缀匹配
            if key_prefix and not item.get("key", "").startswith(key_prefix):
                continue
            # 关键字模糊搜索（匹配 key 或 name）
            if keyword:
                kw = keyword.lower()
                key_match = kw in item.get("key", "").lower()
                name_match = kw in item.get("name", "").lower()
                if not key_match and not name_match:
                    continue
            # 更新录制状态
            item["has_recording"] = _check_has_recording(scripts_repo_path, item.get("key", ""))
            result.append(item)

        return jsonify({"success": True, "data": result})

    # ========== 用例详情 ==========

    @bp.route("/api/tv/cases/<key>", methods=["GET"])
    def get_case(key):
        """获取用例详情（含已录制步骤）"""
        case = _load_case(scripts_repo_path, key)
        if not case:
            return jsonify({"success": False, "error": f"用例 {key} 不存在"}), 404

        # 附带已录制的步骤
        steps_path = os.path.join(scripts_repo_path, key, "steps.json")
        if os.path.exists(steps_path):
            try:
                with open(steps_path, "r", encoding="utf-8") as f:
                    case["recorded_steps"] = json.load(f)
            except Exception:
                case["recorded_steps"] = []
        else:
            case["recorded_steps"] = []

        return jsonify({"success": True, "data": case})

    # ========== JQL 批量导入 ==========

    @bp.route("/api/tv/cases/import/jql", methods=["POST"])
    def import_by_jql():
        """通过 JQL 批量导入用例"""
        data = request.get_json()
        if not data or not data.get("jql"):
            return jsonify({"success": False, "error": "请提供 JQL 查询语句"}), 400

        jql = data["jql"]
        max_results = data.get("max_results", 100)

        try:
            from tv_annotation.jira_client import JiraClient
            client = JiraClient(data_dir)
            cases = client.import_by_jql(jql, max_results=max_results)
        except Exception as e:
            logger.error("JQL 导入失败: %s", e)
            return jsonify({"success": False, "error": f"Jira 导入失败: {e}"}), 500

        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        imported = []
        for case in cases:
            case["imported_at"] = now
            key = case["key"]
            _save_case(scripts_repo_path, key, case)
            entry = _build_index_entry(scripts_repo_path, case)
            update_index_entry(scripts_repo_path, entry)
            imported.append({"key": key, "summary": case.get("summary", "")})

        return jsonify({
            "success": True,
            "message": f"成功导入 {len(imported)} 条用例",
            "data": {"imported": len(imported), "cases": imported},
        })

    # ========== 单条导入 ==========

    @bp.route("/api/tv/cases/import/key", methods=["POST"])
    def import_by_key():
        """通过 Jira Key 导入单条用例"""
        data = request.get_json()
        if not data or not data.get("key"):
            return jsonify({"success": False, "error": "请提供 Jira 用例编号"}), 400

        jira_key = data["key"].strip()

        try:
            from tv_annotation.jira_client import JiraClient
            client = JiraClient(data_dir)
            case = client.import_by_key(jira_key)
        except Exception as e:
            logger.error("单条导入失败 (%s): %s", jira_key, e)
            return jsonify({"success": False, "error": f"导入失败: {e}"}), 500

        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        case["imported_at"] = now
        _save_case(scripts_repo_path, case["key"], case)
        entry = _build_index_entry(scripts_repo_path, case)
        update_index_entry(scripts_repo_path, entry)

        return jsonify({
            "success": True,
            "message": f"成功导入用例 {case['key']}",
            "data": case,
        })

    # ========== 重新同步 ==========

    @bp.route("/api/tv/cases/sync/<key>", methods=["POST"])
    def sync_case(key):
        """重新同步 Jira 字段（不影响 steps.json）"""
        existing = _load_case(scripts_repo_path, key)
        if not existing:
            return jsonify({"success": False, "error": f"用例 {key} 不存在"}), 404
        if existing.get("source") != "jira":
            return jsonify({"success": False, "error": "仅 Jira 用例支持同步"}), 400

        try:
            from tv_annotation.jira_client import JiraClient
            client = JiraClient(data_dir)
            updated = client.sync_case(key)
        except Exception as e:
            logger.error("同步失败 (%s): %s", key, e)
            return jsonify({"success": False, "error": f"同步失败: {e}"}), 500

        # 保留原有的 imported_at
        updated["imported_at"] = existing.get("imported_at", "")
        _save_case(scripts_repo_path, key, updated)
        entry = _build_index_entry(scripts_repo_path, updated)
        update_index_entry(scripts_repo_path, entry)

        return jsonify({
            "success": True,
            "message": f"用例 {key} 已同步",
            "data": updated,
        })

    # ========== 创建自定义用例 ==========

    @bp.route("/api/tv/cases/create", methods=["POST"])
    def create_custom_case():
        """创建自定义用例"""
        data = request.get_json()
        if not data or not data.get("name"):
            return jsonify({"success": False, "error": "请提供用例名称"}), 400

        key = _next_local_key(scripts_repo_path)
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

        case = {
            "key": key,
            "source": "custom",
            "name": data["name"].strip(),
            "description": data.get("description", "").strip(),
            "created_at": now,
            "created_by": socket.gethostname(),
        }

        _save_case(scripts_repo_path, key, case)
        entry = _build_index_entry(scripts_repo_path, case)
        update_index_entry(scripts_repo_path, entry)

        return jsonify({
            "success": True,
            "message": f"自定义用例 {key} 已创建",
            "data": case,
        })

    # ========== 删除用例 ==========

    @bp.route("/api/tv/cases/<key>", methods=["DELETE"])
    def delete_case(key):
        """删除用例"""
        case_dir = os.path.join(scripts_repo_path, key)
        if not os.path.exists(case_dir):
            return jsonify({"success": False, "error": f"用例 {key} 不存在"}), 404

        # 删除用例目录
        import shutil
        shutil.rmtree(case_dir, ignore_errors=True)

        # 从索引中移除
        index = load_index(scripts_repo_path)
        index = [item for item in index if item.get("key") != key]
        save_index(scripts_repo_path, index)

        return jsonify({"success": True, "message": f"用例 {key} 已删除"})

    # ========== Jira 配置管理 ==========

    @bp.route("/api/tv/jira/config", methods=["GET"])
    def get_jira_config():
        """获取 Jira 配置（脱敏）"""
        from common.config_manager import load_jira_config
        config = load_jira_config(data_dir)
        if not config:
            return jsonify({"success": True, "data": None})

        # 脱敏处理：authorization 只显示前 10 个字符
        masked = dict(config)
        auth = masked.get("authorization", "")
        if len(auth) > 10:
            masked["authorization"] = auth[:10] + "****"
        return jsonify({"success": True, "data": masked})

    @bp.route("/api/tv/jira/config", methods=["POST"])
    def save_jira_config():
        """保存 Jira 配置"""
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "请求体为空"}), 400
        if not data.get("base_url") or not data.get("authorization"):
            return jsonify({"success": False, "error": "需要 base_url 和 authorization"}), 400

        config = {
            "base_url": data["base_url"].rstrip("/"),
            "authorization": data["authorization"],
        }

        from common.config_manager import save_jira_config as _save_jira
        _save_jira(data_dir, config)

        return jsonify({"success": True, "message": "Jira 配置已保存"})

    return bp
