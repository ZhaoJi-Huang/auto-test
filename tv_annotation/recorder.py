"""
TV 录制引擎
通过 ADB getevent 监听遥控器按键，录制操作序列为纯 JSON
"""

import json
import logging
import os
import platform
import re
import subprocess
import threading
import time

from common.utils import ADB_PATH
from common.adb_utils import run_adb, check_adb_device, get_current_activity
from tv_annotation.key_mappings import get_key_name, get_adb_keycode

logger = logging.getLogger(__name__)

# 长按判定阈值（秒）
LONG_PRESS_THRESHOLD = 1.5
# 按键分组间隔阈值（秒）：间隔 < 此值的连续按键归为同一组
KEY_GROUP_INTERVAL = 1.0


class TVRecorder:
    """TV 遥控器按键录制引擎

    通过 adb shell getevent 监听按键事件，记录操作序列。
    录制结果为纯 JSON（不截图、不录制视频）。
    """

    def __init__(self, device_serial, scripts_repo_path, key_event_device=None):
        """
        Args:
            device_serial: ADB 设备序列号（TV IP:port）
            scripts_repo_path: 脚本仓库根目录
            key_event_device: 按键输入设备路径，如 /dev/input/event0；为 None 时自动查找
        """
        self._device_serial = device_serial
        self._scripts_repo_path = scripts_repo_path
        self._key_event_device = key_event_device

        # 录制状态
        self._is_recording = False
        self._case_key = None
        self._raw_keys = []       # 原始按键事件列表
        self._steps = []          # 已确认的步骤（ADB 命令、AI 指令等非按键步骤直接入此列表）
        self._lock = threading.Lock()

        # getevent 子进程及监听线程
        self._getevent_proc = None
        self._listen_thread = None

        # 按键状态跟踪
        self._key_press_times = {}  # key_code -> 按下时间戳

        # Activity 缓存
        self._current_activity = ""
        self._initial_activity = ""

        # getevent 重启控制
        self._activity_fetch_thread = None
        self._getevent_intentional_stop = False  # 标记是否为主动停止（获取 Activity）

    # ------------------------------------------------------------------
    # 公共属性
    # ------------------------------------------------------------------

    @property
    def is_recording(self):
        return self._is_recording

    @property
    def case_key(self):
        return self._case_key

    @property
    def step_count(self):
        """当前已记录步骤数（含未分组的原始按键）"""
        with self._lock:
            return len(self._steps) + (1 if self._raw_keys else 0)

    @property
    def steps(self):
        """返回当前已记录步骤的副本"""
        with self._lock:
            return list(self._steps)

    @property
    def raw_keys(self):
        """返回当前未分组的原始按键列表"""
        with self._lock:
            return list(self._raw_keys)

    # ------------------------------------------------------------------
    # 录制控制
    # ------------------------------------------------------------------

    def start(self, case_key):
        """开始录制

        Args:
            case_key: 用例标识，如 "PROJ-101"

        Returns:
            (bool, str): (是否成功, 消息)
        """
        if self._is_recording:
            return False, "录制已在进行中"

        # 前置检查：设备连接
        ok, msg = check_adb_device(self._device_serial)
        if not ok:
            return False, f"设备检查失败: {msg}"

        # 查找按键输入设备
        if not self._key_event_device:
            device_path = self._find_key_event_device()
            if not device_path:
                return False, "未找到按键输入设备，请在配置中手动指定 key_event_device"
            self._key_event_device = device_path

        logger.info(f"开始录制: case_key={case_key}, device={self._key_event_device}")

        # 录制开始时获取初始 Activity
        self._initial_activity = get_current_activity(self._device_serial)
        self._current_activity = self._initial_activity
        logger.info(f"初始 Activity: {self._initial_activity}")

        # 重置状态
        with self._lock:
            self._case_key = case_key
            self._raw_keys = []
            self._steps = []
            self._key_press_times = {}

        # 启动 getevent 监听
        self._is_recording = True
        self._start_getevent_listener()

        return True, "录制已启动"

    def stop(self):
        """停止录制

        Returns:
            (bool, str, list): (是否成功, 消息, steps列表)
        """
        if not self._is_recording:
            return False, "当前没有在录制", []

        logger.info("停止录制")
        self._is_recording = False

        # 等待 Activity 获取线程完成（如果正在运行）
        if self._activity_fetch_thread and self._activity_fetch_thread.is_alive():
            self._activity_fetch_thread.join(timeout=5)

        # 终止 getevent 进程
        self._stop_getevent_process()

        # 等待监听线程结束
        if self._listen_thread and self._listen_thread.is_alive():
            self._listen_thread.join(timeout=5)

        # 停止 getevent 后获取最终 Activity（此时 ADB 可用）
        time.sleep(0.1)
        final_activity = get_current_activity(self._device_serial)
        if final_activity:
            self._current_activity = final_activity

        # 将剩余原始按键进行分组并追加到 steps
        with self._lock:
            self._flush_raw_keys_with_activity()
            final_steps = list(self._steps)

        # 保存到文件
        self._save_steps(final_steps)

        return True, "录制已停止", final_steps

    # ------------------------------------------------------------------
    # 插入操作
    # ------------------------------------------------------------------

    def insert_adb_command(self, command, description=""):
        """插入 ADB 命令步骤

        执行命令并记录执行前后的 Activity。

        Args:
            command: ADB shell 命令（不含 "adb shell" 前缀）
            description: 命令描述

        Returns:
            (bool, str): (是否成功, 消息)
        """
        if not self._is_recording:
            return False, "当前没有在录制"

        # 先将已有原始按键分组
        with self._lock:
            self._flush_raw_keys_with_activity()

        # 获取执行前 Activity
        before_activity = get_current_activity(self._device_serial)

        # 执行命令
        try:
            result = run_adb(
                ["shell"] + command.split(),
                device_serial=self._device_serial,
                timeout=30,
            )
            output = result.stdout.decode("utf-8", errors="ignore").strip()
        except Exception as e:
            return False, f"ADB 命令执行失败: {e}"

        # 等待 Activity 变化
        time.sleep(0.5)

        # 获取执行后 Activity
        after_activity = get_current_activity(self._device_serial)

        step = {
            "type": "adb_command",
            "command": command,
            "description": description,
            "before_activity": before_activity,
            "after_activity": after_activity,
        }

        with self._lock:
            self._steps.append(step)

        logger.info(f"已插入 ADB 命令: {command}")
        return True, "ADB 命令已执行并记录"

    def insert_ai_instruction(self, ai_type, prompt):
        """插入 AI 指令（仅记录，不执行）

        Args:
            ai_type: "ai_navigate" 或 "ai_verify"
            prompt: AI 指令内容

        Returns:
            (bool, str): (是否成功, 消息)
        """
        if not self._is_recording:
            return False, "当前没有在录制"

        if ai_type not in ("ai_navigate", "ai_verify"):
            return False, f"不支持的 AI 指令类型: {ai_type}"

        # 先将已有原始按键分组
        with self._lock:
            self._flush_raw_keys_with_activity()

        step = {
            "type": ai_type,
            "prompt": prompt,
        }

        with self._lock:
            self._steps.append(step)

        logger.info(f"已插入 AI 指令: {ai_type} - {prompt}")
        return True, f"AI 指令已记录"

    def _flush_raw_keys(self):
        """将未分组的原始按键分组并追加到 _steps（调用前需持有 _lock）"""
        if self._raw_keys:
            grouped = self._group_raw_keys(self._raw_keys)
            self._steps.extend(grouped)
            self._raw_keys = []

    def _flush_raw_keys_with_activity(self):
        """将未分组的原始按键分组，使用缓存的 Activity 填充

        读取 _current_activity（由 _fetch_activity_between_groups 更新），
        调用前需持有 _lock。
        """
        if not self._raw_keys:
            return
        raw_keys = list(self._raw_keys)
        self._raw_keys = []

        # before: 上一步的 after，或初始 Activity
        before_activity = ""
        if self._steps:
            before_activity = self._steps[-1].get("after_activity", "")
        if not before_activity:
            before_activity = self._initial_activity

        # after: 后台采样的最新 Activity
        after_activity = self._current_activity

        # 分组并填充 Activity
        grouped = self._group_raw_keys(raw_keys)
        for step in grouped:
            step["before_activity"] = before_activity
            step["after_activity"] = after_activity
        self._steps.extend(grouped)

    def insert_step_at(self, index, step):
        """在指定位置插入步骤

        Args:
            index: 插入位置（0-based），步骤将插入到该位置之后
            step: 步骤字典

        Returns:
            (bool, str): (是否成功, 消息)
        """
        if not self._is_recording:
            return False, "当前没有在录制"

        with self._lock:
            self._flush_raw_keys()

            # index 范围：0 ~ len(self._steps)
            if index < 0 or index > len(self._steps):
                return False, f"索引超出范围（0-{len(self._steps)}）"

            self._steps.insert(index, step)

        logger.info(f"已在位置 {index} 插入步骤: {step.get('type')}")
        return True, f"已在位置 {index} 插入步骤"

    def insert_key_at(self, index, key_name):
        """在指定位置插入按键步骤

        Args:
            index: 插入位置（0-based）
            key_name: 按键名称，如 "ENTER"、"UP"

        Returns:
            (bool, str): (是否成功, 消息)
        """
        adb_keycode = get_adb_keycode(key_name)
        step = {
            "type": "key_group",
            "commands": [{"key": key_name, "adb_command": f"input keyevent {adb_keycode}"}],
            "interval_ms": 0,
            "before_activity": "",
            "after_activity": "",
        }
        return self.insert_step_at(index, step)

    def delete_step(self, index):
        """删除指定位置的步骤

        Args:
            index: 步骤索引（0-based）

        Returns:
            (bool, str): (是否成功, 消息)
        """
        if not self._is_recording:
            return False, "当前没有在录制"

        with self._lock:
            self._flush_raw_keys()

            if index < 0 or index >= len(self._steps):
                return False, f"索引超出范围（0-{len(self._steps) - 1}）"

            removed = self._steps.pop(index)

        logger.info(f"已删除位置 {index} 的步骤: {removed.get('type')}")
        return True, f"已删除位置 {index} 的步骤（{removed.get('type')}）"

    def delete_last_step(self):
        """删除最后一步操作

        Returns:
            (bool, str): (是否成功, 消息)
        """
        if not self._is_recording:
            return False, "当前没有在录制"

        with self._lock:
            # 优先删除已分组的步骤
            if self._steps:
                removed = self._steps.pop()
                logger.info(f"已删除最后一步: {removed.get('type')}")
                return True, f"已删除最后一步（{removed.get('type')}）"
            # 如果没有已分组步骤，清空原始按键
            elif self._raw_keys:
                self._raw_keys.clear()
                return True, "已清空当前未分组的按键"
            else:
                return False, "没有可删除的步骤"

    # ------------------------------------------------------------------
    # getevent 监听
    # ------------------------------------------------------------------

    def _find_key_event_device(self):
        """自动查找按键输入设备

        优先查找名称含 "ir" 或 "remote" 的设备（红外遥控器）。

        Returns:
            str: 设备路径如 "/dev/input/event0"，找不到返回 None
        """
        try:
            result = run_adb(
                ["shell", "getevent", "-pl"],
                device_serial=self._device_serial,
                timeout=10,
            )
            output = result.stdout.decode("utf-8", errors="ignore")
        except Exception as e:
            logger.warning(f"获取输入设备列表失败: {e}")
            return None

        # 解析设备列表：
        # add device N: /dev/input/eventX
        #   name: "xxx"
        #   events:
        #     KEY ...
        current_device = None
        current_name = ""
        candidates = []

        for line in output.splitlines():
            device_match = re.match(r"add device \d+:\s*(/dev/input/event\d+)", line)
            if device_match:
                current_device = device_match.group(1)
                current_name = ""
                continue

            name_match = re.match(r'\s+name:\s+"(.+)"', line)
            if name_match:
                current_name = name_match.group(1)
                continue

            # 如果该设备支持 KEY 事件
            if current_device and re.match(r"\s+KEY", line):
                candidates.append((current_device, current_name))
                current_device = None  # 避免重复添加

        if not candidates:
            return None

        # 排除触屏/鼠标设备
        exclude_keywords = ["touch", "mouse", "touchscreen", "touchpad", "trackpad"]

        # 第一优先级：名称明确包含 "ir receiver" / "ir remote" / "remote control"
        for device_path, name in candidates:
            name_lower = name.lower()
            if any(ex in name_lower for ex in exclude_keywords):
                continue
            if any(kw in name_lower for kw in ["ir receiver", "ir remote", "remote control"]):
                logger.info(f"自动选择遥控器设备: {device_path} ({name})")
                return device_path

        # 第二优先级：名称包含 ir / remote / rc / cec（但排除 touch/mouse）
        for device_path, name in candidates:
            name_lower = name.lower()
            if any(ex in name_lower for ex in exclude_keywords):
                continue
            if any(kw in name_lower for kw in ["ir", "remote", "rc", "cec"]):
                logger.info(f"自动选择输入设备: {device_path} ({name})")
                return device_path

        # 第三优先级：名称包含 keypad（物理按键，兜底）
        for device_path, name in candidates:
            name_lower = name.lower()
            if any(ex in name_lower for ex in exclude_keywords):
                continue
            if "keypad" in name_lower:
                logger.info(f"使用 keypad 输入设备: {device_path} ({name})")
                return device_path

        # 最后兜底：返回第一个非 touch/mouse 设备
        for device_path, name in candidates:
            name_lower = name.lower()
            if not any(ex in name_lower for ex in exclude_keywords):
                logger.info(f"使用默认输入设备: {device_path} ({name})")
                return device_path

        # 全是 touch/mouse，返回第一个
        device_path, name = candidates[0]
        logger.info(f"使用兜底输入设备: {device_path} ({name})")
        return device_path

    def _start_getevent_listener(self):
        """启动 getevent 子进程和监听线程"""
        cmd = [ADB_PATH, "-s", self._device_serial,
               "shell", "getevent", "-t", self._key_event_device]

        flags = 0
        if platform.system() == "Windows":
            flags = subprocess.CREATE_NO_WINDOW

        try:
            self._getevent_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=flags,
            )
        except Exception as e:
            logger.error(f"启动 getevent 失败: {e}")
            self._is_recording = False
            return

        self._listen_thread = threading.Thread(
            target=self._listen_loop,
            name="getevent-listener",
            daemon=True,
        )
        self._listen_thread.start()
        logger.info("getevent 监听线程已启动")

    def _fetch_activity_between_groups(self):
        """在按键组间隔时获取 Activity

        流程：停止 getevent → 获取 Activity → 刷新按键组 → 重启 getevent
        在独立线程中运行，避免阻塞主流程。
        """
        logger.info("开始获取 Activity（暂停 getevent）")

        try:
            # 1. 停止 getevent 进程，释放 ADB shell
            self._getevent_intentional_stop = True
            self._stop_getevent_process()

            # 等待 getevent 进程完全释放
            time.sleep(0.1)

            # 2. 获取当前 Activity
            activity = get_current_activity(self._device_serial)
            if activity:
                if activity != self._current_activity:
                    logger.info(f"Activity 变化: {self._current_activity} → {activity}")
                self._current_activity = activity
            else:
                logger.warning("获取 Activity 返回空")

            # 3. 将已有按键分组并填充 Activity
            with self._lock:
                self._flush_raw_keys_with_activity()

        except Exception as e:
            logger.error(f"获取 Activity 异常: {e}")
        finally:
            # 4. 重启 getevent 监听（无论是否成功）
            self._getevent_intentional_stop = False
            if self._is_recording:
                self._start_getevent_listener()
                logger.info("getevent 已重启")

    def _trigger_activity_fetch(self):
        """触发 Activity 获取（在独立线程中执行，避免阻塞 getevent 读取）"""
        # 避免重复触发
        if self._activity_fetch_thread and self._activity_fetch_thread.is_alive():
            logger.debug("Activity 获取线程正在运行，跳过本次触发")
            return

        self._activity_fetch_thread = threading.Thread(
            target=self._fetch_activity_between_groups,
            name="activity-fetch",
            daemon=True,
        )
        self._activity_fetch_thread.start()

    def _stop_getevent_process(self):
        """终止 getevent 子进程"""
        if self._getevent_proc:
            try:
                self._getevent_proc.terminate()
                self._getevent_proc.wait(timeout=3)
            except Exception:
                try:
                    self._getevent_proc.kill()
                except Exception:
                    pass
            self._getevent_proc = None

    def _listen_loop(self):
        """getevent 输出读取循环（运行在后台线程）"""
        proc = self._getevent_proc
        if not proc:
            return

        try:
            for raw_line in proc.stdout:
                if not self._is_recording:
                    break

                line = raw_line.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue

                self._parse_event_line(line)
        except Exception as e:
            logger.error(f"getevent 监听异常: {e}")

        # 检查进程退出码
        if proc.poll() is not None:
            exit_code = proc.returncode
            stderr_out = ""
            try:
                stderr_out = proc.stderr.read().decode("utf-8", errors="ignore").strip()
            except Exception:
                pass
            if self._is_recording and not self._getevent_intentional_stop:
                logger.warning(
                    f"getevent 进程意外退出 (exit_code={exit_code})"
                    + (f", stderr: {stderr_out}" if stderr_out else "")
                )
                print(f"[录制] getevent 进程意外退出 (exit_code={exit_code})"
                      + (f": {stderr_out}" if stderr_out else ""))

        logger.info("getevent 监听线程已退出")

    def _parse_event_line(self, line):
        """解析 getevent 输出行

        格式: [  timestamp] type code value
        例: [    1234.567890] 0001 0067 00000001

        EV_KEY type=0001, value: 00000001=按下, 00000000=释放, 00000002=重复
        """
        # 匹配格式: [  timestamp] type code value
        match = re.match(
            r"\[\s*([\d.]+)\]\s+([0-9a-fA-F]{4})\s+([0-9a-fA-F]{4})\s+([0-9a-fA-F]{8})",
            line,
        )
        if not match:
            return

        timestamp = float(match.group(1))
        event_type = int(match.group(2), 16)
        code = int(match.group(3), 16)
        value = int(match.group(4), 16)

        # 只关注 EV_KEY (type=1)
        if event_type != 1:
            return

        if value == 1:
            # 按下
            self._key_press_times[code] = timestamp
        elif value == 0:
            # 释放
            press_time = self._key_press_times.pop(code, None)
            if press_time is None:
                return

            duration = timestamp - press_time
            key_name = get_key_name(code)
            adb_keycode = get_adb_keycode(key_name)
            is_long_press = duration >= LONG_PRESS_THRESHOLD

            key_event = {
                "key": key_name,
                "adb_command": f"input keyevent {adb_keycode}",
                "timestamp": timestamp,
                "is_long_press": is_long_press,
            }
            if is_long_press:
                key_event["duration_ms"] = int(duration * 1000)

            need_fetch = False
            with self._lock:
                # 如果与上一个按键间隔超过阈值，标记需要获取 Activity
                if self._raw_keys:
                    last_ts = self._raw_keys[-1]["timestamp"]
                    if timestamp - last_ts >= KEY_GROUP_INTERVAL:
                        need_fetch = True
                self._raw_keys.append(key_event)

            # 在锁外触发 Activity 获取（停止 getevent → 获取 → 重启）
            if need_fetch:
                self._trigger_activity_fetch()

            logger.debug(f"按键: {key_name} ({'长按' if is_long_press else '短按'})")
        # value == 2 (重复) 忽略

    # ------------------------------------------------------------------
    # 按键分组
    # ------------------------------------------------------------------

    def _group_raw_keys(self, raw_keys):
        """将原始按键按时间间隔分组

        间隔 < KEY_GROUP_INTERVAL 的连续按键归为同一组。
        组内保留按键间的 interval_ms。

        Args:
            raw_keys: 原始按键列表，每项含 timestamp

        Returns:
            list: 分组后的步骤列表
        """
        if not raw_keys:
            return []

        groups = []
        current_group = [raw_keys[0]]

        for i in range(1, len(raw_keys)):
            interval = raw_keys[i]["timestamp"] - raw_keys[i - 1]["timestamp"]
            if interval < KEY_GROUP_INTERVAL:
                current_group.append(raw_keys[i])
            else:
                groups.append(current_group)
                current_group = [raw_keys[i]]
        groups.append(current_group)

        # 转换为步骤（纯数据转换，不获取 Activity）
        steps = []
        for group in groups:
            commands = []
            for i, key_event in enumerate(group):
                cmd = {
                    "key": key_event["key"],
                    "adb_command": key_event["adb_command"],
                }
                if key_event.get("is_long_press"):
                    cmd["is_long_press"] = True
                    cmd["duration_ms"] = key_event.get("duration_ms", 0)
                commands.append(cmd)

            # 组内按键间隔取平均值（用于回放节奏还原）
            if len(group) > 1:
                intervals = []
                for i in range(1, len(group)):
                    intervals.append(group[i]["timestamp"] - group[i - 1]["timestamp"])
                avg_interval_ms = int(sum(intervals) / len(intervals) * 1000)
            else:
                avg_interval_ms = 0

            step = {
                "type": "key_group",
                "commands": commands,
                "interval_ms": avg_interval_ms,
                "before_activity": "",
                "after_activity": "",
            }
            steps.append(step)

        return steps

    # ------------------------------------------------------------------
    # 文件保存
    # ------------------------------------------------------------------

    def _save_steps(self, steps):
        """保存录制步骤到 steps.json

        保存位置: {scripts_repo_path}/{case_key}/steps.json
        """
        if not self._case_key:
            logger.warning("case_key 为空，跳过保存")
            return

        case_dir = os.path.join(self._scripts_repo_path, self._case_key)
        os.makedirs(case_dir, exist_ok=True)

        file_path = os.path.join(case_dir, "steps.json")

        # 清理临时字段（timestamp 等）
        clean_steps = self._clean_steps_for_save(steps)

        # 原子写入：先写临时文件再重命名
        tmp_path = file_path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(clean_steps, f, ensure_ascii=False, indent=2)
            # Windows 上 rename 前需要先删除目标
            if os.path.exists(file_path):
                os.remove(file_path)
            os.rename(tmp_path, file_path)
            logger.info(f"录制步骤已保存: {file_path}（共 {len(clean_steps)} 步）")
        except Exception as e:
            logger.error(f"保存 steps.json 失败: {e}")
            # 清理临时文件
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    def _clean_steps_for_save(self, steps):
        """清理步骤数据中的临时字段，生成用于保存的干净副本"""
        clean = []
        for step in steps:
            s = dict(step)
            if s["type"] == "key_group":
                # 清理 commands 中的临时字段
                clean_cmds = []
                for cmd in s.get("commands", []):
                    c = {k: v for k, v in cmd.items() if k != "timestamp"}
                    clean_cmds.append(c)
                s["commands"] = clean_cmds
            clean.append(s)
        return clean
