"""
统计路由
提供回放结果统计聚合 API
"""

import os
import json
import logging

from flask import Blueprint, jsonify

logger = logging.getLogger(__name__)


def _scan_results(data_dir):
    """递归扫描 replay 目录下所有 result.json 文件

    Args:
        data_dir: 数据根目录

    Returns:
        list: result.json 内容列表
    """
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
                except Exception as e:
                    logger.warning("读取 result.json 失败 %s: %s", fpath, e)
    return results


def create_stats_routes(data_dir):
    """创建统计路由蓝图

    Args:
        data_dir: 数据根目录

    Returns:
        Flask Blueprint
    """
    bp = Blueprint("tv_stats", __name__)

    # ------------------------------------------------------------------
    # GET /api/tv/stats — 获取统计数据
    # ------------------------------------------------------------------
    @bp.route("/api/tv/stats", methods=["GET"])
    def get_stats():
        results = _scan_results(data_dir)

        total_replays = len(results)
        passed = 0
        failed = 0
        aborted = 0
        total_duration = 0

        # 按用例 key 聚合
        by_case_map = {}
        # 收集所有回放记录用于 recent 排序
        recent_list = []
        # 活跃用户集合
        operators = set()

        for r in results:
            result_status = r.get("result", "")
            if result_status == "passed":
                passed += 1
            elif result_status == "failed":
                failed += 1
            elif result_status == "aborted":
                aborted += 1

            duration = r.get("duration_s", 0)
            total_duration += duration

            jira_key = r.get("jira_key", "") or r.get("case_key", "")
            operator = r.get("operator", "")
            if operator:
                operators.add(operator)

            # 聚合到 by_case
            if jira_key:
                if jira_key not in by_case_map:
                    by_case_map[jira_key] = {"jira_key": jira_key, "total": 0, "passed": 0, "failed": 0}
                by_case_map[jira_key]["total"] += 1
                if result_status == "passed":
                    by_case_map[jira_key]["passed"] += 1
                elif result_status == "failed":
                    by_case_map[jira_key]["failed"] += 1

            # 收集 recent 列表
            recent_list.append({
                "jira_key": jira_key,
                "replay_at": r.get("replay_at", r.get("started_at", "")),
                "result": result_status,
                "duration_s": duration,
                "operator": operator,
                "fail_reason": r.get("fail_reason", ""),
            })

        # 按时间倒序排序，取最近 20 条
        recent_list.sort(key=lambda x: x.get("replay_at", ""), reverse=True)
        recent = recent_list[:20]

        # by_case 列表按总次数倒序
        by_case = sorted(by_case_map.values(), key=lambda x: x["total"], reverse=True)

        avg_duration = round(total_duration / total_replays) if total_replays > 0 else 0
        pass_rate = round(passed / total_replays, 3) if total_replays > 0 else 0

        return jsonify({
            "success": True,
            "data": {
                "total_replays": total_replays,
                "passed": passed,
                "failed": failed,
                "aborted": aborted,
                "pass_rate": pass_rate,
                "avg_duration_s": avg_duration,
                "active_operators": len(operators),
                "by_case": by_case,
                "recent": recent,
            }
        })

    return bp
