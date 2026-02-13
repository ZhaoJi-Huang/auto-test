"""
Confluence 同步客户端
将回放统计数据同步到 Confluence 页面
"""

import os
import json
import logging
import threading
from datetime import datetime

import requests as http_requests

logger = logging.getLogger(__name__)


def _load_confluence_config(data_dir):
    """从 jira_config.json 加载 Confluence 配置

    Returns:
        dict 或 None: {"confluence_url": ..., "confluence_page_id": ..., "confluence_token": ...}
    """
    config_path = os.path.join(data_dir, "jira_config.json")
    if not os.path.exists(config_path):
        return None
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception:
        return None

    url = config.get("confluence_url", "")
    page_id = config.get("confluence_page_id", "")
    token = config.get("confluence_token", "")

    if not url or not page_id or not token:
        return None

    return {
        "confluence_url": url.rstrip("/"),
        "confluence_page_id": page_id,
        "confluence_token": token,
    }


def _scan_all_results(data_dir):
    """递归扫描 replay 目录下所有 result.json"""
    replay_dir = os.path.join(data_dir, "replay")
    if not os.path.isdir(replay_dir):
        return []

    results = []
    for root, _dirs, files in os.walk(replay_dir):
        for fname in files:
            if fname == "result.json":
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    results.append(data)
                except Exception:
                    pass
    return results


def _build_html(results):
    """根据结果数据生成 Confluence Storage Format HTML

    Args:
        results: result.json 内容列表

    Returns:
        str: HTML 内容
    """
    total = len(results)
    passed = sum(1 for r in results if r.get("result") == "passed")
    failed = sum(1 for r in results if r.get("result") == "failed")
    aborted = sum(1 for r in results if r.get("result") == "aborted")
    total_duration = sum(r.get("duration_s", 0) for r in results)
    avg_duration = round(total_duration / total) if total > 0 else 0
    pass_rate = round(passed / total * 100, 1) if total > 0 else 0

    operators = set(r.get("operator", "") for r in results if r.get("operator"))

    # 按时间倒序，取最近 20 条
    sorted_results = sorted(results, key=lambda x: x.get("replay_at", x.get("started_at", "")), reverse=True)
    recent = sorted_results[:20]

    # 按用例聚合
    by_case = {}
    for r in results:
        key = r.get("jira_key", "") or r.get("case_key", "")
        if not key:
            continue
        if key not in by_case:
            by_case[key] = {"key": key, "title": r.get("case_title", key), "total": 0, "passed": 0, "failed": 0}
        by_case[key]["total"] += 1
        if r.get("result") == "passed":
            by_case[key]["passed"] += 1
        elif r.get("result") == "failed":
            by_case[key]["failed"] += 1

    update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html_parts = []

    # 汇总信息
    html_parts.append(f"""
<h2>回放统计汇总</h2>
<p><strong>更新时间：</strong>{update_time}</p>
<table>
<tbody>
<tr><th>总回放次数</th><td>{total}</td></tr>
<tr><th>通过</th><td>{passed}</td></tr>
<tr><th>失败</th><td>{failed}</td></tr>
<tr><th>中断</th><td>{aborted}</td></tr>
<tr><th>通过率</th><td>{pass_rate}%</td></tr>
<tr><th>平均时长</th><td>{avg_duration}s</td></tr>
<tr><th>活跃用户数</th><td>{len(operators)}</td></tr>
</tbody>
</table>
""")

    # 最近 20 条记录
    html_parts.append("<h2>最近回放记录（最多 20 条）</h2>")
    html_parts.append("""<table>
<thead><tr><th>时间</th><th>用例</th><th>执行人</th><th>结果</th><th>时长(s)</th><th>失败原因</th></tr></thead>
<tbody>""")
    for r in recent:
        replay_at = r.get("replay_at", r.get("started_at", ""))
        jira_key = r.get("jira_key", "") or r.get("case_key", "")
        operator = r.get("operator", "")
        result = r.get("result", "")
        duration = r.get("duration_s", 0)
        fail_reason = r.get("fail_reason", "")
        # 结果颜色
        color = "#36B37E" if result == "passed" else "#FF5630" if result == "failed" else "#FFAB00"
        html_parts.append(
            f'<tr><td>{replay_at}</td><td>{jira_key}</td><td>{operator}</td>'
            f'<td style="color:{color}"><strong>{result}</strong></td>'
            f'<td>{duration}</td><td>{fail_reason}</td></tr>'
        )
    html_parts.append("</tbody></table>")

    # 各用例统计
    html_parts.append("<h2>各用例统计</h2>")
    html_parts.append("""<table>
<thead><tr><th>用例 Key</th><th>标题</th><th>总次数</th><th>通过</th><th>失败</th><th>通过率</th></tr></thead>
<tbody>""")
    for item in sorted(by_case.values(), key=lambda x: x["total"], reverse=True):
        rate = round(item["passed"] / item["total"] * 100, 1) if item["total"] > 0 else 0
        html_parts.append(
            f'<tr><td>{item["key"]}</td><td>{item["title"]}</td>'
            f'<td>{item["total"]}</td><td>{item["passed"]}</td>'
            f'<td>{item["failed"]}</td><td>{rate}%</td></tr>'
        )
    html_parts.append("</tbody></table>")

    return "\n".join(html_parts)


