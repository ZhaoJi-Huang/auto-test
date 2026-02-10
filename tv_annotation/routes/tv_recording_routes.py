"""
TV录制管理路由
"""
from flask import Blueprint, request, jsonify, Response


def create_tv_recording_routes(recorder):
    """创建TV录制管理路由蓝图"""
    
    bp = Blueprint('tv_recording', __name__)
    
    @bp.route('/api/tv/recording/start', methods=['POST'])
    def start_recording():
        """开始录制 - 完全按照 web_tv_recorder.py 的 api/start 实现
        
        接收参数:
            testcase_name: 测试用例名称（可选）
            step_name: 步骤名称（可选）
        """
        data = request.get_json() or {}
        testcase_name = data.get('testcase_name')
        step_name = data.get('step_name')
        success = recorder.start_recording(testcase_name=testcase_name, step_name=step_name)
        
        return jsonify({
            "success": success,
            "message": "Recording started" if success else "Already recording",
            "session_dir": recorder.session_dir if success else None,
            "testcase_name": testcase_name,
            "step_name": step_name
        })
    
    
    @bp.route('/api/tv/recording/stop', methods=['POST'])
    def stop_recording():
        """停止录制"""
        success = recorder.stop_recording()
        return jsonify({
            "success": success,
            "message": "Recording stopped" if success else "Not recording",
            "total_steps": len(recorder.steps),
            "steps": recorder.steps,
            "session_dir": recorder.session_dir
        })

        # 删除指定步骤的某条操作记录（按索引）
    @bp.route('/api/tv/delete_step_record', methods=['POST'])
    def tv_delete_step_record():
        """删除指定步骤的某条操作记录"""
        try:
            data = request.get_json()
            testcase_name = data.get('testcase_name', '')
            step_name = data.get('step_name', '')
            if not testcase_name or not step_name:
                return jsonify({"error": "Missing testcase_name or step_name"}), 400
            recorder.delete_last_step()

            return jsonify({"success": True, "message": "Record deleted successfully"})
        except Exception as e:
            import traceback
            print(f"Error in tv_delete_step_record: {e}")
            print(traceback.format_exc())
            return jsonify({"error": str(e)}), 500


    @bp.route('/api/tv/recording/change_wait_time', methods=['POST'])
    def change_wait_time():
        """改变等待时间"""
        data = request.get_json()
        wait_time = data.get('wait_time', 0.5)
        recorder.WAIT_TIME = wait_time
        return jsonify({"success": True, "message": "Wait time changed successfully"})
    
    @bp.route('/api/tv/recording/set_continuous_capture', methods=['POST'])
    def set_continuous_capture():
        """设置是否连续截图"""
        data = request.get_json()
        enabled = data.get('enabled', False)
        
        if enabled:
            success = recorder.start_continuous_capture()
            message = "连续截图已开启"
        else:
            success = recorder.stop_continuous_capture()
            message = "连续截图已关闭"
        
        return jsonify({
            "success": success,
            "message": message,
            "enabled": recorder.is_continuous_capture
        })
    
    @bp.route('/api/tv/recording/get_continuous_capture', methods=['GET'])
    def get_continuous_capture():
        """获取连续截图状态"""
        return jsonify({
            "success": True,
            "enabled": recorder.is_continuous_capture
        })
    
    @bp.route('/api/tv/recording/status', methods=['GET'])
    def get_recording_status():
        """获取录制状态"""
        import os
        
        # 获取查询参数中的设备IP
        device_ip = request.args.get('device_ip', None)
        
        # 如果传入了设备IP，更新录制器的设备IP
        if device_ip and device_ip != recorder.device_ip:
            recorder.device_ip = device_ip
        
        status = recorder.get_status()
        
        # 格式化 steps 数据，使其更易于前端展示
        formatted_steps = []
        for step in status.get('steps', []):
            formatted_step = {
                'index': step.get('index', 0),
                'timestamp': step.get('timestamp', ''),
                'action_type': step.get('action_type', ''),
                'key_name': step.get('key_name', ''),
                'adb_command': step.get('adb_command', ''),
                'description': step.get('description', ''),
                'before_img': os.path.basename(step.get('before_img', '')) if step.get('before_img') else None,
                'after_img': os.path.basename(step.get('after_img', '')) if step.get('after_img') else None,
                'success': step.get('success', True)
            }
            # 如果有 output 或 error 字段（ADB命令的返回）
            if 'output' in step:
                formatted_step['output'] = step['output']
            if 'error' in step:
                formatted_step['error'] = step['error']
            
            formatted_steps.append(formatted_step)
        
        # 返回增强的状态信息
        return jsonify({
            'is_recording': status.get('is_recording', False),
            'testcase_name': status.get('testcase_name', ''),
            'step_name': status.get('step_name', ''),
            'step_count': status.get('step_count', 0),
            'steps': formatted_steps,
            'session_dir': status.get('session_dir'),
            'start_time': status.get('start_time'),
            'connected': status.get('connected', False),
            'device_ip': status.get('device_ip', '')
        })
    
    
    @bp.route('/api/tv/adb_devices', methods=['GET'])
    def get_adb_devices():
        """获取 adb devices 结果，用于查看当前已连接的设备"""
        try:
            result = recorder.run_adb(["devices"])
            output = result.stdout.decode('utf-8', errors='ignore')
            error = result.stderr.decode('utf-8', errors='ignore')
            return jsonify({
                "success": result.returncode == 0,
                "output": output,
                "error": error
            })
        except Exception as e:
            import traceback
            print(f"Error in get_adb_devices: {e}")
            print(traceback.format_exc())
            return jsonify({"success": False, "error": str(e)}), 500
    
    
    @bp.route('/api/tv/recording/send_key', methods=['POST'])
    def send_key():
        """发送按键并记录"""
        data = request.get_json()
        key_name = data.get('key', '').strip().upper()
        
        if not key_name:
            return jsonify({"success": False, "message": "按键名称为空"})
        
        success, step_data = recorder.record_manual_action(key_name)
        
        return jsonify({
            "success": success,
            "message": f"按键 {key_name} 已发送并记录",
            "step": step_data
        })
    
    
    @bp.route('/api/tv/recording/send_adb', methods=['POST'])
    def send_adb_command():
        """发送ADB命令并记录"""
        data = request.get_json()
        command = data.get('command', '').strip()
        
        if not command:
            return jsonify({"success": False, "message": "命令为空"})
        
        success, step_data = recorder.record_adb_command(command)
        
        return jsonify({
            "success": success,
            "message": "命令已执行并记录" if success else "命令执行失败",
            "step": step_data
        }), 200
    
    
    @bp.route('/api/tv/recording/screen_stream')
    def screen_stream():
        """实时屏幕流"""
        try:
            # 创建生成器
            stream_generator = recorder.generate_screen_stream()
            
            # 返回流式响应
            response = Response(
                stream_generator,
                mimetype='multipart/x-mixed-replace; boundary=frame'
            )
            
            # 设置响应头，防止缓冲
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            response.headers['X-Accel-Buffering'] = 'no'
            
            return response
        except Exception as e:
            import traceback
            print(f"Screen stream route error: {e}")
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500
    
    return bp
