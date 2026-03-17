"""
TV 自动化测试录制回放工具 - 后端服务入口
仅支持 TV 设备，通过 ADB + 采集卡 实现录制与回放
"""

import os
import sys
import logging
import logging.handlers
import atexit
import json
import time
import shutil

# ==================== 自动更新 ====================

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

def _auto_update():
    """启动时自动拉取最新代码和脚本，代码有更新时自动重启"""
    # 防止无限重启
    if os.environ.get("JUST_UPDATED"):
        os.environ.pop("JUST_UPDATED", None)
        print("[AutoUpdate] 跳过更新检查（刚完成更新重启）")
        return

    import subprocess

    # 1. 检查工具代码仓库是否有未提交修改
    try:
        result = subprocess.run(
            ["git", "-C", BACKEND_DIR, "status", "--porcelain"],
            capture_output=True, text=True, timeout=10,
        )
        if result.stdout.strip():
            print("[AutoUpdate] 本地有未提交修改，跳过代码更新")
        else:
            # 2. git pull 工具代码
            result = subprocess.run(
                ["git", "-C", BACKEND_DIR, "pull", "--ff-only"],
                capture_output=True, text=True, timeout=10,
            )
            output = result.stdout.strip()
            print(f"[AutoUpdate] 工具代码更新: {output}")
            if "Already up to date" not in output and result.returncode == 0:
                print("[AutoUpdate] 代码有更新，正在重启...")
                os.environ["JUST_UPDATED"] = "1"
                os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e:
        print(f"[AutoUpdate] 工具代码更新失败（不影响启动）: {e}")

    # 3. git pull 脚本仓库
    try:
        from common.config_manager import load_app_config
        app_cfg = load_app_config()
        scripts_path = app_cfg["scripts_repo_path"]
        if os.path.isdir(os.path.join(scripts_path, ".git")):
            result = subprocess.run(
                ["git", "-C", scripts_path, "pull", "--ff-only"],
                capture_output=True, text=True, timeout=10,
            )
            print(f"[AutoUpdate] 脚本仓库更新: {result.stdout.strip()}")
        else:
            print(f"[AutoUpdate] 脚本仓库不存在或非 Git 仓库: {scripts_path}")
    except Exception as e:
        print(f"[AutoUpdate] 脚本仓库更新失败（不影响启动）: {e}")


# 执行自动更新（在 Flask 初始化之前）
_auto_update()


# ==================== 日志配置 ====================

LOG_DIR = os.path.join(BACKEND_DIR, "log")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "app.log")


class TeeOutput:
    """同时写入文件和控制台"""
    def __init__(self, file_path, original_stream):
        self.file = open(file_path, "a", encoding="utf-8", buffering=1)
        self.original_stream = original_stream

    def write(self, text):
        self.original_stream.write(text)
        self.original_stream.flush()
        self.file.write(text)
        self.file.flush()

    def flush(self):
        self.original_stream.flush()
        self.file.flush()

    def close(self):
        if self.file:
            self.file.close()


_original_stdout = sys.stdout
_original_stderr = sys.stderr
sys.stdout = TeeOutput(LOG_FILE, _original_stdout)
sys.stderr = TeeOutput(LOG_FILE, _original_stderr)


def _cleanup_logs():
    if isinstance(sys.stdout, TeeOutput):
        sys.stdout.close()
    if isinstance(sys.stderr, TeeOutput):
        sys.stderr.close()

atexit.register(_cleanup_logs)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.handlers.RotatingFileHandler(
            LOG_FILE, maxBytes=10*1024*1024, backupCount=5, encoding="utf-8"
        ),
        logging.StreamHandler(sys.stdout),
    ],
)

# ==================== Flask 应用 ====================

from flask import Flask, send_from_directory, jsonify, request as flask_request

# 加载应用配置
from common.config_manager import load_app_config

app_config = load_app_config()
DATA_DIR = app_config["data_dir"]
SCRIPTS_REPO_PATH = app_config["scripts_repo_path"]

# 确保目录存在
os.makedirs(DATA_DIR, exist_ok=True)

# 初始化审计日志
from common.audit_log import init_audit_log
init_audit_log(DATA_DIR)
os.makedirs(os.path.join(DATA_DIR, "replay"), exist_ok=True)

# 尝试创建脚本仓库目录（如果不存在）
if not os.path.exists(SCRIPTS_REPO_PATH):
    os.makedirs(SCRIPTS_REPO_PATH, exist_ok=True)
    print(f"[INFO] 已创建脚本仓库目录: {SCRIPTS_REPO_PATH}")

# 初始化 Flask
static_folder = os.path.join(BACKEND_DIR, "frontend_dist")
if not os.path.exists(static_folder):
    static_folder = None

app = Flask(__name__, static_folder=static_folder, static_url_path="")
app.config["SECRET_KEY"] = "tv-automation-tool-secret"

api_logger = logging.getLogger("api")


@app.before_request
def _log_request_start():
    flask_request._start_time = time.time()


