"""
录制管理模块
负责手机操作录制、事件捕获、数据保存
"""

import subprocess
import threading
import time
import os
import json
import re
from datetime import datetime
import sys
import shutil
import uuid
from common.utils import sanitize_filename, ADB_PATH

# 添加父目录到路径以导入 action_analyzer
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from .action_analyzer import ActionAnalyzer
mobile_data_dir = os.path.join(os.path.expanduser("~"), "annotation", "mobile")


class RecordingManager:
    """录制管理器"""
    
    def __init__(self, base_dir=None, device_id=None):
        self.device_id = device_id
        self.touch_device = "/dev/input/event3"
        self.touch_device = self._detect_touch_device()
        width_ratio, height_ratio = self._calculate_touch_ratios()
        self.analyzer = ActionAnalyzer(width_ratio=width_ratio, height_ratio=height_ratio)
        self.steps = []
        self.step_count = 0
        self.is_recording = False
        self.recording_thread = None
        self.process = None
        self.last_img = None
        self.last_xml = None
        self.session_dir = None
        self.base_dir = base_dir
        self.recording_start_time = None
        self.uuid = None
        self.WAIT_TIME = 1

        # 用例和步骤信息
        self.testCaseName = None
        self.stepNum = None
        self.step_name = None


    def _calculate_touch_ratios(self):
        """计算触屏硬件坐标到屏幕像素的比例"""
        try:
            # 获取屏幕分辨率
            cmd = [ADB_PATH]
            if self.device_id:
                cmd.extend(["-s", self.device_id])
            cmd.extend(["shell", "wm", "size"])
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
            output = result.stdout.decode('utf-8', errors='ignore')
            
            # 解析 "Physical size: 1260x2800"
            match = re.search(r'(\d+)x(\d+)', output)
            if not match:
                print(">>> 无法获取屏幕分辨率，使用默认比例 0.1")
                return 0.1, 0.1
            
            screen_width = int(match.group(1))
            screen_height = int(match.group(2))
            
            # 获取触屏最大坐标值
            cmd = [ADB_PATH]
            if self.device_id:
                cmd.extend(["-s", self.device_id])
            cmd.extend(["shell", "getevent", "-pl"])
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
            output = result.stdout.decode('utf-8', errors='ignore')
            
            # 查找触屏设备的 ABS_MT_POSITION_X 和 ABS_MT_POSITION_Y 的 max 值
            max_x = None
            max_y = None
            in_touch_device = False
            
            for line in output.split('\n'):
                if '/dev/input/event' in line:
                    in_touch_device = False
                if 'BTN_TOUCH' in line or 'INPUT_PROP_DIRECT' in line:
                    in_touch_device = True
                
                if in_touch_device or (max_x is None):
                    # ABS_MT_POSITION_X: max XXXX
                    if 'ABS_MT_POSITION_X' in line:
                        match_x = re.search(r'max\s+(\d+)', line)
                        if match_x:
                            max_x = int(match_x.group(1))
                    if 'ABS_MT_POSITION_Y' in line:
                        match_y = re.search(r'max\s+(\d+)', line)
                        if match_y:
                            max_y = int(match_y.group(1))
            
            if max_x and max_y:
                width_ratio = screen_width / max_x
                height_ratio = screen_height / max_y
                print(f">>> 屏幕: {screen_width}x{screen_height}, 触屏范围: {max_x}x{max_y}")
                print(f">>> 计算比例: width_ratio={width_ratio:.4f}, height_ratio={height_ratio:.4f}")
                return width_ratio, height_ratio
            else:
                print(">>> 无法获取触屏范围，使用默认比例 0.1")
                return 0.1, 0.1
                
        except Exception as e:
            print(f">>> 计算触屏比例失败: {e}，使用默认 0.1")
            return 0.1, 0.1

    def _detect_touch_device(self):
        """自动检测触屏设备路径"""
        try:
            cmd = [ADB_PATH]
            if self.device_id:
                cmd.extend(["-s", self.device_id])
            cmd.extend(["shell", "getevent", "-pl"])
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
            output = result.stdout.decode('utf-8', errors='ignore')
            
            # 解析输出找到触屏设备
            current_device = None
            for line in output.split('\n'):
                print(line)
                if '/dev/input/event' in line:
                    # 提取设备路径
                    match = re.search(r'(/dev/input/event\d+)', line)
                    if match:
                        current_device = match.group(1)
                if "pen" in line.lower() and "name" in line.lower():
                    current_device = None
                # 查找触屏特征: BTN_TOUCH 或 INPUT_PROP_DIRECT 或包含 "ts" (touchscreen)
                if current_device:
                    if 'BTN_TOUCH' in line or 'INPUT_PROP_DIRECT' in line:
                        print(f">>> 检测到触屏设备: {current_device}")
                        return current_device
            
            # 默认回退
            print(">>> 未检测到触屏，使用默认 /dev/input/event6")
            return "/dev/input/event6"
        except Exception as e:
            print(f">>> 检测触屏失败: {e}，使用默认 /dev/input/event6")
            return "/dev/input/event6"

    def run_adb(self, cmd_list):
        """
        执行 ADB 命令
        - 捕获 stderr，避免在设备未授权/断开时 adb 在控制台疯狂输出
        - 调用方按需自行检查 returncode / stdout / stderr
        """
        prefix = [ADB_PATH]
        if self.device_id:
            prefix.extend(["-s", self.device_id])
        return subprocess.run(
            prefix + cmd_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    def record_adb_command(self, command):
        """记录ADB命令操作"""
        if not self.session_dir:
            self._create_session_dir()
        
        # 操作前截图
        self.before_img, self.before_xml = self.capture_context("before")
        
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
        self.after_img, self.after_xml = self.capture_context("after")
        
        # 记录步骤
        step_data = {
            "index": self.step_count,
            "timestamp": datetime.now().isoformat(),
            "action_type": "manual_adb",
            "adb_command": command,
            "description": f"ADB命令: {command}",
            "before_img": os.path.basename(self.before_img) if self.before_img else None,
            "after_img": os.path.basename(self.after_img) if self.after_img else None,
            "before_xml": os.path.basename(self.before_xml) if self.before_xml else None,
            "after_xml": os.path.basename(self.after_xml) if self.after_xml else None,
            "success": success,
            "output": output,
            "error": error
        }
        
        self.steps.append(step_data)
        self.step_count += 1
        
        # 保存到JSON文件
        self._save_steps()
        
        return success, step_data


    def _create_session_dir(self, test_case=None, step_name=None):
        """创建以测试用例和步骤命名的录制会话文件夹"""
        if test_case and step_name:
            # 使用测试用例和步骤名称创建目录
            base_dir = f"{self.base_dir}/{test_case}"
            if not os.path.exists(base_dir):
                os.makedirs(base_dir)
            
            self.session_dir = f"{base_dir}/{step_name}"
            if not os.path.exists(self.session_dir):
                os.makedirs(self.session_dir)
        
        return self.session_dir

    def capture_context(self, suffix):
        """抓取截图和ViewTree"""
        timestamp = int(time.time() * 1000)
        img_name = f"{self.session_dir}/step_{self.step_count}_{suffix}_{timestamp}.jpg"
        xml_name = f"{self.session_dir}/step_{self.step_count}_{suffix}_{timestamp}.xml"
       
        with open(img_name, "wb") as f:
            cmd = [ADB_PATH]
            if self.device_id:
                cmd.extend(["-s", self.device_id])
            cmd.extend(["exec-out", "screencap", "-p"])
            # 捕获 stderr，避免设备未授权等情况下刷屏
            subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE)
        
        self.run_adb(["shell", "uiautomator", "dump", "/sdcard/window_dump.xml"])
        self.run_adb(["pull", "/sdcard/window_dump.xml", xml_name])

        return img_name, xml_name

    def parse_event_line(self, line):
        pattern = r"\[\s*(\d+\.\d+)\]\s+([0-9a-fA-F]+)\s+([0-9a-fA-F]+)\s+([0-9a-fA-F]+)"
        match = re.match(pattern, line)
        if match:
            return {
                "type": int(match.group(2), 16),
                "code": int(match.group(3), 16),
                "value": int(match.group(4), 16)
            }
        return None

    def recording_loop(self):
        """录制循环 - 在独立线程中运行"""
        print(">>> 录制已启动，请在手机上操作。")
        print(f">>> 录制数据将保存至: {self.session_dir}")
        self.last_img, self.last_xml = self.capture_context("before")
        print(f">>> 初始化完成！请在手机上操作。")
        self.steps.append({"index": -1, "description": "初始化完成！请在手机上操作。"})

        cmd = [ADB_PATH]
        if self.device_id: cmd.extend(["-s", self.device_id])
        cmd.extend(["shell", "getevent", "-t", self.touch_device])

        self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8', errors='ignore')

        while self.is_recording:
            try:
                line = self.process.stdout.readline()
                if not line:
                    # 进程暂时无输出，稍作等待后继续
                    time.sleep(0.05)
                    continue

                # 容错解码，避免编码问题导致异常
                line_str = line.strip()
                event = self.parse_event_line(line_str)
                # print(f"事件: {event}")

                if event:
                    action = self.analyzer.process_line(event)
                    # print(f"操作: {action}")

                    if action:
                        print(f"检测到操作: {action.get('desc', '')}")
                        print(f">>> 等待{self.WAIT_TIME}s后截图...")
                        time.sleep(self.WAIT_TIME)  # 等待画面更新
                        current_img, current_xml = self.capture_context("after")
                        # 从 action 中安全获取字段，缺失时使用默认值，避免 KeyError
                        step_data = {
                            "index": self.step_count,
                            "timestamp": datetime.now().isoformat(),
                            "action_type": action.get("type", ""),
                            "key_name": action.get("key_name", ""),
                            "key_code": action.get("key_code", 0),
                            "duration_ms": action.get("duration_ms", 0),
                            "adb_command": action.get("cmd", ""),
                            "description": action.get("desc", ""),
                            "before_img": os.path.basename(self.last_img) if self.last_img else None,
                            "after_img": os.path.basename(current_img) if current_img else None,
                            "before_xml": os.path.basename(self.last_xml) if self.last_xml else None,
                            "after_xml": os.path.basename(current_xml) if current_xml else None,
                        }
                        self.steps.append(step_data)

                        # 统一保存结构，与 TV 录制器一致，便于后续处理（如上传 / 转 base64）
                        self._save_steps()

                        self.step_count += 1
                        self.last_img = current_img
                        self.last_xml = current_xml

                        print(f">>> 步骤 {self.step_count} 保存完毕。")
                        self.WAIT_TIME = 1
            except Exception as e:
                # 捕获单次循环错误，不退出录制循环
                print(f"[MobileRecorder] 录制循环错误: {e}")
                time.sleep(0.1)

        if self.process:
            self.process.terminate()
        print(f"录制结束。数据已保存至 {self.session_dir}/steps.json")

    def delete_last_step(self):
        if self.steps:
            self.steps.pop()
            self._save_steps()

    def _save_steps(self):
        """保存步骤到 steps.json，结构与 TV 录制器保持一致"""
        if self.session_dir:
            steps_file = os.path.join(self.session_dir, "steps.json")
            result_json = {
                "UUID": self.uuid,
                "start_time": self.recording_start_time,
                "step_name": self.origin_step_name or "",
                "steps": self.steps,
            }
            with open(steps_file, "w", encoding="utf-8") as f:
                json.dump(result_json, f, indent=4, ensure_ascii=False)

    def start_recording(self, testCaseId=None, testCaseName=None, stepNum=None, stepName=None):
        if self.is_recording:
            self.stop_recording()

        # 保存用例和步骤信息
        self.testCaseName = sanitize_filename(testCaseName[0:120])
        self.stepNum = stepNum
        
        self.origin_step_name = stepName
        self.step_name = sanitize_filename(stepName[0:50])
        self.is_recording = True
        self.steps = []
        self.step_count = 0
        self.recording_start_time = time.time()
        self.uuid = uuid.uuid4().hex
        # 在启动线程前创建会话文件夹
        self._create_session_dir(self.testCaseName, self.step_name)
        self.recording_thread = threading.Thread(target=self.recording_loop)
        self.recording_thread.start()
        return True, "录制已启动", self.session_dir

    def stop_recording(self):
        if not self.is_recording:
            return False, "当前没有正在进行的录制", None
        self.is_recording = False
        if self.process:
            self.process.terminate()
        if self.recording_thread:
            self.recording_thread.join(timeout=2)
        result = {
            "steps": self.steps,
            "step_count": self.step_count,
            "session_dir": self.session_dir
        }
        return True, "录制已停止", result

    def get_status(self):
        """
        获取录制状态
        Returns:
            状态字典
        """
        return {
            "is_recording": self.is_recording,
            "step_count": self.step_count,
            "steps": self.steps,
            "step_name": self.step_name,
            "testcase_name": self.testCaseName
        }
    
    def get_device_info(self):
        """
        获取设备信息
        
        Returns:
            设备信息字典
        """
        try:
            # 检查设备连接
            result = self.run_adb(["devices"])
            output = result.stdout.decode('utf-8', errors='ignore')
            devices = []
            for line in output.split('\n')[1:]:
                line = line.strip()
                if line and '\tdevice' in line:
                    device_id = line.split('\t')[0].strip()
                    if device_id:
                        devices.append(device_id)
           
            # 获取屏幕尺寸（增加超时时间，某些设备响应较慢）
            try:
                result = self.run_adb(["shell", "wm", "size"])
                size_output = result.stdout.decode('utf-8', errors='ignore')
                size_match = re.search(r'(\d+)x(\d+)', size_output)
                screen_size = [int(size_match.group(1)), int(size_match.group(2))] if size_match else [0, 0]
            except Exception as e:
                print(f"获取屏幕尺寸失败: {e}")
                screen_size = [0, 0]
            
            # 获取设备型号（增加超时时间，某些设备响应较慢）
            try:
                result = self.run_adb(["shell", "getprop", "ro.product.model"])
                model = result.stdout.decode('utf-8', errors='ignore').strip()
            except Exception as e:
                print(f"获取设备型号失败: {e}")
                model = "未知"
            
            return {
                "connected": True,
                "device_id": self.device_id or devices[0],
                "model": model,
                "is_recording": self.is_recording,
                "screen_size": screen_size,
                "available_devices": devices
            }
        except FileNotFoundError as e:
            return {
                "connected": False,
                "error": str(e)
            }
        except Exception as e:
            error_msg = str(e)
            self.stop_recording()
            # 提供更友好的错误信息
            if "ADB命令失败" in error_msg:
                return {
                    "connected": False,
                    "error": error_msg
                }
            return {
                "connected": False,
                "error": f"获取设备信息时发生错误: {error_msg}"
            }
