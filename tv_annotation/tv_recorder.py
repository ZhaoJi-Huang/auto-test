"""
TV录制器模块 - 基于参考项目实现
支持ADB截图和视频采集卡两种方式
"""
import subprocess
import threading
import time
import os
import json
import re
from datetime import datetime
from flask import Response
import uuid
import glob, base64
from pathlib import Path

try:
    import cv2
    import numpy as np
    # 降低 OpenCV 捕获卡在无设备时的警告级别，避免刷屏
    try:
        cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
    except Exception:
        pass
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False
    print("Warning: OpenCV not installed, capture card support disabled")

from PIL import Image


class CaptureCardManager:
    """视频采集卡管理器 - 单例模式"""
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.cap = None
        self.device_id = 0
        self.frame_lock = threading.Lock()
        self.current_frame = None
        self.is_running = False
        self.capture_thread = None
    
    def start(self, device_id=0, width=1280, height=720):
        """启动视频采集"""
        self.device_id = device_id
        if not HAS_CV2:
            print("OpenCV not installed, cannot start capture card")
            return False

        if self.is_running:
            return True

        try:
            import platform
            if platform.system() == 'Windows':
                self.cap = cv2.VideoCapture(device_id, cv2.CAP_DSHOW)
            else:
                self.cap = cv2.VideoCapture(device_id)
            if not self.cap.isOpened():
                print(f"无法打开视频采集卡设备: {device_id}")
                return False
            
            # 设置分辨率
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            
            # 设置缓冲区大小为1，减少延迟
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            self.is_running = True
            self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.capture_thread.start()
            
            print(f"视频采集卡已启动: 设备{device_id}, 分辨率{width}x{height}")
            return True
        except Exception as e:
            print(f"启动视频采集卡失败: {e}")
            return False
    
    def stop(self):
        """停止视频采集"""
        self.is_running = False
        if self.capture_thread:
            self.capture_thread.join(timeout=2)
        if self.cap:
            self.cap.release()
            self.cap = None
        print("视频采集卡已停止")
    
    def _capture_loop(self):
        """持续采集帧的后台线程"""
        fail_count = 0
        while self.is_running:
            try:
                if self.cap and self.cap.isOpened():
                    ret, frame = self.cap.read()
                    if ret:
                        with self.frame_lock:
                            self.current_frame = frame.copy()
                        fail_count = 0
                    else:
                        fail_count += 1
                        if fail_count >= 5:
                            print("采集卡读取失败（可能未连接或被占用），已停止采集")
                            self.is_running = False
                            if self.cap:
                                self.cap.release()
                                self.cap = None
                            break
                        time.sleep(0.2)
                        continue
                else:
                    # 未连接或已被释放，结束循环
                    self.is_running = False
                    break
                time.sleep(0.1)  # ~10fps采集，减少延迟
            except Exception as e:
                print(f"采集帧错误: {e}")
                time.sleep(0.1)
    
    def get_frame(self):
        """获取当前帧"""
        with self.frame_lock:
            if self.current_frame is not None:
                return self.current_frame.copy()
        return None
    
    def get_frame_as_jpeg(self, quality=85):
        """获取当前帧的JPEG编码"""
        frame = self.get_frame()
        if frame is not None:
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
            ret, jpeg = cv2.imencode('.jpg', frame, encode_param)
            if ret:
                return jpeg.tobytes()
        return None
    
    def get_frame_as_png(self):
        """获取当前帧的PNG编码"""
        frame = self.get_frame()
        if frame is not None:
            ret, png = cv2.imencode('.png', frame)
            if ret:
                return png.tobytes()
        return None
    
    def save_frame(self, filepath):
        """保存当前帧到文件 - 使用PIL保存"""
        try:
            frame = self.get_frame()
            if frame is not None:
                # 使用PIL保存 (OpenCV使用BGR格式，需要转换为RGB)
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_image = Image.fromarray(frame_rgb)
                pil_image.save(filepath, quality=95, optimize=True)
                return True
        except Exception as e:
            print(f"保存图片失败: {e}")
        return False

