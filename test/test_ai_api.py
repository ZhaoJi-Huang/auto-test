"""
测试大模型 API 连通性：图片上传 + 对话
用法: python -m test.test_ai_api [图片路径]
不传图片路径时会自动生成一张测试图片
"""
import datetime
import json
import os
import sys
import tempfile

import requests

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tv_annotation.ai_client import _BASE_HEADERS, _FILE_UPLOAD_URL, _CHAT_URL


def create_test_image():
    """生成一张简单的测试图片"""
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (200, 200), color=(50, 100, 200))
        draw = ImageDraw.Draw(img)
        draw.text((50, 90), "TEST", fill="white")
        path = os.path.join(tempfile.gettempdir(), "ai_api_test.png")
        img.save(path)
        print(f"[生成测试图片] {path}")
        return path
    except ImportError:
        print("[错误] 需要 Pillow 库来生成测试图片: pip install Pillow")
        sys.exit(1)


def test_upload(filepath):
    """测试图片上传"""
    print("\n" + "=" * 60)
    print("1. 测试图片上传")
    print("=" * 60)
    print(f"  URL: {_FILE_UPLOAD_URL}")
    print(f"  文件: {filepath}")
    print(f"  Headers: {json.dumps(_BASE_HEADERS, indent=4, ensure_ascii=False)}")

    filename = os.path.basename(filepath)
    with open(filepath, "rb") as f:
        files = [("files", (filename, f, "image/png"))]
        response = requests.post(
            _FILE_UPLOAD_URL,
            files=files,
            headers=_BASE_HEADERS,
            timeout=30,
        )

    print(f"\n  状态码: {response.status_code}")
    print(f"  响应头: {dict(response.headers)}")
    try:
        resp_json = response.json()
        print(f"  响应体: {json.dumps(resp_json, indent=4, ensure_ascii=False)}")
        if response.ok:
            image_url = resp_json["data"][filename]
            print(f"\n  [成功] 图片 URL: {image_url}")
            return image_url
        else:
            print(f"\n  [失败] HTTP {response.status_code}")
            return None
    except Exception as e:
        print(f"  响应文本: {response.text[:500]}")
        print(f"\n  [失败] 解析响应异常: {e}")
        return None


def test_chat(text, image_url=None):
    """测试对话接口"""
    print("\n" + "=" * 60)
    print("2. 测试对话接口")
    print("=" * 60)
    print(f"  URL: {_CHAT_URL}")

    content = []
    if image_url:
        content.append({"type": "image_url", "image_url": {"url": image_url}})
        print(f"  图片 URL: {image_url}")
    content.append({"type": "text", "text": text})
    print(f"  文本: {text}")

    data = {
        "prompts": [{"role": "user", "content": content}],
        "stream": False,
        "nohup": False,
    }
    print(f"  请求体: {json.dumps(data, indent=4, ensure_ascii=False)}")
    print(f"  Headers: {json.dumps(_BASE_HEADERS, indent=4, ensure_ascii=False)}")

    response = requests.post(
        _CHAT_URL,
        json=data,
        headers=_BASE_HEADERS,
        timeout=60,
    )

    print(f"\n  状态码: {response.status_code}")
    print(f"  响应头: {dict(response.headers)}")
    try:
        resp_json = response.json()
        print(f"  响应体: {json.dumps(resp_json, indent=4, ensure_ascii=False)}")
        if response.ok:
            data_field = resp_json.get("data", {})
            if isinstance(data_field, dict):
                result = data_field.get("text") or data_field.get("content") or str(data_field)
            else:
                result = str(data_field)
            print(f"\n  [成功] 模型返回: {result[:500]}")
        else:
            print(f"\n  [失败] HTTP {response.status_code}")
    except Exception as e:
        print(f"  响应文本: {response.text[:500]}")
        print(f"\n  [失败] 解析响应异常: {e}")


def main():
    # 获取图片路径
    current = datetime.datetime.now()
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
        if not os.path.exists(filepath):
            print(f"[错误] 文件不存在: {filepath}")
            sys.exit(1)
    else:
        filepath = create_test_image()

    # 测试上传
    image_url = test_upload(filepath)
    print(f"图片上传完成，耗时:{datetime.datetime.now() - current}")

    # 测试对话（纯文本）
    current = datetime.datetime.now()
    test_chat("你好，请回复 OK")
    print(f"会话上传完成，耗时:{datetime.datetime.now() - current}")

    # 测试对话（带图片）
    current = datetime.datetime.now()
    if image_url:
        test_chat("请描述这张图片的内容", image_url=image_url)
    else:
        print("\n[跳过] 图片上传失败，跳过带图片的对话测试")
    print(f"图片会话上传完成，耗时:{datetime.datetime.now() - current}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
