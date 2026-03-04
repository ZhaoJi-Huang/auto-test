"""
大模型客户端
通过内部私有化部署的大模型提供 AI 导航和校验能力
"""

import json
import logging
import os
import re
import time

import requests

from common.adb_utils import send_keyevent

logger = logging.getLogger(__name__)

# 大模型平台配置
_BASE_HEADERS = {
    "X-App-Signature": "XcHFOesX3prKv8tLYpkf351_BzfgLv4LZ2U47nDggYk=",
    "X-APP-ID": "abc1502b-93a9-45e9-b3dc-e518a6821866",
    "username": "zhaoji1.huang",
    "authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkZXBhcnRtZW50Ijoi5Yib5paw5bqU55So6YOoIiwiZXhwIjoxNzQyNTM3NTgwLCJ1c2VybmFtZSI6InpoYW9qaTEuaHVhbmcifQ.6Feu-Uv0b5Fwr4GDXWy2QGkqOL_x2peSPauq7Ynyhxg"
}

_FILE_UPLOAD_URL = "https://chat-ape-dls.tclking.com/chatape/v1/files/objects"
_CHAT_URL = "https://chat-ape-dls.tclking.com/3rd_party/v1/chat/agent"

# 复用连接的 Session，避免每次请求重新建立 TCP/TLS 握手
_session = requests.Session()
_session.headers.update(_BASE_HEADERS)

# AI 按键名 → ADB keycode 映射
_AI_KEY_MAP = {
    "UP": "KEYCODE_DPAD_UP",
    "DOWN": "KEYCODE_DPAD_DOWN",
    "LEFT": "KEYCODE_DPAD_LEFT",
    "RIGHT": "KEYCODE_DPAD_RIGHT",
    "ENTER": "KEYCODE_ENTER",
    "BACK": "KEYCODE_BACK",
    "HOME": "KEYCODE_HOME",
}


def _compress_image(filepath, max_size_kb=300, quality=70):
    """压缩图片为 JPEG，减少上传体积

    Args:
        filepath: 原始图片路径
        max_size_kb: 目标最大体积（KB）
        quality: JPEG 质量（1-100）

    Returns:
        str: 压缩后的文件路径（可能与原路径不同）
    """
    file_size_kb = os.path.getsize(filepath) / 1024
    if file_size_kb <= max_size_kb:
        return filepath

    try:
        from PIL import Image
        img = Image.open(filepath)
        compressed_path = filepath.rsplit(".", 1)[0] + "_compressed.jpg"
        img = img.convert("RGB")
        img.save(compressed_path, "JPEG", quality=quality)
        new_size_kb = os.path.getsize(compressed_path) / 1024
        logger.info(f"图片压缩: {file_size_kb:.0f}KB -> {new_size_kb:.0f}KB")
        return compressed_path
    except Exception as e:
        logger.warning(f"图片压缩失败，使用原图: {e}")
        return filepath


def upload_image(filepath):
    """上传图片到大模型平台，返回图片 URL

    Args:
        filepath: 本地图片文件路径

    Returns:
        str: 图片 URL

    Raises:
        RuntimeError: 上传失败时抛出
    """
    # 压缩大图片以加速上传
    upload_path = _compress_image(filepath)
    filename = os.path.basename(upload_path)
    try:
        with open(upload_path, "rb") as f:
            mime = "image/jpeg" if upload_path.endswith(".jpg") else "image/png"
            files = [("files", (filename, f, mime))]
            response = _session.post(
                _FILE_UPLOAD_URL,
                files=files,
                timeout=30,
            )
        response.raise_for_status()
        data = response.json()["data"]
        return data[filename]
    except Exception as e:
        raise RuntimeError(f"图片上传失败: {e}")


def chat(text, image_url=None, workflow_id=None):
    """发送对话请求，返回文本结果

    Args:
        text: 文本内容
        image_url: 图片 URL（可选）
        workflow_id: 工作流 ID（可选）

    Returns:
        str: 大模型返回的文本

    Raises:
        RuntimeError: 请求失败时抛出
    """
    content = []
    if image_url:
        content.append({"type": "image_url", "image_url": {"url": image_url}})
    content.append({"type": "text", "text": text})

    messages = [{"role": "user", "content": content}]
    return chat_with_history(messages, workflow_id=workflow_id)


