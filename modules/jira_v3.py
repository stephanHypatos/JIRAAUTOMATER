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

    # --- Projects ---
    def project_search(self, query: Optional[str] = None, start_at: int = 0, max_results: int = 50) -> Dict[str, Any]:
        """
        GET /rest/api/3/project/search
        Returns: {"self":..., "nextPage":..., "total":..., "values":[{project...}, ...]}
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

    # --- Search (new JQL endpoint) ---
    def search_jql(self, jql: str, fields: Optional[List[str]] = None, max_results: int = 50, next_page_token: Optional[str] = None) -> Dict[str, Any]:
        """
        GET /rest/api/3/search/jql
        Notes: New endpoint may return nextPageToken rather than startAt/total.
        """
        url = f"{self.base_url}/rest/api/3/search/jql"
        params = {"query": jql, "maxResults": max_results}
        if fields:
            params["fields"] = ",".join(fields)
        if next_page_token:
            params["nextPageToken"] = next_page_token
        r = requests.get(url, headers=self._auth_header, params=params, timeout=self.timeout)
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
