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

    def start(self, device_id=0, width=1920, height=1080):
        """启动视频采集"""
        self.device_id = device_id
        if not HAS_CV2:
            print("[CaptureCard] OpenCV 未安装，无法启动采集卡")
            return False
        if self.is_running:
            return True
        try:
            import platform
            if platform.system() == "Windows":
                self.cap = cv2.VideoCapture(device_id, cv2.CAP_DSHOW)
            else:
                self.cap = cv2.VideoCapture(device_id)
            if not self.cap.isOpened():
                print(f"[CaptureCard] 无法打开设备: {device_id}")
                return False
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self.is_running = True
            self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.capture_thread.start()
            print(f"[CaptureCard] 已启动: 设备{device_id}, {width}x{height}")
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
                            print("[CaptureCard] 连续读取失败，停止采集")
                            self.is_running = False
                            if self.cap:
                                self.cap.release()
                                self.cap = None
                            break
                        time.sleep(0.2)
                        continue
                else:
                    self.is_running = False
                    break
                time.sleep(0.033)  # ~30fps
            except Exception as e:
                print(f"[CaptureCard] 采集错误: {e}")
                time.sleep(0.1)

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


def enumerate_capture_devices(max_index=9):
    """枚举可用视频采集设备"""
    if not HAS_CV2:
        return []

    import platform
    is_windows = platform.system() == "Windows"
    device_names = _get_device_names_windows() if is_windows else {}

    devices = []
    for i in range(max_index + 1):
        cap = None
        try:
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW) if is_windows else cv2.VideoCapture(i)
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
