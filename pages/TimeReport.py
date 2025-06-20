## TO do 
## add external partner account ids 
##  create documentation on how to use

# TimeReport.py  –  single-page hours report + budget check
# =========================================================
import io
from typing import Dict, List

import pandas as pd
import streamlit as st
from jira import JIRA

# ────────────────────────────────────────────────────────────────
# ⚙️  CONFIG
# ────────────────────────────────────────────────────────────────
JIRA_STATE_KEY = "jira"

from modules.config import JIRA_URL, ADMINS  # noqa: F401
from modules.jira_operations import (
    get_children_issues_for_report,
    get_project_keys,
    get_jira_issue_type_project_key_with_displayname,
    display_issue_summaries,
)


BUDGET_FIELD_IDS = [
    "customfield_10484",   # Hypatos budget (stays static) customfield_10484 called Hypatos Budget in Jira 
    "customfield_10485",   # Generic “partner budget” field called Partner Budget in Jira 
]
PARTNER_NAME_FIELD = "customfield_10312"   # drop down field  on the parent issuein Jira called Partner

# static fallback for hidden e-mails  (safe if the file is missing/empty)
try:
    from modules.external_groups import EXTERNAL_ACCOUNT_GROUPS  # type: ignore
except Exception:
    EXTERNAL_ACCOUNT_GROUPS: Dict[str, str] = {}

# ────────────────────────────────────────────────────────────────
# 🔑  Jira client
# ────────────────────────────────────────────────────────────────
for key in ("api_username", "api_password", "jira_project_key"):
    st.session_state.setdefault(key, "")

