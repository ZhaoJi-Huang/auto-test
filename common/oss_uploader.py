"""
公共 OSS 上传工具
提供 OSSUploader，供 TV / Mobile 等模块共用
"""

import os
import json
import glob
from pathlib import Path

from .oss_bucket import OSSBucket

class OSSUploader:
    def __init__(self):
        self.bucket = OSSBucket()

    def scan_files(self, directory: str):
        """扫描所有目录或子目录下的 steps.json"""
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file == "steps.json":
                    yield os.path.join(root, file)

    def upload_files(self, directory: str):
        """
        上传指定目录下 steps.json 中引用的所有图片到 OSS，
        并将 JSON 中的图片名替换为对应的 OSS URL。
        """
        OSS_PREFIX = "https://cloudtest-wlcb-prod-01"

        for file_path in self.scan_files(directory):
            with open(file_path, "r", encoding="utf-8") as f:
                result_json = json.load(f)

            m_uuid = result_json.get("UUID", "")
            
            
            images_dir = os.path.dirname(file_path)

            # 仅根据 steps.json 中 steps[*].before_img / after_img 字段上传
            steps = result_json.get("steps", [])
            if not isinstance(steps, list):
                steps = []

            for step in steps:
                if not isinstance(step, dict):
                    continue
                for field in ("before_img", "after_img", "before_xml", "after_xml"):
                    img_ref = step.get(field)
                    # 无值或已经是目标 OSS 域名的 URL，则跳过
                    if not img_ref or isinstance(img_ref, str) and img_ref.startswith(OSS_PREFIX):
                        continue

                    # 将字段值视作本地文件名或路径
                    if os.path.isabs(img_ref):
                        image_path = img_ref
                    else:
                        image_path = os.path.join(images_dir, img_ref)

                    if not os.path.exists(image_path):
                        # 找不到对应文件则跳过
                        continue

                    image_name = os.path.basename(image_path)
                    object_name = f"annotation_data/{m_uuid}/{image_name}"
                    object_name = self.bucket.upload(object_name, image_path)
                    if object_name:
                        oss_url = self.bucket.get_url(object_name)
                    else:
                        oss_url = image_path
                    # 回写为 OSS URL
                    step[field] = oss_url

            

            result_json["uploaded"] = True
            # 先将图片上传后的结果落盘，再上传 steps.json，避免出现步骤文件早于图片上传的情况
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(result_json, f, indent=4, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())

            # 等待上面写入完成后，再上传 steps.json
            object_name = f"annotation_data/{m_uuid}/steps.json"
            uploaded_steps_name = self.bucket.upload(object_name, file_path)
            if uploaded_steps_name:
                url = self.bucket.get_url(uploaded_steps_name)
                result_json["steps_url"] = url
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(result_json, f, indent=4, ensure_ascii=False)

    def convert_base64(self, directory: str):
        """
        读取 steps.json 并将其中引用的图片转换为 base64，
        返回结构: { testCase_name: { instruction_name: steps[] } }
        """
        import base64

        result_json = {}
        OSS_PREFIX = "https://cloudtest-wlcb-prod-01"
        ret = {}
        for file_path in self.scan_files(directory):
            testCase_name = Path(file_path).parts[-3]
            instruction_name = Path(file_path).parts[-2]

            with open(file_path, "r", encoding="utf-8") as f:
                instruction_json = json.load(f)

            images_dir = os.path.dirname(file_path)
            images_path = sorted(glob.glob(os.path.join(images_dir, "*.jpg")))

            image_base64_map = {}
            for image_path in images_path:
                image_name = os.path.basename(image_path)
                with open(image_path, "rb") as f:
                    img_base64 = base64.b64encode(f.read()).decode("utf-8")
                image_base64_map[image_name] = f"data:image/jpeg;base64,{img_base64}"

            def replace_image_values(obj):
                if isinstance(obj, dict):
                    return {k: replace_image_values(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [replace_image_values(item) for item in obj]
                elif isinstance(obj, str):
                    # 如果已经是 OSS URL（cloudtest-wlcb-prod-01 开头），直接保留原值，不转 base64
                    if obj.startswith(OSS_PREFIX):
                        return obj
                    for image_name, img_base64 in image_base64_map.items():
                        if image_name in obj:
                            return img_base64
                return obj

            instruction_json = replace_image_values(instruction_json)
            result_json.setdefault(testCase_name, {})
            result_json[testCase_name][instruction_name] = instruction_json
            ret = instruction_json
        return ret


