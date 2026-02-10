"""
TV测试用例管理路由
"""
import io
from flask import Blueprint, request, jsonify, send_file
import openpyxl
from openpyxl.styles import Font, Border, Side
from openpyxl.comments import Comment
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


def create_tv_testcase_routes(data_xlsx_path):
    """创建TV测试用例路由蓝图"""
    
    bp = Blueprint('tv_testcase', __name__)
    
    # 从Excel文件读取并返回所有测试用例列表
    @bp.route('/api/tv/testcases', methods=['GET'])
    def tv_get_testcases():
        """获取测试用例列表"""
        return handle_get_testcases_request(data_xlsx_path)
    
    
    # 上传测试用例Excel或CSV文件    
    @bp.route('/api/tv/upload_xlsx', methods=['POST'])
    def tv_upload_xlsx():
        """上传data.xlsx或.csv文件"""
        return handle_upload_xlsx_request(request, data_xlsx_path)

        
    # 下载测试用例Excel模板文件
    @bp.route('/api/tv/download_template', methods=['GET'])
    def tv_download_template():
        """下载data.xlsx模板"""
        try:
            # 如果文件不存在，创建临时文件并直接返回
            wb = openpyxl.Workbook()
            ws = wb.active
            
            # 设置表头和对应的填写格式说明
            headers = [
                "JIRA Key", 
                "Summary",
                "Description",
                "Issue Type",
                "JIRA Path",
                "Reporter",
                "Created At",
                "Updated At",
                "Path",
                "Priority",
                "Assignee",
                "Pre Condition",
                "Test Procedure",
                "Expected Result",
            ]
            
            # 每个列头对应的填写格式说明
            header_tips = {
                "JIRA Key": "填写格式：JIRA Key，例如：PROJ-123",
                "Summary": "填写格式：测试用例的概要描述，例如：验证用户登录功能",
                "Description": "填写格式：测试用例的详细描述信息",
                "Issue Type": "填写格式：问题类型，例如：Test Case",
                "JIRA Path": "填写格式：JIRA路径，例如：/project/test",
                "Reporter": "填写格式：报告人，例如：张三",
                "Created At": "填写格式：创建时间，例如：2024-01-01",
                "Updated At": "填写格式：更新时间，例如：2024-01-02",
                "Path": "填写格式：路径信息",
                "Priority": "填写格式：优先级，例如：High, Medium, Low",
                "Assignee": "填写格式：指派人，例如：李四",
                "Pre Condition": "填写格式：前置条件，例如：用户已登录系统",
                "Test Procedure": "填写格式：测试步骤，每行一个步骤，例如：\n1. 打开登录页面\n2. 输入用户名和密码\n3. 点击登录按钮",
                "Expected Result": "填写格式：预期结果，例如：成功登录并跳转到主页",
            }
            
            # 写入表头
            for col_idx, header in enumerate(headers, start=1):
                cell = ws.cell(row=1, column=col_idx, value=header)
                # 设置字体：加粗，字号12
                cell.font = Font(bold=True, size=12)
                # 设置边框
                thin_border = Border(
                    left=Side(style='thin'),
                    right=Side(style='thin'),
                    top=Side(style='thin'),
                    bottom=Side(style='thin')
                )
                cell.border = thin_border
                # 添加注释（tips）
                if header in header_tips:
                    cell.comment = Comment(header_tips[header], "填写提示")
            
            # 将文件保存到内存中
            output = io.BytesIO()
            wb.save(output)
            output.seek(0)
            wb.close()
            
            # 直接返回文件，不保存到磁盘
            return send_file(
                output,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name='data_template.xlsx'
            )
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    
    
    # 更新测试步骤的采集完成状态到Excel
    @bp.route('/api/tv/update_step_status', methods=['POST'])
    def tv_update_step_status():
        """更新步骤采集状态"""
        return handle_update_step_status_request(request, data_xlsx_path)
    
    
    # 修改测试步骤的操作指令到Excel（更新第16列中对应步骤的更改名称）
    @bp.route('/api/tv/update_step_instruction', methods=['POST'])
    def tv_update_step_instruction():
        """更新步骤指令"""
        return handle_update_step_instruction_request(request, data_xlsx_path)


    # 修改用例的前置条件 / 操作步骤 / 预期结果
    @bp.route('/api/tv/update_testcase_meta', methods=['POST'])
    def tv_update_testcase_meta():
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
    @bp.route('/api/tv/delete_step', methods=['POST'])
    def tv_delete_step():
        """删除步骤"""
        return handle_delete_step_request(request, data_xlsx_path)
    
    
    # 在测试用例中插入新的测试步骤到Excel
    @bp.route('/api/tv/add_step', methods=['POST'])
    def tv_add_step():
        """添加步骤"""
        return handle_add_step_request(request, data_xlsx_path)
    
    
    # 导出测试用例Excel文件
    @bp.route('/api/tv/export_testcases', methods=['GET'])
    def tv_export_testcases():
        """导出测试用例Excel文件"""
        return handle_export_testcases_request(data_xlsx_path)
    
    return bp
