"""
Mobile录制管理路由
"""
from flask import Blueprint, request, jsonify


def create_mobile_recording_routes(recording_manager):
    """创建Mobile录制管理路由蓝图"""
    
    bp = Blueprint('mobile_recording', __name__)
    
    @bp.route('/api/mobile/device/info', methods=['GET'])
    def mobile_device_info():
        """获取Mobile设备信息"""
        info = recording_manager.get_device_info()
        return jsonify(info)
    
    @bp.route('/api/mobile/recording/start', methods=['POST'])
    def mobile_start_recording():
        """开始录制"""
        data = request.get_json() or {}
        testCaseId = data.get('testCaseId', '')
        testCaseName = data.get('testCaseName')
        stepNum = data.get('stepNum', 0)
        instruction = data.get('instruction')
        
        success, message, session_id = recording_manager.start_recording(
            testCaseId=testCaseId,
            testCaseName=testCaseName,
            stepNum=stepNum,
            stepName=instruction
        )
        
        
        return jsonify({
            "success": success,
            "message": message,
            "session_id": session_id,
        })
    
    
    @bp.route('/api/mobile/recording/stop', methods=['POST'])
    def mobile_stop_recording():
        """停止录制"""
        success, message, result = recording_manager.stop_recording()
        return jsonify({
            "success": success,
            "message": message,
            "result": result
        })
    @bp.route('/api/mobile/recording/send_adb', methods=['POST'])
    def send_adb_command():
        """发送ADB命令并记录"""
        data = request.get_json()
        command = data.get('command', '').strip()
        
        if not command:
            return jsonify({"success": False, "message": "命令为空"})
        
        success, step_data = recording_manager.record_adb_command(command)
        
        return jsonify({
            "success": success,
            "message": "命令已执行并记录" if success else "命令执行失败",
            "step": step_data
        })

    @bp.route('/api/mobile/recording/change_wait_time', methods=['POST'])
    def change_wait_time():
        """改变等待时间"""
        data = request.get_json()
        wait_time = data.get('wait_time', 0.5)
        recording_manager.WAIT_TIME = wait_time
        return jsonify({"success": True, "message": "Wait time changed successfully"})
    
    # 删除指定步骤的某条操作记录（按索引）
    @bp.route('/api/mobile/delete_step_record', methods=['POST'])
    def mobile_delete_step_record():
        """删除指定步骤的某条操作记录"""
        try:
            data = request.get_json()
            testcase_name = data.get('testcase_name', '')
            step_name = data.get('step_name', '')
            if not testcase_name or not step_name:
                return jsonify({"error": "Missing testcase_name or step_name"}), 400
            recording_manager.delete_last_step()

            return jsonify({"success": True, "message": "Record deleted successfully"})
        except Exception as e:
            import traceback
            print(f"Error in tv_delete_step_record: {e}")
            print(traceback.format_exc())
            return jsonify({"error": str(e)}), 500
    
    @bp.route('/api/mobile/recording/status', methods=['GET'])
    def mobile_recording_status():
        """获取录制状态（包含操作列表）"""
        status = recording_manager.get_status()
        return jsonify(status)
    
    
    @bp.route('/api/mobile/recording/steps', methods=['GET'])
    def mobile_get_recording_steps():
        """获取录制操作列表"""
        status = recording_manager.get_status()
        return jsonify({
            "success": True,
            "steps": status.get("steps", []),
            "step_count": status.get("step_count", 0)
        })
    
    return bp
