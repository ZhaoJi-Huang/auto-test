"""
测试用例公共工具函数模块
"""
import os
import io
import csv
import tempfile
import time
import gc
import openpyxl
from openpyxl.styles import Font, Border, Side
from flask import jsonify, send_file


def map_header_to_field(header):
    """根据列头关键词映射到目标字段"""
    if not header:
        return None
    # 更彻底的清理：移除所有空白字符和不可见字符
    header_lower = ''.join(c for c in str(header).strip().lower() if c.isprintable() or c.isspace()).strip()
    print('header_lower: ', repr(header_lower))  # 使用 repr 可以看到隐藏字符
    
    # JIRA Key: 包含 "key" 或 "关键词"
    if "key" == header_lower or "关键字" == header_lower or "jira key" == header_lower:
        return "JIRA Key"
    # Summary: 包含 "summary" 或 "概要"
    if "summary" == header_lower or "概要" == header_lower:
        return "Summary"
    # Pre Condition: 包含 "case precondition" 或 "前置条件"
    if "case precondition" == header_lower or "前置条件" == header_lower or "pre condition" == header_lower:
        return "Pre Condition"
    # Test Procedure: 包含 "step" 或 "步骤"
    if "step" == header_lower or "步骤" == header_lower or "test procedure" == header_lower:
        return "Test Procedure"
    # Expected Result: 包含 "expected result" 或 "期望结果"
    if "expected result" == header_lower or "期望结果" == header_lower:
        return "Expected Result"
    # JIRA Path: 包含 "jira path"、"jira路径"、"path" 或 "路径"
    if "path" in header_lower or "路径" in header_lower:
        return "JIRA Path"
    
    return None


def read_excel_data(file_path):
    """读取Excel文件数据"""
    # 使用 read_only=True 模式，可以更快释放文件句柄
    wb = openpyxl.load_workbook(file_path, read_only=True)
    ws = wb.active
    
    # 读取表头
    header_row = list(ws.iter_rows(min_row=1, max_row=1, values_only=True))[0]
    headers = [str(h).strip() if h else "" for h in header_row]
    
    # 读取所有数据行
    data_rows = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        data_rows.append([str(cell).strip() if cell is not None else "" for cell in row])
    
    wb.close()
    return headers, data_rows


def read_csv_data(file_stream):
    """读取CSV文件数据"""
    # 尝试不同的编码
    encodings = ['utf-8', 'gbk', 'gb2312', 'utf-8-sig']
    headers = []
    data_rows = []
    
    # 读取所有字节内容
    file_stream.seek(0)
    file_bytes = file_stream.read()
    
    for encoding in encodings:
        try:
            # 解码为文本
            file_text = file_bytes.decode(encoding)
            
            # 尝试检测分隔符
            delimiter = ','
            try:
                # 使用前几行来检测分隔符
                sample_lines = file_text.split('\n')[:5]
                sample_text = '\n'.join(sample_lines)
                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample_text).delimiter
            except:
                # 如果检测失败，默认使用逗号
                pass
            
            # 读取CSV
            text_io = io.StringIO(file_text)
            reader = csv.reader(text_io, delimiter=delimiter)
            headers = [str(h).strip() if h else "" for h in next(reader)]
            data_rows = [[str(cell).strip() if cell else "" for cell in row] for row in reader]
            text_io.close()
            break
        except Exception as e:
            continue
    
    if not headers:
        raise ValueError("无法读取CSV文件，请检查文件编码")
    
    return headers, data_rows


def reorganize_data(source_headers, source_data_rows):
    """重组数据到目标列顺序"""
    # 目标列顺序，如果检测到 jira 路径，则用 JIRA Path 替换 Labels
    target_headers = [
        "JIRA Key", "Summary", "Description", "Issue Type", "JIRA Path", "Reporter", 
        "Created At", "Updated At", "Path", "Priority", "Assignee", 
        "Pre Condition", "Test Procedure", "Expected Result"
    ]
    # 建立源列头到目标字段的映射
    header_to_field = {}
    for idx, header in enumerate(source_headers):
        mapped_field = map_header_to_field(header)
        if mapped_field:
            # 如果已经有映射，保留第一个
            if mapped_field not in header_to_field:
                header_to_field[mapped_field] = idx
    
    # 重组数据
    reorganized_rows = []
    for source_row in source_data_rows:
        new_row = [""] * len(target_headers)
        
        # 填充映射的字段
        for field, source_idx in header_to_field.items():
            if field in target_headers:
                target_idx = target_headers.index(field)
                if source_idx < len(source_row):
                    new_row[target_idx] = source_row[source_idx]
        
        # 保留其他未映射的列（如果源数据有更多列）
        # 这里可以根据需要调整，暂时只映射指定的字段
        
        reorganized_rows.append(new_row)
    
    return target_headers, reorganized_rows