jira = JIRA(
    server=JIRA_URL,
    basic_auth=(
        st.session_state["api_username"],
        st.session_state["api_password"],
    ),
)
st.session_state[JIRA_STATE_KEY] = jira

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
        • If it’s already a plain string, return it.
        • Otherwise return '' so .strip() will give ''.
        """
        if cf_value is None:
            return ""
        # Jira option objects have a 'value' attr (and often 'id', 'self', …)
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
# 📥  Work-log fetcher  (with static-mapping fallback)
# ────────────────────────────────────────────────────────────────
@_cache(show_spinner=False)
def fetch_worklogs(_jira: JIRA, issue_keys: List[str]) -> pd.DataFrame:
    IGNORE_ACCOUNT_IDS = {
        "557058:f58131cb-b67d-43c7-b30d-6b58d40bd077",
    }

    user_cache: Dict[str, Dict] = {}

    def _user_info(acc_id: str) -> Dict:
        if acc_id in user_cache:
            return user_cache[acc_id]
        try:
            u = _jira.user(accountId=acc_id)
            user_cache[acc_id] = u.raw if hasattr(u, "raw") else {}
        except Exception:
            user_cache[acc_id] = {}
        return user_cache[acc_id]

    rows: List[Dict] = []

    def _append(wlogs, issue_key):
        for wl in wlogs:
            au = wl.author
            if not au or au.accountId in IGNORE_ACCOUNT_IDS:
                continue

            # ── try to discover e-mail ──────────────────────────
            email = getattr(au, "emailAddress", None) or \
                    getattr(getattr(au, "raw", {}), "emailAddress", None)

            if not email:
                email = _user_info(au.accountId).get("emailAddress")

            # ── resolve group ───────────────────────────────────
            if email:
                domain = email.split("@")[-1]
                group = domain_to_group(domain)
            else:
                group = EXTERNAL_ACCOUNT_GROUPS.get(au.accountId, "UNKNOWN")

                #st.write(f'WL Author ID: {au.accountId} and issue: {issue_key}')
                email = "unknown"

            rows.append(
                {
                    "issue_key": issue_key,
                    "author_id": au.accountId,
                    "author": au.displayName,
                    "email": email,
                    "group": group,
                    "date": (
                        pd.to_datetime(wl.started, utc=True)
                        .normalize()
                        .tz_localize(None)
                    ),
                    "hours": wl.timeSpentSeconds / 3600,
                }
            )

    for key in issue_keys:
        if hasattr(_jira, "issue_worklogs"):
            start = 0
            while True:
                try:
                    wls = _jira.issue_worklogs(key, startAt=start, maxResults=100)
                except Exception as e:
                    st.warning(f"Work-logs for {key} failed: {e}")
                    break
                if not wls:
                    break
                _append(wls, key)
                if len(wls) < 100:
                    break
                start += len(wls)
        else:
            try:
                _append(_jira.worklogs(key), key)
            except Exception as e:
                st.warning(f"Work-logs for {key} failed: {e}")

    return pd.DataFrame(rows)


# ────────────────────────────────────────────────────────────────
# 🚀  Page logic  (unchanged below, just shortened comments)
# ────────────────────────────────────────────────────────────────
def app(jira: JIRA) -> None:
    st.header("⏱️ Time Tracking Report")

    boards = get_project_keys(
        JIRA_URL,
        st.session_state["api_username"],
        st.session_state["api_password"],
    )
    
    with st.expander('Documentation'):
     st.markdown(
        """ 
        ### Purpose  
        This report shows **all time that has been logged** on every issue underneath a chosen *Project* parent issue, split by **group** (EY / HYPATOS / …) and by **author**.  
        It also tells you whether the work is **within the hour-budget** that was planned for the project.

        ### Jira fields that MUST be filled on the parent “Project” issue  
        | Field on the Project issue | Jira custom-field id | Why it matters |
        | -------------------------- | ------------------- | -------------- |
        | **Partner** (dropdown)     | `customfield_10312` | Tells the app *which* external partner (EY / PwC / KPMG …) the “Partner Budget” belongs to. |
        | **Hypatos Budget**         | `customfield_10484` | Planned hours for internal Hypatos work. |
        | **Partner Budget**         | `customfield_10485` | Planned hours for the partner selected above. |

        If any of these are empty, the budget check cannot run for that project.

        ### How to run the report  
        1. **Log in** with your Jira API credentials (top left of the app).  
        2. In *Time Tracking Report*  
           * pick the **Jira board** that contains your Project issue;  
           * select the **Project** issue itself.  
        3. The page will automatically  
           * fetch every child issue,  
           * download all work-logs,  
           * detect each author’s group,  
           * show totals and a green/red budget indicator.  
        4. Use the **sidebar** to filter by group, author or date, and switch between grouping modes.  
        5. Click **“Download filtered XLSX”** to export whichever slice of data you’re viewing.

        ### Missing or mis-categorised users?  
        If a user’s e-mail is hidden by Jira, add their **account ID** and desired group to  
        `modules/external_groups.EXTERNAL_ACCOUNT_GROUPS`, then refresh the page.

        """
    )
     
    board_key = st.selectbox("Select Jira Board Key:", boards, index=0)
    if not board_key:
        st.stop()

    issue_types = get_jira_issue_type_project_key_with_displayname(jira, board_key)
    parent_key = display_issue_summaries(issue_types)
    if not parent_key:
        st.stop()

    with st.spinner("Fetching child issues…"):
        issue_keys = get_children_issues_for_report(jira, parent_key)
    if not issue_keys:
        st.warning("No children under that parent.")
        st.stop()

    with st.spinner("Gathering work-logs…"):
        df = fetch_worklogs(jira, issue_keys)
    if df.empty:
        st.warning("No work-logs found.")
        st.stop()

    # ── sidebar filters ────────────────────────────────────────
    st.sidebar.header("🔎 Filters & Grouping")
    author_opts = sorted(df["author"].unique())
    sel_authors = st.sidebar.multiselect("Authors", author_opts, default=author_opts)

    group_opts = sorted(df["group"].unique())
    sel_groups = st.sidebar.multiselect("Groups", group_opts, default=group_opts)

    min_d, max_d = df["date"].min(), df["date"].max()
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
        all_fields = ",".join(BUDGET_FIELD_IDS + [PARTNER_NAME_FIELD])
        parent = jira.issue(parent_key, fields=all_fields)

        # 1) fixed HYPATOS budget
        hypatos_raw = getattr(parent.fields, "customfield_10484", None)
        if hypatos_raw not in (None, ""):
            budgets["HYPATOS"] = int(float(hypatos_raw))

        # 2) dynamic partner budget (dropdown)
        partner_obj = getattr(parent.fields, PARTNER_NAME_FIELD, None)
        partner_name = field_value_as_str(partner_obj).strip().upper()
        

        if partner_name:
            partner_budget_raw = getattr(parent.fields, "customfield_10485", None)
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
                continue
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
if st.session_state['api_password'] == '':
    st.warning("Please log in first.")
else:    
    app(st.session_state[JIRA_STATE_KEY])
