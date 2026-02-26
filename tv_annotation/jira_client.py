"""
Jira API 客户端
支持 JQL 批量导入、单条导入、重新同步等操作
"""

import logging
import requests
from urllib.parse import quote

from common.config_manager import load_jira_config

logger = logging.getLogger(__name__)


class JiraClient:
    """Jira REST API 客户端"""

    def __init__(self, data_dir):
        self.data_dir = data_dir

    def _get_config(self):
        """加载并校验 Jira 配置"""
        config = load_jira_config(self.data_dir)
        if not config:
            raise ValueError("Jira 配置未设置，请先在设置中配置 Jira 连接信息")
        if not config.get("base_url") or not config.get("authorization"):
            raise ValueError("Jira 配置不完整，需要 base_url 和 authorization")
        return config

    def _request(self, method, url, config, **kwargs):
        """发送 HTTP 请求，统一错误处理"""
        headers = {"Authorization": config["authorization"]}
        kwargs.setdefault("timeout", 30)
        try:
            resp = requests.request(method, url, headers=headers, **kwargs)
        except requests.exceptions.Timeout:
            raise RuntimeError(f"请求超时: {url}")
        except requests.exceptions.ConnectionError:
            raise RuntimeError(f"无法连接 Jira 服务器: {config['base_url']}")

        if resp.status_code == 401:
            raise RuntimeError("Jira 认证失败，请检查 authorization 配置")
        if resp.status_code == 404:
            raise RuntimeError(f"Jira 资源不存在: {url}")
        if resp.status_code >= 400:
            raise RuntimeError(f"Jira 请求失败 (HTTP {resp.status_code}): {resp.text[:200]}")

        return resp.json()

    def _fetch_steps(self, config, jira_key):
        """获取测试用例的步骤"""
        url = f"{config['base_url']}/rest/synapse/latest/public/testCase/{jira_key}/steps"
        try:
            data = self._request("GET", url, config)
            if isinstance(data, list):
                return [
                    {
                        "sequenceNumber": str(s.get("sequenceNumber", "")),
                        "step": s.get("step", ""),
                        "expectedResult": s.get("expectedResult", ""),
                        "stepData": s.get("stepData", ""),
                    }
                    for s in data
                ]
        except Exception as e:
            logger.warning("获取测试步骤失败 (%s): %s", jira_key, e)
        return []

    def _parse_issue(self, issue, config):
        """从 Jira issue JSON 提取标准化字段"""
        fields = issue.get("fields", {})
        key = issue.get("key", "")

        # 获取测试步骤
        steps = self._fetch_steps(config, key)

        reporter = fields.get("reporter")
        reporter_name = reporter.get("displayName", "") if reporter else ""

        issuetype = fields.get("issuetype")
        issuetype_name = issuetype.get("name", "") if issuetype else ""

        priority = fields.get("priority")
        priority_name = priority.get("name", "") if priority else ""

        labels = fields.get("labels", [])

        return {
            "key": key,
            "source": "jira",
            "summary": fields.get("summary", ""),
            "description": fields.get("description", "") or "",
            "issuetype": issuetype_name,
            "priority": priority_name,
            "labels": labels,
            "reporter": reporter_name,
            "created": fields.get("created", ""),
            "updated": fields.get("updated", ""),
            "customfield_10107": fields.get("customfield_10107", "") or "",
            "precondition": fields.get("customfield_10808", "") or "",
            "test_steps": steps,
        }

    def import_by_jql(self, jql, max_results=100):
        """通过 JQL 批量导入用例

        Args:
            jql: JQL 查询语句
            max_results: 最大返回数量

        Returns:
            list: 导入的用例列表
        """
        config = self._get_config()
        fields = "summary,description,issuetype,priority,labels,reporter,created,updated,customfield_10107,customfield_10808"
        url = (
            f"{config['base_url']}/rest/api/2/search"
            f"?jql={quote(jql)}&fields={fields}&maxResults={max_results}"
        )

        data = self._request("GET", url, config)
        issues = data.get("issues", [])

        cases = []
        for issue in issues:
            case = self._parse_issue(issue, config)
            cases.append(case)

        return cases

    def \
            import_by_key(self, jira_key):
        """通过 Jira Key 导入单条用例

        Args:
            jira_key: Jira 用例编号，如 PROJ-101

        Returns:
            dict: 用例数据
        """
        config = self._get_config()
        url = f"{config['base_url']}/rest/api/2/issue/{jira_key}"
        issue = self._request("GET", url, config)
        return self._parse_issue(issue, config)

    def sync_case(self, jira_key):
        """重新同步 Jira 字段（不影响本地录制数据）

        Args:
            jira_key: Jira 用例编号

        Returns:
            dict: 最新的用例字段
        """
        return self.import_by_key(jira_key)
