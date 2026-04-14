from dataclasses import dataclass

import requests

from src import config


@dataclass
class JiraIssue:
    key: str
    summary: str
    status: str
    assignee_name: str
    assignee_username: str
    priority: str
    url: str
    epic_key: str = ""
    epic_name: str = ""


class JiraClient:
    def __init__(self):
        self._base = config.JIRA_BASE_URL
        self._headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {config.JIRA_API_TOKEN}",
        }

    def _get(self, path: str, params: dict = None) -> dict:
        url = f"{self._base}/rest/api/2/{path}"
        response = requests.get(url, headers=self._headers, params=params, verify=False)
        response.raise_for_status()
        return response.json()

    def _fetch_epic_names(self, epic_keys: list[str]) -> dict[str, str]:
        """Lấy tên epic theo batch, trả về {epic_key: epic_name}."""
        if not epic_keys:
            return {}
        jql = "issueKey in (" + ",".join(epic_keys) + ")"
        data = self._get("search", params={"jql": jql, "maxResults": len(epic_keys), "fields": "summary"})
        return {item["key"]: item["fields"].get("summary", item["key"]) for item in data.get("issues", [])}

    def search_issues(self, jql: str, max_results: int = 100) -> list[JiraIssue]:
        data = self._get("search", params={
            "jql": jql,
            "maxResults": max_results,
            "fields": "summary,status,assignee,priority,customfield_10001",
        })
        issues = []
        for item in data.get("issues", []):
            fields = item["fields"]
            assignee = fields.get("assignee") or {}
            issues.append(JiraIssue(
                key=item["key"],
                summary=fields.get("summary", ""),
                status=fields["status"]["name"],
                assignee_name=assignee.get("displayName", "Chưa gán"),
                assignee_username=assignee.get("name", ""),
                priority=fields.get("priority", {}).get("name", "Medium"),
                url=f"{self._base}/browse/{item['key']}",
                epic_key=fields.get("customfield_10001") or "",
            ))

        # Fetch tên epic theo batch
        epic_keys = list({i.epic_key for i in issues if i.epic_key})
        epic_names = self._fetch_epic_names(epic_keys)
        for issue in issues:
            if issue.epic_key:
                issue.epic_name = epic_names.get(issue.epic_key, issue.epic_key)

        return issues

    def get_active_sprint_issues(self) -> list[JiraIssue]:
        jql = (
            f"project = {config.JIRA_PROJECT_KEY} "
            f"AND sprint in openSprints() "
            f"AND status NOT IN (Done, Closed, Resolved, 'Done Test')"
        )
        return self.search_issues(jql)

    def get_my_issues(self, jira_username: str) -> list[JiraIssue]:
        jql = (
            f"project = {config.JIRA_PROJECT_KEY} "
            f'AND assignee = "{jira_username}" '
            f"AND sprint in openSprints() "
            f"AND status NOT IN (Done, Closed, Resolved, 'Done Test')"
        )
        return self.search_issues(jql)
