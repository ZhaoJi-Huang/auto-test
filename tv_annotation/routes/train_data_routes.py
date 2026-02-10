"""
训练数据API路由
"""
import os
import sys
import io
import json
import math
import time
import requests
import subprocess
import openpyxl
from datetime import datetime
from flask import request, jsonify, Blueprint, send_file

# 导入train_data_config（在backend根目录）
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
from common.utils import sanitize_filename
from train_data_config import TrainDataConfig
from common.oss_uploader import OSSUploader


def isJson(json_string):
    """检查字符串是否是有效的JSON"""
    try:
        json.loads(json_string)
        return True
    except (ValueError, TypeError):
        return False


def create_train_data_routes(base_dir):
    """创建训练数据路由蓝图"""
    
    bp = Blueprint('train_data', __name__)
    
    # 初始化服务
    TRAIN_DATA_CONFIG_FILE = os.path.join(base_dir, "train_data_config.json")
    
    train_data_config = TrainDataConfig(TRAIN_DATA_CONFIG_FILE)

    SYNC_PROGRESS_FILE = os.path.join(base_dir, "train_data_sync_progress.json")

    def _now():
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _read_sync_progress():
        if not os.path.exists(SYNC_PROGRESS_FILE):
            return {
                "status": "idle",
                "sync_id": "",
                "started_at": "",
                "updated_at": "",
                "finished_at": "",
                "total": 0,
                "done": 0,
                "pushed": 0,
                "success": 0,
                "failed": 0,
                "skipped_empty": 0,
                "current": "",
                "message": "",
            }
        try:
            with open(SYNC_PROGRESS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
            return data
        except Exception:
            return {
                "status": "idle",
                "sync_id": "",
                "started_at": "",
                "updated_at": "",
                "finished_at": "",
                "total": 0,
                "done": 0,
                "pushed": 0,
                "success": 0,
                "failed": 0,
                "skipped_empty": 0,
                "current": "",
                "message": "failed to read progress file",
            }

    def _write_sync_progress(data):
        try:
            tmp = SYNC_PROGRESS_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, SYNC_PROGRESS_FILE)
        except Exception:
            pass

    @bp.route('/api/tv/train_data/sync/progress', methods=['GET'])
    def get_train_data_sync_progress():
        """查询历史训练数据同步进度"""
        try:
            progress = _read_sync_progress()
            total = int(progress.get("total") or 0)
            done = int(progress.get("done") or 0)
            status = str(progress.get("status") or "idle")

            percent = 0
            if total > 0:
                percent = int(math.floor(done * 100 / total))
            if total == 0 and status in ["finished", "failed"]:
                percent = 100

            progress["percent"] = max(0, min(100, percent))
            return jsonify({
                "code": 200,
                "message": "OK",
                "data": progress,
            }), 200
        except Exception as e:
            return jsonify({
                "code": 500,
                "message": f"Internal error: {str(e)}",
                "data": None,
            }), 500
    
    # ==================== 配置管理接口 ====================
    
    @bp.route('/api/tv/train_data_config', methods=['GET'])
    def get_train_data_config():
        """获取训练数据API配置"""
        try:
            config = train_data_config.get_config()
            return jsonify({
                "code": 200,
                "message": "OK",
                "data": config
            }), 200
        except Exception as e:
            return jsonify({
                "code": 500,
                "message": f"Failed to load config: {str(e)}",
                "data": None
            }), 500
    
    @bp.route('/api/tv/train_data_config', methods=['POST'])
    def update_train_data_config():
        """更新训练数据API配置"""
        try:
            data = request.get_json() or {}
            # 容错处理：确保值存在且为字符串类型
            api_base_url = str(data.get('api_base_url') or '').strip()
            api_token = str(data.get('api_token') or '').strip()
            
            if not api_base_url:
                return jsonify({
                    "code": 400,
                    "message": "api_base_url is required",
                    "data": None
                }), 400
            
            config = train_data_config.update_config(api_base_url, api_token)
            
            return jsonify({
                "code": 200,
                "message": "Config updated successfully",
                "data": config
            }), 200
        except Exception as e:
            return jsonify({
                "code": 500,
                "message": f"Failed to update config: {str(e)}",
                "data": None
            }), 500
    
    # ==================== 代理接口 ====================
    
    @bp.route('/api/tv/train_data', methods=['POST'])
    def proxy_create_train_data():
        """代理: 插入训练数据"""
        try:
            data = request.get_json()
            base_url = train_data_config.get_base_url()
            headers = train_data_config.get_headers()
            
            response = requests.post(
                f"{base_url}/train_data/v1",
                json=data,
                headers=headers,
                timeout=30
            )
            
            return jsonify(response.json()), response.status_code
        except Exception as e:
            return jsonify({
                "code": 500,
                "message": f"Internal error: {str(e)}",
                "data": None
            }), 
            
    
    @bp.route('/api/tv/train_data/sync', methods=['POST'])
    def proxy_sync_train_data():
        """
        代理: 同步历史训练数据

        需求：将前端 useTrainDataSave.ts 中 handleSaveTrainData 拼接参数的逻辑迁移到后端，
        遍历本地已采集的数据，组装与 /train_data/v1 相同的参数结构并推送到训练数据服务。
        """
        try:
            import uuid  # 延迟导入，避免顶层依赖

            def format_timestamp(dt: datetime) -> str:
                return dt.strftime("%Y-%m-%d %H:%M:%S")

            def format_timestamp2(ts: float, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
                return datetime.fromtimestamp(ts).strftime(fmt)

            # 可选：从请求体中获取用户名和项目名，否则留空
            body = request.get_json(silent=True) or {}
            user_name = body.get("user_name", "")
            project = body.get("project", "")

            # 避免并发同步互相覆盖进度
            existing = _read_sync_progress() or {}
            if str(existing.get("status") or "") == "running":
                return jsonify({
                    "code": 400,
                    "message": "sync is running",
                    "data": existing,
                }), 200

            base_url = train_data_config.get_base_url()
            headers = train_data_config.get_headers()
            oss_uploader = OSSUploader()

            # 同步防重：检查 device_config.json 中是否已有对应 key
            device_config_path = os.path.join(base_dir, "device_config.json")
            device_config = {}
            if os.path.exists(device_config_path):
                try:
                    with open(device_config_path, "r", encoding="utf-8") as f:
                        device_config = json.load(f) or {}
                except Exception:
                    device_config = {}

            synced_keys = device_config.get("synced", "")
            # if synced_keys == "true":
            #     return jsonify({
            #         "code": 400,
            #         "message": "历史训练数据已同步过，不能重复同步",
            #         "data": None,
            #     }), 200

            mobile_base_dir = os.path.join(base_dir, "../", "mobile")
            tv_base_dir = os.path.join(base_dir, "../", "tv")

            total = 0
            success = 0
            failed = 0
            done = 0
            skipped_empty = 0

            # 同时遍历 base_dir 和 mobile 目录
            scan_roots = []
            if os.path.isdir(tv_base_dir):
                scan_roots.append(tv_base_dir)
            if os.path.isdir(mobile_base_dir):
                scan_roots.append(mobile_base_dir)

            # 预扫描 steps.json 数量，用于计算进度百分比
            scan_total = 0
            for root in scan_roots:
                try:
                    for module in os.listdir(root):
                        if module != "data" and module != "record_data":
                            continue
                        testcases_dir = os.path.join(root, "data" if module == "data" else "record_data").replace("\\", "/")
                        if not os.path.isdir(testcases_dir):
                            continue
                        for testcase in os.listdir(testcases_dir):
                            testcase_dir = os.path.join(testcases_dir, sanitize_filename(testcase)).replace("\\", "/")
                            if not os.path.isdir(testcase_dir):
                                continue
                            for step in os.listdir(testcase_dir):
                                step_dir = os.path.join(testcase_dir, sanitize_filename(step)).replace("\\", "/")
                                if not os.path.isdir(step_dir):
                                    continue
                                steps_file = os.path.join(step_dir, "steps.json").replace("\\", "/")
                                if os.path.isfile(steps_file):
                                    scan_total += 1
                except Exception:
                    continue

            sync_id = str(uuid.uuid4())
            progress = {
                "status": "running",
                "sync_id": sync_id,
                "started_at": _now(),
                "updated_at": _now(),
                "finished_at": "",
                "total": scan_total,
                "done": 0,
                "pushed": 0,
                "success": 0,
                "failed": 0,
                "skipped_empty": 0,
                "current": "",
                "message": "",
            }
            _write_sync_progress(progress)
            last_write = [0.0]

            def touch(current=None, message=None, force=False):
                progress["updated_at"] = _now()
                if current is not None:
                    progress["current"] = current
                if message is not None:
                    progress["message"] = message
                progress["done"] = done
                progress["pushed"] = total
                progress["success"] = success
                progress["failed"] = failed
                progress["skipped_empty"] = skipped_empty

                now = time.time()
                if force or (now - last_write[0]) > 0.4:
                    _write_sync_progress(progress)
                    last_write[0] = now

            # 遍历所有根目录下的用例：mobile/<testcase>/steps.json
            
            step_name_dict = {}
            jira_key_dict = {}
            empty_step_list = []
            for root in scan_roots:
                # root 是 tv 还是mobile
                for module in os.listdir(root):
                    if module != "data" and module != "record_data":
                        continue
                    # 读取data.xlsx文件，然后获取 Pre Condition列和 更改的步骤名称列，将每行他们的映射关系保存到字典中
                    data_xlsx_path = os.path.join(root, "data.xlsx")
                    if not os.path.isfile(data_xlsx_path):
                        continue
                    wb = openpyxl.load_workbook(data_xlsx_path)
                    ws = wb.active
                    for row in ws.iter_rows(min_row=2, values_only=True):
                        # 容错处理：确保值存在且为字符串类型
                        step_names_str = str(row[12]).strip() if row[12] is not None else ""
                        step_names = step_names_str.split('\n') if step_names_str else []

                        modified_step_names_str = str(row[15]).strip() if row[15] is not None else ""
                        modified_step_names = modified_step_names_str.split('\n') if modified_step_names_str else []
                        
                        jira_key = str(row[0]).strip() if row[0] is not None else ""
                        
                        for ind, step_name in enumerate(step_names):
                            # 容错处理：确保索引有效
                            modified_step_name = modified_step_names[ind] if ind < len(modified_step_names) and modified_step_names[ind] else None
                            jira_key_dict[step_name] = jira_key
                            if not step_name or not modified_step_name:
                                continue
                            step_name_dict[step_name] = modified_step_name

                    testcases_dir = os.path.join(root,  "data" if module == "data" else "record_data").replace("\\", "/")
                    # 扫描data目录下的所有用例
                    for testcase in os.listdir(testcases_dir):
                        # 扫描step目录下的所有步骤
                        testcase_dir = os.path.join(testcases_dir, sanitize_filename(testcase)).replace("\\", "/")
                        for step in os.listdir(testcase_dir):
                            step_dir = os.path.join(testcase_dir, sanitize_filename(step)).replace("\\", "/")
                            if not os.path.isdir(step_dir):
                                continue
                            
                            steps_file = os.path.join(step_dir, "steps.json").replace("\\", "/")
                            if not os.path.isfile(steps_file):
                                continue

                            touch(current=step_dir)
                            # 先检查是否已经有 step_url / steps_url，没有则上传到 OSS 并回写 JSON
                            with open(steps_file, "r", encoding="utf-8") as f:
                                step_json = json.load(f)
                            # steps.json中的步骤名
                            step_name_in_json = step_json.get("step_name") or step_json.get("instruction") or ""

                            step_url = step_json.get("steps_url") or ""
                            # 上传当前步骤下的图片和 steps.json，并在文件中写入 steps_url
                            oss_uploader.upload_files(step_dir)
                            # 重新读取 steps.json，获取最新的 step_url / steps_url
                            with open(steps_file, "r", encoding="utf-8") as f:
                                step_json = json.load(f)
                            step_url = step_json.get("step_url") or step_json.get("steps_url") or ""

                            # 兼容不同结构：优先使用 "records"，否则退回 "steps"
                            records = step_json.get("steps") or []
                            step_name = step
                            # step_name = step_json.get("instruction") or step_json.get("step_name")
                            if not records:
                                empty_step_list.append(step_dir)
                                done += 1
                                skipped_empty += 1
                                touch()
                                continue

                            execution_record = []
                            for item in records:
                                # 这里按前端 OperationRecord 结构做映射：
                                # action_type, key_name/adb_command, duration_ms, before_img/after_img, before_xml/after_xml, timestamp
                                action_type = item.get("action_type")
                                if not action_type:
                                    continue

                                timestamp = item.get("timestamp")
                                if isinstance(timestamp, (int, float)):
                                    executed_at = format_timestamp(datetime.fromtimestamp(timestamp / 1000.0))
                                else:
                                    executed_at = item.get("executed_at") or format_timestamp(datetime.now())

                                execution_record.append({
                                    "action_type": action_type,
                                    "key_name": item.get("key_name") or item.get("adb_command", ""),
                                    "keypress_duration": str(item.get("duration_ms", "")),
                                    "screenshot_before": item.get("before_img", ""),
                                    "screenshot_after": item.get("after_img", ""),
                                    "viewtree_before": item.get("before_xml", ""),
                                    "viewtree_after": item.get("after_xml", ""),
                                    "screenshot_focus": "",
                                    "focus_text": "",
                                    "op_intent": "",
                                    "executed_at": executed_at,
                                })

                            if not execution_record:
                                continue
                            # 优先使用 steps.json 中的步骤名，没有则使用 data.xlsx 中的步骤名，兜底使用文件夹名
                            modify_name = step_name_in_json or step_name_dict.get(step_name, step_name)
                            payload = {
                                "id": str(uuid.uuid4()),
                                # 前端使用 selectedTestCase.id 作为 jira_key，这里用用例目录名代替
                                "jira_key": jira_key_dict.get(step_name,""),
                                "step_url": step_url,
                                # 与前端保持一致的 jira_path 结构
                                "jira_path": json.dumps({
                                    "user_name": user_name,
                                    "project": project,
                                    "jira_path": step_json.get("jira_path", ""),
                                }, ensure_ascii=False),
                                # 使用步骤目录名或 steps.json 中的 instruction 作为执行命令
                                "execution_cmd": modify_name,
                                # 容错处理：确保 start_time 存在且为有效的时间戳
                                "executed_at": (
                                    format_timestamp2(step_json.get("start_time")) 
                                    if step_json.get("start_time") is not None and isinstance(step_json.get("start_time"), (int, float))
                                    else format_timestamp(datetime.now())
                                ),
                                "execution_record": execution_record,
                            }

                            total += 1
                            try:
                                resp = requests.post(
                                    f"{base_url}/train_data/v1",
                                    json=payload,
                                    headers=headers,
                                    timeout=30
                                )
                                if resp.status_code == 200:
                                    try:
                                        resp_json = resp.json()
                                        if resp_json.get("code") == 200:
                                            success += 1
                                            # 每个步骤上传成功时立即刷新一次进度
                                            touch(force=True)
                                        else:
                                            failed += 1
                                    except Exception:
                                        failed += 1
                                else:
                                    failed += 1
                            except Exception:
                                failed += 1
                            finally:
                                done += 1
                                touch()
            if failed > 0:
                raise Exception(f"Failed to sync train data: {failed}")

            # 同步成功后记录已同步 key
            try:
                device_config["synced"] = "true"
                with open(device_config_path, "w", encoding="utf-8") as f:
                    json.dump(device_config, f, ensure_ascii=False, indent=2)
            except Exception:
                # 记录失败不影响本次同步结果
                pass

            progress["status"] = "finished"
            progress["finished_at"] = _now()
            touch(message="sync finished", force=True)
            return jsonify({
                "code": 200,
                "message": "sync finished",
                "data": {
                    "total": total,
                    "success": success,
                    "failed": failed,
                    "empty_step_list": empty_step_list,
                }
            }), 200

        except Exception as e:
            try:
                progress = _read_sync_progress() or {}
                progress["status"] = "failed"
                progress["finished_at"] = _now()
                progress["updated_at"] = _now()
                progress["message"] = str(e)
                _write_sync_progress(progress)
            except Exception:
                pass
            return jsonify({
                "code": 500,
                "message": f"Internal error: {str(e)}",
                "data": None
            }), 500
    
    @bp.route('/api/tv/train_data/list', methods=['GET'])
    def proxy_list_train_data():
        """代理: 查询训练数据列表"""
        try:
            base_url = train_data_config.get_base_url()
            headers = train_data_config.get_headers()
            params = request.args.to_dict()
            response = requests.get(
                f"{base_url}/train_data/v1/list",
                params=params,
                headers=headers,
                timeout=30
            )
            
            return jsonify(response.json()), response.status_code
        except Exception as e:
            return jsonify({
                "code": 500,
                "message": f"Internal error: {str(e)}",
                "data": None
            }), 500
    
    @bp.route('/api/tv/train_data/<train_data_id>', methods=['GET'])
    def proxy_get_train_data(train_data_id):
        """代理: 获取指定训练数据"""
        try:
            base_url = train_data_config.get_base_url()
            headers = train_data_config.get_headers()
            
            response = requests.get(
                f"{base_url}/train_data/v1/{train_data_id}",
                headers=headers,
                timeout=30
            )
            
            return jsonify(response.json()), response.status_code
        except Exception as e:
            return jsonify({
                "code": 500,
                "message": f"Internal error: {str(e)}",
                "data": None
            }), 500
    
    @bp.route('/api/tv/train_data/<train_data_id>', methods=['DELETE'])
    def proxy_delete_train_data(train_data_id):
        """代理: 删除训练数据"""
        try:
            base_url = train_data_config.get_base_url()
            headers = train_data_config.get_headers()
            
            response = requests.delete(
                f"{base_url}/train_data/v1/{train_data_id}",
                headers=headers,
                timeout=30
            )
            
            return jsonify(response.json()), response.status_code
        except Exception as e:
            return jsonify({
                "code": 500,
                "message": f"Internal error: {str(e)}",
                "data": None
            }), 500

    @bp.route('/api/tv/train_data/fetch_step_json', methods=['POST'])
    def fetch_step_json():
        """后端代理请求 step_url，返回 JSON 文本内容

        优先使用 curl（通常在内部环境里更快、更稳定），失败时回退到 requests。
        """
        try:
            body = request.get_json(silent=True) or {}
            url = (body.get("url") or "").strip()
            if not url:
                return jsonify({
                    "code": 400,
                    "message": "url is required",
                    "data": None,
                }), 400

            text = None

            # 优先使用 curl（在 Windows 下避免编码问题，不使用 text 模式）
            try:
                completed = subprocess.run(
                    ["curl", "-m", "8", "-sS", url],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=10,
                )
                if completed.returncode == 0 and completed.stdout:
                  try:
                      text = completed.stdout.decode("utf-8", errors="ignore")
                  except Exception:
                      # 解码失败时，不影响后续逻辑，交给 requests 兜底
                      text = None
                else:
                    # 如果 curl 调用失败，继续走后面的 requests 兜底
                    pass
            except Exception:
                # curl 调用异常时，也继续走后面的 requests 兜底
                pass

            # curl 未拿到内容时，用 requests 兜底
            if text is None:
                resp = requests.get(url, timeout=8)
                resp.raise_for_status()
                text = resp.text

            return jsonify({
                "code": 200,
                "message": "OK",
                "data": text,
            }), 200
        except Exception as e:
            return jsonify({
                "code": 500,
                "message": f"Failed to fetch step json: {str(e)}",
                "data": None,
            }), 500

    return bp