def write_to_excel(headers, data_rows, output_path):
    """将数据写入Excel文件"""
    wb = openpyxl.Workbook()
    ws = wb.active
    
    # 写入表头
    for col_idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = Font(bold=True, size=12)
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        cell.border = thin_border
    
    # 写入数据行
    for row_idx, row_data in enumerate(data_rows, start=2):
        for col_idx, cell_value in enumerate(row_data, start=1):
            ws.cell(row=row_idx, column=col_idx, value=cell_value)
    
    wb.save(output_path)
    wb.close()


def handle_upload_xlsx(file, data_xlsx_path):
    """
    公共的上传Excel或CSV文件处理函数
    :param file: Flask上传的文件对象
    :param data_xlsx_path: 保存文件的路径
    :return: (success: bool, message: str, path: str, status_code: int or None)
    """
    try:
        if not file or file.filename == '':
            return False, "文件名为空", None, 400
        
        # 支持 .xlsx 和 .csv 文件
        if not (file.filename.endswith('.xlsx') or file.filename.endswith('.csv')):
            return False, "文件格式错误，必须是.xlsx或.csv文件", None, 400
        
        # 读取文件数据
        is_csv = file.filename.endswith('.csv')
        
        if is_csv:
            # 读取CSV文件
            file_stream = io.BytesIO(file.read())
            source_headers, source_data_rows = read_csv_data(file_stream)
        else:
            # 保存临时Excel文件，确保扩展名为.xlsx
            file_content = file.read()
            with tempfile.NamedTemporaryFile(mode='wb', suffix='.xlsx', delete=False) as temp_file:
                temp_path = temp_file.name
                temp_file.write(file_content)
            try:
                source_headers, source_data_rows = read_excel_data(temp_path)
            finally:
                # 确保临时文件被删除，处理 Windows 文件锁定问题
                if os.path.exists(temp_path):
                    # 强制垃圾回收，释放文件句柄
                    gc.collect()
                    # 重试删除，最多尝试3次
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            os.remove(temp_path)
                            break
                        except (OSError, PermissionError) as e:
                            if attempt < max_retries - 1:
                                # 等待一小段时间后重试
                                time.sleep(0.1)
                                gc.collect()
                            else:
                                # 最后一次尝试失败，记录错误但不抛出异常
                                # 临时文件会在系统清理时自动删除
                                pass
        
        # 重组数据
        target_headers, reorganized_rows = reorganize_data(source_headers, source_data_rows)
        
        # 如果原文件存在，先删除
        if os.path.exists(data_xlsx_path):
            os.remove(data_xlsx_path)
        
        # 写入重组后的数据到Excel
        write_to_excel(target_headers, reorganized_rows, data_xlsx_path)
        
        return True, "文件上传成功", data_xlsx_path, None
    except Exception as e:
        return False, str(e), None, 500


