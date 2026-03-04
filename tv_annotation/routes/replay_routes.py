"""
回放路由
提供回放启动、停止、状态查询、结果查询等 API
"""

import json
import os

from flask import Blueprint, jsonify, request, send_file

# 模块级共享引擎实例（供 recording_routes 快速回放复用）
_shared_engine = {"instance": None, "device_config": None, "data_dir": None, "scripts_repo_path": None}


def get_shared_replay_engine():
    """获取共享回放引擎实例（供其他模块调用）"""
    cfg = _shared_engine
    if cfg["instance"] is None and cfg["device_config"] is not None:
        tv_ip = cfg["device_config"].get("tv_ip", "")
        if tv_ip:
            from tv_annotation.capture_card import capture_card
            from tv_annotation.replay_engine import ReplayEngine
            cfg["instance"] = ReplayEngine(
                device_serial=tv_ip,
                data_dir=cfg["data_dir"],
                scripts_repo_path=cfg["scripts_repo_path"],
                capture_card=capture_card,
            )
    return cfg["instance"]


def create_replay_routes(device_config, data_dir, scripts_repo_path):
    """创建回放路由蓝图

    Args:
        device_config: 设备配置字典（包含 tv_ip 等）
        data_dir: 数据根目录
        scripts_repo_path: 脚本仓库路径

    Returns:
        Blueprint
    """
    bp = Blueprint("tv_replay", __name__)

    # 初始化共享引擎配置
    _shared_engine["device_config"] = device_config
    _shared_engine["data_dir"] = data_dir
    _shared_engine["scripts_repo_path"] = scripts_repo_path

    def _get_engine():
        """获取或创建回放引擎实例（使用共享实例）"""
        return get_shared_replay_engine()

    @bp.route("/api/tv/replay/start", methods=["POST"])
    def start_replay():
        """开始回放"""
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "请求体为空"}), 400

        case_key = data.get("case_key", "").strip()
        if not case_key:
            return jsonify({"success": False, "error": "case_key 不能为空"}), 400

        repeat = max(int(data.get("repeat", 1)), 1)
        stop_on_failure = bool(data.get("stop_on_failure", False))

        engine = _get_engine()
        if engine is None:
            return jsonify({"success": False, "error": "未配置设备 IP，请先在配置页设置"})

        # 更新设备序列号（配置可能已变更）
        engine._device_serial = device_config.get("tv_ip", "")

        ok, msg = engine.replay(
            case_key=case_key,
            repeat=repeat,
            stop_on_failure=stop_on_failure,
        )
        return jsonify({"success": ok, "message": msg})

    @bp.route("/api/tv/replay/stop", methods=["POST"])
    def stop_replay():
        """停止回放"""
        engine = _get_engine()
        if engine is None:
            return jsonify({"success": False, "error": "回放引擎未初始化"})

        ok, msg = engine.stop()
        return jsonify({"success": ok, "message": msg})

    @bp.route("/api/tv/replay/status", methods=["GET"])
    def replay_status():
        """获取回放状态"""
        engine = _get_engine()
        if engine is None:
            return jsonify({
                "success": True,
                "data": {
                    "is_replaying": False,
                    "case_key": None,
                    "current_step": 0,
                    "total_steps": 0,
                    "current_run": 0,
                    "total_runs": 0,
                },
            })

        return jsonify({"success": True, "data": engine.status})

    @bp.route("/api/tv/replay/results/<case_key>", methods=["GET"])
    def list_results(case_key):
        """获取指定用例的所有回放结果列表"""
        replay_dir = os.path.join(data_dir, "replay", case_key)
        if not os.path.isdir(replay_dir):
            return jsonify({"success": True, "data": []})

        results = []
        for entry in sorted(os.listdir(replay_dir), reverse=True):
            entry_path = os.path.join(replay_dir, entry)
            if not os.path.isdir(entry_path):
                continue

            # 读取 result.json 或 summary.json
            summary_file = os.path.join(entry_path, "summary.json")
            result_file = os.path.join(entry_path, "result.json")

            info = {"timestamp": entry, "path": entry_path}

            if os.path.isfile(summary_file):
                try:
                    with open(summary_file, "r", encoding="utf-8") as f:
                        summary = json.load(f)
                    info["type"] = "summary"
                    info["result"] = f"通过 {summary.get('passed', 0)}/{summary.get('repeat', 0)}"
                    info["pass_rate"] = summary.get("pass_rate", 0)
                    info["duration_s"] = summary.get("total_duration_s", 0)
                except Exception:
                    pass
            elif os.path.isfile(result_file):
                try:
                    with open(result_file, "r", encoding="utf-8") as f:
                        result = json.load(f)
                    info["type"] = "single"
                    info["result"] = result.get("result", "unknown")
                    info["duration_s"] = result.get("duration_s", 0)
                    info["total_steps"] = result.get("total_steps", 0)
                except Exception:
                    pass

            results.append(info)

        return jsonify({"success": True, "data": results})

    @bp.route("/api/tv/replay/result/<case_key>/<timestamp>", methods=["GET"])
    def get_result(case_key, timestamp):
        """获取特定回放结果详情"""
        result_dir = os.path.join(data_dir, "replay", case_key, timestamp)
        if not os.path.isdir(result_dir):
            return jsonify({"success": False, "error": "回放结果不存在"}), 404

        # 优先读取 summary.json（多次重复），否则读取 result.json
        summary_file = os.path.join(result_dir, "summary.json")
        result_file = os.path.join(result_dir, "result.json")

        if os.path.isfile(summary_file):
            try:
                with open(summary_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return jsonify({"success": True, "data": data})
            except Exception as e:
                return jsonify({"success": False, "error": f"读取汇总失败: {e}"})

        if os.path.isfile(result_file):
            try:
                with open(result_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # 检查是否有回放视频
                video_file = os.path.join(result_dir, "replay.mp4")
                data["has_video"] = os.path.isfile(video_file)
                data["video_url"] = f"/api/tv/replay/video/{case_key}/{timestamp}" if data["has_video"] else None
                return jsonify({"success": True, "data": data})
            except Exception as e:
                return jsonify({"success": False, "error": f"读取结果失败: {e}"})

        return jsonify({"success": False, "error": "未找到结果文件"}), 404

    @bp.route("/api/tv/replay/result/<case_key>/<timestamp>/run/<int:run_index>", methods=["GET"])
    def get_run_result(case_key, timestamp, run_index):
        """获取多轮回放中单轮的详细结果"""
        for part in (case_key, timestamp):
            if ".." in part or "/" in part or "\\" in part:
                return jsonify({"success": False, "error": "非法路径"}), 400

        run_dir = os.path.join(data_dir, "replay", case_key, timestamp, f"run_{run_index}")
        result_file = os.path.join(run_dir, "result.json")

        if not os.path.isfile(result_file):
            return jsonify({"success": False, "error": f"第 {run_index} 轮结果不存在"}), 404

        try:
            with open(result_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 检查是否有回放视频
            video_file = os.path.join(run_dir, "replay.mp4")
            data["has_video"] = os.path.isfile(video_file)
            data["video_url"] = (
                f"/api/tv/replay/video/{case_key}/{timestamp}/run/{run_index}"
                if data["has_video"]
                else None
            )
            return jsonify({"success": True, "data": data})
        except Exception as e:
            return jsonify({"success": False, "error": f"读取结果失败: {e}"})

    @bp.route("/api/tv/replay/screenshot/<case_key>/<timestamp>/<path:filename>", methods=["GET"])
    def get_screenshot(case_key, timestamp, filename):
        """获取回放截图（支持 run_N/filename 子目录格式）"""
        # 安全检查：防止路径穿越
        for part in (case_key, timestamp):
            if ".." in part or "/" in part or "\\" in part:
                return jsonify({"success": False, "error": "非法路径"}), 400
        # filename 可含子目录（如 run_1/step_1.png），只检查 ..
        if ".." in filename:
            return jsonify({"success": False, "error": "非法路径"}), 400

        file_path = os.path.join(data_dir, "replay", case_key, timestamp, filename)
        if not os.path.isfile(file_path):
            return jsonify({"success": False, "error": "截图不存在"}), 404

        return send_file(file_path, mimetype="image/png")

    @bp.route("/api/tv/replay/video/<case_key>/<timestamp>", methods=["GET"])
    def get_video(case_key, timestamp):
        """获取回放视频（支持 Range 请求，浏览器 video 标签需要）"""
        for part in (case_key, timestamp):
            if ".." in part or "/" in part or "\\" in part:
                return jsonify({"success": False, "error": "非法路径"}), 400

        file_path = os.path.join(data_dir, "replay", case_key, timestamp, "replay.mp4")
        if not os.path.isfile(file_path):
            return jsonify({"success": False, "error": "视频不存在"}), 404

        return send_file(file_path, mimetype="video/mp4", conditional=True)

    return bp
