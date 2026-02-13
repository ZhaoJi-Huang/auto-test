"""
TV 模块 - 路由注册
将 TV 相关的所有 API 蓝图注册到 Flask 应用
"""

import os
import sys

# 确保 backend 目录在 sys.path 中
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from common.config_manager import load_device_config, save_device_config


def register_tv_routes(app, data_dir, scripts_repo_path):
    """注册 TV 模块所有路由蓝图

    Args:
        app: Flask 应用实例
        data_dir: 数据根目录（../data 的绝对路径）
        scripts_repo_path: 脚本仓库路径（../tv-test-scripts 的绝对路径）
    """

    # 加载设备配置
    device_config = load_device_config(data_dir)
    print(f"  [INFO] 设备配置: tv_ip={device_config.get('tv_ip', '未配置')}")

    # ---------- 1. 配置路由 ----------
    try:
        from .routes.config_routes import create_config_routes
        bp = create_config_routes(device_config, data_dir)
        app.register_blueprint(bp)
        print("  [OK] 配置路由已注册")
    except Exception as e:
        print(f"  [WARN] 配置路由注册失败: {e}")

    # ---------- 2. 录制路由 ----------
    try:
        from .routes.recording_routes import create_recording_routes
        bp = create_recording_routes(device_config, scripts_repo_path)
        app.register_blueprint(bp)
        print("  [OK] 录制路由已注册")
    except Exception as e:
        print(f"  [WARN] 录制路由注册失败: {e}")

    # ---------- 3. 回放路由 ----------
    try:
        from .routes.replay_routes import create_replay_routes
        bp = create_replay_routes(device_config, data_dir, scripts_repo_path)
        app.register_blueprint(bp)
        print("  [OK] 回放路由已注册")
    except Exception as e:
        print(f"  [WARN] 回放路由注册失败: {e}")

    # ---------- 4. 用例管理路由（Jira + 自定义） ----------
    try:
        from .routes.case_routes import create_case_routes
        bp = create_case_routes(data_dir, scripts_repo_path)
        app.register_blueprint(bp)
        print("  [OK] 用例管理路由已注册")
    except Exception as e:
        print(f"  [WARN] 用例管理路由注册失败: {e}")

    # ---------- 5. 测试计划路由 ----------
    try:
        from .routes.plan_routes import create_plan_routes
        bp = create_plan_routes(data_dir, scripts_repo_path)
        app.register_blueprint(bp)
        print("  [OK] 测试计划路由已注册")
    except Exception as e:
        print(f"  [WARN] 测试计划路由注册失败: {e}")

    # ---------- 6. 统计路由 ----------
    try:
        from .routes.stats_routes import create_stats_routes
        bp = create_stats_routes(data_dir)
        app.register_blueprint(bp)
        print("  [OK] 统计路由已注册")
    except Exception as e:
        print(f"  [WARN] 统计路由注册失败: {e}")

    # ---------- 7. Git 协作路由 ----------
    try:
        from .routes.git_routes import create_git_routes
        bp = create_git_routes(scripts_repo_path)
        app.register_blueprint(bp)
        print("  [OK] Git 协作路由已注册")
    except Exception as e:
        print(f"  [WARN] Git 协作路由注册失败: {e}")

    # ---------- 8. 视频流路由 ----------
    try:
        from .routes.stream_routes import create_stream_routes
        bp = create_stream_routes(device_config)
        app.register_blueprint(bp)
        print("  [OK] 视频流路由已注册")
    except Exception as e:
        print(f"  [WARN] 视频流路由注册失败: {e}")

    # 统计
    tv_routes = [r for r in app.url_map.iter_rules() if "/api/tv/" in r.rule]
    print(f"  [OK] TV 路由注册完毕（共 {len(tv_routes)} 个 API）")