def get_testcases(data_xlsx_path):
    """
    从Excel文件读取并返回所有测试用例列表
    :param data_xlsx_path: Excel文件路径
    :return: (testcases: list, error: str or None)
    """
    if not os.path.exists(data_xlsx_path):
        return [], None

    try:
        wb = openpyxl.load_workbook(data_xlsx_path)
        ws = wb.active
        
        # 读取表头，建立列名到索引的映射
        header_row = list(ws.iter_rows(min_row=1, max_row=1, values_only=True))[0]
        headers = [str(h).strip() if h else "" for h in header_row]
        
        # 建立列名到索引的映射（从1开始，因为openpyxl是1-based）
        header_to_col = {}
        header_to_col_lower = {}
        for idx, header in enumerate(headers, start=1):
            header_clean = header.strip()
            if header_clean:
                header_to_col[header_clean] = idx
                header_to_col_lower[header_clean.lower()] = idx

        def get_header_index(name):
            if not name:
                return None
            return header_to_col_lower.get(str(name).strip().lower())

        # 确保有表头"步骤状态"和"更改的步骤名称"
        need_save = False
        if "步骤状态" not in header_to_col:
            # 获取下一个可用的列索引
            next_col = max(header_to_col.values()) + 1 if header_to_col else len(headers) + 1
            ws.cell(row=1, column=next_col, value="步骤状态")
            header_to_col["步骤状态"] = next_col
            need_save = True
        if "更改的步骤名称" not in header_to_col:
            # 获取下一个可用的列索引
            next_col = max(header_to_col.values()) + 1 if header_to_col else len(headers) + 1
            ws.cell(row=1, column=next_col, value="更改的步骤名称")
            header_to_col["更改的步骤名称"] = next_col
            need_save = True
        
        # 如果添加了新列，保存文件
        if need_save:
            wb.save(data_xlsx_path)
        
        # 定义需要读取的列名
        col_jira_key = get_header_index("JIRA Key")
        col_summary = get_header_index("Summary")
        col_precondition = get_header_index("Pre Condition")
        col_jira_path = get_header_index("JIRA Path")
        col_test_procedure = get_header_index("Test Procedure")
        col_expected_result = get_header_index("Expected Result")
        col_step_status = get_header_index("步骤状态")
        col_modified_steps = get_header_index("更改的步骤名称")
        
        testcases = []

        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            # 根据列名获取对应的单元格数据
            def get_cell_value(col_name):
                if col_name is None:
                    return None
                col_idx = col_name - 1  # 转换为0-based索引
                return row[col_idx] if len(row) > col_idx else None
            
            test_case_id = get_cell_value(col_jira_key) or ""
            summary = get_cell_value(col_summary) or ""
            precondition = get_cell_value(col_precondition) or ""
            jira_path = get_cell_value(col_jira_path) or ""
            operation = get_cell_value(col_test_procedure) or ""
            expect_result = get_cell_value(col_expected_result) or ""
            is_collected_cell = get_cell_value(col_step_status)
            modified_steps_text = get_cell_value(col_modified_steps) or ""
            
            # 按行拆分采集状态，若无则后续默认为 False
            collected_lines = []
            if is_collected_cell is not None:
                collected_lines = [str(x).strip() for x in str(is_collected_cell).splitlines() if str(x).strip() != ""]
            
            if not test_case_id:
                continue

            # 解析步骤列表：Test Procedure 为多行步骤文本
            modified_steps_lines =  [line.strip() for line in modified_steps_text.splitlines() if line.strip()]
            operation_lines = [line.strip() for line in operation.splitlines() if line.strip()]
            raw_steps_lines = modified_steps_lines if len(modified_steps_lines) > len(operation_lines) else operation_lines


            steps = []
            step_index = 0
            for line in raw_steps_lines:
                original_instruction = line
                modified_instruction = line
                if step_index < len(raw_steps_lines):
                    original_instruction = raw_steps_lines[step_index]
                if step_index < len(modified_steps_lines):
                    modified_instruction = modified_steps_lines[step_index]
                # 采集状态按行对应，未提供则默认 False
                collected_flag = False
                if step_index < len(collected_lines):
                    val = collected_lines[step_index].lower()
                    collected_flag = val in ['true']

                steps.append({
                    "step_num": len(steps) + 1,
                    "instruction": modified_instruction,
                    "original_instruction": original_instruction,
                    "is_collected": collected_flag,
                })
                step_index += 1

            # 如果没有有效步骤，跳过该用例
            if not steps:
                continue

            testcase_obj = {
                "id": test_case_id,
                "name": summary,
                "precondition": precondition or "",
                "operation": operation or "",
                "expect_result": expect_result or "",
                "jira_path": jira_path or "",
                "steps": steps,
                "modified_steps": modified_steps_text,
                # 用例整体完成状态：全部步骤都为 True
                "all_collected": all(step["is_collected"] for step in steps),
            }
            testcases.append(testcase_obj)
        
        wb.close()
        return testcases, None
    except Exception as e:
        return None, str(e)


