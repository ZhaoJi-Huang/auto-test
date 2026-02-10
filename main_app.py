"""
统一后端服务 - 整合TV和Mobile功能
"""

import os
from pathlib import Path
import sys
import logging
import atexit
from flask import Flask, send_from_directory, request

# 配置路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TV_MODULE_DIR = BASE_DIR
MOBILE_MODULE_DIR = BASE_DIR  # 使用 BASE_DIR 以便能找到 mobile_annotation 包

# 添加模块路径
sys.path.insert(0, TV_MODULE_DIR)
sys.path.insert(0, MOBILE_MODULE_DIR)

# 日志目录和文件（每次启动清空）
LOG_DIR = os.path.join(BASE_DIR, "log")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "app.log")
open(LOG_FILE, "w").close()  # 启动时清空旧日志

# 创建一个同时写入文件和控制台的类
class TeeOutput:
    """同时将输出写入文件和控制台"""
    def __init__(self, file_path, original_stream):
        self.file = open(file_path, 'a', encoding='utf-8', buffering=1)  # 行缓冲
        self.original_stream = original_stream
    
    def write(self, text):
        # 写入控制台
        self.original_stream.write(text)
        self.original_stream.flush()
        # 写入文件
        self.file.write(text)
        self.file.flush()
    
    def flush(self):
        self.original_stream.flush()
        self.file.flush()
    
    def close(self):
        if self.file:
            self.file.close()

# 保存原始的标准输出和错误流（用于 TeeOutput）
_original_stdout = sys.stdout
_original_stderr = sys.stderr

# 重定向标准输出和标准错误到文件和控制台
sys.stdout = TeeOutput(LOG_FILE, _original_stdout)
sys.stderr = TeeOutput(LOG_FILE, _original_stderr)

# 注册退出时关闭文件的清理函数
def cleanup_logs():
    """程序退出时关闭日志文件"""
    if isinstance(sys.stdout, TeeOutput):
        sys.stdout.close()
    if isinstance(sys.stderr, TeeOutput):
        sys.stderr.close()

atexit.register(cleanup_logs)

# 配置 logging（也会写入文件和控制台）
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)

# 初始化Flask应用
# 打包后使用 backend/frontend_dist，开发时使用 frontend/dist
static_folder = os.path.join(BASE_DIR, 'frontend_dist')

# 检查静态文件夹是否存在
if not os.path.exists(static_folder):
    print(f"[WARNING] Static folder not found: {static_folder}")
    print(f"[WARNING] Please build frontend first: cd frontend && npm run build")
    static_folder = None

app = Flask(__name__, 
            static_folder=static_folder,
            static_url_path='')
app.config['SECRET_KEY'] = 'unified-annotation-platform-secret'

# 添加CORS支持
@app.after_request
def after_request(response):
    """添加CORS头"""
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,X-Version')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# 版本检查中间件
@app.before_request
def check_version():
    """检查请求中的version header与服务器version是否一致"""
    # 跳过OPTIONS请求（CORS预检）
    if request.method == 'OPTIONS':
        return None
    
    # 跳过version接口本身，避免循环依赖
    if request.path != '/api/tv/version':
        return None
    
    try:
        # 获取请求头中的version
        client_version = request.headers.get('X-Version', '')
        
        # 如果没有version header，跳过检查（兼容旧版本客户端）
        if not client_version:
            return None
        
        # 获取服务器端的version
        backend_dir = BASE_DIR
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)
    
        server_version = '3.4'
        
        # 比较版本号
        if client_version != server_version:
            from flask import jsonify
            return jsonify({
                "code": 426,  # 426 Upgrade Required
                "message": "版本不匹配，请更新工具后继续使用",
                "data": {
                    "client_version": client_version,
                    "server_version": server_version
                }
            }), 426
    except Exception as e:
        # 如果检查过程中出错，记录日志但不阻止请求（避免影响正常使用）
        print(f"[WARNING] Version check failed: {e}")
        import traceback
        traceback.print_exc()
    
    return None

print(f"[INFO] BASE_DIR: {BASE_DIR}")
print(f"[INFO] Static folder: {static_folder}")

# 数据目录配置 - 根据系统版本确定存储路径
import platform
if platform.system() == 'Windows':
    ANNOTATION_BASE = "C:/annotation"
else:
    ANNOTATION_BASE = f"{Path.home()}/annotation"

