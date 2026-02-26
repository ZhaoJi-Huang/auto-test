"""
录制路由
提供录制的启动、停止、状态查询、插入指令等 API
"""

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
            "session_dir": None,
            "start_time": None,
            "connected": bool(device_serial),
            "device_ip": device_serial,
        })

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