def update_step_status(data_xlsx_path, test_case_id, step_num, is_collected):
    """
    更新测试步骤的采集完成状态到Excel
    :param data_xlsx_path: Excel文件路径
    :param test_case_id: 测试用例ID
    :param step_num: 步骤编号
    :param is_collected: 是否已采集
    :return: (success: bool, error: str or None)
    """
    try:
        wb = openpyxl.load_workbook(data_xlsx_path)
        ws = wb.active
        
        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            row_test_case_id = row[0] if len(row) > 0 and row[0] else ""
            if row_test_case_id == test_case_id:
                # 读取当前列15（步骤状态）的多行状态
                existing_text = row[14] if len(row) > 14 and row[14] is not None else ""
                lines = str(existing_text).splitlines() if existing_text != "" else []

                index = max(int(step_num) - 1, 0)
                while len(lines) <= index:
                    lines.append("")

                # 如果新写入的位置之前存在空行，将它们填充为 false，避免出现空状态
                for i in range(index):
                    if not lines[i]:
                        lines[i] = "false"

                lines[index] = "true" if is_collected else "false"
                new_text = "\n".join(lines)

                ws.cell(row=row_idx, column=15, value=new_text)
                wb.save(data_xlsx_path)
                wb.close()
                return True, None
        
        wb.close()
        return False, "Test case not found"
    except Exception as e:
        return False, str(e)


def update_step_instruction(data_xlsx_path, test_case_id, step_num, instruction):
    """
    修改测试步骤的操作指令到Excel（更新第16列中对应步骤的更改名称）
    :param data_xlsx_path: Excel文件路径
    :param test_case_id: 测试用例ID
    :param step_num: 步骤编号
    :param instruction: 新的指令内容
    :return: (success: bool, error: str or None)
    """
    try:
        wb = openpyxl.load_workbook(data_xlsx_path)
        ws = wb.active
        
        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            row_test_case_id = row[0] if len(row) > 0 and row[0] else ""
            if row_test_case_id == test_case_id:
                # 读取当前第16列的多行文本
                step_cell = row[12] if len(row) > 12 and row[12] else ""
                step_lines = step_cell.splitlines() if step_cell else []
                existing_text = row[15] if len(row) > 15 and row[15] else ""
                lines = str(existing_text).splitlines() if existing_text else []

                # 确保列表长度足够
                index = max(int(step_num) - 1, 0)
                while len(lines) <= index:
                    lines.append(step_lines[len(lines)])

                lines[index] = instruction or ""
                new_text = "\n".join(lines)

                # 写回第16列"更改的步骤名称"
                ws.cell(row=row_idx, column=16, value=new_text)
                wb.save(data_xlsx_path)
                wb.close()
                return True, None
        
        wb.close()
        return False, "Test case not found"
    except Exception as e:
        return False, str(e)


def update_testcase_meta(data_xlsx_path, test_case_id, precondition, operation, expect_result):
    """
    修改用例的前置条件 / 操作步骤 / 预期结果
    :param data_xlsx_path: Excel文件路径
    :param test_case_id: 测试用例ID
    :param precondition: 前置条件
    :param operation: 操作步骤
    :param expect_result: 预期结果
    :return: (success: bool, error: str or None)
    """
    try:
        if not test_case_id:
            return False, "test_case_id is required"

        wb = openpyxl.load_workbook(data_xlsx_path)
        ws = wb.active

        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            row_test_case_id = row[0] if len(row) > 0 and row[0] else ""
            if row_test_case_id == test_case_id:
                # 更新前置条件（列12）、操作步骤（列13）、预期结果（列14）
                ws.cell(row=row_idx, column=12, value=precondition)
                ws.cell(row=row_idx, column=14, value=expect_result)
                
                # 将更新的 operation 操作步骤写入到 P 列（第16列）"更改的步骤名称"
                if operation:
                    # 将 operation 按行拆分，每行对应一个步骤
                    operation_lines = [line.strip() for line in str(operation).splitlines() if line.strip()]
                    modified_steps_text = "\n".join(operation_lines)
                    ws.cell(row=row_idx, column=16, value=modified_steps_text)
                else:
                    # 如果 operation 为空，清空第16列
                    ws.cell(row=row_idx, column=16, value="")

                wb.save(data_xlsx_path)
                wb.close()
                return True, None

        wb.close()
        return False, "Test case not found"
    except Exception as e:
        return False, str(e)


