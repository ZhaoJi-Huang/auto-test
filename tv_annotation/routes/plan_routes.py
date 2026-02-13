"""
测试计划路由
提供测试计划的增删改查、执行、状态查询、结果查看等 API
"""

import os
import json
import glob
import time
import socket
import logging
import threading
from datetime import datetime

from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

# 计划执行状态（全局，线程安全）
_plan_run_state = {
    "is_running": False,
    "plan_id": None,
    "current_case": 0,
    "total_cases": 0,
    "current_case_key": "",
    "lock": threading.Lock(),
}


def create_plan_routes(data_dir, scripts_repo_path):
    """创建测试计划路由蓝图

    Args:
        data_dir: 数据根目录
        scripts_repo_path: 脚本仓库路径

    Returns:
        Flask Blueprint
    """
    bp = Blueprint("tv_plans", __name__)
    plans_dir = os.path.join(scripts_repo_path, "plans")

    def _ensure_plans_dir():
        """确保计划目录存在"""
        os.makedirs(plans_dir, exist_ok=True)

    def _next_plan_id():
        """生成下一个计划 ID（PLAN-001, PLAN-002, ...）"""
        _ensure_plans_dir()
        existing = glob.glob(os.path.join(plans_dir, "PLAN-*.json"))
        max_num = 0
        for fp in existing:
            name = os.path.splitext(os.path.basename(fp))[0]
            try:
                num = int(name.split("-", 1)[1])
                max_num = max(max_num, num)
            except (ValueError, IndexError):
                pass
        return f"PLAN-{max_num + 1:03d}"

    def _plan_path(plan_id):
        """获取计划文件路径"""
        return os.path.join(plans_dir, f"{plan_id}.json")

    def _load_plan(plan_id):
        """加载计划 JSON"""
        path = _plan_path(plan_id)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_plan(plan_id, plan_data):
        """保存计划 JSON"""
        _ensure_plans_dir()
        path = _plan_path(plan_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(plan_data, f, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # GET /api/tv/plans — 获取所有计划列表
    # ------------------------------------------------------------------
    @bp.route("/api/tv/plans", methods=["GET"])
    def list_plans():
        _ensure_plans_dir()
        plan_files = glob.glob(os.path.join(plans_dir, "PLAN-*.json"))
        plans = []
        for fp in sorted(plan_files):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                plans.append({
                    "id": data.get("id", ""),
                    "name": data.get("name", ""),
                    "description": data.get("description", ""),
                    "cases_count": len(data.get("cases", [])),
                    "created_at": data.get("created_at", ""),
                    "created_by": data.get("created_by", ""),
                })
            except Exception as e:
                logger.warning("读取计划文件失败 %s: %s", fp, e)
        return jsonify({"success": True, "data": plans})

    # ------------------------------------------------------------------
    # GET /api/tv/plans/<plan_id> — 获取计划详情
    # ------------------------------------------------------------------
    @bp.route("/api/tv/plans/<plan_id>", methods=["GET"])
    def get_plan(plan_id):
        plan = _load_plan(plan_id)
        if plan is None:
            return jsonify({"success": False, "error": f"计划 {plan_id} 不存在"}), 404
        return jsonify({"success": True, "data": plan})

    # ------------------------------------------------------------------
    # POST /api/tv/plans — 创建计划
    # ------------------------------------------------------------------
    @bp.route("/api/tv/plans", methods=["POST"])
    def create_plan():
        body = request.get_json()
        if not body or not body.get("name"):
            return jsonify({"success": False, "error": "缺少 name 参数"}), 400

        plan_id = _next_plan_id()
        plan_data = {
            "id": plan_id,
            "name": body["name"].strip(),
            "description": body.get("description", "").strip(),
            "created_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "created_by": socket.gethostname(),
            "cases": body.get("cases", []),
            "stop_on_failure": body.get("stop_on_failure", False),
        }
        _save_plan(plan_id, plan_data)
        return jsonify({"success": True, "message": f"计划 {plan_id} 已创建", "data": plan_data})

    # ------------------------------------------------------------------
    # PUT /api/tv/plans/<plan_id> — 更新计划
    # ------------------------------------------------------------------
    @bp.route("/api/tv/plans/<plan_id>", methods=["PUT"])
    def update_plan(plan_id):
        plan = _load_plan(plan_id)
        if plan is None:
            return jsonify({"success": False, "error": f"计划 {plan_id} 不存在"}), 404

        body = request.get_json()
        if not body:
            return jsonify({"success": False, "error": "请求体为空"}), 400

        # 更新允许修改的字段
        if "name" in body:
            plan["name"] = body["name"].strip()
        if "description" in body:
            plan["description"] = body["description"].strip()
        if "cases" in body:
            plan["cases"] = body["cases"]
        if "stop_on_failure" in body:
            plan["stop_on_failure"] = body["stop_on_failure"]

        _save_plan(plan_id, plan)
        return jsonify({"success": True, "message": f"计划 {plan_id} 已更新", "data": plan})

    # ------------------------------------------------------------------
    # DELETE /api/tv/plans/<plan_id> — 删除计划
    # ------------------------------------------------------------------
    @bp.route("/api/tv/plans/<plan_id>", methods=["DELETE"])
    def delete_plan(plan_id):
        path = _plan_path(plan_id)
        if not os.path.exists(path):
            return jsonify({"success": False, "error": f"计划 {plan_id} 不存在"}), 404
        os.remove(path)
        return jsonify({"success": True, "message": f"计划 {plan_id} 已删除"})

    # ------------------------------------------------------------------
    # POST /api/tv/plans/<plan_id>/run — 执行测试计划
    # ------------------------------------------------------------------
    @bp.route("/api/tv/plans/<plan_id>/run", methods=["POST"])
    def run_plan(plan_id):
        plan = _load_plan(plan_id)
        if plan is None:
            return jsonify({"success": False, "error": f"计划 {plan_id} 不存在"}), 404

        with _plan_run_state["lock"]:
            if _plan_run_state["is_running"]:
                return jsonify({
                    "success": False,
                    "error": f"正在执行计划 {_plan_run_state['plan_id']}，请等待完成"
                }), 409

            _plan_run_state["is_running"] = True
            _plan_run_state["plan_id"] = plan_id
            _plan_run_state["current_case"] = 0
            _plan_run_state["total_cases"] = len(plan.get("cases", []))
            _plan_run_state["current_case_key"] = ""

        thread = threading.Thread(
            target=_execute_plan,
            args=(plan, data_dir, scripts_repo_path),
            daemon=True,
        )
        thread.start()

        return jsonify({"success": True, "message": "计划执行已启动"})

    # ------------------------------------------------------------------
    # GET /api/tv/plans/<plan_id>/status — 获取计划执行状态
    # ------------------------------------------------------------------
    @bp.route("/api/tv/plans/<plan_id>/status", methods=["GET"])
    def plan_status(plan_id):
        with _plan_run_state["lock"]:
            return jsonify({
                "success": True,
                "data": {
                    "is_running": _plan_run_state["is_running"] and _plan_run_state["plan_id"] == plan_id,
                    "current_case": _plan_run_state["current_case"],
                    "total_cases": _plan_run_state["total_cases"],
                    "current_case_key": _plan_run_state["current_case_key"],
                }
            })

    # ------------------------------------------------------------------
    # GET /api/tv/plans/<plan_id>/results — 获取计划执行结果列表
    # ------------------------------------------------------------------
    @bp.route("/api/tv/plans/<plan_id>/results", methods=["GET"])
    def plan_results(plan_id):
        results_base = os.path.join(data_dir, "replay", "plans", plan_id)
        if not os.path.isdir(results_base):
            return jsonify({"success": True, "data": []})

        results = []
        for entry in sorted(os.listdir(results_base), reverse=True):
            result_file = os.path.join(results_base, entry, "plan_result.json")
            if os.path.exists(result_file):
                try:
                    with open(result_file, "r", encoding="utf-8") as f:
                        result_data = json.load(f)
                    results.append(result_data)
                except Exception as e:
                    logger.warning("读取计划结果失败 %s: %s", result_file, e)
        return jsonify({"success": True, "data": results})

    return bp


def _execute_plan(plan, data_dir, scripts_repo_path):
    """在后台线程中执行测试计划

    Args:
        plan: 计划数据字典
        data_dir: 数据根目录
        scripts_repo_path: 脚本仓库路径
    """
    plan_id = plan["id"]
    cases = plan.get("cases", [])
    stop_on_failure = plan.get("stop_on_failure", False)

    run_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_dir = os.path.join(data_dir, "replay", "plans", plan_id, timestamp)
    os.makedirs(result_dir, exist_ok=True)

    # 延迟导入回放引擎（可能尚未实现）
    replay_engine = None
    try:
        from tv_annotation.replay_engine import ReplayEngine
        replay_engine = ReplayEngine
    except ImportError:
        logger.warning("回放引擎未实现，计划执行将标记用例为 engine_unavailable")

    # 延迟导入 ADB 工具
    try:
        from common.adb_utils import check_adb_device, send_keyevent
        from common.config_manager import load_device_config
        device_config = load_device_config(data_dir)
        device_serial = device_config.get("tv_ip", "")
    except ImportError:
        device_serial = ""

    # ADB 连接检查
    adb_ok = False
    if device_serial:
        try:
            ok, msg = check_adb_device(device_serial)
            adb_ok = ok
            if not ok:
                logger.warning("ADB 设备连接检查失败: %s", msg)
        except Exception as e:
            logger.warning("ADB 检查异常: %s", e)

    case_results = []
    passed = 0
    failed = 0
    no_script = 0
    aborted = 0
    plan_start = time.time()

    for idx, case_entry in enumerate(cases):
        case_key = case_entry.get("key", "")
        repeat = case_entry.get("repeat", 1)

        with _plan_run_state["lock"]:
            _plan_run_state["current_case"] = idx + 1
            _plan_run_state["current_case_key"] = case_key

        # 检查脚本是否存在
        case_dir = os.path.join(scripts_repo_path, case_key)
        steps_file = os.path.join(case_dir, "steps.json")
        if not os.path.exists(steps_file):
            case_results.append({
                "key": case_key,
                "result": "no_script",
                "duration_s": 0,
            })
            no_script += 1
            continue

        # 回放引擎不可用
        if replay_engine is None:
            case_results.append({
                "key": case_key,
                "result": "engine_unavailable",
                "duration_s": 0,
            })
            aborted += 1
            continue

        # 按 HOME 键重置
        if adb_ok:
            try:
                send_keyevent(device_serial, "KEYCODE_HOME")
                time.sleep(1)
            except Exception as e:
                logger.warning("发送 HOME 键失败: %s", e)

        # 执行回放（支持 repeat）
        case_start = time.time()
        repeat_pass = 0
        repeat_fail = 0
        case_result = "passed"

        for r in range(repeat):
            try:
                engine = replay_engine(
                    device_serial=device_serial,
                    scripts_repo_path=scripts_repo_path,
                    data_dir=data_dir,
                )
                ok, msg = engine.replay(case_key)
                if ok:
                    repeat_pass += 1
                else:
                    repeat_fail += 1
            except Exception as e:
                logger.error("回放异常 %s (第 %d 次): %s", case_key, r + 1, e)
                repeat_fail += 1

        case_duration = round(time.time() - case_start)

        if repeat_fail > 0:
            case_result = "failed"

        result_entry = {
            "key": case_key,
            "result": case_result,
            "duration_s": case_duration,
        }
        if repeat > 1:
            result_entry["repeat"] = repeat
            result_entry["repeat_pass"] = repeat_pass
            result_entry["repeat_fail"] = repeat_fail

        case_results.append(result_entry)

        if case_result == "passed":
            passed += 1
        else:
            failed += 1

        # 失败且 stop_on_failure → 中止后续用例
        if case_result == "failed" and stop_on_failure:
            # 剩余用例标记为 aborted
            for remaining in cases[idx + 1:]:
                case_results.append({
                    "key": remaining.get("key", ""),
                    "result": "aborted",
                    "duration_s": 0,
                })
                aborted += 1
            break

    total_duration = round(time.time() - plan_start)
    finished_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    total_cases = len(cases)
    pass_rate = round(passed / total_cases, 4) if total_cases > 0 else 0

    plan_result = {
        "plan_id": plan_id,
        "plan_name": plan.get("name", ""),
        "run_at": run_at,
        "finished_at": finished_at,
        "total_duration_s": total_duration,
        "total_cases": total_cases,
        "passed": passed,
        "failed": failed,
        "no_script": no_script,
        "aborted": aborted,
        "pass_rate": pass_rate,
        "cases": case_results,
    }

    # 写入结果文件
    result_path = os.path.join(result_dir, "plan_result.json")
    try:
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(plan_result, f, ensure_ascii=False, indent=2)
        logger.info("计划 %s 执行完成，结果已保存: %s", plan_id, result_path)
    except Exception as e:
        logger.error("保存计划结果失败: %s", e)

    # 重置执行状态
    with _plan_run_state["lock"]:
        _plan_run_state["is_running"] = False
        _plan_run_state["plan_id"] = None
        _plan_run_state["current_case"] = 0
        _plan_run_state["total_cases"] = 0
        _plan_run_state["current_case_key"] = ""
