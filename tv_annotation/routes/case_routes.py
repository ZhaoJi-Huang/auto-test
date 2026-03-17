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
from common.audit_log import audit_log

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


def get_case_dir(scripts_repo_path, key, index=None):
    """根据 index.json 中的 module 字段定位用例目录

    Args:
        scripts_repo_path: 脚本仓库根路径
        key: 用例 key
        index: 可选，已加载的 index 数据（避免重复读取）

    Returns:
        用例目录的绝对路径
    """
    if index is None:
        index = load_index(scripts_repo_path)
    module = ""
    for item in index:
        if item.get("key") == key:
            module = item.get("module") or ""
            break
    if module:
        return os.path.join(scripts_repo_path, module, key)
    return os.path.join(scripts_repo_path, key)


def _check_has_recording(scripts_repo_path, key, index=None):
    """检查用例是否有录制数据"""
    case_dir = get_case_dir(scripts_repo_path, key, index)
    steps_path = os.path.join(case_dir, "steps.json")
    return os.path.exists(steps_path)


def _build_index_entry(scripts_repo_path, case_data, module=None):
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
        "module": module or "",
        "has_recording": False,
        "last_replay": None,
        "last_replay_result": None,
    }

    # has_recording 需要知道 module 来定位目录
    if module:
        steps_path = os.path.join(scripts_repo_path, module, key, "steps.json")
    else:
        steps_path = os.path.join(scripts_repo_path, key, "steps.json")
    entry["has_recording"] = os.path.exists(steps_path)

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


def _save_case(scripts_repo_path, key, case_data, module=None):
    """保存 case.json 到用例目录"""
    if module:
        case_dir = os.path.join(scripts_repo_path, module, key)
    else:
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


def rebuild_index(scripts_repo_path):
    """扫描磁盘上的 case 目录，将未在 index.json 中的用例补充进去

    Returns:
        int: 新增的用例数量
    """
    index = load_index(scripts_repo_path)
    existing_keys = {item.get("key") for item in index}
    added = 0

    # 需要排除的目录
    skip_dirs = {"plans", ".git", "__pycache__", "node_modules"}

    def _scan_dir(base_dir, module=""):
        """扫描目录下的 case.json 文件"""
        nonlocal added
        if not os.path.isdir(base_dir):
            return
        for name in os.listdir(base_dir):
            if name in skip_dirs or name.startswith("."):
                continue
            entry_dir = os.path.join(base_dir, name)
            if not os.path.isdir(entry_dir):
                continue
            case_json = os.path.join(entry_dir, "case.json")
            if os.path.isfile(case_json):
                # 这是一个用例目录
                if name not in existing_keys:
                    try:
                        with open(case_json, "r", encoding="utf-8") as f:
                            case_data = json.load(f)
                        entry = _build_index_entry(scripts_repo_path, case_data, module or None)
                        index.append(entry)
                        existing_keys.add(name)
                        added += 1
                    except Exception as e:
                        logger.warning("扫描用例 %s 失败: %s", name, e)
            else:
                # 可能是模块目录，递归扫描
                _scan_dir(entry_dir, module=name)

    _scan_dir(scripts_repo_path)

    if added > 0:
        save_index(scripts_repo_path, index)
        logger.info("索引重建：新增 %d 个用例", added)

    return added


