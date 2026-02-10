"""
TV设备配置路由
"""
import requests
from flask import Blueprint, request, jsonify


def create_tv_config_routes(device_config, setup_tv_services_func):
    """创建TV配置路由蓝图"""
    
    bp = Blueprint('tv_config', __name__)
    
    # 获取TV设备配置信息
    @bp.route('/api/tv/config', methods=['GET'])
    def tv_get_config():
        """获取TV配置"""
        return jsonify(device_config)
    
    
    # 更新并应用TV设备配置
    @bp.route('/api/tv/config', methods=['POST'])
    def tv_apply_config():
        """应用TV配置"""
        data = request.get_json()
        new_tv_ip = data.get('tv_ip', '').strip()
        key_event_device = data.get('key_event_device', '').strip()
        
        if not new_tv_ip:
            return jsonify({"error": "TV IP is required"}), 400
        
        device_config['tv_ip'] = new_tv_ip
        if key_event_device:
            device_config['key_event_device'] = key_event_device
        
        try:
            setup_tv_services_func()
            return jsonify({"success": True, "message": "配置已更新"})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})
    
    # 版本信息代理接口
    @bp.route('/api/tv/version', methods=['GET'])
    def tv_version():
        """获取版本信息（代理接口）"""
        try:
            
            # 返回响应
            return jsonify({"success": True, "message": "已经是最新版本"}), 200
        except requests.exceptions.RequestException as e:
            return jsonify({
                "error": f"Proxy request failed: {str(e)}"
            }), 500
        except Exception as e:
            return jsonify({
                "error": f"Unexpected error: {str(e)}"
            }), 500
    
    return bp