def sync_to_confluence(data_dir):
    """异步同步统计数据到 Confluence 页面

    在后台线程中执行，失败不影响主流程。

    Args:
        data_dir: 数据根目录
    """
    thread = threading.Thread(target=_do_sync, args=(data_dir,), daemon=True)
    thread.start()


def _do_sync(data_dir):
    """执行实际的 Confluence 同步"""
    try:
        config = _load_confluence_config(data_dir)
        if not config:
            logger.info("Confluence 配置不完整，跳过同步")
            return

        base_url = config["confluence_url"]
        page_id = config["confluence_page_id"]
        token = config["confluence_token"]

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        # 1. 获取当前页面版本号
        get_url = f"{base_url}/rest/api/content/{page_id}?expand=version"
        try:
            resp = http_requests.get(get_url, headers=headers, timeout=30)
        except http_requests.exceptions.ConnectionError:
            logger.error("Confluence 同步失败：无法连接 %s", base_url)
            return
        except http_requests.exceptions.Timeout:
            logger.error("Confluence 同步失败：请求超时")
            return

        if resp.status_code == 401:
            logger.error("Confluence 同步失败：Token 无效，请检查 confluence_token 配置")
            return
        if resp.status_code != 200:
            logger.error("Confluence 同步失败：获取页面失败 (HTTP %d): %s", resp.status_code, resp.text[:200])
            return

        page_data = resp.json()
        current_version = page_data.get("version", {}).get("number", 0)
        page_title = page_data.get("title", "回放统计")

        # 2. 读取并聚合结果
        results = _scan_all_results(data_dir)
        html_content = _build_html(results)

        # 3. 更新页面
        put_url = f"{base_url}/rest/api/content/{page_id}"
        payload = {
            "id": page_id,
            "type": "page",
            "title": page_title,
            "version": {"number": current_version + 1},
            "body": {
                "storage": {
                    "value": html_content,
                    "representation": "storage",
                }
            },
        }

        try:
            resp = http_requests.put(put_url, headers=headers, json=payload, timeout=30)
        except http_requests.exceptions.ConnectionError:
            logger.error("Confluence 同步失败：更新页面时无法连接服务器")
            return
        except http_requests.exceptions.Timeout:
            logger.error("Confluence 同步失败：更新页面超时")
            return

        if resp.status_code == 200:
            logger.info("Confluence 同步成功（版本 %d → %d）", current_version, current_version + 1)
        else:
            logger.error("Confluence 同步失败：更新页面失败 (HTTP %d): %s", resp.status_code, resp.text[:200])

    except Exception as e:
        logger.error("Confluence 同步异常: %s", e)
