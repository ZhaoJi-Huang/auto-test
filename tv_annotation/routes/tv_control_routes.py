"""
TV遥控操作路由
"""
import os
import time
import json
import re
import subprocess
from flask import Blueprint, request, jsonify, Response, send_from_directory
from common.utils import sanitize_filename, ADB_PATH


def create_tv_control_routes(current_folder_path_getter, 
                             current_folder_path_setter, tv_data_dir, device_config):
    """创建TV遥控操作路由蓝图（去掉remote_control依赖，直接使用ADB）"""
    
    bp = Blueprint('tv_control', __name__)
    
    # 向TV设备发送按键操作并记录截图（完全按照参考项目web_tv_recorder.py中的/api/keyevent实现）
    @bp.route('/api/tv/send_key', methods=['POST'])
    def tv_send_key():
        """发送按键事件并记录到info.txt（兼容测试步骤采集模式）"""
        current_folder_path = current_folder_path_getter()
        device_ip = device_config['tv_ip']
        data = request.get_json()
        key = data.get('key', '').strip()
        duration = data.get('duration', 0)
        command = data.get('command', '')
        exec_count = data.get('exec_count', 1)
        
        # 兼容两种参数格式
        if not key and not command:
            return jsonify({"success": False, "message": "Key name is empty"}), 400
        
        use_adb = bool(command)
        if command:
            key = command
        
        # 转换为大写（与参考项目保持一致）
        key_name = key.upper()
        
        try:
            # 如果有current_folder_path，说明在采集模式，使用原有的info.txt记录方式
            if current_folder_path and os.path.exists(current_folder_path):
                # 操作前截图（使用ADB直接截图）
                timestamp = time.strftime("%H%M%S")
                screenshot_before = os.path.join(current_folder_path, f"screenshot_{timestamp}.png")
                
                # 使用ADB截图
                adb_cmd = [ADB_PATH]
                # if device_ip:
                #     adb_cmd.extend(["-s", device_ip])
                adb_cmd.extend(["exec-out", "screencap", "-p"])
                
                with open(screenshot_before, "wb") as f:
                    subprocess.run(adb_cmd, stdout=f, timeout=10)
                
                # 执行操作
                if use_adb:
                    # ADB命令模式 - 完全按照参考项目 /api/adb 实现
                    adb_command = command
                    
                    # 自动添加 shell 前缀
                    adb_direct_commands = ['devices', 'connect', 'disconnect', 'push', 'pull', 
                                           'install', 'uninstall', 'logcat', 'bugreport', 'reboot',
                                           'forward', 'reverse', 'version', 'start-server', 'kill-server']
                    first_word = adb_command.split()[0] if adb_command.split() else ''
                    
                    cmd = [ADB_PATH]
                    # if device_ip:
                    #     cmd.extend(["-s", device_ip])
                    
                    if first_word == 'shell':
                        cmd.extend(adb_command.split())
                    elif first_word in adb_direct_commands:
                        cmd.extend(adb_command.split())
                    else:
                        cmd.extend(["shell"] + adb_command.split())
                    
                    # 执行ADB命令
                    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
                    
                    adb_output = result.stdout.decode('utf-8', errors='ignore')
                    adb_error = result.stderr.decode('utf-8', errors='ignore')
                    adb_success = result.returncode == 0
                else:
                    # 普通按键模式 - 使用ADB keyevent
                    from ..tv_recorder import TVRecorder
                    temp_recorder = TVRecorder(device_config=device_config)
                    
                    # 获取ADB keycode
                    adb_keycode = temp_recorder.ADB_KEYCODE_MAP.get(key_name, f"KEYCODE_{key_name}")
                    
                    # 构建命令
                    cmd = [ADB_PATH]
                    # if device_ip:
                    #     cmd.extend(["-s", device_ip])
                    
                    if exec_count > 1:
                        # 重复执行
                        for _ in range(exec_count):
                            subprocess.run(cmd + ["shell", "input", "keyevent", adb_keycode], 
                                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
                            time.sleep(0.1)
                    elif duration > 0.5:
                        # 长按
                        subprocess.run(cmd + ["shell", "input", "keyevent", "--longpress", adb_keycode],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
                    else:
                        # 普通点击
                        subprocess.run(cmd + ["shell", "input", "keyevent", adb_keycode],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
                    
                    adb_output = ""
                    adb_error = ""
                    adb_success = True
                
                # 等待界面响应
                time.sleep(0.5)
                
                # 操作后截图（使用ADB直接截图）
                screenshot_after = os.path.join(current_folder_path, f"screenshot_{timestamp}_after.png")
                
                adb_cmd = [ADB_PATH]
                # if device_ip:
                #     adb_cmd.extend(["-s", device_ip])
                adb_cmd.extend(["exec-out", "screencap", "-p"])
                
                with open(screenshot_after, "wb") as f:
                    subprocess.run(adb_cmd, stdout=f, timeout=10)
                
                # 读取info.txt
                info_file = os.path.join(current_folder_path, 'info.txt')
                try:
                    with open(info_file, 'r', encoding='utf-8') as f:
                        file_content = json.load(f)
                except:
                    file_content = {
                        "执行时间": time.strftime('%Y-%m-%d %H:%M:%S'),
                        "操作记录": []
                    }
                
                # 构建操作类型描述
                if use_adb:
                    operation_type = f"[adb] {adb_command}"
                else:
                    operation_type = f"{key_name}*{exec_count}" if exec_count > 1 else (f"{key_name}_LONG" if duration > 0.5 else key_name)
                
                # 记录操作
                operation = {
                    "操作类型": operation_type,
                    "按键时长": f"{duration:.2f}秒" if not use_adb else "N/A",
                    "截图路径": os.path.basename(screenshot_before),
                    "操作后截图": os.path.basename(screenshot_after),
                    "执行时间": time.strftime('%Y-%m-%d %H:%M:%S')
                }
                
                # 如果是ADB命令，添加输出信息
                if use_adb:
                    if adb_success:
                        operation["命令输出"] = adb_output or "(no output)"
                    else:
                        operation["命令输出"] = adb_error or adb_output
                        operation["命令状态"] = f"失败 (返回码: {result.returncode})"
                
                file_content["操作记录"].append(operation)
                
                # 保存info.txt
                with open(info_file, 'w', encoding='utf-8') as f:
                    json.dump(file_content, f, ensure_ascii=False, indent=2)
                
                # 返回响应
                if use_adb:
                    if adb_success:
                        return jsonify({
                            "success": True,
                            "message": f"Command executed and recorded",
                            "output": adb_output or "(no output)"
                        })
                    else:
                        return jsonify({
                            "success": False,
                            "message": f"Command failed with code {result.returncode}",
                            "output": adb_error or adb_output
                        })
                else:
                    return jsonify({
                        "success": True,
                        "message": f"Key {key_name} sent and recorded"
                    })
            
            # 如果没有current_folder_path，只执行按键（不记录）
            if use_adb:
                # 执行ADB命令
                cmd = [ADB_PATH]
                # if device_ip:
                #     cmd.extend(["-s", device_ip])
                cmd.extend(["shell"] + command.split())
                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
            else:
                # 执行按键
                from ..tv_recorder import TVRecorder
                temp_recorder = TVRecorder(device_config=device_config)
                adb_keycode = temp_recorder.ADB_KEYCODE_MAP.get(key_name, f"KEYCODE_{key_name}")
                
                cmd = [ADB_PATH]
                # if device_ip:
                #     cmd.extend(["-s", device_ip])
                subprocess.run(cmd + ["shell", "input", "keyevent", adb_keycode],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
            
            return jsonify({
                "success": True,
                "message": f"Key {key_name} sent"
            })
            
        except subprocess.TimeoutExpired:
            return jsonify({"success": False, "message": "Command timeout", "output": ""}), 500
        except Exception as e:
            import traceback
            print(f"Error in tv_send_key: {e}")
            traceback.print_exc()
            return jsonify({"success": False, "message": str(e), "output": ""}), 500
    
    
    # 开始新的测试步骤采集，创建数据目录并初始化记录文件
    @bp.route('/api/tv/send_prompt', methods=['POST'])
    def tv_send_prompt():
        """发送测试提示 - 开始采集（加红点）"""
        data = request.get_json()
        prompt = data.get('prompt', '')
        testcase_name = data.get('testcase_name')
        
        if not prompt:
            return jsonify({"error": "No prompt provided"}), 400
        
        if testcase_name:
            testcase_folder = os.path.join(tv_data_dir, sanitize_filename(testcase_name))
            os.makedirs(testcase_folder, exist_ok=True)
            folder_path = os.path.join(testcase_folder, sanitize_filename(prompt))
       
        
        os.makedirs(folder_path, exist_ok=True)
        current_folder_path_setter(folder_path)
        
        content = {
            "执行时间": time.strftime('%Y-%m-%d %H:%M:%S'),
            "执行指令": prompt,
            "操作记录": [],
            "status": "collecting",  # 采集中状态（红点）
            "status_message": "正在采集操作记录，请停止操作"
        }
        
        info_file = os.path.join(folder_path, 'info.txt')
        with open(info_file, 'w', encoding='utf-8') as f:
            json.dump(content, f, ensure_ascii=False, indent=2)
        
        return jsonify({
            "success": True, 
            "message": "Prompt received",
            "status": "collecting",
            "status_message": "正在采集操作记录，请停止操作"
        })
    
    
    # 完成当前测试步骤的采集，保存最终截图和记录
    @bp.route('/api/tv/finish_collection', methods=['POST'])
    def tv_finish_collection():
        """完成采集"""
        device_ip = device_config['tv_ip']
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
                folder_path = os.path.join(tv_data_dir, sanitize_filename(testcase_name), sanitize_filename(instruction))
            
            if not folder_path or not os.path.exists(folder_path):
                return jsonify({"error": f"Folder not found: {folder_path}"}), 404
            
            timestamp = time.strftime("%H%M%S")
            screenshot_name = f"screenshot_FINISH_{timestamp}.png"
            screenshot_path = os.path.join(folder_path, screenshot_name)
            
            # 使用ADB截图
            try:
                adb_cmd = [ADB_PATH]
                if device_ip:
                    adb_cmd.extend(["-s", device_ip])
                adb_cmd.extend(["exec-out", "screencap", "-p"])
                
                with open(screenshot_path, "wb") as f:
                    subprocess.run(adb_cmd, stdout=f, timeout=10)
            except Exception as e:
                print(f"Error capturing screenshot: {e}")
                screenshot_name = ""
            
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
                "截图路径": screenshot_name,
                "执行时间": time.strftime('%Y-%m-%d %H:%M:%S')
            }
            file_content["操作记录"].append(finish_operation)
            
            # 更新状态为就绪（绿点）
            file_content["status"] = "ready"
            file_content["status_message"] = "操作记录采集完成，可以开始下一步操作"
            
            with open(info_file, 'w', encoding='utf-8') as f:
                json.dump(file_content, f, ensure_ascii=False, indent=2)
            
            return jsonify({
                "success": True, 
                "message": "FINISH operation recorded", 
                "screenshot": screenshot_name,
                "status": "ready",
                "status_message": "操作记录采集完成，可以开始下一步操作"
            })
        except Exception as e:
            import traceback
            print(f"Error in tv_finish_collection: {e}")
            print(traceback.format_exc())
            return jsonify({"error": str(e)}), 500
    
    
    # 提供TV设备的实时视频流（已废弃，使用录制模块的视频流）
    # @bp.route('/api/tv/video_stream')
    # def tv_video_stream():
    #     """TV视频流 - 已迁移到 /api/tv/recording/screen_stream"""
    #     return jsonify({"error": "Please use /api/tv/recording/screen_stream instead"}), 410
    
    
    # 提供TV采集数据文件的静态访问服务
    @bp.route('/tv_data/<path:subpath>')
    def serve_tv_data(subpath):
        """提供TV数据文件"""
        return send_from_directory(tv_data_dir, subpath)
    
    return bp