def delete_step(data_xlsx_path, test_case_id, step_num):
    """
    从Excel中删除指定的测试步骤
    :param data_xlsx_path: Excel文件路径
    :param test_case_id: 测试用例ID
    :param step_num: 步骤编号
    :return: (success: bool, error: str or None)
    """
    try:
        wb = openpyxl.load_workbook(data_xlsx_path)
        ws = wb.active
        
        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            row_test_case_id = row[0] if len(row) > 0 and row[0] else ""
            if row_test_case_id == test_case_id:
                # 读取操作步骤（列13）、采集状态（列15）、更改的步骤名称（列16）
                operation_text = row[12] if len(row) > 12 and row[12] else ""
                collected_text = row[14] if len(row) > 14 and row[14] is not None else ""
                modified_text = row[15] if len(row) > 15 and row[15] else ""

                operation_lines = str(operation_text).splitlines() if operation_text else []
                collected_lines = str(collected_text).splitlines() if collected_text != "" else []
                modified_lines = str(modified_text).splitlines() if modified_text else []

                index = max(int(step_num) - 1, 0)

                # 如果步骤索引超出范围，视为未找到
                if index >= len(operation_lines):
                    wb.close()
                    return False, "Step not found"

                # 删除对应步骤行
                del operation_lines[index]
                if index < len(collected_lines):
                    del collected_lines[index]
                if index < len(modified_lines):
                    del modified_lines[index]

                # 写回操作步骤和更改名称
                ws.cell(row=row_idx, column=13, value="\n".join(operation_lines) if operation_lines else "")
                ws.cell(row=row_idx, column=16, value="\n".join(modified_lines) if modified_lines else "")

                # 写回采集状态：删除后若长度为 0，清空；否则保持对齐
                collected_value = ""
                if collected_lines:
                    collected_value = "\n".join(collected_lines)
                ws.cell(row=row_idx, column=15, value=collected_value)

                wb.save(data_xlsx_path)
                wb.close()
                return True, None
        
        wb.close()
        return False, "Test case not found"
    except Exception as e:
        return False, str(e)


def add_step(data_xlsx_path, test_case_id, instruction, after_step_num):
    """
    在测试用例中插入新的测试步骤到Excel
    :param data_xlsx_path: Excel文件路径
    :param test_case_id: 测试用例ID
    :param instruction: 新步骤的指令
    :param after_step_num: 在哪个步骤后插入（None或0表示追加到末尾）
    :return: (success: bool, error: str or None)
    """
    try:
        wb = openpyxl.load_workbook(data_xlsx_path)
        ws = wb.active
        
        found = False
        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            row_test_case_id = row[0] if len(row) > 0 and row[0] else ""
            if row_test_case_id == test_case_id:
                found = True
                # 读取操作步骤（列13）、更改的步骤名称（列16）和采集状态（列15）
                operation_text = row[12] if len(row) > 12 and row[12] else ""
                modified_text = row[15] if len(row) > 15 and row[15] else ""
                collected_text = row[14] if len(row) > 14 and row[14] is not None else ""

                operation_lines = str(operation_text).splitlines() if operation_text else []
                modified_lines = str(modified_text).splitlines() if modified_text else []
                collected_lines = str(collected_text).splitlines() if collected_text != "" else []

                # 计算插入位置：after_step_num 后插入，1-based；为空则追加到末尾
                insert_index = len(operation_lines) if not after_step_num or after_step_num <= 0 else min(after_step_num, len(operation_lines))
                operation_lines.insert(insert_index, instruction or "")

                # modified 对齐，插入空串
                while len(modified_lines) < insert_index:
                    modified_lines.append("")
                modified_lines.insert(insert_index, "")

                # 处理采集状态：确保列表长度足够
                while len(collected_lines) < insert_index:
                    collected_lines.append("")
                
                # 如果新插入的位置之前存在空行，将它们填充为 false，避免出现空状态
                for i in range(insert_index):
                    if not collected_lines[i]:
                        collected_lines[i] = "false"
                
                # 在插入位置添加 false 状态
                collected_lines.insert(insert_index, "false")

                ws.cell(row=row_idx, column=13, value="\n".join(operation_lines))
                ws.cell(row=row_idx, column=16, value="\n".join(modified_lines))
                # 写回采集状态
                ws.cell(row=row_idx, column=15, value="\n".join(collected_lines))

                wb.save(data_xlsx_path)
                wb.close()
                return True, None

        wb.close()
        if not found:
            return False, "Test case not found"
    except Exception as e:
        return False, str(e)


# ==================== Flask Request 包装函数 ====================
# 这些函数处理 request 参数获取和异常，返回 Flask Response

