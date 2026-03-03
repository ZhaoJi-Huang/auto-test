"""
TV 回放引擎
读取录制的操作序列（steps.json），逐步回放并校验 Activity
"""

import json
import logging
import os
import platform
import subprocess
import threading
import time
from datetime import datetime

from common.adb_utils import (
    check_adb_device,
    get_current_activity,
    run_adb,
    send_keyevent,
)
from common.utils import ADB_PATH
from tv_annotation.key_mappings import ADB_KEYCODE_MAP, get_linux_keycode

logger = logging.getLogger(__name__)

# Activity 稳定等待参数
_ACTIVITY_POLL_INTERVAL = 0.05  # 轮询间隔（秒），ADB 本身耗时 200-600ms，无需额外长等待
_ACTIVITY_POLL_TIMEOUT = 5.0    # 最大等待时间（秒）


class ReplayEngine:
    """TV 回放引擎

    从 steps.json 读取录制的操作序列，逐步回放并进行 Activity 校验。
    支持 AI 导航、AI 校验、ADB 命令、按键组等操作类型。
    """

    def __init__(self, device_serial, data_dir, scripts_repo_path, capture_card):
        """
        Args:
            device_serial: ADB 设备序列号（TV IP:port）
            data_dir: 数据根目录（回放结果保存位置）
            scripts_repo_path: 脚本仓库路径（读取 steps.json）
            capture_card: 采集卡实例（用于截图）
        """
        self._device_serial = device_serial
        self._data_dir = data_dir
        self._scripts_repo_path = scripts_repo_path
        self._capture_card = capture_card

        # sendevent 长按：输入设备路径（延迟检测）+ adb root 状态
        self._input_device = None
        self._adb_rooted = False

        # 回放状态
        self._is_replaying = False
        self._stop_requested = False
        self._quick_mode = False
        self._case_key = None
        self._current_step = 0
        self._total_steps = 0
        self._current_run = 0
        self._total_runs = 0
        self._replay_thread = None
        self._lock = threading.Lock()
        # 实时步骤状态列表，供前端轮询
        self._steps_overview = []  # [{type, summary, status}, ...]
        self._step_results = []    # 已完成步骤的结果快照

    # ------------------------------------------------------------------
    # 公共属性
    # ------------------------------------------------------------------

    @property
    def is_replaying(self):
        return self._is_replaying

    @property
    def status(self):
        """返回当前回放状态"""
        with self._lock:
            return {
                "is_replaying": self._is_replaying,
                "quick_mode": self._quick_mode,
                "case_key": self._case_key,
                "current_step": self._current_step,
                "total_steps": self._total_steps,
                "current_run": self._current_run,
                "total_runs": self._total_runs,
                "steps_overview": list(self._steps_overview),
                "step_results": list(self._step_results),
            }

    # ------------------------------------------------------------------
    # 回放控制
    # ------------------------------------------------------------------

    def replay(self, case_key, repeat=1, stop_on_failure=False):
        """启动回放（在后台线程中运行）

        Args:
            case_key: 用例标识，如 "PROJ-101"
            repeat: 重复次数
            stop_on_failure: 失败时是否停止后续重复

        Returns:
            (bool, str): (是否成功启动, 消息)
        """
        if self._is_replaying:
            return False, "回放已在进行中"

        # 加载步骤文件
        steps_file = os.path.join(self._scripts_repo_path, case_key, "steps.json")
        if not os.path.isfile(steps_file):
            return False, f"未找到步骤文件: {steps_file}"

        try:
            with open(steps_file, "r", encoding="utf-8") as f:
                steps = json.load(f)
        except Exception as e:
            return False, f"读取步骤文件失败: {e}"

        if not steps:
            return False, "步骤文件为空"

        # 检查设备
        ok, msg = check_adb_device(self._device_serial)
        if not ok:
            return False, f"设备检查失败: {msg}"

        # 确保 adb root（sendevent 长按需要）
        self._ensure_adb_root()

        # 初始化状态
        with self._lock:
            self._is_replaying = True
            self._stop_requested = False
            self._case_key = case_key
            self._total_steps = len(steps)
            self._current_step = 0
            self._total_runs = repeat
            self._current_run = 0
            self._step_results = []
            # 构建步骤概览（供前端展示）
            self._steps_overview = self._build_steps_overview(steps)

        # 创建结果目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_dir = os.path.join(self._data_dir, "replay", case_key, timestamp)
        os.makedirs(result_dir, exist_ok=True)

        # 后台线程执行
        self._replay_thread = threading.Thread(
            target=self._replay_worker,
            args=(case_key, steps, repeat, stop_on_failure, result_dir, timestamp),
            name="replay-worker",
            daemon=True,
        )
        self._replay_thread.start()

        return True, "回放已启动"

    def quick_replay(self, case_key):
        """启动快速回放（无 Activity 校验、无截图、无 AI 验证、固定 1s 间隔）

        Args:
            case_key: 用例标识

        Returns:
            (bool, str): (是否成功启动, 消息)
        """
        if self._is_replaying:
            return False, "回放已在进行中"

        # 加载步骤文件
        steps_file = os.path.join(self._scripts_repo_path, case_key, "steps.json")
        if not os.path.isfile(steps_file):
            return False, f"未找到步骤文件: {steps_file}"

        try:
            with open(steps_file, "r", encoding="utf-8") as f:
                steps = json.load(f)
        except Exception as e:
            return False, f"读取步骤文件失败: {e}"

        if not steps:
            return False, "步骤文件为空"

        # 检查设备
        ok, msg = check_adb_device(self._device_serial)
        if not ok:
            return False, f"设备检查失败: {msg}"

        # 确保 adb root（sendevent 长按需要）
        self._ensure_adb_root()

        # 初始化状态
        with self._lock:
            self._is_replaying = True
            self._stop_requested = False
            self._quick_mode = True
            self._case_key = case_key
            self._total_steps = len(steps)
            self._current_step = 0
            self._total_runs = 1
            self._current_run = 0
            self._step_results = []
            self._steps_overview = self._build_steps_overview(steps)

        # 后台线程执行（无结果目录）
        self._replay_thread = threading.Thread(
            target=self._replay_worker,
            args=(case_key, steps, 1, False, None, None),
            name="quick-replay-worker",
            daemon=True,
        )
        self._replay_thread.start()

        return True, "快速回放已启动"

    def stop(self):
        """停止回放"""
        if not self._is_replaying:
            return False, "当前没有在回放"
        self._stop_requested = True
        return True, "正在停止回放..."

    # ------------------------------------------------------------------
    # 回放工作线程
    # ------------------------------------------------------------------

    def _replay_worker(self, case_key, steps, repeat, stop_on_failure, result_dir, timestamp):
        """回放工作线程主函数"""
        runs = []
        started_at = datetime.now().isoformat()
        video_recorder = None
        quick = self._quick_mode

        try:
            # 快速回放不录视频
            if not quick:
                try:
                    from tv_annotation.video_recorder import VideoRecorder
                    video_recorder = VideoRecorder(self._capture_card)
                except ImportError:
                    logger.warning("视频录制模块不可用，跳过视频录制")

            for run_idx in range(1, repeat + 1):
                if self._stop_requested:
                    break

                with self._lock:
                    self._current_run = run_idx
                    self._current_step = 0

                logger.info(f"{'快速' if quick else ''}回放: {case_key} 第 {run_idx}/{repeat} 次")

                run_dir = None
                if not quick:
                    # 创建本次运行目录
                    if repeat > 1:
                        run_dir = os.path.join(result_dir, f"run_{run_idx}")
                    else:
                        run_dir = result_dir
                    os.makedirs(run_dir, exist_ok=True)

                    # 开始视频录制
                    video_path = os.path.join(run_dir, "replay.mp4")
                    if video_recorder:
                        try:
                            video_recorder.start(video_path)
                        except Exception as e:
                            logger.warning(f"视频录制启动失败: {e}")

                # 执行回放
                run_result = self._execute_single_run(steps, run_dir)

                if not quick:
                    # 停止视频录制
                    if video_recorder and video_recorder.is_recording:
                        try:
                            video_recorder.stop()
                        except Exception as e:
                            logger.warning(f"视频录制停止失败: {e}")

                    # 保存本次结果
                    result_data = {
                        "jira_key": case_key,
                        "replay_at": datetime.now().isoformat(),
                        "duration_s": run_result["duration_s"],
                        "result": run_result["result"],
                        "total_steps": len(steps),
                        "failed_step": run_result.get("failed_step"),
                        "failed_reason": run_result.get("failed_reason"),
                        "operator": platform.node(),
                        "steps": run_result["steps"],
                    }
                    self._save_json(os.path.join(run_dir, "result.json"), result_data)

                runs.append({
                    "run": run_idx,
                    "result": run_result["result"],
                    "duration_s": run_result["duration_s"],
                })

                # 失败时是否停止
                if stop_on_failure and run_result["result"] != "passed":
                    logger.info(f"第 {run_idx} 次回放失败，stop_on_failure=True，停止后续回放")
                    break

            # 保存汇总（多次重复时，快速回放不保存）
            if not quick and repeat > 1:
                finished_at = datetime.now().isoformat()
                passed = sum(1 for r in runs if r["result"] == "passed")
                failed = sum(1 for r in runs if r["result"] == "failed")
                aborted = sum(1 for r in runs if r["result"] == "aborted")
                total_duration = sum(r["duration_s"] for r in runs)

                summary = {
                    "jira_key": case_key,
                    "repeat": repeat,
                    "stop_on_failure": stop_on_failure,
                    "started_at": started_at,
                    "finished_at": finished_at,
                    "total_duration_s": total_duration,
                    "passed": passed,
                    "failed": failed,
                    "aborted": aborted,
                    "pass_rate": round(passed / len(runs), 2) if runs else 0,
                    "runs": runs,
                }
                self._save_json(os.path.join(result_dir, "summary.json"), summary)

        except Exception as e:
            logger.error(f"回放工作线程异常: {e}", exc_info=True)
        finally:
            # 确保视频录制停止
            if video_recorder and video_recorder.is_recording:
                try:
                    video_recorder.stop()
                except Exception:
                    pass
            with self._lock:
                self._is_replaying = False
                self._stop_requested = False
                self._quick_mode = False
            logger.info(f"回放结束: {case_key}")

    def _execute_single_run(self, steps, run_dir):
        """执行单次回放

        Args:
            steps: 步骤列表
            run_dir: 本次运行结果目录

        Returns:
            dict: {
                "result": "passed" | "failed" | "aborted",
                "duration_s": float,
                "steps": [...],
                "failed_step": int | None,
                "failed_reason": str | None
            }
        """
        step_results = []
        run_start = time.time()

        # 前置：按 HOME 键回到首页
        send_keyevent(self._device_serial, "KEYCODE_HOME")
        time.sleep(2.0)

        for idx, step in enumerate(steps):
            if self._stop_requested:
                return {
                    "result": "aborted",
                    "duration_s": round(time.time() - run_start, 1),
                    "steps": step_results,
                    "failed_step": None,
                    "failed_reason": "用户手动停止",
                }

            with self._lock:
                self._current_step = idx + 1

            step_type = step.get("type", "")
            step_start = time.time()

            logger.info(f"回放步骤 {idx + 1}/{len(steps)}: {step_type}")

            try:
                if step_type == "key_group":
                    result = self._execute_key_group(step, idx, run_dir)
                elif step_type == "adb_command":
                    result = self._execute_adb_command(step, idx, run_dir)
                elif step_type == "ai_navigate":
                    result = self._execute_ai_navigate(step, idx, run_dir)
                elif step_type == "ai_verify":
                    result = self._execute_ai_verify(step, idx, run_dir)
                else:
                    result = {"status": "skipped", "reason": f"未知步骤类型: {step_type}"}
            except Exception as e:
                result = {"status": "error", "reason": str(e)}
                logger.error(f"步骤 {idx + 1} 执行异常: {e}")

            result["step_index"] = idx
            result["step_type"] = step_type
            result["duration_s"] = round(time.time() - step_start, 1)

            # 附加原始步骤描述信息，供前端展示
            if step_type == "key_group":
                result["commands"] = step.get("commands", [])
                result["interval_ms"] = step.get("interval_ms", 0)
            elif step_type == "adb_command":
                result["command"] = step.get("command", "")
                result["description"] = step.get("description", "")
            elif step_type in ("ai_navigate", "ai_verify"):
                result["prompt"] = step.get("prompt", "")

            step_results.append(result)

            # 实时更新步骤结果（供前端轮询）
            with self._lock:
                self._step_results = list(step_results)

            # 如果步骤失败且需要中断
            if result.get("status") == "failed":
                return {
                    "result": "failed",
                    "duration_s": round(time.time() - run_start, 1),
                    "steps": step_results,
                    "failed_step": idx + 1,
                    "failed_reason": result.get("reason", ""),
                }

        return {
            "result": "passed",
            "duration_s": round(time.time() - run_start, 1),
            "steps": step_results,
            "failed_step": None,
            "failed_reason": None,
        }

    # ------------------------------------------------------------------
    # 步骤执行器
    # ------------------------------------------------------------------

    def _execute_key_group(self, step, step_idx, run_dir):
        """执行按键组步骤

        流程：
        1. 获取当前 Activity，与录制时 before_activity 对比
        2. 执行按键组（按 interval_ms 间隔）
        3. 等待画面稳定
        4. 获取 Activity，与录制时 after_activity 对比

        快速回放模式：跳过 Activity 校验和截图，仅发送按键 + 1s 等待
        """
        commands = step.get("commands", [])
        interval_ms = step.get("interval_ms", 200)
        interval_s = max(interval_ms / 1000.0, 0.1)

        if self._quick_mode:
            # 快速回放：仅执行按键 + 固定 1s 等待
            for cmd_idx, cmd in enumerate(commands):
                if self._stop_requested:
                    return {"status": "aborted", "reason": "用户手动停止"}
                is_long_press = cmd.get("is_long_press", False)
                duration_ms = cmd.get("duration_ms", 0)
                key_name = cmd.get("key", "")
                adb_keycode = ADB_KEYCODE_MAP.get(key_name, cmd.get("adb_command", "").split()[-1] if cmd.get("adb_command") else "")
                if is_long_press and duration_ms > 0:
                    self._send_long_press(adb_keycode, duration_ms)
                else:
                    send_keyevent(self._device_serial, adb_keycode)
                if cmd_idx < len(commands) - 1:
                    time.sleep(interval_s)
            time.sleep(1.0)
            return {"status": "passed"}

        expected_before = step.get("before_activity", "")
        expected_after = step.get("after_activity", "")

        # 1. 校验 before_activity
        if expected_before:
            current = get_current_activity(self._device_serial)
            if current and expected_before and current != expected_before:
                # 状态偏离：截图并中断
                screenshot_path = os.path.join(run_dir, f"step_{step_idx + 1}_deviation.png")
                self._take_screenshot(screenshot_path)
                return {
                    "status": "failed",
                    "reason": f"状态偏离: 期望 {expected_before}，实际 {current}",
                    "screenshot": screenshot_path,
                }

        # 2. 执行按键
        for cmd_idx, cmd in enumerate(commands):
            if self._stop_requested:
                return {"status": "aborted", "reason": "用户手动停止"}

            is_long_press = cmd.get("is_long_press", False)
            duration_ms = cmd.get("duration_ms", 0)
            key_name = cmd.get("key", "")
            adb_keycode = ADB_KEYCODE_MAP.get(key_name, cmd.get("adb_command", "").split()[-1] if cmd.get("adb_command") else "")

            if is_long_press and duration_ms > 0:
                self._send_long_press(adb_keycode, duration_ms)
            else:
                send_keyevent(self._device_serial, adb_keycode)

            # 只在非最后一个按键后等待间隔
            if cmd_idx < len(commands) - 1:
                time.sleep(interval_s)

        # 3. 等待 TV 动画完成
        time.sleep(1.0)

        # 4. 校验 after_activity（智能等待：匹配则跳过多轮轮询）
        if expected_after:
            current = get_current_activity(self._device_serial)
            if current == expected_after:
                # 已匹配，无需等待
                logger.info(f"after_activity 直接匹配: {current}")
            elif current:
                # 不匹配，等待画面稳定后再检查
                self._wait_activity_stable()
                current = get_current_activity(self._device_serial)
                if current and current != expected_after:
                    # 尝试 BACK 键恢复
                    logger.warning(f"after_activity 不一致，尝试 BACK 键恢复: 期望 {expected_after}，实际 {current}")
                    send_keyevent(self._device_serial, "KEYCODE_BACK")
                    time.sleep(1.0)

                    current = get_current_activity(self._device_serial)
                    if current == expected_after:
                        return {
                            "status": "warning",
                            "reason": f"BACK 键恢复成功（原始 Activity 不一致）",
                        }
                    else:
                        screenshot_path = os.path.join(run_dir, f"step_{step_idx + 1}_mismatch.png")
                        self._take_screenshot(screenshot_path)
                        return {
                            "status": "failed",
                            "reason": f"after_activity 不一致且恢复失败: 期望 {expected_after}，实际 {current}",
                            "screenshot": screenshot_path,
                        }
        else:
            # 无 after_activity 期望值，短暂等待画面稳定
            self._wait_activity_stable()

        # 截图记录
        screenshot_path = os.path.join(run_dir, f"step_{step_idx + 1}.png")
        self._take_screenshot(screenshot_path)

        return {"status": "passed", "screenshot": screenshot_path}

    def _execute_adb_command(self, step, step_idx, run_dir):
        """执行 ADB 命令步骤

        流程与 key_group 类似：校验 before_activity → 执行 → 等待稳定 → 校验 after_activity
        快速回放模式：跳过 Activity 校验和截图，仅执行命令 + 1s 等待
        """
        command = step.get("command", "")

        if not command:
            return {"status": "skipped", "reason": "命令为空"}

        if self._quick_mode:
            # 快速回放：仅执行命令 + 等待
            try:
                result = run_adb(
                    ["shell"] + command.split(),
                    device_serial=self._device_serial,
                    timeout=30,
                )
                output = result.stdout.decode("utf-8", errors="ignore").strip()
            except Exception as e:
                return {"status": "failed", "reason": f"ADB 命令执行失败: {e}"}
            time.sleep(1.0)
            return {"status": "passed", "output": output}

        expected_before = step.get("before_activity", "")
        expected_after = step.get("after_activity", "")

        # 1. 校验 before_activity
        if expected_before:
            current = get_current_activity(self._device_serial)
            if current and expected_before and current != expected_before:
                screenshot_path = os.path.join(run_dir, f"step_{step_idx + 1}_deviation.png")
                self._take_screenshot(screenshot_path)
                return {
                    "status": "failed",
                    "reason": f"状态偏离: 期望 {expected_before}，实际 {current}",
                    "screenshot": screenshot_path,
                }

        # 2. 执行 ADB 命令
        try:
            result = run_adb(
                ["shell"] + command.split(),
                device_serial=self._device_serial,
                timeout=30,
            )
            output = result.stdout.decode("utf-8", errors="ignore").strip()
        except Exception as e:
            return {"status": "failed", "reason": f"ADB 命令执行失败: {e}"}

        # 3. 校验 after_activity（智能等待）
        if expected_after:
            current = get_current_activity(self._device_serial)
            if current == expected_after:
                logger.info(f"after_activity 直接匹配: {current}")
            elif current:
                self._wait_activity_stable()
                current = get_current_activity(self._device_serial)
                if current and current != expected_after:
                    send_keyevent(self._device_serial, "KEYCODE_BACK")
                    time.sleep(1.0)
                    current = get_current_activity(self._device_serial)
                    if current == expected_after:
                        return {"status": "warning", "reason": "BACK 键恢复成功"}
                    else:
                        screenshot_path = os.path.join(run_dir, f"step_{step_idx + 1}_mismatch.png")
                        self._take_screenshot(screenshot_path)
                        return {
                            "status": "failed",
                            "reason": f"after_activity 不一致: 期望 {expected_after}，实际 {current}",
                            "screenshot": screenshot_path,
                        }
        else:
            self._wait_activity_stable()

        screenshot_path = os.path.join(run_dir, f"step_{step_idx + 1}.png")
        self._take_screenshot(screenshot_path)

        return {"status": "passed", "output": output, "screenshot": screenshot_path}

    def _execute_ai_navigate(self, step, step_idx, run_dir):
        """执行 AI 导航步骤"""
        prompt = step.get("prompt", "")
        if not prompt:
            return {"status": "skipped", "reason": "AI 导航 prompt 为空"}

        try:
            from tv_annotation.ai_client import ai_navigate

            def capture_func(filepath):
                return self._take_screenshot(filepath)

            result = ai_navigate(
                prompt=prompt,
                device_serial=self._device_serial,
                capture_func=capture_func,
            )

            return {
                "status": "passed" if result["result"] == "success" else "warning",
                "ai_result": result["result"],
                "total_rounds": result["total_rounds"],
                "rounds": result["rounds"],
            }
        except Exception as e:
            logger.error(f"AI 导航异常: {e}")
            return {"status": "warning", "reason": f"AI 导航异常: {e}"}

    def _execute_ai_verify(self, step, step_idx, run_dir):
        """执行 AI 校验步骤（失败不中断回放）"""
        if self._quick_mode:
            return {"status": "skipped", "reason": "快速回放跳过 AI 验证"}

        prompt = step.get("prompt", "")
        if not prompt:
            return {"status": "skipped", "reason": "AI 校验 prompt 为空"}

        screenshot_path = os.path.join(run_dir, f"step_{step_idx + 1}_verify.png")
        self._take_screenshot(screenshot_path)

        try:
            from tv_annotation.ai_client import ai_verify

            result = ai_verify(prompt=prompt, screenshot_path=screenshot_path)

            return {
                "status": "passed" if result["passed"] else "warning",
                "ai_passed": result["passed"],
                "ai_reason": result["reason"],
                "ai_confidence": result["confidence"],
                "screenshot": screenshot_path,
            }
        except Exception as e:
            logger.error(f"AI 校验异常: {e}")
            return {
                "status": "warning",
                "reason": f"AI 校验异常: {e}",
                "screenshot": screenshot_path,
            }

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    @staticmethod
    def _build_steps_overview(steps):
        """从原始步骤列表构建概览信息（类型 + 摘要文字）"""
        overview = []
        for step in steps:
            step_type = step.get("type", "")
            summary = ""
            if step_type == "key_group":
                cmds = step.get("commands", [])
                if len(cmds) == 1:
                    c = cmds[0]
                    key = c.get("key", "")
                    if c.get("is_long_press"):
                        dur = c.get("duration_ms", 0)
                        summary = f"长按 {key} {dur / 1000:.1f}s" if dur else f"长按 {key}"
                    else:
                        summary = key
                elif len(cmds) > 1:
                    keys = [c.get("key", "") for c in cmds]
                    if len(set(keys)) == 1:
                        summary = f"{keys[0]} ×{len(keys)}"
                    else:
                        summary = " → ".join(keys)
                interval = step.get("interval_ms", 0)
                if interval and len(cmds) > 1:
                    summary += f"（间隔 {interval}ms）"
            elif step_type == "adb_command":
                summary = step.get("description") or step.get("command", "")
            elif step_type == "ai_navigate":
                prompt = step.get("prompt", "")
                summary = prompt[:40] + "..." if len(prompt) > 40 else prompt
            elif step_type == "ai_verify":
                prompt = step.get("prompt", "")
                summary = prompt[:40] + "..." if len(prompt) > 40 else prompt
            overview.append({"type": step_type, "summary": summary})
        return overview

    def _take_screenshot(self, filepath):
        """截图：使用采集卡或回退 ADB

        Returns:
            bool: 是否成功
        """
        t0 = time.time()
        try:
            ok = self._capture_card.take_screenshot(filepath, self._device_serial)
            logger.info(f"截图耗时: {time.time() - t0:.2f}s, 结果: {ok}")
            return ok
        except Exception as e:
            logger.warning(f"截图失败: {e} (耗时 {time.time() - t0:.2f}s)")
            return False

    def _wait_activity_stable(self):
        """等待 Activity 稳定

        连续两次相同则认为稳定，最多等待 5s。
        """
        prev_activity = ""
        start = time.time()
        while time.time() - start < _ACTIVITY_POLL_TIMEOUT:
            current = get_current_activity(self._device_serial)
            if current and current == prev_activity:
                return  # 连续两次相同，稳定
            prev_activity = current
            time.sleep(_ACTIVITY_POLL_INTERVAL)

    def _send_long_press(self, keycode, duration_ms):
        """通过 sendevent 精确模拟长按：按下 → 等待指定时长 → 松开

        需要 adb root 权限（由 _ensure_adb_root 在回放启动时完成）。
        keycode: ADB keycode 名称（如 KEYCODE_DPAD_DOWN）
        duration_ms: 按住时长（毫秒）
        """
        # ADB keycode → 按键名 → Linux input event code
        key_name = None
        for name, adb_code in ADB_KEYCODE_MAP.items():
            if adb_code == keycode:
                key_name = name
                break

        linux_code = get_linux_keycode(key_name) if key_name else None
        if linux_code is None:
            logger.warning(f"无法获取 Linux keycode: {keycode}，使用 --longpress 回退")
            run_adb(["shell", "input", "keyevent", "--longpress", keycode],
                    device_serial=self._device_serial,
                    timeout=max(duration_ms / 1000.0 + 5, 10))
            return

        # 延迟检测输入设备
        if self._input_device is None:
            self._input_device = self._find_input_device()
        if not self._input_device:
            logger.warning("未找到输入设备，使用 --longpress 回退")
            run_adb(["shell", "input", "keyevent", "--longpress", keycode],
                    device_serial=self._device_serial,
                    timeout=max(duration_ms / 1000.0 + 5, 10))
            return

        duration_s = duration_ms / 1000.0
        dev = self._input_device
        # sendevent: EV_KEY=1, value 1=按下 0=松开; EV_SYN=0 0 0 同步
        shell_cmd = (
            f"sendevent {dev} 1 {linux_code} 1; "
            f"sendevent {dev} 0 0 0; "
            f"sleep {duration_s:.2f}; "
            f"sendevent {dev} 1 {linux_code} 0; "
            f"sendevent {dev} 0 0 0"
        )

        logger.info(f"sendevent 长按: {key_name}(linux={linux_code}), 时长={duration_ms}ms, 设备={dev}")
        try:
            run_adb(
                ["shell", shell_cmd],
                device_serial=self._device_serial,
                timeout=duration_s + 10,
            )
        except Exception as e:
            logger.warning(f"sendevent 长按失败: {e}")

    def _ensure_adb_root(self):
        """确保 adb 以 root 模式运行（sendevent 需要写入 /dev/input/ 权限）"""
        if self._adb_rooted:
            return
        try:
            result = subprocess.run(
                [ADB_PATH, "-s", self._device_serial, "root"],
                capture_output=True, timeout=10,
            )
            output = result.stdout.decode("utf-8", errors="ignore").strip()
            logger.info(f"adb root: {output}")
            self._adb_rooted = True
            # adb root 会重启 adbd，等待设备重新连接
            time.sleep(2)
        except Exception as e:
            logger.warning(f"adb root 失败: {e}")

    def _find_input_device(self):
        """自动查找遥控器输入设备路径（用于 sendevent 长按）

        优先选 IR Receiver / Remote 设备。

        Returns:
            str: 设备路径如 "/dev/input/event2"，找不到返回 None
        """
        import re
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

        current_device = None
        current_name = ""
        candidates = []
        exclude = ["touch", "mouse", "touchscreen", "touchpad"]

        for line in output.splitlines():
            m = re.match(r"add device \d+:\s*(/dev/input/event\d+)", line)
            if m:
                current_device = m.group(1)
                current_name = ""
                continue
            m = re.match(r'\s+name:\s+"(.+)"', line)
            if m:
                current_name = m.group(1)
                continue
            if current_device and re.match(r"\s+KEY", line):
                candidates.append((current_device, current_name))
                current_device = None

        # 优先选遥控器 / IR 设备
        for dev, name in candidates:
            nl = name.lower()
            if any(ex in nl for ex in exclude):
                continue
            if any(kw in nl for kw in ["ir receiver", "ir remote", "remote control"]):
                logger.info(f"选择遥控器设备: {dev} ({name})")
                return dev

        for dev, name in candidates:
            nl = name.lower()
            if any(ex in nl for ex in exclude):
                continue
            if any(kw in nl for kw in ["ir", "remote", "rc", "cec"]):
                logger.info(f"选择输入设备: {dev} ({name})")
                return dev

        # 兜底：第一个非 touch 设备
        for dev, name in candidates:
            if not any(ex in name.lower() for ex in exclude):
                logger.info(f"使用默认输入设备: {dev} ({name})")
                return dev

        logger.warning("未找到合适的输入设备")
        return None

    def _save_json(self, filepath, data):
        """原子写入 JSON 文件"""
        tmp_path = filepath + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            if os.path.exists(filepath):
                os.remove(filepath)
            os.rename(tmp_path, filepath)
        except Exception as e:
            logger.error(f"保存 JSON 失败: {e}")
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
