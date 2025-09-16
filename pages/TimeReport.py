# pages/TimeReport.py — single-page hours report + budget check (Jira Cloud REST v3)

import io
from typing import Dict, List, Iterable

import pandas as pd
import streamlit as st

from modules.config import JIRA_URL, ADMINS  # noqa: F401
from modules.jira_v3 import JiraV3
from modules.jira_operations import (
    get_children_issues_for_report,
    get_project_keys,
    get_jira_issue_type_project_key_with_displayname,
    display_issue_summaries,
)

# ────────────────────────────────────────────────────────────────
# ⚙️  CONFIG
# ────────────────────────────────────────────────────────────────
JIRA_STATE_KEY = "jira_client"

BUDGET_FIELD_IDS = [
    "customfield_10484",   # Hypatos Budget
    "customfield_10485",   # Partner Budget
]
PARTNER_NAME_FIELD = "customfield_10312"   # Partner (single-select)

# static fallback for hidden e-mails  (safe if the file is missing/empty)
try:
    from modules.external_groups import EXTERNAL_ACCOUNT_GROUPS  # type: ignore
except Exception:
    EXTERNAL_ACCOUNT_GROUPS: Dict[str, str] = {}

# ────────────────────────────────────────────────────────────────
# 🔑  Jira client (credentials from session)
# ────────────────────────────────────────────────────────────────
for key in ("api_username", "api_password", "jira_project_key"):
    st.session_state.setdefault(key, "")

if st.session_state["api_password"]:
    client = JiraV3(JIRA_URL, st.session_state["api_username"], st.session_state["api_password"])
    st.session_state[JIRA_STATE_KEY] = client
else:
    client = None

# ────────────────────────────────────────────────────────────────
# 🗃️  Cache decorator
# ────────────────────────────────────────────────────────────────
_cache = (
    st.cache_data
    if hasattr(st, "cache_data")
    else st.cache
    if hasattr(st, "cache")
    else st.experimental_memo
)

# ------------------------------------------------------------------
# helper: extract text from dropdown/str field
# ------------------------------------------------------------------
def field_value_as_str(cf_value) -> str:
    """
    • If the field is a single-select option, return option.value.
    • If it’s a Jira JSON dict like {"value": "..."} return that value.
    • If it’s already a plain string, return it.
    • Otherwise return '' so .strip() will give ''.
    """
    if cf_value is None:
        return ""
    # JSON dict case
    if isinstance(cf_value, dict) and "value" in cf_value:
        return str(cf_value["value"])
    # python-jira object style (still safe)
    if hasattr(cf_value, "value"):
        return str(cf_value.value)
    return str(cf_value)

# ────────────────────────────────────────────────────────────────
# 🔧  domain → group helper
# ────────────────────────────────────────────────────────────────
def domain_to_group(domain: str) -> str:
    if not domain or domain == "unknown":
        return "UNKNOWN"

    parts = domain.lower().split(".")
    if len(parts) < 2:
        return domain.upper()

    sld = parts[-2]
    tbl = {
        "ey": "EY",
        "hy": "HYPATOS",
        "hypatos": "HYPATOS",
    }
    return tbl.get(sld, sld.upper())

