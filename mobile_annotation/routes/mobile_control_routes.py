"""
Mobile遥控操作和数据记录路由
复用TV的控制和记录逻辑结构
"""
import base64
import os
import subprocess
import time
import json
import re
from flask import Blueprint, request, jsonify, Response
from common.utils import sanitize_filename, ADB_PATH


def create_mobile_control_routes(current_folder_path_getter, current_folder_path_setter, mobile_data_dir, recording_manager):
    """创建Mobile控制操作路由蓝图"""
    
    bp = Blueprint('mobile_control', __name__)
    @bp.route('/api/mobile/send_key', methods=['POST'])
    def mobile_send_key():
        data = request.get_json()
        command = data.get('command', '').strip()

        # 执行ADB命令
        cmd = [ADB_PATH]
        cmd.extend(["shell"] + command.split())
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        
        return jsonify({
            "success": True,
            "message": f"Command {command} sent"
        })

    @bp.route('/api/mobile/screen_stream')
    def mobile_screen_stream():
        """Mobile实时屏幕流"""
        
        def generate():
            while True:
                try:
                    result = recording_manager.run_adb(["exec-out", "screencap", "-p"])
                    if result and result.stdout:
                        yield (
                            b'--frame\r\n'
                            b'Content-Type: image/png\r\n\r\n' + result.stdout + b'\r\n'
                        )
                    time.sleep(0.1)
                except Exception as e:
                    error_msg = str(e)
                    if "超时" in error_msg:
                        if not hasattr(generate, '_timeout_logged'):
                            print(f"Screen capture timeout: {error_msg}")
                            generate._timeout_logged = True
                    else:
                        print(f"Screen capture error: {e}")
                    time.sleep(1)
        
        return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')
  
    # 开始新的测试步骤采集
    @bp.route('/api/mobile/send_prompt', methods=['POST'])
    def mobile_send_prompt():
        """发送测试提示"""
        data = request.get_json()
        prompt = data.get('prompt', '')
        testcase_name = data.get('testcase_name')
        
        if not prompt:
            return jsonify({"error": "No prompt provided"}), 400
        
        if testcase_name:
            testcase_folder = os.path.join(mobile_data_dir, sanitize_filename(testcase_name))
            os.makedirs(testcase_folder, exist_ok=True)
            folder_path = os.path.join(testcase_folder, sanitize_filename(prompt))
        else:
            folder_path = os.path.join(mobile_data_dir, sanitize_filename(prompt))
        
        os.makedirs(folder_path, exist_ok=True)
        current_folder_path_setter(folder_path)
        
        content = {
            "执行时间": time.strftime('%Y-%m-%d %H:%M:%S'),
            "执行指令": prompt,
            "操作记录": []
        }
        
        info_file = os.path.join(folder_path, 'info.txt')
        with open(info_file, 'w', encoding='utf-8') as f:
            json.dump(content, f, ensure_ascii=False, indent=2)
        
        return jsonify({"success": True, "message": "Prompt received"})
    
    
    # 完成当前测试步骤的采集
    @bp.route('/api/mobile/finish_collection', methods=['POST'])
    def mobile_finish_collection():
        """完成采集"""
        current_folder_path = current_folder_path_getter()
        
        try:
            data = request.get_json()
            testcase_name = data.get('testcase_name', '')
            instruction = data.get('instruction', '')
            
            if not testcase_name or not instruction:
                return jsonify({"error": "Missing testcase_name or instruction"}), 400
            
            folder_path = None
            if current_folder_path and os.path.exists(current_folder_path):
                folder_path = current_folder_path
            else:
                folder_path = os.path.join(mobile_data_dir, sanitize_filename(testcase_name), sanitize_filename(instruction))
                if not os.path.exists(folder_path):
                    testcase_folder = os.path.join(mobile_data_dir, sanitize_filename(testcase_name))
                    if os.path.exists(testcase_folder):
                        # 清理后的 instruction 用于匹配
                        sanitized_instruction = sanitize_filename(instruction)
                        for f in os.listdir(testcase_folder):
                            if f.startswith(f"{sanitized_instruction}_"):
                                folder_path = os.path.join(testcase_folder, f)
                                break
            
            if not folder_path or not os.path.exists(folder_path):
                return jsonify({"error": f"Folder not found: {folder_path}"}), 404
            
            info_file = os.path.join(folder_path, 'info.txt')
            try:
                with open(info_file, 'r', encoding='utf-8') as f:
                    file_content = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                file_content = {
                    "执行时间": time.strftime('%Y-%m-%d %H:%M:%S'),
                    "执行指令": instruction,
                    "操作记录": []
                }
            
            finish_operation = {
                "操作类型": "FINISH",
                "执行时间": time.strftime('%Y-%m-%d %H:%M:%S')
            }
            file_content["操作记录"].append(finish_operation)
            
            with open(info_file, 'w', encoding='utf-8') as f:
                json.dump(file_content, f, ensure_ascii=False, indent=2)
            
            return jsonify({"success": True, "message": "FINISH operation recorded"})
        except Exception as e:
            import traceback
            print(f"Error in mobile_finish_collection: {e}")
            print(traceback.format_exc())
            return jsonify({"error": str(e)}), 500
    
    return bp
