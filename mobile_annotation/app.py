"""
Mobile模块路由注册
将Mobile相关的所有API注册到主应用
"""

import os

# 导入Mobile模块（已在mobile_annotation包内）
from .recorder import RecordingManager


# 全局管理器
recording_manager = None

def register_mobile_routes(app, base_dir):
    """
    注册Mobile模块的所有路由
    
    Args:
        app: Flask应用实例
        base_dir: Mobile数据基础目录
    """
    
    global recording_manager
    
    # 设置数据目录
    MOBILE_DATA_DIR = os.path.join(base_dir, "record_data")
    os.makedirs(MOBILE_DATA_DIR, exist_ok=True)
  
    
    recording_manager = RecordingManager(base_dir=MOBILE_DATA_DIR)
    
    # ==================== 注册各个路由蓝图 ====================
    
    try:
        # 导入录制管理路由
        from .routes.mobile_recording_routes import create_mobile_recording_routes
        recording_bp = create_mobile_recording_routes(recording_manager)
        app.register_blueprint(recording_bp)
        

        # 导入上传/回放路由（含 get_steps_records）
        from .routes.mobile_upload_routes import create_mobile_upload_routes
        upload_bp = create_mobile_upload_routes(MOBILE_DATA_DIR)
        app.register_blueprint(upload_bp)
        
        print("  [OK] Mobile设备/录制/回放/数据路由已注册")
    except Exception as e:
        print(f"  [WARNING] Mobile基础路由注册失败: {e}")
        import traceback
        traceback.print_exc()


    
    
    # ==================== 注册测试用例管理路由 ====================
    
    # 数据目录
    DATA_XLSX_PATH = os.path.join(base_dir, "data.xlsx")
    
    # 当前采集文件夹路径
    mobile_current_folder_path = None
    
    def get_mobile_current_folder_path():
        return mobile_current_folder_path
    
    def set_mobile_current_folder_path(path):
        nonlocal mobile_current_folder_path
        mobile_current_folder_path = path
    
    # 注册测试用例管理路由
    try:
        # 导入测试用例路由
        from .routes.mobile_testcase_routes import create_mobile_testcase_routes
        testcase_bp = create_mobile_testcase_routes(DATA_XLSX_PATH)
        app.register_blueprint(testcase_bp)
        
        # 导入控制路由
        from .routes.mobile_control_routes import create_mobile_control_routes
        control_bp = create_mobile_control_routes(
            get_mobile_current_folder_path,
            set_mobile_current_folder_path,
            MOBILE_DATA_DIR,
            recording_manager
        )
        app.register_blueprint(control_bp)
        
        print(f"  [OK] Mobile测试用例路由已注册")
    except Exception as e:
        print(f"  [WARNING] Mobile测试用例路由注册失败: {e}")
        import traceback
        traceback.print_exc()
    
    
    print(f"  [OK] Mobile路由已注册 (共 {len([r for r in app.url_map.iter_rules() if '/api/mobile/' in r.rule])} 个API)")
