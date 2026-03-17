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
from common.audit_log import audit_log

logger = logging.getLogger(__name__)

# 计划执行状态（全局，线程安全）
_plan_run_state = {
    "is_running": False,
    "stop_requested": False,
    "plan_id": None,
    "plan_name": "",
    "current_case": 0,
    "total_cases": 0,
    "current_case_key": "",
    "current_case_name": "",
    "current_repeat": 0,
    "total_repeat": 0,
    # 当前用例回放引擎的步骤级状态
    "replay_status": None,
    # 已完成用例的简要结果
    "case_results": [],
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

    def _get_case_name(case_key):
        """获取用例名称"""
        from tv_annotation.routes.case_routes import get_case_dir
        case_dir = get_case_dir(scripts_repo_path, case_key)
        case_path = os.path.join(case_dir, "case.json")
        if os.path.exists(case_path):
            try:
                with open(case_path, "r", encoding="utf-8") as f:
                    case_data = json.load(f)
                return case_data.get("name") or case_data.get("summary", "")
            except Exception:
                pass
        return ""

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
        audit_log("计划删除", plan_id)
        return jsonify({"success": True, "message": f"计划 {plan_id} 已删除"})

    # ------------------------------------------------------------------
    # POST /api/tv/plans/<plan_id>/run — 执行测试计划
    # ------------------------------------------------------------------
    @bp.route("/api/tv/plans/<plan_id>/run", methods=["POST"])
    def run_plan(plan_id):
        plan = _load_plan(plan_id)
        if plan is None:
            return jsonify({"success": False, "error": f"计划 {plan_id} 不存在"}), 404

        body = request.get_json() or {}
        repeat = max(int(body.get("repeat", 1)), 1)

        with _plan_run_state["lock"]:
            if _plan_run_state["is_running"]:
                return jsonify({
                    "success": False,
                    "error": f"正在执行计划 {_plan_run_state['plan_id']}，请等待完成"
                }), 409

            _plan_run_state["is_running"] = True
            _plan_run_state["stop_requested"] = False
            _plan_run_state["plan_id"] = plan_id
            _plan_run_state["plan_name"] = plan.get("name", "")
            _plan_run_state["current_case"] = 0
            _plan_run_state["total_cases"] = len(plan.get("cases", []))
            _plan_run_state["current_case_key"] = ""
            _plan_run_state["current_case_name"] = ""
            _plan_run_state["current_repeat"] = 0
            _plan_run_state["total_repeat"] = repeat
            _plan_run_state["replay_status"] = None
            _plan_run_state["case_results"] = []

        thread = threading.Thread(
            target=_execute_plan,
            args=(plan, repeat, data_dir, scripts_repo_path),
            daemon=True,
        )
        thread.start()

        audit_log("计划执行", plan_id, f"{plan.get('name', '')}, {len(plan.get('cases', []))}个用例, repeat={repeat}")
        return jsonify({"success": True, "message": "计划执行已启动"})

    # ------------------------------------------------------------------
    # POST /api/tv/plans/<plan_id>/stop — 停止执行
    # ------------------------------------------------------------------
    @bp.route("/api/tv/plans/<plan_id>/stop", methods=["POST"])
    def stop_plan(plan_id):
        with _plan_run_state["lock"]:
            if not _plan_run_state["is_running"] or _plan_run_state["plan_id"] != plan_id:
                return jsonify({"success": False, "error": "该计划未在执行中"}), 400
            _plan_run_state["stop_requested"] = True

        # 同时停止当前正在运行的回放引擎
        try:
            from tv_annotation.routes.replay_routes import get_shared_replay_engine
            engine = get_shared_replay_engine()
            if engine:
                engine.stop()
        except Exception as e:
            logger.warning("停止回放引擎失败: %s", e)

        return jsonify({"success": True, "message": "正在停止..."})

    # ------------------------------------------------------------------
    # GET /api/tv/plans/<plan_id>/status — 获取计划执行状态
    # ------------------------------------------------------------------
    @bp.route("/api/tv/plans/<plan_id>/status", methods=["GET"])
    def plan_status(plan_id):
        with _plan_run_state["lock"]:
            is_running = _plan_run_state["is_running"] and _plan_run_state["plan_id"] == plan_id

            # 实时获取回放引擎状态
            replay_status = None
            if is_running:
                try:
                    from tv_annotation.routes.replay_routes import get_shared_replay_engine
                    engine = get_shared_replay_engine()
                    if engine:
                        replay_status = engine.status
                except Exception:
                    pass

            return jsonify({
                "success": True,
                "data": {
                    "is_running": is_running,
                    "plan_name": _plan_run_state["plan_name"],
                    "current_case": _plan_run_state["current_case"],
                    "total_cases": _plan_run_state["total_cases"],
                    "current_case_key": _plan_run_state["current_case_key"],
                    "current_case_name": _plan_run_state["current_case_name"],
                    "current_repeat": _plan_run_state["current_repeat"],
                    "total_repeat": _plan_run_state["total_repeat"],
                    "replay_status": replay_status,
                    "case_results": list(_plan_run_state["case_results"]),
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


def _get_latest_replay_timestamp(data_dir, case_key):
    """获取用例最近一次回放的 timestamp 目录名"""
    replay_dir = os.path.join(data_dir, "replay", case_key)
    if not os.path.isdir(replay_dir):
        return None
    entries = sorted(os.listdir(replay_dir), reverse=True)
    for entry in entries:
        if os.path.isdir(os.path.join(replay_dir, entry)):
            return entry
    return None


def _check_latest_replay_result(data_dir, case_key):
    """检查用例最近一次回放的实际结果，返回 True=passed"""
    ts = _get_latest_replay_timestamp(data_dir, case_key)
    if not ts:
        return False
    result_dir = os.path.join(data_dir, "replay", case_key, ts)

    # 先检查 summary.json（多轮）
    summary_file = os.path.join(result_dir, "summary.json")
    if os.path.isfile(summary_file):
        try:
            with open(summary_file, "r", encoding="utf-8") as f:
                summary = json.load(f)
            return summary.get("failed", 0) == 0 and summary.get("passed", 0) > 0
        except Exception:
            pass

    # 再检查 result.json（单次）
    result_file = os.path.join(result_dir, "result.json")
    if os.path.isfile(result_file):
        try:
            with open(result_file, "r", encoding="utf-8") as f:
                result = json.load(f)
            return result.get("result") == "passed"
        except Exception:
            pass

    return False


def _execute_plan(plan, repeat, data_dir, scripts_repo_path):
    """在后台线程中执行测试计划

    Args:
        plan: 计划数据字典
        repeat: 每个用例重复执行次数
        data_dir: 数据根目录
        scripts_repo_path: 脚本仓库路径
    """
    plan_id = plan["id"]
    raw_cases = plan.get("cases", [])
    stop_on_failure = plan.get("stop_on_failure", False)

    # 兼容 cases 为字符串数组或对象数组
    cases = []
    for c in raw_cases:
        if isinstance(c, str):
            cases.append({"key": c})
        elif isinstance(c, dict):
            cases.append(c)
        else:
            continue

    run_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_dir = os.path.join(data_dir, "replay", "plans", plan_id, timestamp)
    os.makedirs(result_dir, exist_ok=True)

    # 获取共享回放引擎
    engine = None
    try:
        from tv_annotation.routes.replay_routes import get_shared_replay_engine
        engine = get_shared_replay_engine()
    except Exception as e:
        logger.warning("获取回放引擎失败: %s", e)

    # 延迟导入 ADB 工具
    try:
        from common.adb_utils import check_adb_device, send_keyevent, ensure_device_serial
        from common.config_manager import load_device_config
        device_config = load_device_config(data_dir)
        device_serial, auto_msg = ensure_device_serial(device_config, data_dir)
        if auto_msg:
            logger.info("测试计划: %s", auto_msg)
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

    def _get_case_name(case_key):
        case_path = os.path.join(scripts_repo_path, case_key, "case.json")
        if os.path.exists(case_path):
            try:
                with open(case_path, "r", encoding="utf-8") as f:
                    case_data = json.load(f)
                return case_data.get("name") or case_data.get("summary", "")
            except Exception:
                pass
        return ""

    for idx, case_entry in enumerate(cases):
        # 检查是否请求停止
        with _plan_run_state["lock"]:
            if _plan_run_state["stop_requested"]:
                # 剩余用例标记为 aborted
                for remaining in cases[idx:]:
                    case_results.append({
                        "key": remaining.get("key", ""),
                        "result": "aborted",
                        "duration_s": 0,
                    })
                    aborted += 1
                break

        case_key = case_entry.get("key", "")
        case_name = _get_case_name(case_key)

        with _plan_run_state["lock"]:
            _plan_run_state["current_case"] = idx + 1
            _plan_run_state["current_case_key"] = case_key
            _plan_run_state["current_case_name"] = case_name

        # 检查脚本是否存在
        from tv_annotation.routes.case_routes import get_case_dir
        case_dir_path = get_case_dir(scripts_repo_path, case_key)
        steps_file = os.path.join(case_dir_path, "steps.json")
        if not os.path.exists(steps_file):
            case_results.append({
                "key": case_key,
                "name": case_name,
                "result": "no_script",
                "duration_s": 0,
            })
            no_script += 1
            with _plan_run_state["lock"]:
                _plan_run_state["case_results"] = list(case_results)
            continue

        # 回放引擎不可用
        if engine is None:
            case_results.append({
                "key": case_key,
                "name": case_name,
                "result": "engine_unavailable",
                "duration_s": 0,
            })
            aborted += 1
            with _plan_run_state["lock"]:
                _plan_run_state["case_results"] = list(case_results)
            continue

        # 按 HOME 键重置
        if adb_ok:
            try:
                send_keyevent(device_serial, "KEYCODE_HOME")
                time.sleep(1)
            except Exception as e:
                logger.warning("发送 HOME 键失败: %s", e)

        # 使用共享回放引擎执行（支持 repeat）
        case_start = time.time()
        repeat_pass = 0
        repeat_fail = 0
        repeat_aborted = 0
        case_result = "passed"
        was_stopped = False
        # 收集每轮的回放 timestamp 和结果
        run_records = []

        for r in range(repeat):
            # 检查停止
            with _plan_run_state["lock"]:
                if _plan_run_state["stop_requested"]:
                    was_stopped = True
                    repeat_aborted += (repeat - r)
                    break
                _plan_run_state["current_repeat"] = r + 1

            try:
                started, msg = engine.replay(
                    case_key=case_key,
                    repeat=1,
                    stop_on_failure=False,
                )
                if not started:
                    logger.error("回放启动失败 %s: %s", case_key, msg)
                    repeat_fail += 1
                    run_records.append({"run": r + 1, "result": "failed", "replay_timestamp": None})
                    continue

                # 等待回放完成
                stopped_mid = False
                while engine.status.get("is_replaying", False):
                    with _plan_run_state["lock"]:
                        if _plan_run_state["stop_requested"]:
                            engine.stop()
                            stopped_mid = True
                            break
                    time.sleep(0.5)

                if stopped_mid:
                    was_stopped = True
                    repeat_aborted += (repeat - r)
                    # 记录被中止这一轮的 timestamp
                    ts = _get_latest_replay_timestamp(data_dir, case_key)
                    run_records.append({"run": r + 1, "result": "aborted", "replay_timestamp": ts})
                    break

                # 从回放结果目录读取实际结果
                ts = _get_latest_replay_timestamp(data_dir, case_key)
                run_passed = _check_latest_replay_result(data_dir, case_key)
                run_result = "passed" if run_passed else "failed"
                run_records.append({"run": r + 1, "result": run_result, "replay_timestamp": ts})
                if run_passed:
                    repeat_pass += 1
                else:
                    repeat_fail += 1
            except Exception as e:
                logger.error("回放异常 %s (第 %d 次): %s", case_key, r + 1, e)
                repeat_fail += 1
                run_records.append({"run": r + 1, "result": "failed", "replay_timestamp": None})

        case_duration = round(time.time() - case_start)

        # 判定结果
        if was_stopped and repeat_pass == 0 and repeat_fail == 0:
            case_result = "aborted"
        elif repeat_fail > 0:
            case_result = "failed"
        elif was_stopped:
            case_result = "failed"
        else:
            case_result = "passed"

        result_entry = {
            "key": case_key,
            "name": case_name,
            "result": case_result,
            "duration_s": case_duration,
        }
        if repeat > 1:
            result_entry["repeat"] = repeat
            result_entry["repeat_pass"] = repeat_pass
            result_entry["repeat_fail"] = repeat_fail
            result_entry["repeat_aborted"] = repeat_aborted
            result_entry["runs"] = run_records

        # 记录该用例的回放 timestamp（单轮取最新，多轮在 runs 中）
        if repeat == 1 and run_records:
            result_entry["replay_timestamp"] = run_records[0].get("replay_timestamp")
        elif repeat == 1:
            latest_ts = _get_latest_replay_timestamp(data_dir, case_key)
            if latest_ts:
                result_entry["replay_timestamp"] = latest_ts

        case_results.append(result_entry)

        with _plan_run_state["lock"]:
            _plan_run_state["case_results"] = list(case_results)

        if case_result == "passed":
            passed += 1
        else:
            failed += 1

        # 失败且 stop_on_failure → 中止后续用例
        if case_result == "failed" and stop_on_failure:
            for remaining in cases[idx + 1:]:
                case_results.append({
                    "key": remaining.get("key", ""),
                    "name": _get_case_name(remaining.get("key", "")),
                    "result": "aborted",
                    "duration_s": 0,
                })
                aborted += 1
            with _plan_run_state["lock"]:
                _plan_run_state["case_results"] = list(case_results)
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
        "repeat": repeat,
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
        audit_log("计划完成", plan_id, f"通过{passed}/{total_cases}, 耗时{total_duration}s")
    except Exception as e:
        logger.error("保存计划结果失败: %s", e)

    # 重置执行状态
    with _plan_run_state["lock"]:
        _plan_run_state["is_running"] = False
        _plan_run_state["stop_requested"] = False
        _plan_run_state["plan_id"] = None
        _plan_run_state["plan_name"] = ""
        _plan_run_state["current_case"] = 0
        _plan_run_state["total_cases"] = 0
        _plan_run_state["current_case_key"] = ""
        _plan_run_state["current_case_name"] = ""
        _plan_run_state["current_repeat"] = 0
        _plan_run_state["total_repeat"] = 0
        _plan_run_state["replay_status"] = None
        _plan_run_state["case_results"] = []
