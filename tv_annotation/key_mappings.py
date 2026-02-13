"""
TV 遥控器按键映射
Linux input event code → 按键名 → Android keycode
"""

# Linux input event codes → 可读按键名
KEY_CODE_MAP = {
    # 方向键
    103: "UP", 108: "DOWN", 105: "LEFT", 106: "RIGHT",
    # 设置 / 信源
    561: "SETTING", 471: "SOURCE",
    # 确认 / 返回
    28: "ENTER", 96: "ENTER", 158: "BACK", 1: "ESC",
    # 主页 / 菜单
    102: "HOME", 172: "HOME", 139: "MENU", 127: "MENU",
    # 音量
    115: "VOLUME_UP", 114: "VOLUME_DOWN", 113: "MUTE",
    # 频道
    402: "CHANNEL_UP", 403: "CHANNEL_DOWN",
    # 数字键 0-9
    2: "1", 3: "2", 4: "3", 5: "4", 6: "5",
    7: "6", 8: "7", 9: "8", 10: "9", 11: "0",
    # 媒体控制
    164: "PLAY_PAUSE", 166: "STOP", 167: "RECORD",
    168: "REWIND", 208: "FAST_FORWARD",
    163: "NEXT", 165: "PREVIOUS",
    # 电源
    116: "POWER",
    # 功能键
    59: "F1", 60: "F2", 61: "F3", 62: "F4",
    # 其他
    14: "BACKSPACE", 57: "SPACE", 111: "DELETE",
}

# 按键名 → Android ADB keycode
ADB_KEYCODE_MAP = {
    "UP": "KEYCODE_DPAD_UP",
    "DOWN": "KEYCODE_DPAD_DOWN",
    "LEFT": "KEYCODE_DPAD_LEFT",
    "RIGHT": "KEYCODE_DPAD_RIGHT",
    "ENTER": "KEYCODE_ENTER",
    "BACK": "KEYCODE_BACK",
    "ESC": "KEYCODE_BACK",
    "HOME": "KEYCODE_HOME",
    "SETTING": "4077",
    "SOURCE": "178",
    "MENU": "KEYCODE_MENU",
    "VOLUME_UP": "KEYCODE_VOLUME_UP",
    "VOLUME_DOWN": "KEYCODE_VOLUME_DOWN",
    "MUTE": "KEYCODE_MUTE",
    "CHANNEL_UP": "KEYCODE_CHANNEL_UP",
    "CHANNEL_DOWN": "KEYCODE_CHANNEL_DOWN",
    "1": "KEYCODE_1", "2": "KEYCODE_2", "3": "KEYCODE_3",
    "4": "KEYCODE_4", "5": "KEYCODE_5", "6": "KEYCODE_6",
    "7": "KEYCODE_7", "8": "KEYCODE_8", "9": "KEYCODE_9",
    "0": "KEYCODE_0",
    "PLAY_PAUSE": "KEYCODE_MEDIA_PLAY_PAUSE",
    "STOP": "KEYCODE_MEDIA_STOP",
    "RECORD": "KEYCODE_MEDIA_RECORD",
    "REWIND": "KEYCODE_MEDIA_REWIND",
    "FAST_FORWARD": "KEYCODE_MEDIA_FAST_FORWARD",
    "NEXT": "KEYCODE_MEDIA_NEXT",
    "PREVIOUS": "KEYCODE_MEDIA_PREVIOUS",
    "POWER": "KEYCODE_POWER",
    "F1": "KEYCODE_F1", "F2": "KEYCODE_F2",
    "F3": "KEYCODE_F3", "F4": "KEYCODE_F4",
    "BACKSPACE": "KEYCODE_DEL",
    "SPACE": "KEYCODE_SPACE",
    "DELETE": "KEYCODE_FORWARD_DEL",
}


def get_key_name(key_code):
    """将 Linux input event code 转换为可读名称"""
    return KEY_CODE_MAP.get(key_code, f"UNKNOWN_{key_code}")


def get_adb_keycode(key_name):
    """获取 ADB 回放用的 keycode"""
    return ADB_KEYCODE_MAP.get(key_name, f"KEYCODE_{key_name}")
