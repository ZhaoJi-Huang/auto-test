"""
公共工具函数模块
"""
import os
import re
import shutil


def get_adb_path():
    """获取adb可执行文件的完整路径

    优先使用 shutil.which 在 PATH 中查找，
    找不到时尝试常见的 Windows 安装位置。

    Returns:
        adb 可执行文件的完整路径字符串，找不到则返回 'adb'（依赖 PATH）
    """
    # 先尝试 PATH
    path = shutil.which("adb")
    if path:
        return path

    # Windows 常见位置
    common_dirs = [
        os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools"),
        r"D:\Android_adb\platform-tools-latest-windows\platform-tools",
        r"C:\platform-tools",
    ]
    for d in common_dirs:
        candidate = os.path.join(d, "adb.exe")
        if os.path.isfile(candidate):
            return candidate

    # 都找不到，返回 'adb' 让调用方报出清晰的错误
    return "adb"


# 模块级缓存，启动时解析一次
ADB_PATH = get_adb_path()


def sanitize_filename(name):
    """清理文件名中的特殊字符，防止创建文件夹报错
    
    注意：此函数会替换所有特殊字符，包括路径分隔符 / 和 \，因为文件名中不应该包含这些字符
    
    Args:
        name: 原始文件名
        
    Returns:
        清理后的文件名
    """
    if not name:
        return name
    # Windows 文件系统不允许的特殊字符: < > : " / \ | ? *
    # 同时替换换行符、回车符、制表符等控制字符
    # 替换所有不允许的字符为下划线
    sanitized = re.sub(r'[<>:"/\\|?*\r\n\t]', '_', str(name))
    # 移除所有其他控制字符（ASCII 0-31）
    sanitized = re.sub(r'[\x00-\x1f]', '_', sanitized)
    # 移除首尾空格和点号（Windows不允许以点号结尾）
    sanitized = sanitized.strip(' .')
    # 如果清理后为空，使用默认名称
    if not sanitized:
        sanitized = 'unnamed'
    return sanitized
