# confluence_native.py
import json
import time
from typing import Dict, List, Optional, Any, Union
import requests
import streamlit as st
from bs4 import BeautifulSoup

from modules.config import HP_ID_TCUS_SPACE  

# ---------- Low-level native Confluence client (v1 + v2 mix for ADF) ----------

class ConfluenceAPI:
    """
    Minimal native Confluence client using REST APIs.
    - Auto-detects and handles both Storage (legacy) and ADF/atlas_doc_format (new editor).
    - Uses v1 endpoints for most operations; v2 for ADF create/update (Cloud).
    """

    def __init__(self, base_url: str, email: str, api_token: str, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.v1 = f"{self.base_url}/rest/api"
        # The Cloud “wiki/api/v2” base usually lives at <base>/api/v2 or <base>/wiki/api/v2 depending on your site URL.
        # For Atlassian Cloud with /wiki in the base_url, /api/v2 (without /rest) is correct:
        # e.g. https://example.atlassian.net/wiki/api/v2
        if self.base_url.endswith("/wiki"):
            self.v2 = f"{self.base_url}/api/v2"
        else:
            # Fallback (rare) - try plain api/v2
            self.v2 = f"{self.base_url}/api/v2"

        self.auth = (email, api_token)
        self.timeout = timeout
        self.session = requests.Session()
        self.session.auth = self.auth
        self.session.headers.update({"Accept": "application/json"})

    # ---------- Core helpers ----------

    def _get(self, url: str, params: Optional[Dict[str, Any]] = None):
        r = self.session.get(url, params=params, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def _post(self, url: str, json_body: Dict[str, Any]):
        r = self.session.post(url, json=json_body, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def _put(self, url: str, json_body: Dict[str, Any]):
        r = self.session.put(url, json=json_body, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    # ---------- Read page with both body types ----------

    def get_page_by_id(self, page_id: str) -> Dict[str, Any]:
        """
        Fetch the page and try to include BOTH storage and ADF if available.
        """
        url = f"{self.v1}/content/{page_id}"
        params = {
            "expand": "body.storage,body.atlas_doc_format,version,space,ancestors"
        }
        return self._get(url, params=params)

    # ---------- Create/update (storage vs ADF aware) ----------

    def create_page_storage(self, space_key: str, title: str, storage_html: str, parent_id: Optional[str] = None):
        url = f"{self.v1}/content"
        body = {
            "type": "page",
            "title": title,
            "space": {"key": space_key},
            "body": {
                "storage": {
                    "value": storage_html,
                    "representation": "storage"
                }
            }
        }
        if parent_id:
            body["ancestors"] = [{"id": str(parent_id)}]
        return self._post(url, body)

    def update_page_storage(self, page_id: str, title: str, storage_html: str, version_number: int):
        url = f"{self.v1}/content/{page_id}"
        body = {
            "id": str(page_id),
            "type": "page",
            "title": title,
            "version": {"number": version_number + 1},
            "body": {
                "storage": {
                    "value": storage_html,
                    "representation": "storage"
                }
            }
        }
        return self._put(url, body)

    def create_page_adf(
        self,
        space_id: str,
        title: str,
        adf_doc: Dict[str, Any],
        parent_id: Optional[str] = None,
        subtype: Optional[str] = "live",   # <- default to Live Doc
        status: Optional[str] = None,
    ):
        url = f"{self.v2}/pages"
        payload = {
            "title": title,
            "spaceId": str(space_id),
            "body": {"representation": "atlas_doc_format", "value": adf_doc},
        }
        if parent_id:
            payload["parentId"] = str(parent_id)
        if subtype:
            payload["subtype"] = subtype          # <- this is the key bit
        if status:
            payload["status"] = status
        return self._post(url, payload)

    def update_page_adf(self, page_id: str, title: str, adf_doc: Dict[str, Any], version_number: int):
        url = f"{self.v2}/pages/{page_id}"
        payload = {
            "id": str(page_id),
            "title": title,
            "version": {"number": version_number + 1},
            "body": {
                "representation": "atlas_doc_format",
                "value": adf_doc
            }
        }
        return self._put(url, payload)

    # ---------- Body conversions (Cloud) ----------

    def convert_storage_to_adf(self, storage_html: str) -> Dict[str, Any]:
        """
        Cloud: convert storage HTML to ADF.
        """
        url = f"{self.v1}/contentbody/convert/atlas_doc_format"
        return self._post(url, {"value": storage_html, "representation": "storage"})

    def convert_adf_to_storage(self, adf_doc: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.v1}/contentbody/convert/storage"
        return self._post(url, {"value": adf_doc, "representation": "atlas_doc_format"})

    # ---------- Spaces & pages listing ----------

    def get_space(self, space_key: str, expand: str = "homepage"):
        url = f"{self.v1}/space/{space_key}"
        return self._get(url, params={"expand": expand})

    def get_all_spaces(self, limit: int = 50) -> Dict[str, Any]:
        url = f"{self.v1}/space"
        start = 0
        results: List[Any] = []
        while True:
            data = self._get(url, params={"limit": limit, "start": start})
            results.extend(data.get("results", []))
            if data.get("_links", {}).get("next"):
                start += limit
            else:
                break
        return {"results": results}

    def create_space(self, space_key: str, space_name: str):
        url = f"{self.v1}/space"
        return self._post(url, {"key": space_key, "name": space_name})

    def get_all_pages_from_space(self, space_key: str, limit: int = 50) -> List[Dict[str, Any]]:
        url = f"{self.v1}/content"
        start = 0
        pages: List[Dict[str, Any]] = []
        while True:
            data = self._get(url, params={"spaceKey": space_key, "limit": limit, "start": start, "type": "page"})
            pages.extend(data.get("results", []))
            if data.get("_links", {}).get("next"):
                start += limit
            else:
                break
        return pages

    def get_child_pages(self, parent_page_id: str) -> List[Dict[str, Any]]:
        url = f"{self.v1}/content/{parent_page_id}/child/page"
        pages: List[Dict[str, Any]] = []
        start = 0
        limit = 50
        while True:
            data = self._get(url, params={"limit": limit, "start": start})
            pages.extend(data.get("results", []))
            if data.get("_links", {}).get("next"):
                start += limit
            else:
                break
        return pages

    # ---------- Utilities ----------

    def get_space_id(self, space_key: str) -> Optional[str]:
        # v2 first
        try:
            data = self._get(f"{self.v2}/spaces", params={"keys": space_key, "limit": 1})
            results = data.get("results") or data.get("data") or []
            if results:
                return str(results[0].get("id"))
        except requests.HTTPError:
            pass
        # v1 fallback (sometimes includes id)
        try:
            sp = self.get_space(space_key)
            if "id" in sp:
                return str(sp["id"])
        except Exception:
            pass
        return None


    def page_exists(self, space_key: str, page_title: str) -> bool:
        pages = self.get_all_pages_from_space(space_key)
        for p in pages:
            if p.get("title") == page_title:
                return True
        return False


# ---------- ADF utilities ----------

def adf_replace(doc: Any, replacements: Dict[str, str]) -> Any:
    """
    Recursively replace placeholder substrings in all string nodes of an ADF document.
    """
    if isinstance(doc, dict):
        return {k: adf_replace(v, replacements) for k, v in doc.items()}
    if isinstance(doc, list):
        return [adf_replace(x, replacements) for x in doc]
    if isinstance(doc, str):
        s = doc
        for k, v in replacements.items():
            if k in s:
                s = s.replace(k, v)
        return s
    return doc


# ---------- Streamlit helper functions (rewritten to use native API) ----------

def add_row_to_confluence_table(api: ConfluenceAPI, page_id: str, table_index: int, row_data: List[str]):
    """
    Adds a new row to a Storage-format table. If the page is ADF, we currently raise
    a gentle error (ADF tables require ADF ops).
    """
    page = api.get_page_by_id(page_id)
    version = page["version"]["number"]
    title = page["title"]

    storage = page.get("body", {}).get("storage", {})
    storage_html = storage.get("value")

    adf = page.get("body", {}).get("atlas_doc_format", {})

    if adf and not storage_html:
        st.error("This page uses the live editor (ADF). Table row insertion via Storage HTML is not supported here.")
        return

    if not storage_html:
        raise Exception("No storage body found on the page (cannot modify table HTML).")

    soup = BeautifulSoup(storage_html, "html.parser")
    tables = soup.find_all("table")
    if len(tables) <= table_index:
        raise Exception(f"Table at index {table_index} not found.")

    table = tables[table_index]
    new_row = soup.new_tag("tr")
    for cell in row_data:
        td = soup.new_tag("td")
        td.string = cell
        new_row.append(td)
    table.append(new_row)

    updated = api.update_page_storage(page_id=page_id, title=title, storage_html=str(soup), version_number=version)
    st.write("Added new row to customer's table.")
    return updated


def get_existing_space_keys(api: ConfluenceAPI):
    try:
        spaces = api.get_all_spaces()
        return [s["key"] for s in spaces.get("results", [])]
    except Exception as e:
        st.error(f"Error getting existing space keys: {e}")


def create_new_space(api: ConfluenceAPI, space_name: str, space_key: str):
    return api.create_space(space_key, space_name)


def page_exists(api: ConfluenceAPI, space_key: str, page_title: str) -> bool:
    return api.page_exists(space_key, page_title)


def get_child_pages(api: ConfluenceAPI, parent_page_id: str):
    return api.get_child_pages(parent_page_id)


def _read_page_body(api: ConfluenceAPI, page_id: str):
    """
    Returns a tuple: (format, body, version, title, spaceKey, spaceId, ancestors)
    format: "adf" or "storage"
    body:   dict (adf) or str (storage)
    """
    page = api.get_page_by_id(page_id)
    version = page["version"]["number"]
    title = page["title"]
    space_key = page.get("space", {}).get("key")
    space_id = page.get("space", {}).get("id")  # Cloud often provides this
    ancestors = page.get("ancestors", [])

    adf = page.get("body", {}).get("atlas_doc_format", {})
    storage = page.get("body", {}).get("storage", {})

    if adf and "value" in adf:
        return "adf", adf["value"], version, title, space_key, str(space_id) if space_id else None, ancestors

    if storage and "value" in storage:
        return "storage", storage["value"], version, title, space_key, str(space_id) if space_id else None, ancestors

    # Last ditch: try converting if only one exists as empty
    if storage and not storage.get("value"):
        # maybe convert ADF -> storage?
        if adf and "value" in adf:
            conv = api.convert_adf_to_storage(adf["value"])
            return "storage", conv.get("value", ""), version, title, space_key, str(space_id) if space_id else None, ancestors

    raise Exception("Could not read page body in storage or atlas_doc_format.")


def _create_child_page_like(
    api: "ConfluenceAPI",
    source_format: str,
    source_body: Union[Dict[str, Any], str],
    target_space_key: str,
    target_space_id: Optional[str],
    title: str,
    parent_id: Optional[str],
):
    if not target_space_id:
        target_space_id = api.get_space_id(target_space_key)

    # ensure ADF body
    if source_format == "adf":
        adf_body = source_body
    else:
        adf_body = api.convert_storage_to_adf(source_body).get("value")

    if not target_space_id or not adf_body:
        raise RuntimeError("Missing spaceId or ADF body for Live Doc creation.")

    # Explicitly create as Live Doc
    return api.create_page_adf(
        space_id=target_space_id,
        title=title,
        adf_doc=adf_body,
        parent_id=parent_id,
        subtype="live",
    )

def copy_child_pages(api: ConfluenceAPI, source_page_id: str, target_space_key: str,
                     target_parent_id: Optional[str] = None, project_type_key: str = "default"):
    try:
        child_pages = get_child_pages(api, source_page_id)
        for child in child_pages:
            child_id = child["id"]

            fmt, body, _, title, _, _, _ = _read_page_body(api, child_id)

            # Placeholder replacements
            replacements = {
                "[*CUS*]": f"[{target_space_key}]",
                "[*PROJECTTYPE*]": project_type_key
            }
            new_title = title
            for k, v in replacements.items():
                if k in new_title:
                    new_title = new_title.replace(k, v)

            if page_exists(api, target_space_key, new_title):
                st.warning(f"Page '{new_title}' already exists in space '{target_space_key}'. Skipping.")
                continue

            # Apply replacements inside body
            new_body = body
            if fmt == "adf":
                new_body = adf_replace(body, replacements)
            else:
                # storage: simple string replace
                for k, v in replacements.items():
                    if k in new_body:
                        new_body = new_body.replace(k, v)

            # Need spaceId for ADF create; try to resolve
            target_space_id = api.get_space_id(target_space_key)

            try:
                created = _create_child_page_like(
                    api,
                    source_format=fmt,
                    source_body=new_body,
                    target_space_key=target_space_key,
                    target_space_id=target_space_id,
                    title=new_title,
                    parent_id=target_parent_id
                )
                st.success(f"Created page: '{new_title}' in space '{target_space_key}'.")
                # Recurse to copy grandchildren
                copy_child_pages(api, child_id, target_space_key, created.get("id"), project_type_key=project_type_key)

            except Exception as e:
                st.error(f"Error creating page '{new_title}': {e}")
                continue

    except Exception as e:
        st.error(f"Error copying pages: {e}")


def copy_pages_from_space(api: ConfluenceAPI, source_space_key: str, target_space_key: str,
                          project_type_key: str, copyflag: str = "space"):
    try:
        sp = api.get_space(source_space_key, expand="homepage")
        home_page_id = sp["homepage"]["id"]

        if copyflag == "project":
            home_page_id = HP_ID_TCUS_SPACE

        copy_child_pages(api, home_page_id, target_space_key, project_type_key=project_type_key)
        st.success(f"All template pages for project type: {project_type_key} copied to the space: {target_space_key}", icon="✅")
    except Exception as e:
        st.error(f"Error copying pages from space: {e}")


# ---------------- Example Streamlit usage (in your app page) ----------------
def get_api_from_secrets() -> ConfluenceAPI:
    base = st.secrets["confluence_base_url"]
    email = st.secrets["confluence_email"]
    token = st.secrets["confluence_api_token"]
    return ConfluenceAPI(base_url=base, email=email, api_token=token)