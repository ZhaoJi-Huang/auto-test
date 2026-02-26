"""
视频采集卡管理器 - 单例模式
从 tv_recorder.py 中提取，供录制、回放、视频录制共用
"""

import threading
import time
import subprocess

try:
    import cv2
    import numpy as np
    try:
        cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
    except Exception:
        pass
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    from PIL import Image
except ImportError:
    Image = None


class CaptureCardManager:
    """视频采集卡管理器 - 单例模式，线程安全"""
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

    def _open_device(self, device_id, width=1920, height=1080):
        """打开采集设备并配置分辨率，返回是否成功"""
        import platform
        if platform.system() == "Windows":
            cap = cv2.VideoCapture(device_id, cv2.CAP_DSHOW)
        else:
            cap = cv2.VideoCapture(device_id)
        if not cap.isOpened():
            return None

        # 设置期望分辨率
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # 读取实际分辨率（DirectShow 可能不支持设置的值）
        actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"[CaptureCard] 设备{device_id} 实际分辨率: {actual_w}x{actual_h}")

        # 如果实际分辨率过低，尝试常见的高分辨率
        if actual_w < 1280:
            for try_w, try_h in [(1920, 1080), (1280, 720)]:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, try_w)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, try_h)
                new_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                new_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                if new_w >= 1280:
                    print(f"[CaptureCard] 分辨率已调整为: {new_w}x{new_h}")
                    break

        return cap

    def start(self, device_id=0, width=1920, height=1080):
        """启动视频采集"""
        self.device_id = device_id
        self._target_width = width
        self._target_height = height
        if not HAS_CV2:
            print("[CaptureCard] OpenCV 未安装，无法启动采集卡")
            return False
        if self.is_running:
            return True
        try:
            self.cap = self._open_device(device_id, width, height)
            if self.cap is None:
                print(f"[CaptureCard] 无法打开设备: {device_id}")
                return False
            self.is_running = True
            self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.capture_thread.start()
            print(f"[CaptureCard] 已启动: 设备{device_id}")
            return True
        except Exception as e:
            print(f"[CaptureCard] 启动失败: {e}")
            return False

    def stop(self):
        """停止视频采集"""
        self.is_running = False
        if self.capture_thread:
            self.capture_thread.join(timeout=2)
        if self.cap:
            self.cap.release()
            self.cap = None
        print("[CaptureCard] 已停止")

    def _capture_loop(self):
        """后台采集线程"""
        fail_count = 0
        reopen_count = 0
        max_reopen = 3  # 最多重新打开设备 3 次
        while self.is_running:
            try:
                if self.cap and self.cap.isOpened():
                    ret, frame = self.cap.read()
                    if ret:
                        with self.frame_lock:
                            self.current_frame = frame.copy()
                        fail_count = 0
                        reopen_count = 0
                    else:
                        fail_count += 1
                        if fail_count >= 30:
                            # 连续失败较多，尝试重新打开设备
                            if reopen_count < max_reopen:
                                reopen_count += 1
                                print(f"[CaptureCard] 连续读取失败，尝试重新打开设备 ({reopen_count}/{max_reopen})")
                                try:
                                    self.cap.release()
                                except Exception:
                                    pass
                                time.sleep(2)
                                self.cap = self._open_device(
                                    self.device_id,
                                    self._target_width,
                                    self._target_height,
                                )
                                fail_count = 0
                            else:
                                print("[CaptureCard] 多次重新打开设备均失败，停止采集")
                                self.is_running = False
                                if self.cap:
                                    self.cap.release()
                                    self.cap = None
                                break
                        time.sleep(0.1)
                        continue
                else:
                    # 设备未打开，尝试重新打开
                    if reopen_count < max_reopen:
                        reopen_count += 1
                        print(f"[CaptureCard] 设备未打开，尝试重新打开 ({reopen_count}/{max_reopen})")
                        time.sleep(2)
                        self.cap = self._open_device(
                            self.device_id,
                            self._target_width,
                            self._target_height,
                        )
                        continue
                    self.is_running = False
                    break
                time.sleep(0.033)  # ~30fps
            except Exception as e:
                print(f"[CaptureCard] 采集错误: {e}")
                time.sleep(0.5)

    def get_frame(self):
        """获取当前帧（numpy array）"""
        with self.frame_lock:
            if self.current_frame is not None:
                return self.current_frame.copy()
        return None

    def get_frame_as_jpeg(self, quality=85):
        """获取当前帧的 JPEG 编码"""
        if not HAS_CV2:
            return None
        frame = self.get_frame()
        if frame is not None:
            ret, jpeg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
            if ret:
                return jpeg.tobytes()
        return None

    def get_frame_as_png(self):
        """获取当前帧的 PNG 编码"""
        if not HAS_CV2:
            return None
        frame = self.get_frame()
        if frame is not None:
            ret, png = cv2.imencode(".png", frame)
            if ret:
                return png.tobytes()
        return None

    def save_frame(self, filepath):
        """保存当前帧到文件"""
        try:
            if not HAS_CV2:
                return False
            frame = self.get_frame()
            if frame is not None:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                if Image:
                    pil_image = Image.fromarray(frame_rgb)
                    pil_image.save(filepath, quality=95, optimize=True)
                else:
                    cv2.imwrite(filepath, frame)
                return True
        except Exception as e:
            print(f"[CaptureCard] 保存图片失败: {e}")
        return False

    def take_screenshot(self, filepath, device_serial=None):
        """截图：优先采集卡，回退 ADB screencap

        Args:
            filepath: 保存路径
            device_serial: ADB 设备序列号（回退用）

        Returns:
            bool: 是否成功
        """
        # 优先采集卡
        if self.is_running and self.save_frame(filepath):
            return True
        # 回退 ADB
        if device_serial:
            try:
                from common.utils import ADB_PATH
                import platform
                flags = 0
                if platform.system() == "Windows":
                    flags = subprocess.CREATE_NO_WINDOW
                with open(filepath, "wb") as f:
                    subprocess.run(
                        [ADB_PATH, "-s", device_serial, "exec-out", "screencap", "-p"],
                        stdout=f, stderr=subprocess.PIPE, timeout=10,
                        creationflags=flags,
                    )
                return True
            except Exception as e:
                print(f"[CaptureCard] ADB 截图失败: {e}")
        return False


