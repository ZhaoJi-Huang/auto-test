"""
录制路由
提供录制的启动、停止、状态查询、插入指令等 API
"""

import json
import os

from flask import Blueprint, request, jsonify
from tv_annotation.recorder import TVRecorder

# 模块级录制器实例（单例，由 create_recording_routes 初始化）
_recorder = None


def create_recording_routes(device_config, scripts_repo_path):
    """创建录制路由蓝图

    Args:
        device_config: 设备配置字典（含 tv_ip, key_event_device 等）
        scripts_repo_path: 脚本仓库路径

    Returns:
        Flask Blueprint
    """
    global _recorder

    bp = Blueprint("tv_recording", __name__)

    def _get_recorder():
        """获取或创建录制器实例（延迟初始化，使用最新配置）"""
        global _recorder
        device_serial = device_config.get("tv_ip", "")
        key_event_device = device_config.get("key_event_device", "")

        # 如果设备变更，重新创建录制器
        if (_recorder is None
                or _recorder._device_serial != device_serial):
            _recorder = TVRecorder(
                device_serial=device_serial,
                scripts_repo_path=scripts_repo_path,
                key_event_device=key_event_device or None,
            )
        return _recorder

    # ------------------------------------------------------------------
    # POST /api/tv/recording/start — 开始录制
    # ------------------------------------------------------------------
    @bp.route("/api/tv/recording/start", methods=["POST"])
    def start_recording():
        data = request.get_json()
        if not data or not data.get("case_key"):
            return jsonify({"success": False, "error": "缺少 case_key 参数"}), 400

        case_key = data["case_key"].strip()
        if not case_key:
            return jsonify({"success": False, "error": "case_key 不能为空"}), 400

        device_serial = device_config.get("tv_ip", "")
        if not device_serial:
            return jsonify({"success": False, "error": "未配置设备 IP，请先在设置中配置"}), 400

        recorder = _get_recorder()
        ok, msg = recorder.start(case_key)

        if ok:
            return jsonify({"success": True, "message": msg})
        else:
            return jsonify({"success": False, "error": msg})

    # ------------------------------------------------------------------
    # POST /api/tv/recording/stop — 停止录制
    # ------------------------------------------------------------------
    @bp.route("/api/tv/recording/stop", methods=["POST"])
    def stop_recording():
        recorder = _get_recorder()
        ok, msg, steps = recorder.stop()

        if ok:
            return jsonify({
                "success": True,
                "message": msg,
                "data": {
                    "total_steps": len(steps),
                    "steps": steps,
                },
            })
        else:
            return jsonify({"success": False, "error": msg})

    # ------------------------------------------------------------------
    # GET /api/tv/recording/status — 录制状态
    # ------------------------------------------------------------------
    @bp.route("/api/tv/recording/status", methods=["GET"])
    def recording_status():
        """录制状态（轻量接口，不执行 ADB 命令，避免阻塞）"""
        recorder = _get_recorder()
        device_serial = device_config.get("tv_ip", "")
        return jsonify({
            "is_recording": recorder.is_recording,
            "testcase_name": recorder.case_key or "",
            "step_name": recorder.case_key or "",
            "case_key": recorder.case_key or "",
            "step_count": recorder.step_count,
            "steps": recorder.steps,
            "raw_keys": recorder.raw_keys,
            "session_dir": None,
            "start_time": None,
            "connected": bool(device_serial),
            "device_ip": device_serial,
        })

    # ------------------------------------------------------------------
    # GET /api/tv/recording/saved_steps/<case_key> — 获取已保存的录制步骤
    # ------------------------------------------------------------------
    @bp.route("/api/tv/recording/saved_steps/<case_key>", methods=["GET"])
    def get_saved_steps(case_key):
        """从 steps.json 读取已保存的录制步骤"""
        steps_path = os.path.join(scripts_repo_path, case_key, "steps.json")
        if not os.path.exists(steps_path):
            return jsonify({"success": True, "data": []})
        try:
            with open(steps_path, "r", encoding="utf-8") as f:
                steps = json.load(f)
            return jsonify({"success": True, "data": steps})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})

    # ------------------------------------------------------------------
    # 已保存步骤的编辑操作（非录制状态下编辑 steps.json）
    # ------------------------------------------------------------------

    def _load_saved_steps(case_key):
        """读取 steps.json"""
        path = os.path.join(scripts_repo_path, case_key, "steps.json")
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_steps(case_key, steps):
        """保存 steps.json"""
        case_dir = os.path.join(scripts_repo_path, case_key)
        os.makedirs(case_dir, exist_ok=True)
        path = os.path.join(case_dir, "steps.json")
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(steps, f, ensure_ascii=False, indent=2)
        if os.path.exists(path):
            os.remove(path)
        os.rename(tmp_path, path)

    @bp.route("/api/tv/recording/saved_steps/<case_key>/insert", methods=["POST"])
    def insert_saved_step(case_key):
        """在已保存步骤的指定位置插入步骤"""
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "请求体为空"}), 400

        index = data.get("index")
        step_type = data.get("type", "").strip()
        if index is None:
            return jsonify({"success": False, "error": "缺少 index 参数"}), 400
        if not step_type:
            return jsonify({"success": False, "error": "缺少 type 参数"}), 400

        try:
            index = int(index)
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "index 必须为整数"}), 400

        steps = _load_saved_steps(case_key)
        if index < 0 or index > len(steps):
            return jsonify({"success": False, "error": f"索引超出范围（0-{len(steps)}）"}), 400

        if step_type == "key":
            key_name = data.get("key", "").strip().upper()
            if not key_name:
                return jsonify({"success": False, "error": "缺少 key 参数"}), 400
            from tv_annotation.key_mappings import get_adb_keycode
            adb_keycode = get_adb_keycode(key_name)
            step = {
                "type": "key_group",
                "commands": [{"key": key_name, "adb_command": f"input keyevent {adb_keycode}"}],
                "interval_ms": 0,
                "before_activity": "",
                "after_activity": "",
            }
        elif step_type == "adb_command":
            command = data.get("command", "").strip()
            if not command:
                return jsonify({"success": False, "error": "缺少 command 参数"}), 400
            step = {
                "type": "adb_command",
                "command": command,
                "description": data.get("description", "").strip(),
                "before_activity": "",
                "after_activity": "",
            }
        elif step_type in ("ai_navigate", "ai_verify"):
            prompt = data.get("prompt", "").strip()
            if not prompt:
                return jsonify({"success": False, "error": "缺少 prompt 参数"}), 400
            step = {"type": step_type, "prompt": prompt}
        else:
            return jsonify({"success": False, "error": f"不支持的类型: {step_type}"}), 400

        steps.insert(index, step)
        _save_steps(case_key, steps)
        return jsonify({"success": True, "message": f"已在位置 {index} 插入步骤", "data": steps})

    @bp.route("/api/tv/recording/saved_steps/<case_key>/delete", methods=["POST"])
    def delete_saved_step(case_key):
        """删除已保存步骤的指定位置"""
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "请求体为空"}), 400

        index = data.get("index")
        if index is None:
            return jsonify({"success": False, "error": "缺少 index 参数"}), 400

        try:
            index = int(index)
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "index 必须为整数"}), 400

        steps = _load_saved_steps(case_key)
        if index < 0 or index >= len(steps):
            return jsonify({"success": False, "error": f"索引超出范围（0-{len(steps) - 1}）"}), 400

        removed = steps.pop(index)
        _save_steps(case_key, steps)
        return jsonify({"success": True, "message": f"已删除位置 {index} 的步骤（{removed.get('type')}）", "data": steps})

    @bp.route("/api/tv/recording/saved_steps/<case_key>/update", methods=["POST"])
    def update_saved_step(case_key):
        """修改已保存步骤的指定位置"""
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "请求体为空"}), 400

        index = data.get("index")
        step_type = data.get("type", "").strip()
        if index is None:
            return jsonify({"success": False, "error": "缺少 index 参数"}), 400
        if not step_type:
            return jsonify({"success": False, "error": "缺少 type 参数"}), 400

        try:
            index = int(index)
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "index 必须为整数"}), 400

        steps = _load_saved_steps(case_key)
        if index < 0 or index >= len(steps):
            return jsonify({"success": False, "error": f"索引超出范围（0-{len(steps) - 1}）"}), 400

        if step_type == "key":
            key_name = data.get("key", "").strip().upper()
            if not key_name:
                return jsonify({"success": False, "error": "缺少 key 参数"}), 400
            from tv_annotation.key_mappings import get_adb_keycode
            adb_keycode = get_adb_keycode(key_name)
            steps[index] = {
                "type": "key_group",
                "commands": [{"key": key_name, "adb_command": f"input keyevent {adb_keycode}"}],
                "interval_ms": 0,
                "before_activity": "",
                "after_activity": "",
            }
        elif step_type == "adb_command":
            command = data.get("command", "").strip()
            if not command:
                return jsonify({"success": False, "error": "缺少 command 参数"}), 400
            steps[index] = {
                "type": "adb_command",
                "command": command,
                "description": data.get("description", "").strip(),
                "before_activity": "",
                "after_activity": "",
            }
        elif step_type in ("ai_navigate", "ai_verify"):
            prompt = data.get("prompt", "").strip()
            if not prompt:
                return jsonify({"success": False, "error": "缺少 prompt 参数"}), 400
            steps[index] = {"type": step_type, "prompt": prompt}
        else:
            return jsonify({"success": False, "error": f"不支持的类型: {step_type}"}), 400

        _save_steps(case_key, steps)
        return jsonify({"success": True, "message": f"已修改位置 {index} 的步骤", "data": steps})

    # ------------------------------------------------------------------
    # POST /api/tv/recording/insert_adb — 插入 ADB 命令
    # ------------------------------------------------------------------
    @bp.route("/api/tv/recording/insert_adb", methods=["POST"])
    def insert_adb_command():
        data = request.get_json()
        if not data or not data.get("command"):
            return jsonify({"success": False, "error": "缺少 command 参数"}), 400

        command = data["command"].strip()
        description = data.get("description", "").strip()

        recorder = _get_recorder()
        ok, msg = recorder.insert_adb_command(command, description)

        if ok:
            return jsonify({"success": True, "message": msg})
        else:
            return jsonify({"success": False, "error": msg})

    # ------------------------------------------------------------------
    # POST /api/tv/recording/insert_ai — 插入 AI 指令
    # ------------------------------------------------------------------
    @bp.route("/api/tv/recording/insert_ai", methods=["POST"])
    def insert_ai_instruction():
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "请求体为空"}), 400

        ai_type = data.get("type", "").strip()
        prompt = data.get("prompt", "").strip()

        if not ai_type:
            return jsonify({"success": False, "error": "缺少 type 参数"}), 400
        if not prompt:
            return jsonify({"success": False, "error": "缺少 prompt 参数"}), 400

        recorder = _get_recorder()
        ok, msg = recorder.insert_ai_instruction(ai_type, prompt)

        if ok:
            return jsonify({"success": True, "message": msg})
        else:
            return jsonify({"success": False, "error": msg})

    # ------------------------------------------------------------------
    # POST /api/tv/recording/delete_last — 删除最后一步
    # ------------------------------------------------------------------
    @bp.route("/api/tv/recording/delete_last", methods=["POST"])
    def delete_last_step():
        recorder = _get_recorder()
        ok, msg = recorder.delete_last_step()

        if ok:
            return jsonify({"success": True, "message": msg})
        else:
            return jsonify({"success": False, "error": msg})

    # ------------------------------------------------------------------
    # POST /api/tv/recording/insert_step_at — 在指定位置插入步骤
    # ------------------------------------------------------------------
    @bp.route("/api/tv/recording/insert_step_at", methods=["POST"])
    def insert_step_at():
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "请求体为空"}), 400

        index = data.get("index")
        step_type = data.get("type", "").strip()

        if index is None:
            return jsonify({"success": False, "error": "缺少 index 参数"}), 400
        if not step_type:
            return jsonify({"success": False, "error": "缺少 type 参数"}), 400

        try:
            index = int(index)
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "index 必须为整数"}), 400

        recorder = _get_recorder()

        if step_type == "key":
            key_name = data.get("key", "").strip().upper()
            if not key_name:
                return jsonify({"success": False, "error": "缺少 key 参数"}), 400
            ok, msg = recorder.insert_key_at(index, key_name)
        elif step_type == "adb_command":
            command = data.get("command", "").strip()
            description = data.get("description", "").strip()
            if not command:
                return jsonify({"success": False, "error": "缺少 command 参数"}), 400
            step = {
                "type": "adb_command",
                "command": command,
                "description": description,
                "before_activity": "",
                "after_activity": "",
            }
            ok, msg = recorder.insert_step_at(index, step)
        elif step_type in ("ai_navigate", "ai_verify"):
            prompt = data.get("prompt", "").strip()
            if not prompt:
                return jsonify({"success": False, "error": "缺少 prompt 参数"}), 400
            step = {
                "type": step_type,
                "prompt": prompt,
            }
            ok, msg = recorder.insert_step_at(index, step)
        else:
            return jsonify({"success": False, "error": f"不支持的类型: {step_type}"}), 400

        if ok:
            return jsonify({"success": True, "message": msg})
        else:
            return jsonify({"success": False, "error": msg})

    # ------------------------------------------------------------------
    # POST /api/tv/recording/delete_step — 删除指定位置步骤
    # ------------------------------------------------------------------
    @bp.route("/api/tv/recording/delete_step", methods=["POST"])
    def delete_step():
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "请求体为空"}), 400

        index = data.get("index")
        if index is None:
            return jsonify({"success": False, "error": "缺少 index 参数"}), 400

        try:
            index = int(index)
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "index 必须为整数"}), 400

        recorder = _get_recorder()
        ok, msg = recorder.delete_step(index)

        if ok:
            return jsonify({"success": True, "message": msg})
        else:
            return jsonify({"success": False, "error": msg})

    # ------------------------------------------------------------------
    # POST /api/tv/recording/quick_replay — 快速回放
    # ------------------------------------------------------------------
    @bp.route("/api/tv/recording/quick_replay", methods=["POST"])
    def quick_replay():
        """启动快速回放（无 Activity 校验、无截图、无 AI 验证）"""
        data = request.get_json()
        if not data or not data.get("case_key"):
            return jsonify({"success": False, "error": "缺少 case_key 参数"}), 400

        case_key = data["case_key"].strip()
        if not case_key:
            return jsonify({"success": False, "error": "case_key 不能为空"}), 400

        device_serial = device_config.get("tv_ip", "")
        if not device_serial:
            return jsonify({"success": False, "error": "未配置设备 IP，请先在设置中配置"}), 400

        from tv_annotation.routes.replay_routes import get_shared_replay_engine
        engine = get_shared_replay_engine()
        if engine is None:
            return jsonify({"success": False, "error": "回放引擎未初始化，请先检查设备配置"})

        # 更新设备序列号
        engine._device_serial = device_serial

        ok, msg = engine.quick_replay(case_key)
        return jsonify({"success": ok, "message": msg})

    # ------------------------------------------------------------------
    # POST /api/tv/recording/quick_replay/stop — 停止快速回放
    # ------------------------------------------------------------------
    @bp.route("/api/tv/recording/quick_replay/stop", methods=["POST"])
    def stop_quick_replay():
        """停止快速回放"""
        from tv_annotation.routes.replay_routes import get_shared_replay_engine
        engine = get_shared_replay_engine()
        if engine is None:
            return jsonify({"success": False, "error": "回放引擎未初始化"})

        ok, msg = engine.stop()
        return jsonify({"success": ok, "message": msg})

    # ------------------------------------------------------------------
    # 旧前端兼容路由
    # ------------------------------------------------------------------
    @bp.route("/api/tv/recording/send_key", methods=["POST"])
    def send_key():
        """发送按键（兼容旧前端）"""
        data = request.get_json()
        key_name = data.get("key", "").strip().upper()
        if not key_name:
            return jsonify({"success": False, "message": "按键名称为空"})
        # 直接通过 ADB 发送按键
        try:
            from tv_annotation.key_mappings import get_adb_keycode
            from common.adb_utils import send_keyevent
            keycode = get_adb_keycode(key_name)
            send_keyevent(device_config.get("tv_ip", ""), keycode)
            return jsonify({"success": True, "message": f"按键 {key_name} 已发送"})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)})

    @bp.route("/api/tv/recording/send_adb", methods=["POST"])
    def send_adb():
        """发送 ADB 命令（兼容旧前端）"""
        data = request.get_json()
        command = data.get("command", "").strip()
        if not command:
            return jsonify({"success": False, "message": "命令为空"})
        try:
            from common.adb_utils import run_adb
            device_serial = device_config.get("tv_ip", "")
            first_word = command.split()[0] if command.split() else ""
            adb_direct = ["devices", "connect", "disconnect", "push", "pull",
                          "install", "uninstall", "reboot"]
            if first_word == "shell" or first_word in adb_direct:
                cmd = command.split()
            else:
                cmd = ["shell"] + command.split()
            result = run_adb(cmd, device_serial=device_serial)
            output = result.stdout.decode("utf-8", errors="ignore")
            return jsonify({"success": result.returncode == 0, "message": "命令已执行", "output": output})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)})

    @bp.route("/api/tv/recording/change_wait_time", methods=["POST"])
    def change_wait_time():
        """改变等待时间（兼容旧前端）"""
        return jsonify({"success": True, "message": "已更新"})

    @bp.route("/api/tv/send_key", methods=["POST"])
    def legacy_send_key():
        """发送按键（旧前端入口）"""
        return send_key()

    @bp.route("/api/tv/delete_step_record", methods=["POST"])
    def legacy_delete_step_record():
        """删除步骤记录（兼容旧前端）"""
        return delete_last_step()

    @bp.route("/api/tv/testcases", methods=["GET"])
    def legacy_testcases():
        """获取测试用例（兼容旧前端，返回空列表）"""
        return jsonify({"testcases": [], "message": "请使用新的 /api/tv/cases 接口"})

    return bp
