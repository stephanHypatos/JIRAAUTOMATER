# modules/jira_v3.py

import base64
import requests
from typing import Dict, Any, List, Optional


class JiraV3:
    def __init__(self, base_url: str, email: str, api_token: str, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        token_bytes = f"{email}:{api_token}".encode("utf-8")
        self._auth_header = {
            "Authorization": f"Basic {base64.b64encode(token_bytes).decode('utf-8')}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        self.timeout = timeout

    # -------------------- Projects --------------------

    def project_search(self, query: Optional[str] = None, start_at: int = 0, max_results: int = 50) -> Dict[str, Any]:
        """
        GET /rest/api/3/project/search
        Returns: {"self":..., "nextPage":..., "total":..., "values":[{...}]}
        """
        url = f"{self.base_url}/rest/api/3/project/search"
        params = {"startAt": start_at, "maxResults": max_results}
        if query:
            params["query"] = query
        r = requests.get(url, headers=self._auth_header, params=params, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def project_search_all(self, query: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        start = 0
        while True:
            data = self.project_search(query=query, start_at=start)
            values = data.get("values", [])
            out.extend(values)
            if limit and len(out) >= limit:
                return out[:limit]
            total = data.get("total", 0)
            start += len(values)
            if start >= total or not values:
                return out

    # -------------------- Search (new JQL endpoint) --------------------

    def search_jql(
        self,
        jql: str,
        fields: Optional[List[str]] = None,
        max_results: int = 50,
        next_page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        GET /rest/api/3/search/jql
        Note: param name is *jql*, not "query".
        Some tenants prefer POST; we fallback to POST if GET returns 400.
        """
        url = f"{self.base_url}/rest/api/3/search/jql"
        params = {"jql": jql, "maxResults": max_results}
        if fields:
            # Comma-separated is accepted for GET
            params["fields"] = ",".join(fields)
        if next_page_token:
            params["nextPageToken"] = next_page_token

        r = requests.get(url, headers=self._auth_header, params=params, timeout=self.timeout)
        if r.status_code == 400:
            # Fallback to POST variant (same path) with JSON body
            body = {"jql": jql, "maxResults": max_results}
            if fields:
                body["fields"] = fields
            if next_page_token:
                body["nextPageToken"] = next_page_token
            r = requests.post(url, headers=self._auth_header, json=body, timeout=self.timeout)

        r.raise_for_status()
        return r.json()

    def search_jql_all(self, jql: str, fields: Optional[List[str]] = None, page_size: int = 100) -> List[Dict[str, Any]]:
        issues: List[Dict[str, Any]] = []
        token: Optional[str] = None
        while True:
            data = self.search_jql(jql, fields=fields, max_results=page_size, next_page_token=token)
            issues.extend(data.get("issues", []))
            token = data.get("nextPageToken")
            if not token:
                return issues

    # -------------------- Issues (CRUD & links) --------------------

    def get_issue(self, issue_key: str, fields: Optional[List[str]] = None, expand: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        GET /rest/api/3/issue/{key}?fields=...&expand=...
        """
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}"
        params: Dict[str, str] = {}
        if fields:
            params["fields"] = ",".join(fields)
        if expand:
            params["expand"] = ",".join(expand)
        r = requests.get(url, headers=self._auth_header, params=params, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def create_issue(self, fields: Dict[str, Any]) -> Dict[str, Any]:
        """
        POST /rest/api/3/issue
        Body: {"fields": {...}}
        """
        url = f"{self.base_url}/rest/api/3/issue"
        r = requests.post(url, headers=self._auth_header, json={"fields": fields}, timeout=self.timeout)
        r.raise_for_status()
        return r.json()  # {"id": "...", "key": "...", "self": "..."}

    def update_issue_fields(self, issue_key: str, fields: Dict[str, Any]) -> None:
        """
        PUT /rest/api/3/issue/{key}
        Body: {"fields": {...}}
        """
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}"
        r = requests.put(url, headers=self._auth_header, json={"fields": fields}, timeout=self.timeout)
        r.raise_for_status()

    def assign_issue(self, issue_key: str, account_id: str) -> None:
        """
        PUT /rest/api/3/issue/{key}/assignee
        In GDPR strict mode, ONLY 'accountId' is allowed.
        """
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}/assignee"
        r = requests.put(
            url,
            headers=self._auth_header,
            json={"accountId": account_id},  # only accountId
            timeout=self.timeout,
        )
        if r.status_code not in (200, 204):
            raise RuntimeError(f"Assignment failed for {issue_key}: {r.text}")

    def get_issue_links(self, issue_key: str) -> List[Dict[str, Any]]:
        """
        Fetch issue links via fields=issuelinks
        """
        data = self.get_issue(issue_key, fields=["issuelinks"])
        return data.get("fields", {}).get("issuelinks", []) or []

    def create_issue_link(self, link_type_name: str, inward_key: str, outward_key: str) -> None:
        """
        POST /rest/api/3/issueLink
        Body: {"type":{"name":link_type_name},"inwardIssue":{"key":...},"outwardIssue":{"key":...}}
        """
        url = f"{self.base_url}/rest/api/3/issueLink"
        body = {
            "type": {"name": link_type_name},
            "inwardIssue": {"key": inward_key},
            "outwardIssue": {"key": outward_key},
        }
        r = requests.post(url, headers=self._auth_header, json=body, timeout=self.timeout)
        r.raise_for_status()

    def delete_issue(self, issue_key: str, delete_subtasks: bool = True) -> None:
        """
        DELETE /rest/api/3/issue/{issueKey}?deleteSubtasks=true
        """
        import requests
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}"
        params = {"deleteSubtasks": str(delete_subtasks).lower()}
        r = requests.delete(url, headers=self._auth_header, params=params, timeout=self.timeout)
        r.raise_for_status()

    def list_transitions(self, issue_key: str) -> list:
        """
        GET /rest/api/3/issue/{issueKey}/transitions
        Returns a list of transitions (each contains id, name, and 'to' status).
        """
        import requests
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}/transitions"
        r = requests.get(url, headers=self._auth_header, timeout=self.timeout)
        r.raise_for_status()
        return (r.json() or {}).get("transitions", []) or []


    def transition_issue(self, issue_key: str, transition_id: str) -> None:
        """
        POST /rest/api/3/issue/{issueKey}/transitions
        Body: {"transition": {"id": "..." } }
        """
        import requests
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}/transitions"
        payload = {"transition": {"id": transition_id}}
        r = requests.post(url, headers=self._auth_header, json=payload, timeout=self.timeout)
        r.raise_for_status()


    def transition_issue_by_status_name(self, issue_key: str, target_status_name: str) -> bool:
        """
        Convenience: find a transition whose target status name matches (case-insensitive)
        and perform it. Returns True if transitioned, False if not found.
        """
        transitions = self.list_transitions(issue_key)
        target = None
        for t in transitions:
            to_name = (t.get("to") or {}).get("name", "")
            if to_name.lower() == target_status_name.lower():
                target = t.get("id")
                break
        if not target:
            return False
        self.transition_issue(issue_key, target)
        return True


    # -------------------- Convenience --------------------

    def list_subtasks(self, parent_key: str) -> List[Dict[str, Any]]:
        """
        Return direct children using bounded JQL (ordered by created ASC).
        """
        jql = f'parent = "{parent_key}" ORDER BY created ASC'
        data = self.search_jql(
            jql,
            fields=["summary", "description", "issuetype", "duedate", "customfield_10015", "created"],
            max_results=100,
        )
        return data.get("issues", [])