def enumerate_capture_devices(max_index=5):
    """枚举可用视频采集设备

    Windows 上 DirectShow 打开不存在的设备非常慢，
    因此限制最大索引并跳过单例已占用的设备。
    """
    if not HAS_CV2:
        return []

    import platform
    is_windows = platform.system() == "Windows"
    device_names = _get_device_names_windows() if is_windows else {}

    # 获取单例已占用的设备索引
    singleton_device_id = None
    if capture_card.is_running:
        singleton_device_id = capture_card.device_id

    devices = []
    for i in range(max_index + 1):
        # 如果单例正在使用该设备，直接加入列表（不重复打开）
        if singleton_device_id is not None and i == singleton_device_id:
            name = device_names.get(i, f"视频设备 {i}")
            devices.append({"index": i, "name": name + " (当前使用中)"})
            continue

        cap = None
        try:
            if is_windows:
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            else:
                cap = cv2.VideoCapture(i)
            if cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    name = device_names.get(i, f"视频设备 {i}")
                    devices.append({"index": i, "name": name})
        except Exception:
            pass
        finally:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass
    return devices


def _get_device_names_windows():
    """Windows: 通过 PowerShell 获取视频采集设备名"""
    try:
        import platform
        if platform.system() != "Windows":
            return {}
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        result = subprocess.run(
            ["powershell", "-Command",
             "Get-PnpDevice -Class Camera -Status OK | Sort-Object InstanceId | Select-Object -ExpandProperty FriendlyName"],
            capture_output=True, text=True, timeout=5, creationflags=flags,
        )
        if result.returncode == 0:
            names = [ln.strip() for ln in result.stdout.strip().splitlines() if ln.strip()]
            return {i: name for i, name in enumerate(names)}
    except Exception:
        pass
    return {}


# 全局单例
capture_card = CaptureCardManager()