def chat_with_history(messages, workflow_id=None):
    """发送多轮对话请求，支持完整会话历史

    Args:
        messages: 消息列表，每项格式 {"role": "user"|"assistant", "content": ...}
        workflow_id: 工作流 ID（可选）

    Returns:
        str: 大模型返回的文本

    Raises:
        RuntimeError: 请求失败时抛出
    """
    data = {
        "prompts": messages,
        "stream": False,
        "nohup": False,
    }
    if workflow_id:
        data["assistant_id"] = workflow_id

    response = None
    try:
        response = _session.post(
            _CHAT_URL,
            json=data,
            timeout=60,
        )
        response.raise_for_status()
        result = response.json()
        # 兼容不同返回结构：优先 data.text，其次 data.content，最后整个 data
        data_field = result.get("data", {})
        if isinstance(data_field, dict):
            return data_field.get("text") or data_field.get("content") or json.dumps(data_field, ensure_ascii=False)
        return str(data_field)
    except Exception as e:
        resp_text = ""
        if response is not None:
            try:
                resp_text = response.text[:500]
            except Exception:
                pass
        logger.error(f"大模型请求失败: {e}, 响应: {resp_text}")
        raise RuntimeError(f"大模型请求失败: {e}")


def _parse_json_response(text):
    """从大模型返回文本中提取 JSON

    大模型可能返回 markdown 代码块包裹的 JSON，需要提取。

    Args:
        text: 大模型返回的原始文本

    Returns:
        dict: 解析后的 JSON 对象

    Raises:
        ValueError: 解析失败时抛出
    """
    # 用正则提取第一个 {...} 块，兼容任何包裹格式（纯文本、markdown、双重序列化等）
    text = text.strip()
    match = re.search(r"\{[^{}]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # 兜底：支持嵌套 {} 的复杂 JSON
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"无法解析大模型返回的 JSON: {text[:200]}")


