"""
TV 自动化测试录制回放工具 - 后端服务入口
仅支持 TV 设备，通过 ADB + 采集卡 实现录制与回放
"""

import os
import sys
import logging
import atexit
import json

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
open(LOG_FILE, "w").close()


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
        logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)

# ==================== Flask 应用 ====================

from flask import Flask, send_from_directory, jsonify

# 加载应用配置
from common.config_manager import load_app_config

app_config = load_app_config()
DATA_DIR = app_config["data_dir"]
SCRIPTS_REPO_PATH = app_config["scripts_repo_path"]

# 确保目录存在
os.makedirs(DATA_DIR, exist_ok=True)
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


@app.after_request
def after_request(response):
    """添加 CORS 头"""
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization,X-Version")
    response.headers.add("Access-Control-Allow-Methods", "GET,PUT,POST,DELETE,OPTIONS")
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

    app.run(host="0.0.0.0", port=5004, debug=False)