def _load_case(scripts_repo_path, key, index=None):
    """读取用例的 case.json"""
    case_dir = get_case_dir(scripts_repo_path, key, index)
    path = os.path.join(case_dir, "case.json")
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

        # 筛选参数
        module = request.args.get("module", "").strip()

        result = []
        for item in index:
            # 来源筛选
            if source and item.get("source") != source:
                continue
            # 前缀匹配
            if key_prefix and not item.get("key", "").startswith(key_prefix):
                continue
            # 模块筛选
            if module and (item.get("module") or "") != module:
                continue
            # 关键字模糊搜索（匹配 key 或 name）
            if keyword:
                kw = keyword.lower()
                key_match = kw in item.get("key", "").lower()
                name_match = kw in item.get("name", "").lower()
                if not key_match and not name_match:
                    continue
            # 更新录制状态
            item["has_recording"] = _check_has_recording(scripts_repo_path, item.get("key", ""), index)
            result.append(item)

        return jsonify({"success": True, "data": result})

    # ========== 用例详情 ==========

    @bp.route("/api/tv/cases/<key>", methods=["GET"])
    def get_case(key):
        """获取用例详情（含已录制步骤）"""
        index = load_index(scripts_repo_path)
        case = _load_case(scripts_repo_path, key, index)
        if not case:
            return jsonify({"success": False, "error": f"用例 {key} 不存在"}), 404

        # 附带已录制的步骤
        case_dir = get_case_dir(scripts_repo_path, key, index)
        steps_path = os.path.join(case_dir, "steps.json")
        if os.path.exists(steps_path):
            try:
                with open(steps_path, "r", encoding="utf-8") as f:
                    case["recorded_steps"] = json.load(f)
            except Exception:
                case["recorded_steps"] = []
        else:
            case["recorded_steps"] = []

        # 附带 module 信息
        for item in index:
            if item.get("key") == key:
                case["module"] = item.get("module") or ""
                break

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
        module = data.get("module", "").strip()
        imported = []
        for case in cases:
            case["imported_at"] = now
            key = case["key"]
            _save_case(scripts_repo_path, key, case, module=module)
            entry = _build_index_entry(scripts_repo_path, case, module=module)
            update_index_entry(scripts_repo_path, entry)
            imported.append({"key": key, "summary": case.get("summary", "")})

        audit_log("JQL批量导入", "", f"导入{len(imported)}条用例")
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
        module = data.get("module", "").strip()
        case["imported_at"] = now
        _save_case(scripts_repo_path, case["key"], case, module=module)
        entry = _build_index_entry(scripts_repo_path, case, module=module)
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
        module = data.get("module", "").strip()

        case = {
            "key": key,
            "source": "custom",
            "name": data["name"].strip(),
            "description": data.get("description", "").strip(),
            "precondition": data.get("precondition", "").strip(),
            "test_steps": data.get("test_steps") or [],
            "created_at": now,
            "created_by": socket.gethostname(),
        }

        _save_case(scripts_repo_path, key, case, module=module)
        entry = _build_index_entry(scripts_repo_path, case, module=module)
        update_index_entry(scripts_repo_path, entry)

        audit_log("用例创建", key, case["name"])
        return jsonify({
            "success": True,
            "message": f"自定义用例 {key} 已创建",
            "data": case,
        })

    # ========== 编辑用例 ==========

    @bp.route("/api/tv/cases/<key>", methods=["PUT"])
    def update_case(key):
        """编辑用例（仅自定义用例可编辑全部字段，Jira 用例仅可编辑补充字段）"""
        index = load_index(scripts_repo_path)
        existing = _load_case(scripts_repo_path, key, index)
        if not existing:
            return jsonify({"success": False, "error": f"用例 {key} 不存在"}), 404

        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "请求体为空"}), 400

        # 查找当前 module
        old_module = ""
        for item in index:
            if item.get("key") == key:
                old_module = item.get("module") or ""
                break

        # 可编辑字段
        if existing.get("source") == "custom":
            if "name" in data:
                existing["name"] = data["name"].strip()
            if "description" in data:
                existing["description"] = data.get("description", "").strip()
        # 通用可编辑字段
        if "precondition" in data:
            existing["precondition"] = data.get("precondition", "").strip()
        if "test_steps" in data:
            existing["test_steps"] = data.get("test_steps") or []

        existing["updated_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

        # 处理模块变更（移动目录）
        new_module = data.get("module", old_module)
        if isinstance(new_module, str):
            new_module = new_module.strip()
        else:
            new_module = old_module

        if new_module != old_module:
            import shutil
            old_dir = get_case_dir(scripts_repo_path, key, index)
            if new_module:
                new_dir = os.path.join(scripts_repo_path, new_module, key)
            else:
                new_dir = os.path.join(scripts_repo_path, key)
            if os.path.exists(old_dir):
                os.makedirs(os.path.dirname(new_dir), exist_ok=True)
                shutil.move(old_dir, new_dir)

        _save_case(scripts_repo_path, key, existing, module=new_module)
        entry = _build_index_entry(scripts_repo_path, existing, module=new_module)
        update_index_entry(scripts_repo_path, entry)

        return jsonify({
            "success": True,
            "message": f"用例 {key} 已更新",
            "data": existing,
        })

    # ========== 复制用例 ==========

    @bp.route("/api/tv/cases/<key>/copy", methods=["POST"])
    def copy_case(key):
        """复制用例为新的自定义用例"""
        index = load_index(scripts_repo_path)
        existing = _load_case(scripts_repo_path, key, index)
        if not existing:
            return jsonify({"success": False, "error": f"用例 {key} 不存在"}), 404

        # 继承原用例的 module
        old_module = ""
        for item in index:
            if item.get("key") == key:
                old_module = item.get("module") or ""
                break

        new_key = _next_local_key(scripts_repo_path)
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

        # 构建新用例，复制关键字段
        new_case = {
            "key": new_key,
            "source": "custom",
            "name": (existing.get("name") or existing.get("summary", "")) + " (副本)",
            "description": existing.get("description", ""),
            "precondition": existing.get("precondition", ""),
            "test_steps": existing.get("test_steps") or [],
            "created_at": now,
            "created_by": socket.gethostname(),
        }

        _save_case(scripts_repo_path, new_key, new_case, module=old_module)
        entry = _build_index_entry(scripts_repo_path, new_case, module=old_module)
        update_index_entry(scripts_repo_path, entry)

        # 同时复制录制步骤（如果有的话）
        src_dir = get_case_dir(scripts_repo_path, key, index)
        src_steps = os.path.join(src_dir, "steps.json")
        if os.path.exists(src_steps):
            import shutil
            if old_module:
                dst_steps = os.path.join(scripts_repo_path, old_module, new_key, "steps.json")
            else:
                dst_steps = os.path.join(scripts_repo_path, new_key, "steps.json")
            shutil.copy2(src_steps, dst_steps)
            # 更新索引中的录制状态
            entry["has_recording"] = True
            update_index_entry(scripts_repo_path, entry)

        return jsonify({
            "success": True,
            "message": f"用例已复制为 {new_key}",
            "data": new_case,
        })

    # ========== 删除用例 ==========

    @bp.route("/api/tv/cases/<key>", methods=["DELETE"])
    def delete_case(key):
        """删除用例"""
        index = load_index(scripts_repo_path)
        case_dir = get_case_dir(scripts_repo_path, key, index)
        if not os.path.exists(case_dir):
            return jsonify({"success": False, "error": f"用例 {key} 不存在"}), 404

        # 删除用例目录
        import shutil
        shutil.rmtree(case_dir, ignore_errors=True)

        # 从索引中移除
        index = load_index(scripts_repo_path)
        index = [item for item in index if item.get("key") != key]
        save_index(scripts_repo_path, index)

        audit_log("用例删除", key)
        return jsonify({"success": True, "message": f"用例 {key} 已删除"})

    # ========== Jira 配置管理 ==========

    # ========== 模块管理 ==========

    @bp.route("/api/tv/modules", methods=["GET"])
    def list_modules():
        """获取所有模块列表"""
        index = load_index(scripts_repo_path)
        modules = set()
        for item in index:
            m = item.get("module") or ""
            if m:
                modules.add(m)
        # 同时扫描目录中存在但 index 中没有的模块文件夹
        if os.path.isdir(scripts_repo_path):
            for name in os.listdir(scripts_repo_path):
                full = os.path.join(scripts_repo_path, name)
                if os.path.isdir(full) and name not in ("plans", ".git") and not name.startswith("."):
                    # 判断是模块文件夹（包含子目录有 case.json）还是用例文件夹
                    if os.path.exists(os.path.join(full, "case.json")):
                        continue  # 这是用例目录，不是模块
                    modules.add(name)
        return jsonify({"success": True, "data": sorted(modules)})

    @bp.route("/api/tv/modules", methods=["POST"])
    def create_module():
        """创建模块"""
        data = request.get_json()
        if not data or not data.get("name"):
            return jsonify({"success": False, "error": "请提供模块名称"}), 400
        name = data["name"].strip()
        if not name:
            return jsonify({"success": False, "error": "模块名称不能为空"}), 400
        if "/" in name or "\\" in name or ".." in name:
            return jsonify({"success": False, "error": "模块名称不能包含路径分隔符"}), 400
        module_dir = os.path.join(scripts_repo_path, name)
        if os.path.exists(module_dir):
            return jsonify({"success": False, "error": f"模块 '{name}' 已存在"}), 409
        os.makedirs(module_dir, exist_ok=True)
        return jsonify({"success": True, "message": f"模块 '{name}' 已创建"})

    @bp.route("/api/tv/modules/<name>", methods=["PUT"])
    def rename_module(name):
        """重命名模块"""
        data = request.get_json()
        if not data or not data.get("new_name"):
            return jsonify({"success": False, "error": "请提供新名称"}), 400
        new_name = data["new_name"].strip()
        if not new_name:
            return jsonify({"success": False, "error": "新名称不能为空"}), 400
        if "/" in new_name or "\\" in new_name or ".." in new_name:
            return jsonify({"success": False, "error": "名称不能包含路径分隔符"}), 400
        old_dir = os.path.join(scripts_repo_path, name)
        new_dir = os.path.join(scripts_repo_path, new_name)
        if not os.path.isdir(old_dir):
            return jsonify({"success": False, "error": f"模块 '{name}' 不存在"}), 404
        if os.path.exists(new_dir):
            return jsonify({"success": False, "error": f"模块 '{new_name}' 已存在"}), 409
        os.rename(old_dir, new_dir)
        # 更新 index.json 中所有该模块下的用例
        index = load_index(scripts_repo_path)
        for item in index:
            if item.get("module") == name:
                item["module"] = new_name
        save_index(scripts_repo_path, index)
        return jsonify({"success": True, "message": f"模块已重命名为 '{new_name}'"})

    @bp.route("/api/tv/modules/<name>", methods=["DELETE"])
    def delete_module(name):
        """删除空模块"""
        module_dir = os.path.join(scripts_repo_path, name)
        if not os.path.isdir(module_dir):
            return jsonify({"success": False, "error": f"模块 '{name}' 不存在"}), 404
        # 检查是否有用例
        index = load_index(scripts_repo_path)
        cases_in_module = [item for item in index if item.get("module") == name]
        if cases_in_module:
            return jsonify({"success": False, "error": f"模块下还有 {len(cases_in_module)} 个用例，请先移走或删除"}), 400
        import shutil
        shutil.rmtree(module_dir, ignore_errors=True)
        return jsonify({"success": True, "message": f"模块 '{name}' 已删除"})

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