@app.after_request
def after_request(response):
    """添加 CORS 头 + API 请求日志"""
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization,X-Version")
    response.headers.add("Access-Control-Allow-Methods", "GET,PUT,POST,DELETE,OPTIONS")

    # API 请求日志
    if flask_request.path.startswith("/api/") and flask_request.method != "OPTIONS":
        duration = time.time() - getattr(flask_request, '_start_time', time.time())
        parts = [f"{flask_request.method} {flask_request.path} -> {response.status_code} ({duration:.2f}s)"]

        # Query 参数
        if flask_request.args:
            parts.append(f"params={dict(flask_request.args)}")

        # Request Body（仅小于 2KB 的 JSON）
        if flask_request.is_json and flask_request.content_length and flask_request.content_length < 2048:
            body = flask_request.get_json(silent=True)
            if body:
                parts.append(f"body={body}")

        # 失败时记录错误摘要
        if response.status_code >= 400:
            error_info = response.get_data(as_text=True)[:500]
            parts.append(f"error={error_info}")

        api_logger.info(" ".join(parts))

    return response


# ==================== 基础路由 ====================

@app.route("/")
def index():
    """主页"""
    static_dir = os.path.join(BACKEND_DIR, "frontend_dist")
    index_path = os.path.join(static_dir, "index.html")
    if not os.path.exists(index_path):
        return "<h1>Frontend not built</h1><p>cd frontend && npm run build</p>", 404
    return send_from_directory(static_dir, "index.html")


@app.errorhandler(Exception)
def handle_exception(e):
    """全局异常处理：返回 JSON 而非 HTML 错误页"""
    api_logger.exception(f"未捕获异常: {flask_request.method} {flask_request.path}")
    return jsonify({"success": False, "error": f"服务器内部错误: {str(e)}"}), 500


@app.errorhandler(404)
def fallback(e):
    """SPA fallback：非 API 路径返回 index.html，由前端路由处理"""
    from flask import request
    if request.path.startswith("/api/"):
        return jsonify({"success": False, "error": "接口不存在"}), 404
    static_dir = os.path.join(BACKEND_DIR, "frontend_dist")
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return send_from_directory(static_dir, "index.html")
    return "Not Found", 404


@app.route("/api/status")
def api_status():
    """服务状态（兼容旧前端格式）"""
    return jsonify({
        "status": "ok",
        "modules": {
            "tv": True,
            "mobile": False
        },
        "data_dir": DATA_DIR,
        "scripts_repo_path": SCRIPTS_REPO_PATH,
    })


@app.route("/api/health")
def health_check():
    """健康检查：主动探测各依赖组件的实际状态"""
    checks = {}

    # 1. ADB 设备连接
    try:
        from common.config_manager import load_device_config
        from common.adb_utils import check_adb_device, ensure_device_serial
        device_config = load_device_config(DATA_DIR)
        serial, auto_msg = ensure_device_serial(device_config, DATA_DIR)
        if serial:
            ok, msg = check_adb_device(serial)
            detail = auto_msg + ("，连接正常" if ok else f"，{msg}") if auto_msg else msg
            checks["adb_device"] = {"status": "connected" if ok else "disconnected", "detail": detail}
        else:
            checks["adb_device"] = {"status": "not_configured", "detail": auto_msg or "未配置设备地址"}
    except Exception as e:
        checks["adb_device"] = {"status": "error", "detail": str(e)}

    # 2. 采集卡状态
    try:
        from tv_annotation.capture_card import CaptureCardManager
        cc = CaptureCardManager()
        checks["capture_card"] = {"status": "running" if cc.is_running else "stopped"}
    except Exception as e:
        checks["capture_card"] = {"status": "error", "detail": str(e)}

    # 3. 脚本仓库
    scripts_git = os.path.join(SCRIPTS_REPO_PATH, ".git")
    checks["scripts_repo"] = {
        "status": "ok" if os.path.isdir(scripts_git) else ("exists" if os.path.isdir(SCRIPTS_REPO_PATH) else "missing"),
    }

    # 4. 数据目录可写
    checks["data_dir_writable"] = os.access(DATA_DIR, os.W_OK)

    # 5. 磁盘剩余空间
    try:
        usage = shutil.disk_usage(DATA_DIR)
        checks["disk_free_mb"] = usage.free // (1024 * 1024)
    except Exception:
        checks["disk_free_mb"] = None

    healthy = checks.get("data_dir_writable", False)
    return jsonify({"healthy": healthy, "checks": checks}), 200 if healthy else 503


# ==================== 注册 TV 模块路由 ====================

try:
    from tv_annotation.app import register_tv_routes
    register_tv_routes(app, DATA_DIR, SCRIPTS_REPO_PATH)
    print("[OK] TV 模块路由注册成功")
except Exception as e:
    print(f"[ERROR] TV 模块路由注册失败: {e}")
    import traceback
    traceback.print_exc()


# ==================== 禁用请求日志 ====================

log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)


# ==================== 启动 ====================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("    TV 自动化测试录制回放工具")
    print("=" * 60)
    print(f"  数据目录:     {DATA_DIR}")
    print(f"  脚本仓库:     {SCRIPTS_REPO_PATH}")
    print(f"  服务地址:     http://localhost:5004")
    print("=" * 60 + "\n")

    app.run(host="0.0.0.0", port=5004, debug=False, threaded=True)