# 全局视频采集卡实例
capture_card = CaptureCardManager()

from common.utils import sanitize_filename, ADB_PATH

class TVRecorder:
    """TV遥控器按键录制器"""
    
    def __init__(self, device_config=None, use_capture_card=True, base_dir=None, device_id=None):
        self.device_config = device_config or {}
        self.device_ip = device_config['tv_ip']
        self.device_id = device_id
        self.use_capture_card = use_capture_card and HAS_CV2
        self.steps = []
        self.step_count = 0
        self.step_name = ""
        self.testcase_name = ""
        self.is_recording = False
        self.recording_thread = None
        self.process = None
        self.last_img = None
        self.session_dir = None
        self.recording_start_time = None
        self.key_event_device = None
        self.base_dir = base_dir
        self.WAIT_TIME = 0.5
        
        # 打印初始化信息
        print(f"[TVRecorder] 初始化完成 - device_ip: {self.device_ip}, base_dir: {base_dir}")
        
        # 长按检测阈值
        self.LONG_PRESS_TIME = 1.5

        # 连续截图相关
        self.continuous_capture_thread = None
        self._capture_thread_running = False  # 控制线程生命周期
        self.is_continuous_capture = False    # 控制是否执行截图，可随时开关
        
        # 按键状态跟踪
        self.key_press_time = {}
        
        # TV遥控器按键码映射 (Linux input event codes)
        self.KEY_CODE_MAP = {
            # 方向键
            103: "UP", 108: "DOWN", 105: "LEFT", 106: "RIGHT",
            # setting
            561: "SETTING", 471: "SOURCE",
            # 确认/返回
            28: "ENTER", 96: "ENTER", 158: "BACK", 1: "ESC",
            # 主页/菜单
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
        
        # ADB keycode 映射
        self.ADB_KEYCODE_MAP = {
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
            "7": "KEYCODE_7", "8": "KEYCODE_8", "9": "KEYCODE_9", "0": "KEYCODE_0",
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

    def run_adb(self, cmd_list):
        """执行ADB命令"""
        prefix = [ADB_PATH]
        if self.device_id:
            prefix.extend(["-s", self.device_id])
        return subprocess.run(prefix + cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def find_key_event_device(self):
        """自动查找键盘/遥控器的event设备，优先从device_config读取，否则查询并写入配置文件"""
        print(">>> 正在查找按键输入设备...")
        
        # 优先从device_config读取
        if self.device_config.get('key_event_device'):
            self.key_event_device = self.device_config['key_event_device']
            print(f">>> 从配置读取按键设备: {self.key_event_device}")
            return self.key_event_device
        
        # 配置文件中没有，通过ADB查询
        result = self.run_adb(["shell", "getevent", "-pl"])
        output = result.stdout.decode('utf-8', errors='ignore')
        
        current_device = None
        current_name = None
        devices = []  # [(device_path, device_name), ...]
        
        for line in output.split('\n'):
            device_match = re.match(r'add device \d+: (/dev/input/event\d+)', line)
            if device_match:
                current_device = device_match.group(1)
                current_name = None
                continue
            
            name_match = re.match(r'\s*name:\s*"(.+)"', line)
            if name_match and current_device:
                current_name = name_match.group(1)
                continue
            
            if current_device and 'KEY' in line:
                devices.append((current_device, current_name or ""))
                current_device = None
                current_name = None
        
        if devices:
            print(f">>> 找到按键设备: {devices}")
            # 优先查找名称中包含 "Receiver" 的设备（IR遥控器接收器）
            for device_path, device_name in devices:
                if "Receiver" in device_name:
                    print(f">>> 选择IR接收器设备: {device_path} ({device_name})")
                    self.key_event_device = device_path
                    break
            else:
                # 如果没有找到Receiver设备，使用最后一个
                self.key_event_device = devices[-1][0]
                print(f">>> 未找到Receiver设备，使用: {self.key_event_device}")
            
            # 更新device_config并写入配置文件
            self.device_config['key_event_device'] = self.key_event_device
            config_file = os.path.join(self.base_dir, "device_config.json") if self.base_dir else None
            if config_file:
                try:
                    config = {}
                    if os.path.exists(config_file):
                        with open(config_file, 'r', encoding='utf-8') as f:
                            config = json.load(f)
                    config['key_event_device'] = self.key_event_device
                    with open(config_file, 'w', encoding='utf-8') as f:
                        json.dump(config, f, ensure_ascii=False, indent=2)
                    print(f">>> 已将按键设备写入配置文件: {self.key_event_device}")
                except Exception as e:
                    print(f">>> 写入配置文件失败: {e}")
            
            return self.key_event_device
        else:
            print(">>> 未找到按键设备，将监控所有事件")
            return None

    def parse_event_line(self, line):
        """解析getevent输出的事件行"""
        pattern = r'\[\s*(\d+\.\d+)\]\s+([0-9a-fA-F]+)\s+([0-9a-fA-F]+)\s+([0-9a-fA-F]+)'
        match = re.match(pattern, line)
        if match:
            return {
                "timestamp": float(match.group(1)),
                "type": int(match.group(2), 16),
                "code": int(match.group(3), 16),
                "value": int(match.group(4), 16)
            }
        return None

    def get_key_name(self, key_code):
        """将按键码转换为可读名称"""
        return self.KEY_CODE_MAP.get(key_code, f"UNKNOWN_{key_code}")

    def get_adb_keycode(self, key_name):
        """获取ADB回放用的keycode"""
        return self.ADB_KEYCODE_MAP.get(key_name, f"KEYCODE_{key_name}")

    def process_key_event(self, event):
        """处理按键事件"""
        # EV_KEY (type = 1)
        if event['type'] != 1:
            return None
        
        key_code = event['code']
        value = event['value']
        
        # value: 0=释放, 1=按下, 2=重复(长按)
        if value == 1:  # 按下
            self.key_press_time[key_code] = time.time()
            return None
            
        elif value == 0:  # 释放
            if key_code not in self.key_press_time:
                return None
            
            press_start = self.key_press_time.pop(key_code)
            duration = time.time() - press_start
            key_name = self.get_key_name(key_code)
            adb_keycode = self.get_adb_keycode(key_name)
            
            if duration >= self.LONG_PRESS_TIME:
                # 长按
                duration_ms = int(duration * 1000)
                return {
                    "type": "long_press",
                    "key_name": key_name,
                    "key_code": key_code,
                    "duration_ms": duration_ms,
                    "cmd": f"input keyevent --longpress {adb_keycode}",
                    "desc": f"长按 {key_name} ({duration_ms}ms)"
                }
            else:
                # 普通点按
                return {
                    "type": "key_press",
                    "key_name": key_name,
                    "key_code": key_code,
                    "duration_ms": int(duration * 1000),
                    "cmd": f"input keyevent {adb_keycode}",
                    "desc": f"按键 {key_name}"
                }
        
        return None

    def recording_loop(self):
        """录制循环 - 在独立线程中运行"""
        print(">>> TV按键录制已启动")
        print(f">>> 录制数据将保存至: {self.session_dir}")
        # 查找按键设备
        self.find_key_event_device()
        
        # 抓取初始截图
        self.last_img = self.capture_screenshot("before")
        print(">>> 初始化完成！请使用遥控器操作电视。")

        # 构建getevent命令
        cmd = [ADB_PATH]
        if self.device_id:
            cmd.extend(["-s", self.device_id])
        
        if self.key_event_device:
            cmd.extend(["shell", "getevent", "-t", self.key_event_device])
        else:
            cmd.extend(["shell", "getevent", "-t"])
        self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8', errors='ignore')
        while self.is_recording:
            line = self.process.stdout.readline()
            if not line:
                break
            
            line_str = line.strip()
            event = self.parse_event_line(line_str)
            if event:
                action = self.process_key_event(event)
                
                if action:
                    self.is_continuous_capture = False
                    print(f"检测到操作: {action['desc']}")
                    print(f">>> 等待{self.WAIT_TIME}s后截图...")
                    time.sleep(self.WAIT_TIME)  # 等待画面更新
                    current_img = self.capture_screenshot("after")
                    
                    step_data = {
                        "index": self.step_count,
                        "timestamp": datetime.now().isoformat(),
                        "action_type": action['type'],
                        "key_name": action['key_name'],
                        "key_code": action['key_code'],
                        "duration_ms": action['duration_ms'],
                        "adb_command": action['cmd'],
                        "description": action['desc'],
                        "before_img": os.path.basename(self.last_img) if self.last_img else None,
                        "after_img": os.path.basename(current_img) if current_img else None
                    }
                    self.steps.append(step_data)
                    
                    # 保存到JSON文件
                    self._save_steps()

                    self.step_count += 1
                    self.last_img = current_img
                    self.is_continuous_capture = True
                    print(f">>> 步骤 {self.step_count} 保存完毕。")
                    self.WAIT_TIME = 0.5

        if self.process:
            self.process.terminate()
        print(f"录制结束。数据已保存至 {self.session_dir}/steps.json")

    def _create_session_dir(self):
        """创建以测试用例和步骤命名的录制会话文件夹"""
        # 确保 base_dir 存在
        if not self.base_dir:
            print("[TVRecorder] 错误: base_dir 未设置，无法创建会话目录")
            return None
        test_case = self.testcase_name
        step_name = self.step_name
        print(f"[TVRecorder] 创建会话目录 - base_dir: {self.base_dir}, test_case: {test_case}, step_name: {step_name}")

        if test_case and step_name:
            base_dir = os.path.join(self.base_dir, "data", sanitize_filename(test_case))
            if not os.path.exists(base_dir):
                os.makedirs(base_dir)
                print(f"[TVRecorder] 创建测试用例目录: {base_dir}")
            
            self.session_dir = os.path.join(base_dir, sanitize_filename(step_name))
            if not os.path.exists(self.session_dir):
                os.makedirs(self.session_dir)
                print(f"[TVRecorder] 创建步骤目录: {self.session_dir}")
            else:
                print(f"[TVRecorder] 步骤目录已存在: {self.session_dir}")

    def capture_screenshot(self, suffix):
        """抓取截图 - 支持ADB和视频采集卡两种方式"""
        timestamp = int(time.time() * 1000)
        img_name = f"{self.session_dir}/step_{self.step_count}_{suffix}_{timestamp}.jpg"

        # 使用视频采集卡截图
        if not capture_card.is_running:
            capture_card.start(device_id=capture_card.device_id)
        
        if capture_card.save_frame(img_name):
            return img_name
        
        # 使用ADB截图
        with open(img_name, "wb") as f:
            cmd = [ADB_PATH]
            if self.device_id:
                cmd.extend(["-s", self.device_id])
            cmd.extend(["exec-out", "screencap", "-p"])
            subprocess.run(cmd, stdout=f)
        
        return img_name

    def send_key_command(self, key_name, duration_ms=None):
        """发送按键命令"""
        adb_keycode = self.ADB_KEYCODE_MAP.get(key_name, f"KEYCODE_{key_name}")
        
        if duration_ms and duration_ms >= self.LONG_PRESS_TIME * 1000:
            cmd = f"input keyevent --longpress {adb_keycode}"
        else:
            cmd = f"input keyevent {adb_keycode}"
        
        try:
            result = self.run_adb(["shell"] + cmd.split())
            return result.returncode == 0, cmd
        except Exception as e:
            print(f"发送按键失败: {e}")
            return False, cmd

    def record_manual_action(self, key_name, action_type="manual_key"):
        """记录手动操作"""
        if not self.session_dir:
            self._create_session_dir()
        self.is_continuous_capture = False
        # 操作前截图
        before_img = self.capture_screenshot("before")
        
        # 发送按键命令
        success, adb_cmd = self.send_key_command(key_name)
        
        # 等待界面响应后截图
        time.sleep(self.WAIT_TIME)
        after_img = self.capture_screenshot("after")
        
        # 记录步骤
        step_data = {
            "index": self.step_count,
            "timestamp": datetime.now().isoformat(),
            "action_type": action_type,
            "key_name": key_name,
            "adb_command": adb_cmd,
            "description": f"手动按键 {key_name}",
            "before_img": os.path.basename(before_img) if before_img else None,
            "after_img": os.path.basename(after_img) if after_img else None,
            "success": success
        }
        
        self.steps.append(step_data)
        self.step_count += 1
        
        # 保存到JSON文件
        self._save_steps()
        self.is_continuous_capture = True
        return success, step_data

    def record_adb_command(self, command):
        """记录ADB命令操作"""
        if not self.session_dir:
            self._create_session_dir()
        
        # 操作前截图
        before_img = self.capture_screenshot("before")
        
        # 执行ADB命令
        try:
            # 自动添加 shell 前缀
            adb_direct_commands = ['devices', 'connect', 'disconnect', 'push', 'pull', 
                                   'install', 'uninstall', 'logcat', 'bugreport', 'reboot']
            first_word = command.split()[0] if command.split() else ''
            
            if first_word == 'shell':
                cmd = command.split()
            elif first_word in adb_direct_commands:
                cmd = command.split()
            else:
                cmd = ["shell"] + command.split()
            
            result = self.run_adb(cmd)
            success = result.returncode == 0
            output = result.stdout.decode('utf-8', errors='ignore')
            error = result.stderr.decode('utf-8', errors='ignore')
            
        except Exception as e:
            success = False
            output = ""
            error = str(e)
        
        # 等待界面响应后截图
        time.sleep(2)
        after_img = self.capture_screenshot("after")
        
        # 记录步骤
        step_data = {
            "index": self.step_count,
            "timestamp": datetime.now().isoformat(),
            "action_type": "manual_adb",
            "adb_command": command,
            "description": f"ADB命令: {command}",
            "before_img": os.path.basename(before_img) if before_img else None,
            "after_img": os.path.basename(after_img) if after_img else None,
            "success": success,
            "output": output,
            "error": error
        }
        
        self.steps.append(step_data)
        self.step_count += 1
        
        # 保存到JSON文件
        self._save_steps()
        
        return success, step_data

    def _save_steps(self):
        """保存步骤到JSON文件"""
        if self.session_dir:
            steps_file = os.path.join(self.session_dir, "steps.json")
            result_json = {"UUID": self.uuid, "start_time": self.recording_start_time, "instruction": self.step_name, "steps": self.steps}
            with open(steps_file, "w", encoding='utf-8') as f:
                json.dump(result_json, f, indent=4, ensure_ascii=False)

    def delete_last_step(self):
        if self.steps:
            self.is_continuous_capture = False
            self.steps.pop()
            self._save_steps()

    def start_recording(self, testcase_name=None, step_name=None):
        """开始录制 - 完全按照 web_tv_recorder.py 的实现
        
        Args:
            testcase_name: 测试用例名称（可选）
            step_name: 步骤名称（可选）
        
        Returns:
            bool: 是否成功启动录制
        """
        if self.is_recording:
            return False
        
        self.step_name = step_name.strip()[0:50]
        self.testcase_name = testcase_name.strip()[0:120]
        self.is_recording = True
        self.steps = []
        self.step_count = 0
        self.key_press_time = {}
        self.recording_start_time = time.time()
        self.uuid = uuid.uuid4().hex
        self._create_session_dir()
        
        # 启动录制线程，自动监听按键事件
        self.recording_thread = threading.Thread(target=self.recording_loop)
        self.recording_thread.start()

        self.start_continuous_capture()
        
        return True

    def stop_recording(self):
        """停止录制 - 完全按照 web_tv_recorder.py 的实现"""
        if not self.is_recording:
            return False
        
        # 最终保存
        self._save_steps()
        
        self.is_recording = False
        self.testcase_name = ""
        self.step_name = ""
        self.step_count = 0
        
        # 终止getevent进程
        if self.process:
            self.process.terminate()
        
        # 等待录制线程结束
        if self.recording_thread:
            self.recording_thread.join(timeout=2)

        self.stop_continuous_capture()
        
        # 计算录制时长
        recording_duration = time.time() - self.recording_start_time if self.recording_start_time else 0
        
        
        result = {
            "session_dir": self.session_dir,
            "total_steps": self.step_count,
            "duration": recording_duration,
            "steps": self.steps
        }
        
        return True

    def check_device_connected(self):
        """检查设备是否连接"""
        try:
            result = subprocess.run(
                [ADB_PATH, "devices"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5
            )
            
            if result.returncode != 0:
                return False
            
            output = result.stdout.decode('utf-8', errors='ignore')
            lines = output.strip().split('\n')
            
            # 跳过第一行标题
            for line in lines[1:]:
                if line.strip():
                    # 格式: "device_id\tdevice"
                    parts = line.split('\t')
                    if len(parts) >= 2 and parts[1].strip() == 'device':
                        device_id = parts[0].strip()
                        # 检查是否匹配当前设备IP
                        if self.device_ip and device_id == self.device_ip:
                            return True
                        # 如果没有指定设备IP，只要有设备连接就返回True
                        if not self.device_ip:
                            return True
            
            return False
        except Exception as e:
            print(f"检查设备连接失败: {e}")
            return False

    def get_status(self):
        """获取录制状态"""
        connected = self.check_device_connected()
        
        return {
            "is_recording": self.is_recording,
            "step_count": self.step_count,
            "steps": self.steps,
            "step_name": self.step_name,
            "testcase_name": self.testcase_name,
            "session_dir": self.session_dir,
            "start_time": self.recording_start_time,
            "connected": connected,
            "device_ip": self.device_ip
        }

    def generate_screen_stream_adb(self):
        """通过ADB生成实时屏幕流"""
        try:
            while True:
                try:
                    cmd = [ADB_PATH]
                    if self.device_ip:
                        cmd.extend(["-s", self.device_ip])
                    cmd.extend(["exec-out", "screencap", "-p"])
                    
                    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
                    if result.returncode == 0 and result.stdout:
                        yield (b'--frame\r\n'
                               b'Content-Type: image/png\r\n\r\n' + result.stdout + b'\r\n')
                    time.sleep(0.1)  # 约10fps
                except subprocess.TimeoutExpired:
                    print("ADB screen capture timeout")
                    time.sleep(1)
                except Exception as e:
                    print(f"ADB screen capture error: {e}")
                    time.sleep(1)
        except GeneratorExit:
            print("Screen stream client disconnected")
        except Exception as e:
            print(f"Screen stream error: {e}")
    
    def generate_screen_stream_capture_card(self):
        """通过视频采集卡生成实时屏幕流"""
        # 确保采集卡已启动
        if not capture_card.is_running:
            print('[Screen Stream] Starting capture card...')
            if not HAS_CV2:
                # 容器环境或未安装 OpenCV 时，直接回退到 ADB 方案
                print('OpenCV not installed, fallback to ADB screen stream')
                for chunk in self.generate_screen_stream_adb():
                    yield chunk
                return
            if not capture_card.start(device_id=capture_card.device_id):
                print('[Screen Stream] Capture card failed to start, aborting stream, fallback to ADB')
                for chunk in self.generate_screen_stream_adb():
                    yield chunk
                return
        
        # 等待采集卡初始化完成（最多等待3秒）
        max_wait = 30  # 30 * 0.1s = 3s
        wait_count = 0
        while wait_count < max_wait and capture_card.get_frame() is None:
            time.sleep(0.1)
            wait_count += 1
        
        if capture_card.get_frame() is None:
            print('[Screen Stream] Capture card initialization timeout')
            return
        
        print('[Screen Stream] Capture card ready, starting stream...')
        
        try:
            while True:
                try:
                    jpeg_data = capture_card.get_frame_as_jpeg(quality=85)
                    if jpeg_data:
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + jpeg_data + b'\r\n')
                    else:
                        # 如果没有帧数据，短暂等待
                        time.sleep(0.05)
                    time.sleep(0.033)  # 约30fps
                except Exception as e:
                    print(f"[Screen Stream] Frame error: {e}")
                    time.sleep(0.1)
        except GeneratorExit:
            print("[Screen Stream] Client disconnected")
        except Exception as e:
            print(f"[Screen Stream] Stream error: {e}")
    
    def generate_screen_stream(self):
        """根据配置选择视频源生成屏幕流"""
        # 优先使用采集卡（前提是启用了 use_capture_card 且环境安装了 OpenCV）
        if self.use_capture_card and HAS_CV2:
            return self.generate_screen_stream_capture_card()
        # 否则统一回退到 ADB 截图流
        print("[Screen Stream] Using ADB screen stream (capture card disabled or OpenCV not available)")
        return self.generate_screen_stream_adb()

    def start_capture_thread(self):
        """启动截图线程（线程会持续运行，通过is_continuous_capture控制是否执行截图）"""
        if self._capture_thread_running:
            return False
        
        self._capture_thread_running = True
        self.continuous_capture_thread = threading.Thread(target=self._continuous_capture_loop, daemon=True)
        self.continuous_capture_thread.start()
        print("[TVRecorder] 截图线程已启动")
        return True

    def stop_capture_thread(self):
        """停止截图线程"""
        if not self._capture_thread_running:
            return False
        
        self._capture_thread_running = False
        self.is_continuous_capture = False
        if self.continuous_capture_thread:
            self.continuous_capture_thread.join(timeout=2)
            self.continuous_capture_thread = None
        print("[TVRecorder] 截图线程已停止")
        return True

    def start_continuous_capture(self):
        """开启连续截图（如果线程未启动会自动启动）"""
        if not self._capture_thread_running:
            self.start_capture_thread()
        self.is_continuous_capture = True
        print("[TVRecorder] 连续截图已开启")
        return True

    def stop_continuous_capture(self):
        """暂停连续截图（线程保持运行，可随时恢复）"""
        self.is_chacontinuous_capture = False
        print("[TVRecorder] 连续截图已暂停")
        return True

    def _continuous_capture_loop(self):
        """连续截图循环 - 每0.5秒截图并更新最后一个步骤的after_img"""
        while self._capture_thread_running:
            try:
                # 只有当 is_continuous_capture 为 True 时才执行截图
                if self.is_continuous_capture and self.steps and self.session_dir:
                    # 截取新图片
                    new_img = self.capture_screenshot("after")
                    if new_img:
                        # 获取旧图片路径用于删除
                        old_after_img = self.steps[-1].get("after_img")
                        old_img_path = os.path.join(self.session_dir, old_after_img) if old_after_img else None
                        
                        # 更新最后一个步骤的after_img
                        if self.is_continuous_capture:
                            self.steps[-1]["after_img"] = os.path.basename(new_img)
                            self._save_steps()
                            self.last_img = os.path.basename(new_img)
                            
                            # 删除旧图片（如果存在且与新图片不同）
                            if old_img_path and os.path.exists(old_img_path) and old_img_path != new_img:
                                try:
                                    os.remove(old_img_path)
                                except Exception as e:
                                    print(f"[TVRecorder] 删除旧截图失败: {e}")
                        
                time.sleep(self.WAIT_TIME)
            except Exception as e:
                print(f"[TVRecorder] 连续截图错误: {e}")
                time.sleep(self.WAIT_TIME)