"""
设备配置路由
"""

from flask import Blueprint, request, jsonify
from common.audit_log import audit_log


def create_config_routes(device_config, data_dir):
    """创建配置管理路由蓝图"""

    bp = Blueprint("tv_config", __name__)

    @bp.route("/api/tv/config", methods=["GET"])
    def get_config():
        """获取设备配置（直接返回配置对象，兼容旧前端）"""
        return jsonify(device_config)

    @bp.route("/api/tv/config", methods=["POST"])
    def update_config():
        """更新设备配置"""
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "请求体为空"}), 400

        # 更新配置
        for key in ["tv_ip", "serial_port", "remote_port", "key_event_device"]:
            if key in data:
                device_config[key] = data[key].strip() if isinstance(data[key], str) else data[key]

        # 采集卡设备索引
        if "device_id" in data:
            new_id = int(data["device_id"])
            old_id = device_config.get("device_id")
            device_config["device_id"] = new_id
            if new_id != old_id:
                try:
                    from tv_annotation.capture_card import capture_card
                    capture_card.stop()
                    capture_card.start(device_id=new_id)
                except Exception as e:
                    return jsonify({"success": False, "error": f"采集卡重启失败: {e}"})

        # 持久化
        from common.config_manager import save_device_config
        save_device_config(data_dir, device_config)

        # 审计日志：记录配置变更
        changes = [f"{k}={data[k]}" for k in ["tv_ip", "serial_port", "device_id", "key_event_device"] if k in data]
        if changes:
            audit_log("配置变更", "", ", ".join(changes))

        # 如果有新 IP（网络设备），尝试 ADB 连接；USB 设备无需 connect
        tv_ip = device_config.get("tv_ip")
        if tv_ip and ":" in tv_ip:
            from common.adb_utils import connect_device
            ok, msg = connect_device(tv_ip)
            if not ok:
                return jsonify({"success": True, "message": f"配置已保存，但 ADB 连接失败: {msg}"})

        return jsonify({"success": True, "message": "配置已更新"})

    @bp.route("/api/tv/capture-devices", methods=["GET"])
    def list_capture_devices():
        """枚举可用视频采集设备"""
        try:
            from tv_annotation.capture_card import enumerate_capture_devices
            devices = enumerate_capture_devices()
            return jsonify({"success": True, "data": devices})
        except Exception as e:
            return jsonify({"success": False, "error": str(e), "data": []})

    @bp.route("/api/tv/device/check", methods=["GET"])
    def check_device():
        """检查 ADB 设备连接状态（支持 IP 和 USB 连接）"""
        tv_ip = device_config.get("tv_ip")
        if not tv_ip:
            # 未配置 IP 时，尝试自动检测已连接的设备
            from common.adb_utils import list_adb_devices
            devices = list_adb_devices()
            available = [d for d in devices if d["status"] == "device"]
            if not available:
                return jsonify({"success": False, "error": "未检测到已连接的 ADB 设备，请通过 USB 连接设备或配置设备 IP"})
            # 自动使用第一个可用设备
            serial = available[0]["serial"]
            device_config["tv_ip"] = serial
            from common.config_manager import save_device_config
            save_device_config(data_dir, device_config)
            from common.adb_utils import check_adb_device
            ok, msg = check_adb_device(serial)
            conn_type = available[0]["type"]
            type_label = "USB" if conn_type == "usb" else "网络"
            return jsonify({"success": ok, "message": f"已自动检测到{type_label}设备 {serial}" + (f"，{msg}" if msg else "，连接正常")})
        from common.adb_utils import check_adb_device
        ok, msg = check_adb_device(tv_ip)
        return jsonify({"success": ok, "message": msg if msg else "设备连接正常"})

    @bp.route("/api/tv/input-devices", methods=["GET"])
    def list_input_devices():
        """获取 TV 上的输入设备列表（用于选择 getevent 监听设备）"""
        tv_ip = device_config.get("tv_ip")
        if not tv_ip:
            return jsonify({"success": False, "error": "未配置设备地址，请先连接设备", "data": []})
        try:
            import re
            from common.adb_utils import run_adb
            result = run_adb(["shell", "getevent", "-pl"],
                             device_serial=tv_ip, timeout=10)
            output = result.stdout.decode("utf-8", errors="ignore")

            devices = []
            current_device = None
            current_name = ""
            has_key = False

            for line in output.splitlines():
                dev_match = re.match(r"add device \d+:\s*(/dev/input/event\d+)", line)
                if dev_match:
                    # 保存上一个设备
                    if current_device and has_key:
                        devices.append({"path": current_device, "name": current_name})
                    current_device = dev_match.group(1)
                    current_name = ""
                    has_key = False
                    continue
                name_match = re.match(r'\s+name:\s+"(.+)"', line)
                if name_match:
                    current_name = name_match.group(1)
                    continue
                if current_device and re.match(r"\s+KEY", line):
                    has_key = True

            # 最后一个设备
            if current_device and has_key:
                devices.append({"path": current_device, "name": current_name})

            return jsonify({"success": True, "data": devices})
        except Exception as e:
            return jsonify({"success": False, "error": str(e), "data": []})

    @bp.route("/api/tv/version", methods=["GET"])
    def version():
        """版本检查（兼容旧前端）"""
        return jsonify({"success": True, "message": "已经是最新版本"}), 200

    @bp.route("/api/tv/adb_devices", methods=["GET"])
    def adb_devices():
        """获取 ADB 设备列表（兼容旧前端）"""
        try:
            from common.adb_utils import run_adb
            result = run_adb(["devices"])
            output = result.stdout.decode("utf-8", errors="ignore")
            return jsonify({"success": True, "output": output})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @bp.route("/api/tv/adb_devices/list", methods=["GET"])
    def adb_devices_list():
        """获取已连接 ADB 设备的结构化列表"""
        try:
            from common.adb_utils import list_adb_devices
            devices = list_adb_devices()
            return jsonify({"success": True, "data": devices})
        except Exception as e:
            return jsonify({"success": False, "error": str(e), "data": []})

    return bp