# 使用正斜杠统一路径格式
TV_BASE_DIR = os.path.join(ANNOTATION_BASE, "tv").replace("\\", "/")
MOBILE_BASE_DIR = os.path.join(ANNOTATION_BASE, "mobile").replace("\\", "/")

# 确保目录存在
os.makedirs(TV_BASE_DIR, exist_ok=True)
os.makedirs(MOBILE_BASE_DIR, exist_ok=True)

# ==================== 导入模块 ====================

# TV模块导入
try:
    import sys
    tv_annotation_path = BASE_DIR  # 使用 BASE_DIR 而不是 tv_annotation 子目录
    sys.path.insert(0, tv_annotation_path)
    from tv_annotation.app import register_tv_routes
    tv_available = True
    print("[OK] TV模块加载成功")
except Exception as e:
    tv_available = False
    print(f"[ERROR] TV模块加载失败: {e}")

# Mobile模块导入
try:
    from mobile_annotation.app import register_mobile_routes
    mobile_available = True
    print("[OK] Mobile模块加载成功")
except Exception as e:
    mobile_available = False
    print(f"[ERROR] Mobile模块加载失败: {e}")


# ==================== 主页路由 ====================

@app.route('/')
def index():
    """主页 - 返回前端构建产物"""
    # 统一使用 backend/frontend_dist 目录
    # BASE_DIR 在打包和开发环境中都指向 backend 目录
    static_dir = os.path.join(BASE_DIR, 'frontend_dist')
    
    # 检查index.html是否存在
    index_path = os.path.join(static_dir, 'index.html')
    if not os.path.exists(index_path):
        return f"""
        <html>
        <body>
            <h1>Frontend not built</h1>
            <p>Static directory: {static_dir}</p>
            <p>index.html not found at: {index_path}</p>
            <p>Please build frontend:</p>
            <pre>cd frontend && npm run build</pre>
        </body>
        </html>
        """, 404
    
    return send_from_directory(static_dir, 'index.html')


@app.route('/api/status')
def api_status():
    """API状态检查"""
    return {
        "status": "ok",
        "modules": {
            "tv": tv_available,
            "mobile": mobile_available
        }
    }


# ==================== 注册路由 ====================

def register_routes():
    """注册所有模块的路由"""
    
    if tv_available:
        # 项目重启时清空训练数据同步进度文件
        sync_progress_file = os.path.join(TV_BASE_DIR, "train_data_sync_progress.json")
        if os.path.exists(sync_progress_file):
            try:
                os.remove(sync_progress_file)
                print(f"[INFO] 已清空训练数据同步进度文件: {sync_progress_file}")
            except Exception as e:
                print(f"[WARNING] 清空训练数据同步进度文件失败: {e}")
        
        try:
            register_tv_routes(app, TV_BASE_DIR)
            print("[OK] TV路由注册成功")
        except Exception as e:
            print(f"[ERROR] TV路由注册失败: {e}")
    
    if mobile_available:
        try:
            register_mobile_routes(app, MOBILE_BASE_DIR)
            print("[OK] Mobile路由注册成功")
        except Exception as e:
            print(f"[ERROR] Mobile路由注册失败: {e}")

# ==================== 启动服务 ====================

# 立即注册路由（确保在任何情况下都能注册）
register_routes()

# 禁用 Flask 默认的请求日志
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)  # 只显示错误，不显示每个请求

if __name__ == '__main__':
    print("\n" + "=" * 70)
    print(" " * 15 + "Unified Annotation Platform")
    print("=" * 70)
    
    print("\n" + "=" * 70)
    print("功能模块:")
    print(f"  {'[OK]' if tv_available else '[X]'} TV Annotation - 电视自动化测试标注")
    print(f"  {'[OK]' if mobile_available else '[X]'} Mobile Annotation - 手机操作录制回放")
    print("=" * 70)
    print("数据目录:")
    print(f"  TV数据: {TV_BASE_DIR}")
    print(f"  Mobile数据: {MOBILE_BASE_DIR}")
    print("=" * 70)
    print("服务信息:")
    print("  地址: http://localhost:5004")
    print("  端口: 5004")
    print("=" * 70)
    print("前端开发:")
    print("  cd frontend && npm run dev")
    print("=" * 70)
    print("\n启动中...\n")
    
    # 使用 Flask 内置服务器启动（已移除 SocketIO）
    app.run(host='0.0.0.0', port=5004, debug=False)
