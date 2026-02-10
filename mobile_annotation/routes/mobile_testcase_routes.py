"""
Mobile测试用例管理路由
"""
from flask import Blueprint, request
from common.testcase_utils import (
    handle_get_testcases_request,
    handle_upload_xlsx_request,
    handle_update_step_status_request,
    handle_update_step_instruction_request,
    handle_update_testcase_meta_request,
    handle_delete_step_request,
    handle_add_step_request,
    handle_export_testcases_request
)


def create_mobile_testcase_routes(data_xlsx_path):
    """创建Mobile测试用例路由蓝图"""
    
    bp = Blueprint('mobile_testcase', __name__)
    
    # 从Excel文件读取并返回所有测试用例列表
    @bp.route('/api/mobile/testcases', methods=['GET'])
    def mobile_get_testcases():
        """获取测试用例列表"""
        return handle_get_testcases_request(data_xlsx_path)
    
    
    # 上传测试用例Excel文件
    @bp.route('/api/mobile/upload_xlsx', methods=['POST'])
    def mobile_upload_xlsx():
        """上传data.xlsx或.csv文件"""
        return handle_upload_xlsx_request(request, data_xlsx_path)
    
    
    # 更新测试步骤的采集完成状态到Excel
    @bp.route('/api/mobile/update_step_status', methods=['POST'])
    def mobile_update_step_status():
        """更新步骤采集状态"""
        return handle_update_step_status_request(request, data_xlsx_path)
    
    
    # 修改测试步骤的操作指令到Excel
    @bp.route('/api/mobile/update_step_instruction', methods=['POST'])
    def mobile_update_step_instruction():
        """更新步骤指令"""
        return handle_update_step_instruction_request(request, data_xlsx_path)


    # 修改用例的前置条件 / 操作步骤 / 预期结果
    @bp.route('/api/mobile/update_testcase_meta', methods=['POST'])
    def mobile_update_testcase_meta():
        """
        更新某个用例的前置条件、操作步骤、预期结果
        请求体: {
            "test_case_id": "xxx",
            "precondition": "...",
            "operation": "多行步骤文本...",
            "expect_result": "..."
        }
        """
        return handle_update_testcase_meta_request(request, data_xlsx_path)
    
    
    # 从Excel中删除指定的测试步骤
    @bp.route('/api/mobile/delete_step', methods=['POST'])
    def mobile_delete_step():
        """删除步骤"""
        return handle_delete_step_request(request, data_xlsx_path)
    
    
    # 在测试用例中插入新的测试步骤到Excel
    @bp.route('/api/mobile/add_step', methods=['POST'])
    def mobile_add_step():
        """添加步骤"""
        return handle_add_step_request(request, data_xlsx_path)
    
    
    # 导出测试用例Excel文件
    @bp.route('/api/mobile/export_testcases', methods=['GET'])
    def mobile_export_testcases():
        """导出测试用例Excel文件"""
        return handle_export_testcases_request(data_xlsx_path)
    
    return bp
