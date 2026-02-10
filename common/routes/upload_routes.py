"""
公共上传路由 - OSS上传功能
支持 TV 和 Mobile 模块共用
"""
from flask import Blueprint, request, jsonify
import os
from glob import glob

from common.oss_uploader import OSSUploader
from common.utils import sanitize_filename


def create_upload_routes(module_name, data_dir):
    """
    创建公共上传路由蓝图
    
    Args:
        module_name: 模块名称，如 'tv' 或 'mobile'，用于生成 API 路径前缀
        data_dir: 数据目录路径
    """
    
    bp = Blueprint(f'{module_name}_upload', __name__)

    # 公共 OSSUploader 实例
    oss_uploader = OSSUploader()
    
    @bp.route(f'/api/{module_name}/upload_to_oss', methods=['POST'])
    def upload_to_oss():
        try:
            data = request.get_json()
            testcase_name = data.get('testcase_name', '').strip()
            step_name = data.get('step_name', '').strip()
            
            if not testcase_name:
                return jsonify({
                    "success": False,
                    "message": "测试用例名称不能为空"
                }), 400
            
            testcase_dir = os.path.join(data_dir, sanitize_filename(testcase_name[0:120]), sanitize_filename(step_name[0:50]))
            
            # 先检测是否存在可上传的图片（任意 steps.json 目录下的 .jpg）
            image_count = 0
            for file_path in oss_uploader.scan_files(testcase_dir.replace("\\", "/")):
                images_dir = os.path.dirname(file_path)
                images_path = glob(os.path.join(images_dir, "*.jpg"))
                image_count += len(images_path)
            
            if image_count == 0:
                # 没有可上传的图片，直接返回提示信息
                return jsonify({
                    "success": True,
                    "has_images": False,
                    "image_count": 0,
                    "message": f"该测试用例下没有可上传的图片"
                })
            
            # 存在图片时才执行真正的上传
            oss_uploader.upload_files(testcase_dir.replace("\\", "/"))
            return jsonify({
                "success": True,
                "has_images": True,
                "image_count": image_count,
                "message": f"测试用例 '{testcase_name}' 上传成功",
                "testcase_dir": testcase_dir
            })
            
        except ImportError as e:
            return jsonify({
                "success": False,
                "message": f"OSS上传模块未配置: {str(e)}"
            }), 500
        except Exception as e:
            import traceback
            print(f"上传失败: {e}")
            traceback.print_exc()
            return jsonify({
                "success": False,
                "message": f"上传失败: {str(e)}"
            }), 500

    @bp.route(f'/api/{module_name}/get_steps_records', methods=['POST'])
    def get_steps_records():
        data = request.get_json()
        testcase_name = data.get('testcase_name', '').strip()
        step_name = data.get('step_name', '').strip()
        
        if not testcase_name or not step_name:
            return jsonify({
                "success": False,
                "message": "测试用例名称和步骤名称不能为空"
            }), 400
        
        testcase_dir = os.path.join(data_dir, sanitize_filename(testcase_name[0:120]), sanitize_filename(step_name[0:50]))
        
        return jsonify({
            "success": True,
            "data": oss_uploader.convert_base64(testcase_dir.replace("\\", "/")),
            "message": f"get_steps_records '{testcase_name}' 成功",
            "testcase_dir": testcase_dir
        })
   
    @bp.route(f'/api/{module_name}/renew_url', methods=['POST'])
    def renew_url():
        data = request.get_json()
        
        url_input = data.get('urls')
    
        renewed_urls = []
        for url in url_input:
            new_url = oss_uploader.bucket.renew_url(url)
            renewed_urls.append(new_url)
            
        # 构建返回结果
        result = {
            "success": True,
            "urls": renewed_urls,
            "message": f"成功处理 {len(renewed_urls)} 个 URL"
        }
        
        return jsonify(result)
    return bp

