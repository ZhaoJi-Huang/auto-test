"""
回放视频录制器
通过采集卡持续获取帧并写入 MP4 视频文件，与回放引擎独立线程运行
"""

import logging
import threading
import time

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

logger = logging.getLogger(__name__)


class VideoRecorder:
    """回放视频录制器

    从采集卡持续获取帧，写入 MP4 视频文件。
    在独立后台线程中运行，不阻塞回放引擎。
    """

    def __init__(self, capture_card):
        """
        Args:
            capture_card: CaptureCardManager 实例
        """
        self._capture_card = capture_card
        self._is_recording = False
        self._writer = None
        self._thread = None
        self._output_path = None
        self._lock = threading.Lock()

    @property
    def is_recording(self):
        return self._is_recording

    def start(self, output_path, fps=10, resolution=(1920, 1080)):
        """开始录制视频

        Args:
            output_path: 输出视频文件路径（.mp4）
            fps: 帧率
            resolution: 分辨率 (width, height)
        """
        if not HAS_CV2:
            raise RuntimeError("OpenCV 未安装，无法录制视频")

        if self._is_recording:
            logger.warning("视频录制已在进行中")
            return

        self._output_path = output_path
        width, height = resolution

        # 使用 mp4v 编码器
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self._writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        if not self._writer.isOpened():
            self._writer = None
            raise RuntimeError(f"无法创建视频文件: {output_path}")

        self._is_recording = True
        self._thread = threading.Thread(
            target=self._recording_loop,
            args=(fps,),
            name="video-recorder",
            daemon=True,
        )
        self._thread.start()
        logger.info(f"视频录制已启动: {output_path} ({width}x{height} @ {fps}fps)")

    def stop(self):
        """停止录制，返回视频文件路径

        Returns:
            str: 视频文件路径，未录制时返回 None
        """
        if not self._is_recording:
            return None

        self._is_recording = False

        # 等待录制线程结束
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

        # 释放 VideoWriter
        with self._lock:
            if self._writer:
                self._writer.release()
                self._writer = None

        path = self._output_path
        logger.info(f"视频录制已停止: {path}")
        return path

    def _recording_loop(self, fps):
        """后台线程：持续从采集卡获取帧并写入视频

        Args:
            fps: 目标帧率
        """
        frame_interval = 1.0 / fps

        while self._is_recording:
            loop_start = time.time()

            try:
                frame = self._capture_card.get_frame()
                if frame is not None:
                    with self._lock:
                        if self._writer and self._writer.isOpened():
                            # 确保帧尺寸匹配
                            self._writer.write(frame)
            except Exception as e:
                logger.error(f"视频录制帧写入失败: {e}")

            # 控制帧率
            elapsed = time.time() - loop_start
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        logger.info("视频录制线程已退出")
