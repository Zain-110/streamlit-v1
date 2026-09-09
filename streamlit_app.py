from __future__ import annotations

from pathlib import Path
import math
import pandas as pd
import numpy as np
import streamlit as st

import app as core
from model_logic import (
    aggregate_customer_period, available_daily_dates, available_periods,
    branch_cost_to_income_breakdown, cost_activity_table, daily_branch_summary,
    daily_customer_snapshot, daily_data_freshness, daily_rm_snapshot, daily_trend,
    employee_cost_breakdown, management_action_table, score_breakdown,
    tableau_semantic_model_register, model_metric_register, period_logic_table,
    population_bridge_logic,
)
from target_store import create_target, decide_target, latest_approved, latest_approved_rm_map, rows_for_scope

st.set_page_config(
    page_title="UBL UAE | RM Cost & Performance",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE_DIR = Path(__file__).resolve().parent
LOGO = BASE_DIR / "ubl_logo.png"
DATA = core.DATA
BRANCHES = core.BRANCHES
TARGET_METRICS = core.TARGET_METRICS
TARGET_ACCESS = core.TARGET_ACCESS

NAV = [
    "Executive Overview",
    "Daily Management",
    "RM Performance",
    "RM 360",
    "Branch Performance",
    "Customer & Relationship",
    "Cost & Economics",
    "Target Management",
    "Methodology",
]

st.markdown("""
<style>
    .block-container {padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1500px;}
    [data-testid="stSidebar"] {border-right: 1px solid #dbe3e9;}
    [data-testid="stMetric"] {
        background: white;
        border: 1px solid #dbe3e9;
        border-radius: 12px;
        padding: 12px 14px;
    }
    .ubl-eyebrow {font-size:11px;letter-spacing:.12em;color:#6d9bb6;font-weight:800;text-transform:uppercase;margin-bottom:2px}
    .ubl-title {font-size:30px;font-weight:850;letter-spacing:-.035em;color:#182333;margin:4px 0 4px}
    .ubl-sub {font-size:14px;color:#667483;line-height:1.5;margin-bottom:10px}
    .ubl-note {background:#eef5f9;border:1px solid #d7e6ef;border-radius:10px;padding:12px 14px;font-size:12px;color:#33536a}
    .ubl-warn {background:#fff6e5;border:1px solid #eed8a8;border-radius:10px;padding:12px 14px;font-size:12px;color:#705519}
    .ubl-small {font-size:11px;color:#758391}
    .status-approved {display:inline-block;background:#e8f5ef;color:#1e694c;border-radius:999px;padding:3px 8px;font-size:11px;font-weight:800}
    .status-pending {display:inline-block;background:#fff4df;color:#8c620c;border-radius:999px;padding:3px 8px;font-size:11px;font-weight:800}
    .status-rejected {display:inline-block;background:#fae8e8;color:#923a3a;border-radius:999px;padding:3px 8px;font-size:11px;font-weight:800}
    .stDataFrame {border:1px solid #e0e7ec;border-radius:10px;}
</style>
""", unsafe_allow_html=True)


def money(v, ccy="USD", d=1):
    if v is None or pd.isna(v):
        return "—"
    return f"{ccy} {float(v):,.{d}f}m"

def pct(v, d=1):
    if v is None or pd.isna(v):
        return "—"
    return f"{float(v)*100:,.{d}f}%"

def number(v, d=1):
    if v is None or pd.isna(v):
        return "—"
    return f"{float(v):,.{d}f}"

def header(title, subtitle):
    st.markdown('<div class="ubl-eyebrow">UAE FINANCE · RELATIONSHIP MANAGEMENT</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="ubl-title">{title}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="ubl-sub">{subtitle}</div>', unsafe_allow_html=True)

def metrics(items):
    cols = st.columns(len(items))
    for col, (label, value, help_text) in zip(cols, items):
        col.metric(label, value, help=help_text)

def style_money_df(df, money_cols=(), pct_cols=(), integer_cols=()):
    out = df.copy()
    for c in money_cols:
        if c in out:
            out[c] = out[c].map(lambda x: money(x, "AED" if "AED" in c else "USD"))
    for c in pct_cols:
        if c in out:
            out[c] = out[c].map(pct)
    for c in integer_cols:
        if c in out:
            out[c] = out[c].map(lambda x: f"{int(x):,}" if pd.notna(x) else "—")
    return out

def eligible_rms(branch, role):
    return core.eligible_rm_names(branch, role)

def base_perf(mode, period, branch, role, rm_focus="All RMs", band="All Bands"):
    x = core.governed_perf(mode, period)
    if branch != "All UAE":
        x = x[x["Branch"].eq(branch)]
    if role != "All":
        x = x[x["Role"].eq(role)]
    if rm_focus != "All RMs":
        x = x[x["RM"].eq(rm_focus)]
    if band != "All Bands":
        x = x[x["Performance_Band"].eq(band)]
    return x.copy()

def customer_scope(mode, period, branch, role, rm_focus, segment, cohort, quality):
    x = aggregate_customer_period(mode, period, DATA).copy()
    roles = DATA.roster[["Employee_ID","Role"]].drop_duplicates()
    x = x.merge(roles, on="Employee_ID", how="left")
    if branch != "All UAE":
        x = x[x.Branch.eq(branch)]
    if role != "All":
        x = x[x.Role.eq(role)]
    if rm_focus != "All RMs":
        x = x[x.RM.eq(rm_focus)]
    if segment != "All Segments":
        x = x[x.Segment.eq(segment)]
    if cohort != "All Cohorts":
        x = x[x.Cohort.eq(cohort)]
    if quality != "All Portfolio Quality":
        x = x[x.Risk_Stage.eq(quality)]
    return x

# ---------------- Sidebar / state ----------------
if LOGO.exists():
    st.sidebar.image(str(LOGO), width=145)
st.sidebar.markdown("### UBL UAE")
st.sidebar.caption("RM Cost & Performance Management")

page = st.sidebar.radio("Navigation", NAV, label_visibility="collapsed")
st.sidebar.divider()

if page == "Daily Management":
    dates = available_daily_dates(DATA)
    date = st.sidebar.selectbox("Business date", list(reversed(dates)), index=0)
    branch = st.sidebar.selectbox("Branch", ["All UAE"] + BRANCHES)
    role = st.sidebar.selectbox("Role", ["All","RM","SRM"])
    rms = eligible_rms(branch, role)
    daily_rm = st.sidebar.selectbox("RM focus", ["All RMs"] + rms)
    segment = st.sidebar.selectbox("Customer segment", ["All Segments","Corporate","Individual"])
    cohort = st.sidebar.selectbox("Relationship cohort", ["All Cohorts","ETB","NTB"])
    quality = st.sidebar.selectbox("Portfolio quality", ["All Portfolio Quality","Stage 1","Stage 2","Stage 3"])
    movement = st.sidebar.selectbox("Movement direction", ["All Movements","Inflows","Outflows"])
    mode, period, rm_focus, band = "Quarter", available_periods("Quarter",DATA)[-1], daily_rm, "All Bands"
else:
    mode = st.sidebar.radio("View by", ["Quarter","Month"], horizontal=True)
    periods = available_periods(mode, DATA)
    period = st.sidebar.selectbox("Reporting period" if page != "Target Management" else "Target period", periods, index=len(periods)-1)
    branch = st.sidebar.selectbox("Branch", ["All UAE"] + BRANCHES)
    role = st.sidebar.selectbox("Role", ["All","RM","SRM"])
    rms = eligible_rms(branch, role)
    rm_focus = st.sidebar.selectbox("RM focus", ["All RMs"] + rms)
    date, daily_rm, movement = available_daily_dates(DATA)[-1], "All RMs", "All Movements"

    if page not in {"Target Management","Methodology"}:
        segment = st.sidebar.selectbox("Customer segment", ["All Segments","Corporate","Individual"])
        cohort = st.sidebar.selectbox("Relationship cohort", ["All Cohorts","ETB","NTB"])
        quality = st.sidebar.selectbox("Portfolio quality", ["All Portfolio Quality","Stage 1","Stage 2","Stage 3"])
        band = st.sidebar.selectbox("Performance band", ["All Bands","Exceptional","Strong","Successful","Watch","Needs Review","Ramp-up"])
    else:
        segment, cohort, quality, band = "All Segments","All Cohorts","All Portfolio Quality","All Bands"

st.sidebar.caption("RM Focus automatically cascades from the selected Branch and Role.")

# ---------------- Pages ----------------
if page == "Executive Overview":
    header("Executive Overview", "One management view of RM delivery, customer economics, Branch performance and portfolio quality.")
    perf = base_perf(mode, period, branch, role, rm_focus, band)
    cust = customer_scope(mode, period, branch, role, rm_focus, segment, cohort, quality)
    if perf.empty:
        st.warning("No RMs match the selected scope.")
    else:
        metrics([
            ("Active RMs", f"{perf.RM.nunique():,}", "RMs in the selected management scope"),
            ("R3M Avg CASA", money(perf.Current_R3M_Avg_CASA_USDm.sum()), "Latest rolling three-month average"),
            ("Advances", money(perf.Advances_AEDm.sum(),"AED"), "Attributed lending exposure"),
            ("RM Economics", money(perf.RM_Economics_AEDm.sum(),"AED",2), "Relationship contribution less direct RM cost"),
        ])
        st.subheader("Performance distribution")
        band_counts = perf.groupby("Performance_Band", dropna=False).size().rename("RMs").reset_index()
        st.bar_chart(band_counts.set_index("Performance_Band"))
        st.subheader("RM management table")
        show = perf[["RM","Role","Branch","Current_R3M_Avg_CASA_USDm","Target_R3M_CASA_USDm","R3M_Target_Attainment","Advances_AEDm","Relationship_Contribution_AEDm","RM_Economics_AEDm","Performance_Index","Performance_Band","Target_Source","Target_Version"]].copy()
        show = show.rename(columns={"Current_R3M_Avg_CASA_USDm":"R3M Avg CASA","Target_R3M_CASA_USDm":"Approved Target","R3M_Target_Attainment":"Attainment","Advances_AEDm":"Advances","Relationship_Contribution_AEDm":"Relationship Contribution","RM_Economics_AEDm":"RM Economics","Performance_Index":"Index","Performance_Band":"Band"})
        st.dataframe(style_money_df(show, ["R3M Avg CASA","Approved Target","Advances","Relationship Contribution","RM Economics"], ["Attainment"]), use_container_width=True, hide_index=True)
        if not cust.empty:
            st.subheader("Top customer relationships")
            cshow = cust.nlargest(12,"Deposits_USDm")[["Customer","CIF","RM","Branch","Segment","Cohort","Risk_Stage","Deposits_USDm","Advances_AEDm","Relationship_Contribution_AEDm"]]
            cshow = cshow.rename(columns={"Risk_Stage":"Portfolio Quality","Deposits_USDm":"PE Deposits","Advances_AEDm":"Advances","Relationship_Contribution_AEDm":"Relationship Contribution"})
            st.dataframe(style_money_df(cshow, ["PE Deposits","Advances","Relationship Contribution"]), use_container_width=True, hide_index=True)

elif page == "Daily Management":
    header("Daily Management", "Operational management signal: what changed since the previous available business date, where, and which RM/customer caused it.")
    rm_daily = daily_rm_snapshot(date, DATA)
    if branch != "All UAE": rm_daily = rm_daily[rm_daily.Branch.eq(branch)]
    if role != "All": rm_daily = rm_daily[rm_daily.Role.eq(role)]
    if daily_rm != "All RMs": rm_daily = rm_daily[rm_daily.RM.eq(daily_rm)]
    freshness = daily_data_freshness(date)
    metrics([
        ("RM-attributed PE CASA", money(rm_daily.PE_CASA_USDm.sum()), f"Business date {date}"),
        ("MTD Avg CASA", money(rm_daily.MTD_Avg_CASA_USDm.sum()), "Certified available reporting dates"),
        ("DoD movement", money(rm_daily.DoD_Change_USDm.sum()), "Current minus previous available reporting date"),
        ("Funded NTB YTD", f"{int(rm_daily.Funded_NTB_YTD.sum()):,}", "Observed funded NTB population"),
    ])
    st.caption(f"Previous available business date: {freshness.get('Previous Available Date','—')} · Publication status: {freshness.get('Status','Certified demo')}")
    trend = daily_trend(date, DATA, business_days=10, branch=None if branch=="All UAE" else branch, role=None if role=="All" else role)
    if not trend.empty:
        st.subheader("10-business-day CASA trend")
        chart_cols = [c for c in ["RM_Attributed_PE_USDm","Management_PE_USDm","MTD_Avg_CASA_USDm"] if c in trend.columns]
        if chart_cols:
            st.line_chart(trend.set_index("Reporting_Date")[chart_cols])
    st.subheader("RM / SRM daily position")
    dshow = rm_daily[["RM","Role","Branch","PE_CASA_USDm","MTD_Avg_CASA_USDm","Advances_AEDm","Funded_NTB_YTD","NTB_Run_Rate","DoD_Change_USDm","Vs_Prior_Month_End_USDm"]].copy()
    dshow = dshow.rename(columns={"PE_CASA_USDm":"PE CASA","MTD_Avg_CASA_USDm":"MTD Avg CASA","Advances_AEDm":"Advances","Funded_NTB_YTD":"Funded NTB YTD","NTB_Run_Rate":"NTB Run Rate","DoD_Change_USDm":"DoD","Vs_Prior_Month_End_USDm":"vs Prior Month End"})
    st.dataframe(style_money_df(dshow, ["PE CASA","MTD Avg CASA","Advances","DoD","vs Prior Month End"]), use_container_width=True, hide_index=True)

    cust = daily_customer_snapshot(date, DATA)
    if branch != "All UAE": cust = cust[cust.Branch.eq(branch)]
    if daily_rm != "All RMs": cust = cust[cust.RM.eq(daily_rm)]
    if segment != "All Segments": cust = cust[cust.Segment.eq(segment)]
    if cohort != "All Cohorts": cust = cust[cust.Cohort.eq(cohort)]
    if quality != "All Portfolio Quality": cust = cust[cust.Risk_Stage.eq(quality)]
    if movement == "Inflows": cust = cust[cust.Daily_Change_USDm.gt(0)]
    if movement == "Outflows": cust = cust[cust.Daily_Change_USDm.lt(0)]
    if not cust.empty:
        st.subheader("Largest customer movements")
        cshow = cust.reindex(cust.Daily_Change_USDm.abs().sort_values(ascending=False).index).head(15)
        cols = [c for c in ["Customer","CIF","RM","Branch","Segment","Cohort","Risk_Stage","PE_Deposits_USDm","Daily_Change_USDm"] if c in cshow.columns]
        st.dataframe(style_money_df(cshow[cols], [c for c in cols if "USDm" in c]), use_container_width=True, hide_index=True)

elif page == "RM Performance":
    header("RM Performance", "Month/Quarter assessment against approved targets, sustainable portfolio measures, economics and quality context.")
    perf = base_perf(mode, period, branch, role, rm_focus, band)
    if perf.empty:
        st.warning("No RMs match the selected scope.")
    else:
        metrics([
            ("RMs", f"{len(perf):,}", "Selected population"),
            ("Median performance", f"{perf.Performance_Index.median():.1f}", "Current shadow-calibration index"),
            ("R3M Avg CASA", money(perf.Current_R3M_Avg_CASA_USDm.sum()), "Sustainable balance lens"),
            ("Approved target coverage", pct(perf.Target_Status.eq("APPROVED").mean()), "RMs with approved targets"),
        ])
        show = perf[["RM","Role","Branch","Current_R3M_Avg_CASA_USDm","Target_R3M_CASA_USDm","R3M_Target_Attainment","R3M_Growth_pct","ETB_Retention","Persistent_Funded_NTB_R3M","Cost_to_Income_R3M","Top5_Concentration","Performance_Index","Performance_Band","Primary_Driver","Strength_Driver","Target_Version"]].copy()
        show.columns = ["RM","Role","Branch","R3M Avg CASA","Approved Target","Attainment","R3M Growth","ETB Retention","Persistent Funded NTB","RM C/I","Top 5 Concentration","Index","Band","Primary Driver","Strength","Target Version"]
        st.dataframe(style_money_df(show, ["R3M Avg CASA","Approved Target"], ["Attainment","R3M Growth","ETB Retention","RM C/I","Top 5 Concentration"]), use_container_width=True, hide_index=True)

elif page == "RM 360":
    header("RM 360", "One RM view connecting approved target, portfolio, relationship economics, customer drivers, direct employee cost and management actions.")
    available = eligible_rms(branch, role)
    if not available:
        st.warning("No RM exists for the selected Branch/Role.")
    else:
        default_rm = rm_focus if rm_focus != "All RMs" and rm_focus in available else available[0]
        rm = st.selectbox("Select RM for RM 360", available, index=available.index(default_rm))
        perf_all = core.governed_perf(mode, period)
        r = perf_all[perf_all.RM.eq(rm)].iloc[0]
        metrics([
            ("R3M Avg CASA", money(r.Current_R3M_Avg_CASA_USDm), "Current sustainable balance"),
            ("Approved Target", money(r.Target_R3M_CASA_USDm), f"Source: {r.Target_Source} · V{int(r.Target_Version) if pd.notna(r.Target_Version) else '—'}"),
            ("Target Attainment", pct(r.R3M_Target_Attainment), "Actual versus approved target"),
            ("RM Economics", money(r.RM_Economics_AEDm,"AED",2), "Relationship contribution less direct RM employee cost"),
        ])
        c1,c2 = st.columns(2)
        with c1:
            st.subheader("RM profile")
            st.dataframe(pd.DataFrame([{
                "RM Code": r.Employee_ID.replace("EMP-","RM-") if str(r.Employee_ID).startswith("EMP-") else r.Employee_ID,
                "RM": r.RM, "Role": r.Role, "Branch": r.Branch,
                "Joining Date": str(r.Joining_Date), "Tenure Months": int(r.Tenure_Months),
                "Manager": r.Manager, "Performance Band": r.Performance_Band
            }]), use_container_width=True, hide_index=True)
        with c2:
            st.subheader("Management actions")
            st.dataframe(management_action_table(r), use_container_width=True, hide_index=True)
        st.subheader("Score breakdown")
        st.dataframe(score_breakdown(r), use_container_width=True, hide_index=True)
        cust = aggregate_customer_period(mode, period, DATA)
        cust = cust[cust.RM.eq(rm)].sort_values("Deposits_USDm", ascending=False)
        st.subheader("Customer relationships")
        cols = ["Customer","CIF","Segment","Cohort","Risk_Stage","Deposits_USDm","Avg_Deposits_USDm","Advances_AEDm","Relationship_Contribution_AEDm","Movement_USDm"]
        st.dataframe(style_money_df(cust[cols].head(30), ["Deposits_USDm","Avg_Deposits_USDm","Advances_AEDm","Relationship_Contribution_AEDm","Movement_USDm"]), use_container_width=True, hide_index=True)
        st.subheader("Direct RM employee cost")
        ec = employee_cost_breakdown(mode, period, DATA, rm=rm)
        st.dataframe(style_money_df(ec, [c for c in ec.columns if c.endswith("_AEDm")]), use_container_width=True, hide_index=True)

elif page == "Branch Performance":
    header("Branch Performance", "Branch target, RM allocation coverage, team performance, management portfolio and fully-loaded economics.")
    perf = base_perf(mode, period, branch, role, rm_focus, band)
    bp = core.governed_branch_performance(mode, period, core.governed_perf(mode,period))
    if branch != "All UAE": bp = bp[bp.Branch.eq(branch)]
    if bp.empty:
        st.warning("No Branch matches the selected scope.")
    else:
        metrics([
            ("Branches", f"{len(bp):,}", "Selected Branch population"),
            ("Management PE", money(bp.Management_PE_USDm.sum()), "RM-attributed + BM-owned + unassigned + other management populations"),
            ("Relationship Contribution", money(bp.Relationship_Contribution_AEDm.sum(),"AED",2), "Customer economics before structural Branch OPEX"),
            ("Fully Loaded Branch Economics", money(bp.Fully_Loaded_Branch_Economics_AEDm.sum(),"AED",2), "After whole-Branch OPEX"),
        ])
        show = bp[["Branch","Active_RMs","R3M_Avg_CASA_USDm","Approved_Branch_Target_USDm","Branch_Target_Attainment","Allocated_RM_Target_USDm","Unallocated_Target_USDm","Allocation_Coverage","Branch_Cost_to_Income","Fully_Loaded_Branch_Economics_AEDm","Branch_Performance_Index","Performance_Band"]].copy()
        show.columns = ["Branch","Active RMs","R3M Avg CASA","Approved Branch Target","Target Attainment","Allocated RM Targets","Unallocated / BM","Allocation Coverage","Branch C/I","Fully Loaded Economics","Index","Band"]
        st.dataframe(style_money_df(show, ["R3M Avg CASA","Approved Branch Target","Allocated RM Targets","Unallocated / BM","Fully Loaded Economics"], ["Target Attainment","Allocation Coverage","Branch C/I"]), use_container_width=True, hide_index=True)
        st.subheader("Whole-Branch OPEX")
        ci = branch_cost_to_income_breakdown(mode, period, DATA)
        if branch != "All UAE": ci=ci[ci.Branch.eq(branch)]
        ci_show = ci[["Branch","People_Cost_AEDm","Premises_Occupancy_AEDm","Other_Operating_Support_AEDm","Total_Branch_OPEX_AEDm","Branch_Cost_to_Income"]]
        st.dataframe(style_money_df(ci_show, ["People_Cost_AEDm","Premises_Occupancy_AEDm","Other_Operating_Support_AEDm","Total_Branch_OPEX_AEDm"], ["Branch_Cost_to_Income"]), use_container_width=True, hide_index=True)

elif page == "Customer & Relationship":
    header("Customer & Relationship", "CIF-level economics and portfolio detail, traceable back to RM, account/facility and source facts.")
    cust = customer_scope(mode, period, branch, role, rm_focus, segment, cohort, quality)
    if cust.empty:
        st.warning("No customer relationships match the selected filters.")
    else:
        metrics([
            ("Relationships", f"{cust.CIF.nunique():,}", "Unique CIFs"),
            ("PE Deposits", money(cust.Deposits_USDm.sum()), "Current period-end customer deposits"),
            ("Advances", money(cust.Advances_AEDm.sum(),"AED"), "Lending exposure"),
            ("Relationship Contribution", money(cust.Relationship_Contribution_AEDm.sum(),"AED",2), "Relationship value less customer cost-to-serve"),
        ])
        cols = ["Customer","CIF","RM","Branch","Segment","Cohort","Risk_Stage","Deposits_USDm","Avg_Deposits_USDm","Advances_AEDm","Deposit_Funding_Value_AEDm","Lending_Contribution_AEDm","NFI_AEDm","Cost_to_Serve_AEDm","Relationship_Contribution_AEDm","Movement_USDm"]
        st.dataframe(style_money_df(cust[cols].sort_values("Deposits_USDm",ascending=False), [c for c in cols if c.endswith("_USDm") or c.endswith("_AEDm")]), use_container_width=True, hide_index=True)

elif page == "Cost & Economics":
    header("Cost & Economics", "Customer → RM → Branch economics, with three senior-management OPEX buckets and no double-counting of RM cost.")
    perf = base_perf(mode, period, branch, role, rm_focus, band)
    ci = branch_cost_to_income_breakdown(mode, period, DATA, core.governed_perf(mode,period))
    if branch != "All UAE": ci=ci[ci.Branch.eq(branch)]
    metrics([
        ("Relationship Value", money(ci.Relationship_Value_AEDm.sum(),"AED",2), "Total attributable customer relationship value"),
        ("People Cost", money(ci.People_Cost_AEDm.sum(),"AED",2), "All Branch employees including RMs"),
        ("Premises & Occupancy", money(ci.Premises_Occupancy_AEDm.sum(),"AED",2), "Rent/lease, utilities and physical Branch costs"),
        ("Other Operating & Support", money(ci.Other_Operating_Support_AEDm.sum(),"AED",2), "Technology, admin, operations, depreciation and approved shared support"),
    ])
    st.subheader("Whole-Branch OPEX")
    cols = ["Branch","Relationship_Value_AEDm","People_Cost_AEDm","Premises_Occupancy_AEDm","Other_Operating_Support_AEDm","Total_Branch_OPEX_AEDm","Branch_Cost_to_Income","Fully_Loaded_Branch_Economics_AEDm","Customer_CTS_Attribution_AEDm"]
    st.dataframe(style_money_df(ci[cols], [c for c in cols if c.endswith("_AEDm")], ["Branch_Cost_to_Income"]), use_container_width=True, hide_index=True)
    st.info("Customer CTS remains an attribution lens. It is not added again to whole-Branch OPEX, avoiding double counting.")
    st.subheader("RM economics")
    ecols = ["RM","Branch","Role","Relationship_Value_AEDm","Cost_to_Serve_AEDm","Relationship_Contribution_AEDm","Direct_RM_Cost_AEDm","Cost_to_Income_R3M","RM_Economics_AEDm"]
    st.dataframe(style_money_df(perf[ecols], [c for c in ecols if c.endswith("_AEDm")], ["Cost_to_Income_R3M"]), use_container_width=True, hide_index=True)
    st.subheader("Direct RM employee cost")
    ec = employee_cost_breakdown(mode, period, DATA)
    if branch != "All UAE": ec=ec[ec.Branch.eq(branch)]
    if role != "All": ec=ec[ec.Role.eq(role)]
    if rm_focus != "All RMs": ec=ec[ec.RM.eq(rm_focus)]
    st.dataframe(style_money_df(ec, [c for c in ec.columns if c.endswith("_AEDm")]), use_container_width=True, hide_index=True)
    st.subheader("Customer cost-to-serve activity attribution")
    act = cost_activity_table(mode, period, DATA, None if rm_focus=="All RMs" else rm_focus, None if branch=="All UAE" else branch)
    st.dataframe(act, use_container_width=True, hide_index=True)

elif page == "Target Management":
    access_key = st.sidebar.selectbox("Target access simulation", ["Viewer","Maker","Approver"], format_func=lambda x: TARGET_ACCESS[x])
    metric = st.sidebar.selectbox("Metric", list(TARGET_METRICS), format_func=lambda x: TARGET_METRICS[x]["name"])
    header("Target Management", "Governed Branch and RM target workflow. Only approved targets feed the performance layer; Tableau remains read-only.")
    st.markdown('<div class="ubl-note"><b>Production design:</b> Target Management writes to a product-owned target register. Maker → Pending → Checker → Approved. Tableau consumes an approved-target view only. Production access comes from UBL SSO/AD and backend authorization.</div>', unsafe_allow_html=True)

    rows = rows_for_scope(mode=mode, period=period, branch=None if branch=="All UAE" else branch, metric=metric)
    branch_latest=[]
    for br in BRANCHES:
        if branch!="All UAE" and br!=branch: continue
        rec=latest_approved(level="BRANCH",mode=mode,period=period,branch=br,metric=metric)
        if rec: branch_latest.append(rec)
    rm_map=latest_approved_rm_map(mode,period,metric)
    rm_latest=[r for r in rm_map.values() if branch=="All UAE" or r.get("Branch")==branch]
    branch_total=sum(float(r.get("TargetValue",0)) for r in branch_latest)
    rm_total=sum(float(r.get("TargetValue",0)) for r in rm_latest)
    metrics([
        ("Approved Branch Target", money(branch_total), "Latest approved Branch versions"),
        ("Approved RM Allocations", money(rm_total), "Latest approved RM versions"),
        ("Unallocated / BM", money(branch_total-rm_total if branch_total else np.nan), "Explicit residual; not forced to RM targets"),
        ("Allocation Coverage", pct(rm_total/branch_total if branch_total else np.nan), "Approved RM allocations / approved Branch target"),
    ])

    if access_key == "Maker":
        if branch == "All UAE":
            st.warning("Select a specific Branch in the sidebar before creating or revising targets.")
        else:
            ef, et = core.period_effective_dates(mode, period)
            c1,c2 = st.columns(2)
            with c1:
                st.subheader("Revise Branch target")
                current = latest_approved(level="BRANCH",mode=mode,period=period,branch=branch,metric=metric)
                current_val=float(current.get("TargetValue")) if current else 0.0
                with st.form("branch_target_form"):
                    st.text_input("Branch", branch, disabled=True)
                    st.text_input("Metric", TARGET_METRICS[metric]["name"], disabled=True)
                    value=st.number_input(f"Target value ({TARGET_METRICS[metric]['unit']})", min_value=0.0001, value=max(current_val,0.0001), step=0.1)
                    reason=st.text_area("Reason for target / revision", "Management target review")
                    submitted=st.form_submit_button("Submit Branch target for approval", use_container_width=True)
                    if submitted:
                        rec=create_target(level="BRANCH",mode=mode,period=period,branch=branch,rm="",metric=metric,
                            metric_name=TARGET_METRICS[metric]["name"],value=value,unit=TARGET_METRICS[metric]["unit"],
                            effective_from=ef,effective_to=et,created_by=TARGET_ACCESS["Maker"],reason=reason)
                        st.success(f"{rec['TargetID']} submitted. The previous approved target remains live until approval.")
                        st.rerun()
            with c2:
                st.subheader("Revise RM target")
                if rm_focus == "All RMs":
                    st.warning("Select an RM in RM Focus. The RM list is already restricted by Branch and Role.")
                else:
                    current = latest_approved(level="RM",mode=mode,period=period,branch=branch,rm=rm_focus,metric=metric)
                    current_val=float(current.get("TargetValue")) if current else 0.0
                    with st.form("rm_target_form"):
                        st.text_input("RM", rm_focus, disabled=True)
                        st.text_input("Metric", TARGET_METRICS[metric]["name"], disabled=True)
                        value=st.number_input(f"RM target value ({TARGET_METRICS[metric]['unit']})", min_value=0.0001, value=max(current_val,0.0001), step=0.1)
                        reason=st.text_area("Reason for RM target / revision", "Management target review")
                        submitted=st.form_submit_button("Submit RM target for approval", use_container_width=True)
                        if submitted:
                            rec=create_target(level="RM",mode=mode,period=period,branch=branch,rm=rm_focus,metric=metric,
                                metric_name=TARGET_METRICS[metric]["name"],value=value,unit=TARGET_METRICS[metric]["unit"],
                                effective_from=ef,effective_to=et,created_by=TARGET_ACCESS["Maker"],reason=reason)
                            st.success(f"{rec['TargetID']} submitted. It does not affect performance until approved.")
                            st.rerun()

    elif access_key == "Approver":
        pending=[r for r in rows if r.get("Status")=="PENDING_APPROVAL"]
        st.subheader("Pending approval")
        if not pending:
            st.info("No pending target revisions in the selected scope.")
        for rec in sorted(pending,key=lambda x:x.get("SubmittedAt",""),reverse=True):
            level=rec.get("TargetLevel")
            current=latest_approved(level=level,mode=mode,period=period,branch=rec.get("Branch",""),rm=rec.get("RM",""),metric=metric)
            current_val=float(current.get("TargetValue")) if current else np.nan
            with st.container(border=True):
                st.markdown(f"**{level.title()} · {rec.get('Branch')} · {rec.get('RM') or '—'}**")
                st.caption(f"Current approved: {money(current_val)} · Proposed: {money(rec.get('TargetValue'))} · V{rec.get('Version')} · Submitted by {rec.get('CreatedBy')}")
                st.write(f"Reason: {rec.get('Reason','')}")
                a,b,_=st.columns([1,1,4])
                if a.button("Approve",key="a_"+rec["TargetID"],type="primary"):
                    decide_target(rec["TargetID"],decision="APPROVED",approver=TARGET_ACCESS["Approver"])
                    st.success(f"{rec['TargetID']} approved and is now eligible for the approved-target view.")
                    st.rerun()
                if b.button("Reject",key="r_"+rec["TargetID"]):
                    decide_target(rec["TargetID"],decision="REJECTED",approver=TARGET_ACCESS["Approver"])
                    st.warning(f"{rec['TargetID']} rejected. The previous approved target remains in force.")
                    st.rerun()
    else:
        st.info("View-only access: approved targets and history are visible; no target can be created, approved or rejected.")

    st.subheader("Approved targets in scope")
    latest_rows=branch_latest + sorted(rm_latest,key=lambda r:(r.get("Branch",""),r.get("RM","")))
    if latest_rows:
        show=pd.DataFrame(latest_rows)
        cols=["TargetLevel","Branch","RM","MetricName","TargetValue","Version","EffectiveFrom","EffectiveTo","Status","ApprovedBy","ApprovalDate"]
        show=show[[c for c in cols if c in show.columns]]
        show["TargetValue"]=show["TargetValue"].map(money)
        st.dataframe(show,use_container_width=True,hide_index=True)
    else:
        st.info("No approved targets in this scope.")

    st.subheader("Target audit history")
    if rows:
        hist=pd.DataFrame(sorted(rows,key=lambda r:r.get("SubmittedAt",""),reverse=True))
        cols=["TargetLevel","Branch","RM","MetricName","TargetValue","Version","Status","CreatedBy","SubmittedAt","ApprovedBy","ApprovalDate","RejectedBy","RejectionDate","Reason"]
        hist=hist[[c for c in cols if c in hist.columns]]
        hist["TargetValue"]=hist["TargetValue"].map(money)
        st.dataframe(hist,use_container_width=True,hide_index=True)
    else:
        st.info("No target history in this scope.")

elif page == "Methodology":
    header("Methodology", "Governed model logic designed to move into Tableau without recreating formulas independently in every worksheet.")
    st.markdown("""
<div class="ubl-note">
<b>Target architecture:</b> actuals come from governed source facts. Targets come from a separate controlled maker–checker workflow.
Only <b>APPROVED</b> targets feed performance. Tableau is a read-only consumption layer and does not write to core banking systems.
</div>
""", unsafe_allow_html=True)
    st.subheader("Core principles")
    principles = [
        ["Identity","RMCode is the permanent canonical RM key."],
        ["Ownership","RM→Branch and CIF→RM are effective-dated so transfers do not look like organic growth/loss."],
        ["Daily vs Performance","Daily = operational signal; Month/Quarter/R3M = performance assessment."],
        ["Economics vs Performance","Economics informs performance but does not automatically equal performance."],
        ["Branch OPEX","People + Premises & Occupancy + Other Operating & Support."],
        ["CTS","Customer cost-to-serve is an attribution lens and is not double-counted in whole-Branch OPEX."],
        ["Targets","Maker → Pending → Approver → Approved; revisions are versioned, never overwritten."],
        ["Production Tableau","Governed data layer → approved metric/rule layer → Tableau; Tableau service account should be read-only."],
    ]
    st.dataframe(pd.DataFrame(principles,columns=["Area","Rule"]),use_container_width=True,hide_index=True)

    st.subheader("Metric register")
    st.dataframe(model_metric_register(),use_container_width=True,hide_index=True)
    st.subheader("Tableau logical model")
    st.dataframe(tableau_semantic_model_register(),use_container_width=True,hide_index=True)
    st.subheader("Period logic")
    st.dataframe(period_logic_table(),use_container_width=True,hide_index=True)
    st.subheader("Population bridge")
    st.dataframe(population_bridge_logic(),use_container_width=True,hide_index=True)

st.divider()
st.caption("Illustrative management data shown for product demonstration. Production implementation requires UBL-approved data sources, security, target workflow, DQ controls, reconciliation and Tableau deployment.")
