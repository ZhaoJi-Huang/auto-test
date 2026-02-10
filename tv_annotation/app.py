"""
TV Annotation Module - 路由注册
将TV相关的所有API注册到主应用
"""

import os
import sys
import json
import subprocess
from flask import Blueprint

from common.utils import ADB_PATH

# 确保backend目录在sys.path中（用于导入util等依赖）
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# 导入TV相关模块（已迁移到tv_annotation目录内）
from .tv_recorder import TVRecorder
from .routes.tv_config_routes import create_tv_config_routes
from .routes.tv_testcase_routes import create_tv_testcase_routes
from .routes.tv_control_routes import create_tv_control_routes
from .routes.train_data_routes import create_train_data_routes
from .routes.tv_recording_routes import create_tv_recording_routes
from .routes.tv_upload_routes import create_tv_upload_routes


# 全局变量
tv_recorder = None
device_config = {}

# 默认设备配置
DEFAULT_DEVICE_CONFIG = {
    'tv_ip': "10.144.131.71:5555",
    'serial_port': "/dev/cu.usbserial-11220",
    'remote_port': "/dev/cu.usbserial-11230",
    'device_id': 1
}

def load_device_config(base_dir):
    """从配置文件加载设备配置"""
    global device_config
    config_file = os.path.join(base_dir, "device_config.json")
    
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                device_config = json.load(f)
            print(f"  [OK] 已从配置文件加载设备配置: {config_file}")
        except Exception as e:
            print(f"  [WARNING] 读取设备配置文件失败: {e}，使用默认配置")
            device_config = DEFAULT_DEVICE_CONFIG.copy()
    else:
        # 创建默认配置文件
        device_config = DEFAULT_DEVICE_CONFIG.copy()
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(device_config, f, ensure_ascii=False, indent=2)
            print(f"  [OK] 已创建默认设备配置文件: {config_file}")
        except Exception as e:
            print(f"  [WARNING] 创建设备配置文件失败: {e}")
    
    return device_config


def register_tv_routes(app, base_dir):
    """
    注册TV模块的所有路由
    
    Args:
        app: Flask应用实例
        base_dir: TV数据基础目录
    """
    
    global tv_recorder, device_config
    
    # 加载设备配置
    load_device_config(base_dir)
    
    # 设置数据目录 - 直接使用 base_dir (C:/annotation/tv)，不再添加 /data 子目录
    # 最终路径: C:/annotation/tv/[测试用例]/[步骤]/[数据]
    TV_DATA_DIR = os.path.join(base_dir, "data")
    TV_LOG_DIR = os.path.join(base_dir, "log")
    DATA_XLSX_PATH = os.path.join(base_dir, "data.xlsx")
    TRAIN_DATA_CONFIG_FILE = os.path.join(base_dir, "train_data_config.json")
    
    os.makedirs(TV_DATA_DIR, exist_ok=True)
    os.makedirs(TV_LOG_DIR, exist_ok=True)

    # 初始化训练数据配置文件
    if not os.path.exists(TRAIN_DATA_CONFIG_FILE):
        default_config = {
            "api_base_url": "http://localhost:5001",
            "api_token": "your-token-here"
        }
        with open(TRAIN_DATA_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, ensure_ascii=False, indent=2)
    
    # 初始化服务
    def setup_tv_services():
        tv_ip = device_config['tv_ip']
        serial_port = device_config['serial_port']
        remote_port = device_config['remote_port']
        
        config_file = os.path.join(base_dir, "device_config.json")
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(device_config, f, ensure_ascii=False, indent=2)
            print(f"  [OK] 已创建默认设备配置文件: {config_file}")
        except Exception as e:
            print(f"  [WARNING] 创建设备配置文件失败: {e}")
        
        try:
            result = subprocess.run([ADB_PATH, 'connect', tv_ip],
                                  capture_output=True, text=True, timeout=10)
            print(f"ADB connect result: {result.stdout}")
        except Exception as e:
            print(f"ADB connect error: {e}")
        
    
    # # 初始化服务
    # try:
    #     setup_tv_services()
    # except Exception as e:
    #     print(f"TV服务初始化失败: {e}")
    
    # 初始化TV录制器
    print(f"  [INFO] 初始化TV录制器，base_dir: {base_dir}")
    tv_recorder = TVRecorder(
        device_config=device_config,
        base_dir=base_dir  # 传入正确的base_dir路径
    )
    
    # 预启动视频采集卡（确保视频流立即可用）
    from .tv_recorder import capture_card
    try:
        if capture_card.start(device_id=device_config['device_id'], width=1920, height=1080):
            print(f"  [OK] 视频采集卡已预启动")
        else:
            print(f"  [WARNING] 视频采集卡启动失败，视频流将使用ADB模式")
    except Exception as e:
        print(f"  [WARNING] 视频采集卡初始化错误: {e}")
    
    
    # ==================== 注册蓝图路由 ====================
    
    # 当前采集文件夹路径（在函数内部定义）
    current_folder_path = None
    
    def get_current_folder_path():
        return current_folder_path
    
    def set_current_folder_path(path):
        nonlocal current_folder_path
        current_folder_path = path
    
    # 1. 注册TV配置路由
    config_bp = create_tv_config_routes(device_config, setup_tv_services)
    app.register_blueprint(config_bp)
    
    # 2. 注册TV测试用例路由
    testcase_bp = create_tv_testcase_routes(DATA_XLSX_PATH)
    app.register_blueprint(testcase_bp)
    
    # 3. 注册TV遥控操作路由（移除remote_control依赖）
    control_bp = create_tv_control_routes(
        get_current_folder_path,
        set_current_folder_path,
        TV_DATA_DIR,
        device_config
    )
    app.register_blueprint(control_bp)
    
    # 5. 注册训练数据路由
    try:
        train_data_bp = create_train_data_routes(base_dir)
        app.register_blueprint(train_data_bp)
        print(f"  [OK] 训练数据路由已注册")
    except Exception as e:
        print(f"  [WARNING] 训练数据路由注册失败: {e}")
    
    # 6. 注册TV录制路由
    try:
        recording_bp = create_tv_recording_routes(tv_recorder)
        app.register_blueprint(recording_bp)
        print(f"  [OK] TV录制路由已注册")
    except Exception as e:
        print(f"  [WARNING] TV录制路由注册失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 7. 注册TV上传路由
    try:
        upload_bp = create_tv_upload_routes(TV_DATA_DIR)
        app.register_blueprint(upload_bp)
        print(f"  [OK] TV上传路由已注册")
    except Exception as e:
        print(f"  [WARNING] TV上传路由注册失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 统计注册的路由数量
    tv_routes_count = len([r for r in app.url_map.iter_rules() if '/api/tv/' in r.rule or '/tv_data/' in r.rule])
    print(f"  [OK] TV路由已注册 (共 {tv_routes_count} 个API)")