# ────────────────────────────────────────────────────────────────
# 📥  Work-log fetcher (v3)
# ────────────────────────────────────────────────────────────────
@_cache(show_spinner=False)
def fetch_worklogs(_client: JiraV3, issue_keys: List[str]) -> pd.DataFrame:
    """
    Fetch worklogs for all given issues using REST v3:
      GET /rest/api/3/issue/{issueKey}/worklog?startAt=0&maxResults=100
    Also resolves user email (if visible) via GET /rest/api/3/user?accountId=...
    """
    import requests

    IGNORE_ACCOUNT_IDS = {
        "557058:f58131cb-b67d-43c7-b30d-6b58d40bd077",
    }

    user_cache: Dict[str, Dict] = {}

    def _user_info(acc_id: str) -> Dict:
        if acc_id in user_cache:
            return user_cache[acc_id]
        try:
            url = f"{_client.base_url}/rest/api/3/user"
            resp = requests.get(
                url,
                headers=_client._auth_header,
                params={"accountId": acc_id},
                timeout=_client.timeout,
            )
            if resp.status_code == 200:
                user_cache[acc_id] = resp.json() or {}
            else:
                user_cache[acc_id] = {}
        except Exception:
            user_cache[acc_id] = {}
        return user_cache[acc_id]

    rows: List[Dict] = []

    def _append(worklogs: List[Dict], issue_key: str):
        for wl in worklogs:
            au = wl.get("author") or {}
            account_id = au.get("accountId")
            if not account_id or account_id in IGNORE_ACCOUNT_IDS:
                continue

            # discover e-mail if visible
            email = au.get("emailAddress")
            if not email:
                email = _user_info(account_id).get("emailAddress")

            # resolve group
            if email:
                domain = email.split("@")[-1]
                group = domain_to_group(domain)
            else:
                group = EXTERNAL_ACCOUNT_GROUPS.get(account_id, "UNKNOWN")
                email = "unknown"

            started = wl.get("started")
            ts = pd.NaT
            if started:
                ts = (
                    pd.to_datetime(started, utc=True)
                    .normalize()
                    .tz_localize(None)
                )

            seconds = wl.get("timeSpentSeconds") or 0

            rows.append(
                {
                    "issue_key": issue_key,
                    "author_id": account_id,
                    "author": au.get("displayName", account_id),
                    "email": email,
                    "group": group,
                    "date": ts,
                    "hours": seconds / 3600,
                }
            )

    # loop issues & paginate worklogs
    for key in issue_keys:
        start = 0
        while True:
            url = f"{_client.base_url}/rest/api/3/issue/{key}/worklog"
            params = {"startAt": start, "maxResults": 100}
            try:
                r = requests.get(url, headers=_client._auth_header, params=params, timeout=_client.timeout)
                r.raise_for_status()
                data = r.json() or {}
            except Exception as e:
                st.warning(f"Work-logs for {key} failed: {e}")
                break

            wls = data.get("worklogs", []) or []
            if not wls:
                break

            _append(wls, key)
            start += len(wls)
            if len(wls) < 100:
                break

    return pd.DataFrame(rows)