def handle_get_testcases_request(data_xlsx_path):
    """
    处理获取测试用例列表的请求
    :param data_xlsx_path: Excel文件路径
    :return: Flask Response
    """
    try:
        testcases, error = get_testcases(data_xlsx_path)
        if error:
            return jsonify({"error": error}), 500
        return jsonify(testcases)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def handle_upload_xlsx_request(request, data_xlsx_path):
    """
    处理上传Excel或CSV文件的请求
    :param request: Flask request 对象
    :param data_xlsx_path: 保存文件的路径
    :return: Flask Response
    """
    try:
        if 'file' not in request.files:
            return jsonify({"error": "没有文件"}), 400
        
        file = request.files['file']
        success, message, path, status_code = handle_upload_xlsx(file, data_xlsx_path)
        
        if success:
            return jsonify({
                "success": True, 
                "message": message,
                "path": path
            })
        else:
            return jsonify({"error": message}), status_code or 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def handle_update_step_status_request(request, data_xlsx_path):
    """
    处理更新步骤采集状态的请求
    :param request: Flask request 对象
    :param data_xlsx_path: Excel文件路径
    :return: Flask Response
    """
    try:
        data = request.get_json()
        test_case_id = data.get('test_case_id')
        step_num = data.get('step_num')
        is_collected = data.get('is_collected', True)
        
        success, error = update_step_status(data_xlsx_path, test_case_id, step_num, is_collected)
        if success:
            return jsonify({"success": True})
        else:
            status_code = 404 if error == "Test case not found" else 500
            return jsonify({"error": error}), status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def handle_update_step_instruction_request(request, data_xlsx_path):
    """
    处理更新步骤指令的请求
    :param request: Flask request 对象
    :param data_xlsx_path: Excel文件路径
    :return: Flask Response
    """
    try:
        data = request.get_json()
        test_case_id = data.get('test_case_id')
        step_num = data.get('step_num')
        instruction = data.get('instruction', '')
        
        success, error = update_step_instruction(data_xlsx_path, test_case_id, step_num, instruction)
        if success:
            return jsonify({"success": True})
        else:
            status_code = 404 if error == "Test case not found" else 500
            return jsonify({"error": error}), status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def handle_update_testcase_meta_request(request, data_xlsx_path):
    """
    处理更新用例元数据的请求
    :param request: Flask request 对象
    :param data_xlsx_path: Excel文件路径
    :return: Flask Response
    """
    try:
        data = request.get_json()
        test_case_id = data.get('test_case_id')
        precondition = data.get('precondition', '')
        operation = data.get('operation', '')
        expect_result = data.get('expect_result', '')

        success, error = update_testcase_meta(data_xlsx_path, test_case_id, precondition, operation, expect_result)
        if success:
            return jsonify({"success": True})
        else:
            status_code = 400 if error == "test_case_id is required" else (404 if error == "Test case not found" else 500)
            return jsonify({"error": error}), status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def handle_delete_step_request(request, data_xlsx_path):
    """
    处理删除步骤的请求
    :param request: Flask request 对象
    :param data_xlsx_path: Excel文件路径
    :return: Flask Response
    """
    try:
        data = request.get_json()
        test_case_id = data.get('test_case_id')
        step_num = data.get('step_num')
        
        success, error = delete_step(data_xlsx_path, test_case_id, step_num)
        if success:
            return jsonify({"success": True})
        else:
            status_code = 404 if error in ["Test case not found", "Step not found"] else 500
            return jsonify({"error": error}), status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def handle_add_step_request(request, data_xlsx_path):
    """
    处理添加步骤的请求
    :param request: Flask request 对象
    :param data_xlsx_path: Excel文件路径
    :return: Flask Response
    """
    try:
        data = request.get_json()
        test_case_id = data.get('test_case_id')
        instruction = data.get('instruction', '')
        after_step_num = data.get('after_step_num')
        
        success, error = add_step(data_xlsx_path, test_case_id, instruction, after_step_num)
        if success:
            return jsonify({"success": True})
        else:
            status_code = 404 if error == "Test case not found" else 500
            return jsonify({"error": error}), status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def handle_export_testcases_request(data_xlsx_path):
    """
    处理导出测试用例Excel文件的请求
    :param data_xlsx_path: Excel文件路径
    :return: Flask Response (文件下载)
    """
    try:
        if not os.path.exists(data_xlsx_path):
            return jsonify({"error": "测试用例文件不存在"}), 404
        
        # 使用 send_file 返回文件，设置下载文件名
        return send_file(
            data_xlsx_path,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='testcases.xlsx'
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500
