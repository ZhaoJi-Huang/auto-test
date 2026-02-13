"""
视频流路由 - 实时屏幕预览
"""

import time
from flask import Blueprint, Response


def create_stream_routes(device_config):
    """创建视频流路由蓝图"""

    bp = Blueprint("tv_stream", __name__)

    @bp.route("/api/tv/stream", methods=["GET"])
    def screen_stream():
        """实时屏幕流（MJPEG）"""
        def generate():
            from tv_annotation.capture_card import capture_card
            # 确保采集卡启动
            if not capture_card.is_running:
                device_id = device_config.get("device_id", 0)
                if not capture_card.start(device_id=device_id):
                    return
            # 等待第一帧
            for _ in range(30):
                if capture_card.get_frame() is not None:
                    break
                time.sleep(0.1)
            # 推流
            try:
                while True:
                    jpeg = capture_card.get_frame_as_jpeg(quality=80)
                    if jpeg:
                        yield (b"--frame\r\n"
                               b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n")
                    time.sleep(0.033)  # ~30fps
            except GeneratorExit:
                pass

        return Response(
            generate(),
            mimetype="multipart/x-mixed-replace; boundary=frame",
        )

    @bp.route("/api/tv/screenshot", methods=["GET"])
    def take_screenshot():
        """获取当前屏幕截图（JPEG）"""
        from tv_annotation.capture_card import capture_card
        jpeg = capture_card.get_frame_as_jpeg(quality=95)
        if jpeg:
            return Response(jpeg, mimetype="image/jpeg")
        return {"success": False, "error": "无法获取画面"}, 500

    return bp