# ────────────────────────────────────────────────────────────────
# 🚀  Page logic
# ────────────────────────────────────────────────────────────────
def app(_client: JiraV3) -> None:
    st.header("⏱️ Time Tracking Report")

    boards = get_project_keys(
        JIRA_URL,
        st.session_state["api_username"],
        st.session_state["api_password"],
    )

    with st.expander("Documentation"):
        st.markdown(
        """
        This page gives you a **single-page view** of all time logged under a Jira "Project" issue  
        and checks whether you are within the **planned budget** for that project.

        **Step-by-step guide**

        1. **Authenticate** – Make sure you are logged in with your Jira e-mail + API token (see sidebar or Authenticate page).
        2. **Pick a Jira board** – Select the board that contains the *Project* issue you want to analyse.
        3. **Select the parent "Project" issue** – This is the issue that has children (Epics, Tasks) representing your delivery scope.
        4. The app will:
           * fetch all children, sub-tasks and epic tasks;
           * download every worklog entry;
           * group logged time by user group (e.g. EY, Hypatos, …);
           * compare with the budget fields on the Project issue.
        5. Use the **filters** in the sidebar to focus on a specific date range, user group, or author.
        6. Export the filtered data as an **Excel file** using the download button.

        **Required Jira fields on the parent issue**

        | Field name          | Customfield ID | Purpose |
        | ------------------ | -------------- | ------- |
        | **Partner**        | `customfield_10312` | Links Partner Budget to the right partner |
        | **Hypatos Budget** | `customfield_10484` | Planned internal hours |
        | **Partner Budget** | `customfield_10485` | Planned partner hours |

        If any of these are missing, the **budget check** will be skipped.

        **Tip:**  
        If some users show up as `UNKNOWN`, add their `accountId → group` mapping  
        to `modules/external_groups.EXTERNAL_ACCOUNT_GROUPS` and reload the page.
        """
        )

    board_key = st.selectbox("Select Jira Board Key:", boards, index=0)
    if not board_key:
        st.stop()

    issue_types = get_jira_issue_type_project_key_with_displayname(client, board_key)
    parent_key = display_issue_summaries(issue_types)
    if not parent_key:
        st.stop()

    with st.spinner("Fetching child issues…"):
        issue_keys = get_children_issues_for_report(client, parent_key)
    if not issue_keys:
        st.warning("No children under that parent.")
        st.stop()

    with st.spinner("Gathering work-logs…"):
        df = fetch_worklogs(client, issue_keys)
    if df.empty:
        st.warning("No work-logs found.")
        st.stop()

    # ── sidebar filters ────────────────────────────────────────
    st.sidebar.header("🔎 Filters & Grouping")
    author_opts = sorted(df["author"].dropna().unique())
    sel_authors = st.sidebar.multiselect("Authors", author_opts, default=author_opts)

    group_opts = sorted(df["group"].dropna().unique())
    sel_groups = st.sidebar.multiselect("Groups", group_opts, default=group_opts)

    # Avoid errors if date is NaT
    if df["date"].notna().any():
        min_d, max_d = df["date"].min(), df["date"].max()
    else:
        min_d = max_d = pd.Timestamp.today().normalize()

    raw_start, raw_end = st.sidebar.date_input(
        "Date range",
        value=(min_d.date(), max_d.date()),
        min_value=min_d,
        max_value=max_d,
    )
    start_ts, end_ts = pd.Timestamp(raw_start), pd.Timestamp(raw_end)

    mode = st.sidebar.radio(
        "Group results by",
        ["Group only", "Group × Date", "Author × Date", "Author only"],
        index=0,
    )

    fdf = df[
        (df["group"].isin(sel_groups))
        & (df["author"].isin(sel_authors))
        & (df["date"] >= start_ts)
        & (df["date"] <= end_ts)
    ]
    if fdf.empty:
        st.info("No data after filters.")
        st.stop()

    if mode == "Group × Date":
        grouped = fdf.groupby(["group", "date"], as_index=False)["hours"].sum()
        caption = "Hours by group × date"
    elif mode == "Group only":
        grouped = fdf.groupby("group", as_index=False)["hours"].sum()
        caption = "Total hours per group"
    elif mode == "Author × Date":
        grouped = fdf.groupby(["group", "author", "date"], as_index=False)["hours"].sum()
        caption = "Hours by author × date"
    else:
        grouped = fdf.groupby(["group", "author"], as_index=False)["hours"].sum()
        caption = "Total hours per author"

    grouped["hours"] = grouped["hours"].round().astype(int)
    st.subheader(caption)
    st.dataframe(grouped, use_container_width=True)

    # ── budget check ──────────────────────────────────────────────
    st.subheader("📊 Budget status")

    budgets: Dict[str, int] = {}

    try:
        all_fields = BUDGET_FIELD_IDS + [PARTNER_NAME_FIELD]
        parent = client.get_issue(parent_key, fields=all_fields)

        # 1) fixed HYPATOS budget
        hypatos_raw = parent.get("fields", {}).get("customfield_10484")
        if hypatos_raw not in (None, ""):
            budgets["HYPATOS"] = int(float(hypatos_raw))

        # 2) dynamic partner budget (dropdown)
        partner_obj = parent.get("fields", {}).get(PARTNER_NAME_FIELD)
        partner_name = field_value_as_str(partner_obj).strip().upper()

        if partner_name:
            partner_budget_raw = parent.get("fields", {}).get("customfield_10485")
            if partner_budget_raw not in (None, ""):
                budgets[partner_name] = int(float(partner_budget_raw))

    except Exception as exc:
        st.warning(f"Could not read budgets from parent issue: {exc}")

    if not budgets:
        st.info("No budget fields on this parent issue.")
    else:
        consumed = (
            fdf.groupby("group")["hours"].sum().round().astype(int).to_dict()
        )
        for grp in sorted(set(budgets) | set(consumed)):
            spend = consumed.get(grp, 0)
            limit = budgets.get(grp)
            if limit is None:
                st.info(f"{grp}: no budget set → {spend} h")
            else:
                diff = limit - spend
                if diff >= 0:
                    st.success(f"{grp}: within budget ({spend}/{limit} h, {diff} left)")
                else:
                    st.error(f"{grp}: **{abs(diff)} h over** ({spend}/{limit} h)")

    # ── raw & export ───────────────────────────────────────────
    with st.expander("Show raw work-logs"):
        st.dataframe(fdf, use_container_width=True)

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as w:
        fdf.to_excel(w, index=False, sheet_name="Worklogs")
    buf.seek(0)
    st.download_button(
        "📥 Download filtered XLSX",
        data=buf,
        file_name=f"{parent_key}_worklogs.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ────────────────────────────────────────────────────────────────
# 🔄  Run the page
# ────────────────────────────────────────────────────────────────
if not client:
    st.warning("Please log in first.")
else:
    app(client)