def ai_navigate(prompt, device_serial, capture_func, max_rounds=20, stop_check=None):
    """AI 动态导航：截图 -> 发给大模型（含历史会话） -> 执行按键 -> 循环直到完成

    每一轮的截图和 AI 响应都会作为历史消息传入下一轮，使 AI 能基于
    完整上下文做出更准确的导航决策，避免重复操作。

    Args:
        prompt: 导航目标描述
        device_serial: ADB 设备序列号
        capture_func: 截图函数，签名 capture_func(filepath) -> bool
        max_rounds: 最大轮次
        stop_check: 停止检查函数，返回 True 时中断导航

    Returns:
        dict: {
            "result": "success" | "timeout" | "aborted",
            "rounds": [...],
            "total_rounds": N
        }
    """
    system_prompt = (
        "你是一个 TV 遥控器操作助手。用户会发送 TV 屏幕截图，你需要根据截图分析当前画面并操作遥控器。\n"
        f"用户目标：{prompt}\n"
        "可用按键：UP, DOWN, LEFT, RIGHT, ENTER, BACK, HOME\n"
        "每次只返回一个 JSON，格式如下：\n"
        '若需要操作：{"action": "按键名", "reason": "理由", "done": false}\n'
        '若目标已完成：{"action": "none", "done": true, "reason": "已完成的理由"}\n'
        "注意：\n"
        "- 结合之前的操作历史和画面变化来判断下一步\n"
        "- 如果发现画面没有变化或在重复，尝试不同的策略\n"
        "- 只返回 JSON，不要其他内容"
    )

    # 会话历史：system 消息 + 每轮的 user(截图) / assistant(响应)
    messages = [{"role": "system", "content": system_prompt}]

    rounds = []

    for i in range(1, max_rounds + 1):
        # 检查是否需要停止
        if stop_check and stop_check():
            logger.info(f"AI 导航被中断（第 {i} 轮）")
            return {
                "result": "aborted",
                "rounds": rounds,
                "total_rounds": i - 1,
            }

        round_info = {"round": i}
        round_start = time.time()

        try:
            # 1. 截图
            import tempfile
            t0 = time.time()
            screenshot_path = os.path.join(
                tempfile.gettempdir(), f"ai_nav_{i}.png"
            )
            if not capture_func(screenshot_path):
                round_info["error"] = "截图失败"
                rounds.append(round_info)
                continue
            t_capture = time.time() - t0
            logger.info(f"AI 导航第 {i} 轮 - 截图耗时: {t_capture:.2f}s")

            # 2. 上传图片
            t0 = time.time()
            image_url = upload_image(screenshot_path)
            t_upload = time.time() - t0
            logger.info(f"AI 导航第 {i} 轮 - 图片上传耗时: {t_upload:.2f}s")
            round_info["screenshot"] = screenshot_path

            # 3. 构建本轮 user 消息（截图 + 轮次提示）
            user_content = [
                {"type": "image_url", "image_url": {"url": image_url}},
                {"type": "text", "text": f"第 {i} 轮，这是当前 TV 屏幕截图。请分析并返回下一步操作。"},
            ]
            messages.append({"role": "user", "content": user_content})

            # 4. 发送给大模型（带完整历史）
            t0 = time.time()
            response_text = chat_with_history(messages)
            t_chat = time.time() - t0
            logger.info(f"AI 导航第 {i} 轮 - 大模型对话耗时: {t_chat:.2f}s")
            round_info["ai_response"] = response_text

            # 将 AI 回复加入历史
            messages.append({"role": "assistant", "content": response_text})

            # 5. 解析返回
            logger.info(f"AI 导航第 {i} 轮原始返回: {response_text[:300]}")
            result = _parse_json_response(response_text)
            if not isinstance(result, dict):
                round_info["error"] = f"大模型返回非 JSON 对象: {type(result).__name__}"
                rounds.append(round_info)
                continue
            round_info["parsed"] = result

            # 6. 检查是否完成
            if result.get("done"):
                round_info["action"] = "none"
                rounds.append(round_info)
                logger.info(f"AI 导航完成（第 {i} 轮）: {result.get('reason')}")
                return {
                    "result": "success",
                    "rounds": rounds,
                    "total_rounds": i,
                }

            # 7. 执行按键
            action = result.get("action", "").upper()
            keycode = _AI_KEY_MAP.get(action)
            if keycode:
                send_keyevent(device_serial, keycode)
                round_info["action"] = action
                logger.info(f"AI 导航第 {i} 轮: {action} - {result.get('reason')}")
                # 将执行结果也追加到历史，让 AI 知道按键已执行
                messages.append({
                    "role": "user",
                    "content": f"已执行按键 {action}，等待画面更新..."
                })
            else:
                round_info["error"] = f"未知按键: {action}"
                logger.warning(f"AI 导航返回未知按键: {action}")
                messages.append({
                    "role": "user",
                    "content": f"按键 {action} 无法识别，请重新分析。"
                })

            # 等待画面稳定
            time.sleep(1.0)

        except Exception as e:
            round_info["error"] = str(e)
            logger.error(f"AI 导航第 {i} 轮异常: {e}", exc_info=True)

        round_total = time.time() - round_start
        logger.info(f"AI 导航第 {i} 轮 - 总耗时: {round_total:.2f}s")
        rounds.append(round_info)

    logger.warning(f"AI 导航超时，已达最大轮次 {max_rounds}")
    return {
        "result": "timeout",
        "rounds": rounds,
        "total_rounds": max_rounds,
    }


def ai_verify(prompt, screenshot_path):
    """AI 智能校验：截图 -> 发给大模型 -> 返回通过/失败

    Args:
        prompt: 校验描述
        screenshot_path: 截图文件路径

    Returns:
        dict: {
            "passed": bool,
            "reason": "判断理由",
            "confidence": 0.0-1.0
        }
    """
    verify_prompt_template = (
        "你是一个 TV 界面测试校验助手。当前 TV 屏幕截图如上。\n"
        "请判断：{prompt}\n"
        "返回 JSON 格式：\n"
        '{{"passed": true/false, "reason": "判断理由", "confidence": 0.0-1.0}}\n'
        "只返回 JSON，不要其他内容。"
    )

    try:
        # 上传截图
        image_url = upload_image(screenshot_path)

        # 发送校验请求
        filled_prompt = verify_prompt_template.format(prompt=prompt)
        response_text = chat(filled_prompt, image_url=image_url)

        # 解析返回
        result = _parse_json_response(response_text)
        return {
            "passed": bool(result.get("passed", False)),
            "reason": result.get("reason", ""),
            "confidence": float(result.get("confidence", 0.0)),
        }
    except Exception as e:
        logger.error(f"AI 校验异常: {e}")
        return {
            "passed": False,
            "reason": f"AI 校验异常: {e}",
            "confidence": 0.0,
        }
