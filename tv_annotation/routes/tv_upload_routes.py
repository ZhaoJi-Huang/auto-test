"""
TV数据上传路由 - OSS上传功能
使用公共上传路由
"""
import os
import sys

# 添加 backend 目录到路径，以便导入公共路由
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from common.routes.upload_routes import create_upload_routes


def create_tv_upload_routes(tv_data_dir):
    """
    创建TV数据上传路由蓝图
    
    Args:
        tv_data_dir: TV数据目录路径
    """
    # 使用公共路由，传入模块名和数据目录
    return create_upload_routes(
        module_name='tv',
        data_dir=tv_data_dir
    )
