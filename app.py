from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlparse
from pathlib import Path
from html import escape
import mimetypes
import math
import json

import numpy as np
import pandas as pd

from model_data import (
    AS_OF_DATE, BRANCHES, TEAM_NAMES, BRANCH_SCORE_WEIGHTS, SCORE_CAP, account_rows, build_demo_data,
    facility_rows, trade_rows,
)
from model_logic import (
    aggregate_customer_period, aggregate_rm_period, apply_approved_rm_targets, available_daily_dates,
    available_periods, branch_performance, branch_population_bridge, branch_cost_to_income_breakdown,
    cost_activity_table, daily_branch_summary, daily_customer_snapshot,
    daily_data_freshness, daily_rm_snapshot, daily_trend, employee_cost_breakdown, management_action_table,
    model_metric_register, performance_band, period_end, period_logic_table,
    population_bridge_logic, score_breakdown, target_basis, tableau_semantic_model_register, trend_by_period,
    workforce_summary,
)
from target_store import (
    create_target, decide_target, latest_approved, latest_approved_rm_map,
    load_targets, rows_for_scope,
)

BASE_DIR = Path(__file__).resolve().parent
LOGO_PATH = BASE_DIR / "ubl_logo.png"
DATA = build_demo_data()
RM_FILTER_META = {str(r.RM): {"branch": str(r.Branch), "role": str(r.Role)} for _, r in DATA.roster.iterrows()}
PORT = 8501

TARGET_METRICS = {
    "R3M_CASA": {"name": "R3M Average CASA", "unit": "USDm"},
}
TARGET_ACCESS = {
    "Viewer": "Management Viewer",
    "Maker": "Finance Target Maker",
    "Approver": "Finance Target Approver",
}

NAV = [
    ("Executive Overview", "executive"),
    ("Daily Management", "daily"),
    ("RM Performance", "rm-performance"),
    ("RM 360", "rm360"),
    ("Branch Performance", "branch"),
    ("Customer & Relationship", "customer"),
    ("Cost & Economics", "cost"),
    ("Target Management", "targets"),
    ("Methodology", "methodology"),
]

CSS = r"""
:root{--ubl:#0b7fc1;--ubl-dark:#063b63;--ink:#17212b;--muted:#667483;--bg:#f4f6f8;--white:#fff;--line:#dbe3e9;--good:#247a57;--strong:#187a5f;--watch:#b57c10;--bad:#a74747;--soft:#eef4f8;--teal:#24786e}
*{box-sizing:border-box}body{margin:0;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;background:var(--bg);color:var(--ink)}a{color:inherit;text-decoration:none}.app{display:grid;grid-template-columns:290px 1fr;min-height:100vh}.sidebar{background:#fff;border-right:1px solid var(--line);padding:28px 22px;position:sticky;top:0;height:100vh;overflow:auto}.logo{width:145px;max-height:100px;object-fit:contain;display:block;margin:0 0 16px}.brand{font-weight:800;color:var(--ubl-dark);font-size:18px}.product{color:#7b858f;margin:18px 0 24px;font-size:15px}.nav{display:flex;flex-direction:column;gap:4px}.nav a{padding:9px 10px;border-radius:8px;font-size:14px;color:#273442}.nav a.active{background:#eaf4fa;color:var(--ubl-dark);font-weight:750;border-left:3px solid var(--ubl)}.divider{border:0;border-top:1px solid var(--line);margin:25px 0}.filter label{display:block;color:#4d5c6a;font-size:12px;font-weight:700;margin:14px 0 6px}.filter select{width:100%;padding:10px 11px;border:1px solid #cfd9e1;border-radius:8px;background:#fff;color:#28333d;font-size:14px;cursor:pointer;transition:border-color .15s ease,box-shadow .15s ease}.filter select:focus{outline:none;border-color:#75afd0;box-shadow:0 0 0 3px rgba(11,127,193,.10)}.filter button{width:100%;margin-top:16px;padding:10px;border:0;border-radius:8px;background:var(--ubl-dark);color:#fff;font-weight:750;cursor:pointer}.filter-hint{font-size:10px;line-height:1.45;color:#86939e;margin-top:6px}.filter-status{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-top:8px;font-size:10px;color:#6d7b87}.filter-status a{color:#075f93;font-weight:750}.filter-status a:hover{text-decoration:underline}.filter-group{margin-top:18px;padding-top:14px;border-top:1px solid #edf1f4}.filter-group:first-of-type{margin-top:0;padding-top:0;border-top:0}.filter-group-title{font-size:9px;letter-spacing:.10em;text-transform:uppercase;color:#8a98a5;font-weight:850;margin:0 0 4px}.filter-reset{display:block;text-align:center;margin-top:9px;font-size:10px;color:#6f7e89}.filter-reset:hover{color:#075f93;text-decoration:underline}.main{padding:34px 42px 60px;min-width:0}.eyebrow{font-size:11px;letter-spacing:.12em;color:#90b9d0;font-weight:800;text-transform:uppercase}.title{font-size:30px;font-weight:850;letter-spacing:-.035em;color:#182333;margin:8px 0 10px}.subtitle{max-width:1150px;color:#637180;line-height:1.55;font-size:14px;margin-bottom:18px}.pill{display:inline-flex;gap:6px;align-items:center;border:1px solid #d6e2ea;background:#fff;border-radius:999px;padding:5px 9px;font-size:11px;color:#536270;margin:0 6px 8px 0}.section{margin-top:25px}.section h2{font-size:18px;color:var(--ubl-dark);margin:0 0 5px}.section p.note{font-size:12px;color:#70808e;margin:0 0 12px;line-height:1.45}.cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}.card{background:#fff;border:1px solid var(--line);border-radius:13px;padding:14px 15px;min-height:105px;box-shadow:0 3px 10px rgba(21,49,71,.025)}.card .k{font-size:10px;color:#61717f;text-transform:uppercase;letter-spacing:.075em}.card .v{font-size:23px;font-weight:850;color:var(--ubl-dark);margin-top:10px;line-height:1.06}.card .s{font-size:11px;color:#758391;margin-top:8px;line-height:1.35}.grid2{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(340px,.8fr);gap:20px}.panel{background:#fff;border:1px solid var(--line);border-radius:12px;padding:15px;overflow:hidden}.panel h3{font-size:15px;color:var(--ubl-dark);margin:0 0 4px}.panel .panel-note{color:#758391;font-size:11px;margin-bottom:10px}.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:11px;background:#fff}.tbl{width:100%;border-collapse:separate;border-spacing:0;font-size:12px;white-space:nowrap}.tbl th{position:sticky;top:0;background:#f7f9fb;color:#5f6d7a;text-align:left;font-weight:700;padding:10px;border-bottom:1px solid var(--line);z-index:1}.tbl td{padding:9px 10px;border-bottom:1px solid #e8edf1;color:#263441;vertical-align:top}.tbl tr:last-child td{border-bottom:0}.tbl tr:hover td{background:#f8fbfd}.link{color:#075f93;font-weight:750}.num{text-align:right;font-variant-numeric:tabular-nums}.chip{display:inline-block;padding:4px 7px;border-radius:999px;font-weight:750;font-size:10px}.chip.Exceptional,.chip.Strong{background:#e8f5ef;color:#1e694c}.chip.Successful{background:#eaf4fa;color:#0b5f8d}.chip.Watch{background:#fff4df;color:#8c620c}.chip.Needs-Review{background:#fae8e8;color:#923a3a}.chip.Ramp-up{background:#f0eef8;color:#65558a}.pos{color:var(--good);font-weight:700}.neg{color:var(--bad);font-weight:700}.muted{color:#788692}.info{background:#eef5f9;border:1px solid #d7e6ef;color:#33536a;border-radius:10px;padding:12px 14px;font-size:12px;line-height:1.55}.scope-note{margin:4px 0 14px;color:#657583;font-size:11px;line-height:1.45}.warn{background:#fff6e5;border:1px solid #eed8a8;color:#705519;border-radius:10px;padding:12px 14px;font-size:12px;line-height:1.55}.kv{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;background:#fff;border:1px solid var(--line);padding:14px;border-radius:12px}.kv .item{border-top:1px solid #e6ebef;padding-top:8px}.kv .kk{font-size:9px;color:#778694;text-transform:uppercase;letter-spacing:.07em}.kv .vv{font-size:13px;font-weight:750;color:#243441;margin-top:4px}.tabs{display:flex;gap:18px;border-bottom:1px solid var(--line);margin:16px 0}.tabs a{font-size:13px;padding:9px 0;border-bottom:2px solid transparent}.tabs a.active{color:var(--ubl);border-bottom-color:var(--ubl);font-weight:800}.actions{display:grid;grid-template-columns:55px 1fr 160px 100px;gap:0;border:1px solid var(--line);border-radius:10px;overflow:hidden;background:#fff}.actions div{padding:9px;border-bottom:1px solid #e8edf1;font-size:12px}.actions .head{background:#f7f9fb;color:#5d6b77;font-weight:800}.small{font-size:11px;color:#72808d}.footer{font-size:10px;color:#81909d;margin-top:30px;line-height:1.5}.svg-wrap{width:100%;overflow:hidden}.empty{padding:18px;color:#73808c;background:#f8fafb;border:1px dashed #d3dce3;border-radius:10px;font-size:12px}.method-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.formula{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:#f5f8fa;border:1px solid #dfe6eb;border-radius:8px;padding:10px;font-size:11px;color:#2c4050;white-space:normal}.loading-toast{position:fixed;top:18px;left:50%;z-index:9999;display:flex;align-items:center;gap:10px;padding:11px 16px;border-radius:11px;background:#073b61;color:#fff;box-shadow:0 10px 28px rgba(6,59,99,.23);font-size:12px;font-weight:700;letter-spacing:.01em;opacity:0;pointer-events:none;transform:translate(-50%,-18px);transition:opacity .18s ease,transform .18s ease}.loading-toast.show{opacity:1;transform:translate(-50%,0)}.loading-spinner{width:16px;height:16px;border:2px solid rgba(255,255,255,.35);border-top-color:#fff;border-radius:50%;animation:ublspin .72s linear infinite}@keyframes ublspin{to{transform:rotate(360deg)}}.loading-sub{font-size:10px;font-weight:500;color:#cce4f2;margin-top:1px}.loading-copy{display:flex;flex-direction:column;line-height:1.15}
.filter-check{position:fixed;top:72px;right:28px;z-index:9998;width:min(430px,calc(100vw - 32px));background:#fff;border:1px solid #d7e2e9;border-top:3px solid var(--ubl);border-radius:12px;box-shadow:0 16px 42px rgba(20,48,68,.18);padding:14px 15px;opacity:0;pointer-events:none;transform:translateY(-10px);transition:opacity .16s ease,transform .16s ease}.filter-check.show{opacity:1;pointer-events:auto;transform:translateY(0)}.filter-check-kicker{font-size:9px;letter-spacing:.11em;text-transform:uppercase;color:#7b93a5;font-weight:850}.filter-check-title{font-size:14px;color:var(--ubl-dark);font-weight:850;margin-top:4px}.filter-check-copy{font-size:11px;line-height:1.5;color:#566775;margin-top:6px}.filter-check-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}.filter-check-actions button{border:1px solid #ccd9e2;background:#fff;color:#24465d;border-radius:8px;padding:8px 10px;font-size:10px;font-weight:800;cursor:pointer}.filter-check-actions button.primary{background:var(--ubl-dark);border-color:var(--ubl-dark);color:#fff}.filter-check-actions button:hover{box-shadow:0 2px 8px rgba(20,48,68,.08)}
.target-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.target-form{background:#fff;border:1px solid var(--line);border-radius:12px;padding:16px}.target-form label{display:block;font-size:11px;font-weight:750;color:#536575;margin:10px 0 5px}.target-form input,.target-form select,.target-form textarea{width:100%;border:1px solid #ccd8e1;border-radius:8px;padding:9px 10px;font:inherit;font-size:12px;color:#243441;background:#fff}.target-form textarea{min-height:72px;resize:vertical}.target-form button,.action-btn{border:0;border-radius:8px;padding:9px 12px;background:var(--ubl-dark);color:#fff;font-weight:800;font-size:11px;cursor:pointer}.action-btn.reject{background:#fff;color:#8b3535;border:1px solid #ddbcbc}.status{display:inline-flex;padding:4px 8px;border-radius:999px;font-size:10px;font-weight:800}.status.APPROVED{background:#e8f5ef;color:#1e694c}.status.PENDING_APPROVAL{background:#fff4df;color:#8c620c}.status.REJECTED{background:#fae8e8;color:#923a3a}.access-box{background:#f7fafc;border:1px solid #dbe5eb;border-radius:10px;padding:11px 12px;font-size:11px;line-height:1.5;color:#526473}.mini-metric{display:grid;grid-template-columns:1fr auto;gap:8px;padding:8px 0;border-bottom:1px solid #e8edf1;font-size:12px}.mini-metric:last-child{border-bottom:0}.approval-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;align-items:center;padding:12px 0;border-bottom:1px solid #e8edf1}.approval-row:last-child{border-bottom:0}.approval-actions{display:flex;gap:7px}.target-muted{font-size:10px;color:#7c8994;margin-top:4px}.target-strong{font-weight:800;color:var(--ubl-dark)}
@media(max-width:1200px){.cards{grid-template-columns:repeat(2,minmax(0,1fr))}.grid2{grid-template-columns:1fr}.kv{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(max-width:820px){.target-grid{grid-template-columns:1fr}.app{grid-template-columns:1fr}.sidebar{position:relative;height:auto;border-right:0;border-bottom:1px solid var(--line)}.main{padding:24px 18px}.cards{grid-template-columns:1fr}.kv{grid-template-columns:1fr 1fr}.method-grid{grid-template-columns:1fr}}
"""


def fmt_money(v, ccy="USD", d=1):
    if v is None or (isinstance(v,float) and math.isnan(v)):
        return "—"
    return f"{ccy} {float(v):,.{d}f}m"

def fmt_pct(v, d=1, already_pct=False):
    if v is None or pd.isna(v): return "—"
    x=float(v) if already_pct else float(v)*100
    return f"{x:,.{d}f}%"

def fmt_num(v,d=1):
    if v is None or pd.isna(v): return "—"
    return f"{float(v):,.{d}f}"

def signed_money(v, ccy="USD", d=1):
    if v is None or pd.isna(v): return "—"
    return f"{ccy} {float(v):+,.{d}f}m"

def chip(band):
    cls=str(band).replace(" ","-")
    return f'<span class="chip {escape(cls)}">{escape(str(band))}</span>'

def qlink(view, label, base, **updates):
    q=dict(base); q.update({k:v for k,v in updates.items() if v is not None}); q["view"]=view
    return f'<a class="link" href="/?{urlencode(q)}">{escape(str(label))}</a>'

def nav_url(view, state):
    keep={"mode","period","branch","role","date","rm","cif","daily_rm","rm_scope","segment","cohort","movement","quality","perf_band","target_role","target_metric"}
    q={k:v for k,v in state.items() if k in keep and v}
    q["view"]=view
    return "/?"+urlencode(q)


def card(k,v,s=""):
    return f'<div class="card"><div class="k">{escape(str(k))}</div><div class="v">{v}</div><div class="s">{s}</div></div>'

def cards(items): return '<div class="cards">'+''.join(card(*x) for x in items)+'</div>'


def target_basis_display(r):
    x = target_basis(r).copy()
    formatted = []
    for _, rr in x.iterrows():
        name = rr["Target Component"]
        v = float(rr["Value"])
        if name in {"Prior non-overlapping R3M average", "Final growth target", "Target R3M CASA"}:
            shown = fmt_money(v)
        elif name == "Base strategy growth":
            shown = fmt_pct(v)
        else:
            shown = f"{v:.2f}x"
        formatted.append([name, shown, rr["Meaning"]])
    return pd.DataFrame(formatted, columns=["Target Component", "Value", "Meaning"])

def approved_target_status_chip(status):
    status=str(status or "").upper()
    label={"PENDING_APPROVAL":"Pending Approval","APPROVED":"Approved","REJECTED":"Rejected"}.get(status,status.title())
    return f'<span class="status {escape(status)}">{escape(label)}</span>'


def period_effective_dates(mode: str, period: str):
    if mode == "Month":
        # available period labels are like Aug 2026
        start = pd.Timestamp(period)
        end = start + pd.offsets.MonthEnd(0)
        return start.date().isoformat(), end.date().isoformat()
    core = period.replace(" Current", "")
    q = int(core[1])
    year = int(core.split()[1])
    start = pd.Timestamp(year=year, month=(q-1)*3+1, day=1)
    end = start + pd.offsets.QuarterEnd(startingMonth=3)
    return start.date().isoformat(), end.date().isoformat()


def governed_perf(mode: str, period: str) -> pd.DataFrame:
    base = aggregate_rm_period(mode, period, DATA)
    approved = latest_approved_rm_map(mode, period, "R3M_CASA")
    return apply_approved_rm_targets(base, approved)


def governed_trend(mode: str, selected_period: str, rm: str | None = None, branch: str | None = None, role: str | None = None) -> pd.DataFrame:
    periods = available_periods(mode, DATA)
    idx = periods.index(selected_period)
    use = periods[max(0, idx-4):idx+1]
    rows=[]
    for p in use:
        x=governed_perf(mode,p)
        if rm is not None: x=x[x.RM.eq(rm)]
        if branch is not None: x=x[x.Branch.eq(branch)]
        if role is not None: x=x[x.Role.eq(role)]
        if x.empty: continue
        rows.append({
            "Period":p,
            "R3M_Avg_CASA_USDm":float(x.Current_R3M_Avg_CASA_USDm.sum()),
            "R3M_Target_USDm":float(x.Target_R3M_CASA_USDm.sum()),
            "Advances_AEDm":float(x.Advances_AEDm.sum()),
            "Relationship_Contribution_AEDm":float(x.Relationship_Contribution_AEDm.sum()),
            "Performance_Index":float(x.Performance_Index.mean()),
        })
    return pd.DataFrame(rows)


def governed_branch_performance(mode: str, period: str, perf: pd.DataFrame | None = None) -> pd.DataFrame:
    if perf is None: perf=governed_perf(mode,period)
    bp=branch_performance(mode,period,DATA,perf)
    if bp.empty: return bp
    out=bp.copy()
    for idx,row in out.iterrows():
        branch=str(row.Branch)
        rec=latest_approved(level="BRANCH",mode=mode,period=period,branch=branch,metric="R3M_CASA")
        rm_alloc=float(perf[perf.Branch.eq(branch)].Target_R3M_CASA_USDm.sum())
        if rec:
            branch_target=float(rec.get("TargetValue",0) or 0)
            target_growth=branch_target-float(row.Prior_R3M_USDm)
            actual_growth=float(row.R3M_Avg_CASA_USDm)-float(row.Prior_R3M_USDm)
            growth_points=float(np.clip((actual_growth/target_growth)*100.0,0,SCORE_CAP)) if target_growth>0 else np.nan
            out.at[idx,"Branch_Growth_Points"]=growth_points
            comps={
                "Branch Growth":growth_points,
                "ETB Retention":float(row.Branch_ETB_Points),
                "NTB Sustainable Balance":float(row.Branch_NTB_Points),
                "Economics / C&I":float(row.Branch_Economics_Points),
                "Team Median":float(row.Branch_Team_Median_Points),
                "Team Health":float(row.Branch_Team_Health_Points),
                "Attribution Discipline":float(row.Branch_Attribution_Points),
                "Controls / Service":float(row.Branch_Controls_Service_Points),
            }
            score=float(sum(comps[k]*BRANCH_SCORE_WEIGHTS[k] for k in BRANCH_SCORE_WEIGHTS))
            out.at[idx,"Branch_Performance_Index"]=score
            out.at[idx,"Performance_Band"]=performance_band(score)
            out.at[idx,"Approved_Branch_Target_USDm"]=branch_target
            out.at[idx,"Branch_Target_Attainment"]=float(row.R3M_Avg_CASA_USDm)/branch_target if branch_target>0 else np.nan
            out.at[idx,"Target_Version"]=int(rec.get("Version",1) or 1)
        else:
            out.at[idx,"Approved_Branch_Target_USDm"]=np.nan
            out.at[idx,"Branch_Target_Attainment"]=np.nan
            out.at[idx,"Target_Version"]=np.nan
        out.at[idx,"Allocated_RM_Target_USDm"]=rm_alloc
        bt=out.at[idx,"Approved_Branch_Target_USDm"]
        if pd.notna(bt) and float(bt)>0:
            out.at[idx,"Unallocated_Target_USDm"]=float(bt)-rm_alloc
            out.at[idx,"Allocation_Coverage"]=rm_alloc/float(bt)
        else:
            out.at[idx,"Unallocated_Target_USDm"]=np.nan
            out.at[idx,"Allocation_Coverage"]=np.nan
    return out


def target_audit_row(mode: str, period: str, branch: str, rm: str) -> pd.DataFrame:
    rec=latest_approved(level="RM",mode=mode,period=period,branch=branch,rm=rm,metric="R3M_CASA")
    if not rec: return pd.DataFrame()
    return pd.DataFrame([{
        "Target":"R3M Average CASA",
        "Approved Value":float(rec["TargetValue"]),
        "Version":f"V{int(rec.get('Version',1))}",
        "Effective From":rec.get("EffectiveFrom",""),
        "Effective To":rec.get("EffectiveTo",""),
        "Approved By":rec.get("ApprovedBy",""),
        "Approval Date":rec.get("ApprovalDate",""),
        "Status":rec.get("Status",""),
    }])


def section(title,note=""):
    return f'<div class="section"><h2>{escape(title)}</h2>{f"<p class=\"note\">{escape(note)}</p>" if note else ""}'

def end_section(): return '</div>'

def table_html(df:pd.DataFrame, columns, labels=None, formats=None, links=None, max_rows=100):
    labels=labels or {}; formats=formats or {}; links=links or {}
    if df is None or df.empty:
        return '<div class="empty">No applicable records for the selected scope.</div>'
    x=df.head(max_rows)
    out=['<div class="table-wrap"><table class="tbl"><thead><tr>']
    for c in columns:
        out.append(f'<th>{escape(labels.get(c,c.replace("_"," ")))}</th>')
    out.append('</tr></thead><tbody>')
    for _,r in x.iterrows():
        out.append('<tr>')
        for c in columns:
            v=r.get(c,"—")
            if c in links:
                val=links[c](r)
            else:
                f=formats.get(c)
                if f: val=f(v)
                elif isinstance(v,(pd.Timestamp,)): val=v.strftime('%d %b %Y')
                elif hasattr(v,'strftime') and not isinstance(v,str):
                    try: val=v.strftime('%d %b %Y')
                    except: val=escape(str(v))
                else: val=escape(str(v))
            cls='num' if c in formats else ''
            out.append(f'<td class="{cls}">{val}</td>')
        out.append('</tr>')
    out.append('</tbody></table></div>')
    return ''.join(out)


def svg_line(df, x_col, series, height=280):
    if df is None or df.empty: return '<div class="empty">No trend data.</div>'
    w=920; h=height; ml=58; mr=24; mt=30; mb=55; pw=w-ml-mr; ph=h-mt-mb
    vals=[]
    for c,_ in series: vals += [float(v) for v in df[c].dropna().tolist()]
    if not vals: return '<div class="empty">No trend data.</div>'
    ymin=min(vals); ymax=max(vals); pad=(ymax-ymin)*.12 or 1; ymin-=pad; ymax+=pad
    xs=np.linspace(ml,ml+pw,len(df)) if len(df)>1 else np.array([ml+pw/2])
    def y(v): return mt+ph-(float(v)-ymin)/(ymax-ymin)*ph
    colors=['#0b7fc1','#24786e','#b57c10','#6b5b8e']
    parts=[f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}" role="img">']
    for i in range(5):
        yy=mt+ph*i/4; val=ymax-(ymax-ymin)*i/4
        parts.append(f'<line x1="{ml}" y1="{yy:.1f}" x2="{ml+pw}" y2="{yy:.1f}" stroke="#e6edf2" stroke-width="1"/>')
        parts.append(f'<text x="{ml-8}" y="{yy+4:.1f}" text-anchor="end" font-size="10" fill="#7d8994">{val:.0f}</text>')
    for si,(c,label) in enumerate(series):
        pts=[]
        for xx,v in zip(xs,df[c]): pts.append(f'{xx:.1f},{y(v):.1f}')
        col=colors[si%len(colors)]
        parts.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{col}" stroke-width="3"/>')
        for xx,v in zip(xs,df[c]): parts.append(f'<circle cx="{xx:.1f}" cy="{y(v):.1f}" r="4" fill="{col}"/>')
        parts.append(f'<rect x="{ml+si*160}" y="7" width="12" height="3" fill="{col}"/><text x="{ml+16+si*160}" y="13" font-size="11" fill="#344452">{escape(label)}</text>')
    for xx,lbl in zip(xs,df[x_col].astype(str)):
        parts.append(f'<text x="{xx:.1f}" y="{h-18}" text-anchor="middle" font-size="10" fill="#6f7d89">{escape(lbl)}</text>')
    parts.append('</svg>')
    return '<div class="svg-wrap">'+''.join(parts)+'</div>'


def svg_bar(labels, values, height=280):
    w=640; h=height; ml=48; mr=18; mt=24; mb=62; pw=w-ml-mr; ph=h-mt-mb
    vmax=max([float(v) for v in values]+[1]); bw=pw/max(len(values),1)*.62; gap=pw/max(len(values),1)
    colors={'Exceptional':'#24786e','Strong':'#2a805b','Successful':'#0b7fc1','Watch':'#b57c10','Needs Review':'#a74747','Ramp-up':'#6b5b8e'}
    parts=[f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}">']
    for i in range(5):
        yy=mt+ph*i/4; parts.append(f'<line x1="{ml}" y1="{yy:.1f}" x2="{ml+pw}" y2="{yy:.1f}" stroke="#e6edf2"/>')
    for i,(lbl,v) in enumerate(zip(labels,values)):
        xx=ml+i*gap+(gap-bw)/2; bh=float(v)/vmax*ph; yy=mt+ph-bh; col=colors.get(lbl,'#0b7fc1')
        parts.append(f'<rect x="{xx:.1f}" y="{yy:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="2" fill="{col}"/>')
        parts.append(f'<text x="{xx+bw/2:.1f}" y="{yy-5:.1f}" text-anchor="middle" font-size="11" fill="#364653">{int(v)}</text>')
        parts.append(f'<text x="{xx+bw/2:.1f}" y="{h-30}" text-anchor="middle" font-size="9" fill="#6f7d89" transform="rotate(-22 {xx+bw/2:.1f} {h-30})">{escape(lbl)}</text>')
    parts.append('</svg>')
    return '<div class="svg-wrap">'+''.join(parts)+'</div>'


def eligible_rm_names(branch="All UAE", role="All"):
    """Return RM names valid for the selected management scope, preserving roster display order."""
    roster=DATA.roster[["RM","Branch","Role"]].drop_duplicates().copy()
    if branch!="All UAE":
        roster=roster[roster.Branch.eq(branch)]
    if role!="All":
        roster=roster[roster.Role.eq(role)]
    allowed=set(roster.RM.astype(str))
    return [name for name in TEAM_NAMES if name in allowed]


def resolve_state(params):
    view=params.get('view',['executive'])[0]
    mode=params.get('mode',['Quarter'])[0]
    if mode not in {'Quarter','Month'}: mode='Quarter'
    periods=available_periods(mode,DATA)
    period=params.get('period',[periods[-1]])[0]
    if period not in periods: period=periods[-1]
    branch=params.get('branch',['All UAE'])[0]
    if branch!='All UAE' and branch not in BRANCHES: branch='All UAE'
    role=params.get('role',['All'])[0]
    if role not in {'All','RM','SRM'}: role='All'
    dates=available_daily_dates(DATA)
    date=params.get('date',[dates[-1]])[0]
    if date not in dates: date=dates[-1]
    rm=params.get('rm',[TEAM_NAMES[0]])[0]
    if rm not in TEAM_NAMES: rm=TEAM_NAMES[0]
    rm_scope=params.get('rm_scope',['All RMs'])[0]
    if rm_scope!='All RMs' and rm_scope not in TEAM_NAMES: rm_scope='All RMs'
    cif=params.get('cif',[''])[0]
    account=params.get('account',[''])[0]
    tab=params.get('tab',['performance'])[0]
    daily_rm=params.get('daily_rm',['All RMs'])[0]
    if daily_rm!='All RMs' and daily_rm not in TEAM_NAMES: daily_rm='All RMs'
    segment=params.get('segment',['All Segments'])[0]
    if segment not in {'All Segments','Corporate','Individual'}: segment='All Segments'
    cohort=params.get('cohort',['All Cohorts'])[0]
    if cohort not in {'All Cohorts','ETB','NTB'}: cohort='All Cohorts'
    movement=params.get('movement',['All Movements'])[0]
    if movement not in {'All Movements','Inflows','Outflows'}: movement='All Movements'
    quality=params.get('quality',['All Portfolio Quality'])[0]
    if quality not in {'All Portfolio Quality','Stage 1','Stage 2','Stage 3'}: quality='All Portfolio Quality'
    perf_band=params.get('perf_band',['All Bands'])[0]
    allowed_bands={'All Bands','Exceptional','Strong','Successful','Watch','Needs Review','Ramp-up'}
    if perf_band not in allowed_bands: perf_band='All Bands'
    target_role=params.get('target_role',['Viewer'])[0]
    if target_role not in TARGET_ACCESS: target_role='Viewer'
    target_metric=params.get('target_metric',['R3M_CASA'])[0]
    if target_metric not in TARGET_METRICS: target_metric='R3M_CASA'
    notice=params.get('notice',[''])[0][:220]
    # Cascading management scope: RM Focus must be valid for the selected Branch and Role.
    eligible_rms=eligible_rm_names(branch,role)
    if rm_scope!='All RMs' and rm_scope not in eligible_rms: rm_scope='All RMs'
    if daily_rm!='All RMs' and daily_rm not in eligible_rms: daily_rm='All RMs'
    return {'view':view,'mode':mode,'period':period,'branch':branch,'role':role,'date':date,'rm':rm,'rm_scope':rm_scope,'cif':cif,'account':account,'tab':tab,'daily_rm':daily_rm,'segment':segment,'cohort':cohort,'movement':movement,'quality':quality,'perf_band':perf_band,'target_role':target_role,'target_metric':target_metric,'notice':notice}


def filtered_perf(state):
    perf=governed_perf(state['mode'],state['period'])
    if state['branch']!='All UAE': perf=perf[perf.Branch.eq(state['branch'])]
    if state['role']!='All': perf=perf[perf.Role.eq(state['role'])]
    if state.get('rm_scope','All RMs')!='All RMs': perf=perf[perf.RM.eq(state['rm_scope'])]
    if state.get('perf_band','All Bands')!='All Bands': perf=perf[perf.Performance_Band.eq(state['perf_band'])]
    return perf.copy()


def filtered_customer_period(state):
    cust=aggregate_customer_period(state['mode'],state['period'],DATA).copy()
    if cust.empty:
        return cust
    roles=DATA.roster[['Employee_ID','Role']].drop_duplicates()
    cust=cust.merge(roles,on='Employee_ID',how='left')
    if state['branch']!='All UAE': cust=cust[cust.Branch.eq(state['branch'])]
    if state['role']!='All': cust=cust[cust.Role.eq(state['role'])]
    if state.get('rm_scope','All RMs')!='All RMs': cust=cust[cust.RM.eq(state['rm_scope'])]
    if state['segment']!='All Segments': cust=cust[cust.Segment.eq(state['segment'])]
    if state['cohort']!='All Cohorts': cust=cust[cust.Cohort.eq(state['cohort'])]
    if state.get('quality','All Portfolio Quality')!='All Portfolio Quality': cust=cust[cust.Risk_Stage.eq(state['quality'])]
    if state.get('perf_band','All Bands')!='All Bands':
        perf=governed_perf(state['mode'],state['period'])[['Employee_ID','Performance_Band']]
        cust=cust.merge(perf,on='Employee_ID',how='left')
        cust=cust[cust.Performance_Band.eq(state['perf_band'])]
    return cust.copy()


def portfolio_slice_active(state):
    return any([
        state.get('segment','All Segments')!='All Segments',
        state.get('cohort','All Cohorts')!='All Cohorts',
        state.get('quality','All Portfolio Quality')!='All Portfolio Quality',
    ])


def portfolio_slice_banner(state, daily=False):
    if not portfolio_slice_active(state):
        return ''
    parts=[]
    if state.get('segment')!='All Segments': parts.append(f"Segment: {escape(state['segment'])}")
    if state.get('cohort')!='All Cohorts': parts.append(f"Cohort: {escape(state['cohort'])}")
    if state.get('quality')!='All Portfolio Quality': parts.append(f"Portfolio quality: {escape(state['quality'])}")
    scope=' · '.join(parts)
    if daily:
        msg='These filters refine customer-level deposits and movements. Branch and RM headline positions continue to show the total certified book for the selected management scope.'
    else:
        msg='These filters refine customer and relationship measures. RM performance, targets and direct employee cost continue to show the full RM position.'
    return f'<div class="scope-note"><b>Customer filters:</b> {scope}. {msg}</div>'


def portfolio_slice_cards(state):
    cust=filtered_customer_period(state)
    if cust.empty:
        return '<div class="empty">No customer relationships match the selected customer filters.</div>'
    return cards([
        ('Relationships',f"{cust.CIF.nunique():,}",'unique CIFs in filtered view'),
        ('PE Deposits',fmt_money(cust.Deposits_USDm.sum()),'period-end deposits'),
        ('Advances',fmt_money(cust.Advances_AEDm.sum(),'AED'),'facility exposure'),
        ('Relationship Contribution',fmt_money(cust.Relationship_Contribution_AEDm.sum(),'AED',2),'after customer cost-to-serve'),
    ])


def portfolio_slice_section(state):
    if not portfolio_slice_active(state):
        return ''
    cust=filtered_customer_period(state)
    if cust.empty:
        top='<div class="empty">No customer relationships match the selected customer filters.</div>'
    else:
        top=cust.sort_values('Deposits_USDm',ascending=False).head(10)
        top=table_html(top,['Customer','CIF','RM','Branch','Segment','Cohort','Risk_Stage','Deposits_USDm','Avg_Deposits_USDm','Advances_AEDm','Relationship_Contribution_AEDm'],labels={'Risk_Stage':'Portfolio Quality','Deposits_USDm':'PE Deposits','Avg_Deposits_USDm':'Average Deposits','Advances_AEDm':'Advances','Relationship_Contribution_AEDm':'Relationship Contribution'},formats={'Deposits_USDm':fmt_money,'Avg_Deposits_USDm':fmt_money,'Advances_AEDm':lambda v:fmt_money(v,'AED'),'Relationship_Contribution_AEDm':lambda v:fmt_money(v,'AED',2)},links={'Customer':lambda r:qlink('customer',r.Customer,state,rm=r.RM,cif=r.CIF),'RM':lambda r:qlink('rm360',r.RM,state,rm=r.RM)},max_rows=10)
    return section('Filtered relationship view','Customer-level detail for the selected Segment, Cohort and Portfolio Quality filters.')+portfolio_slice_cards(state)+f'<div style="height:12px"></div>'+top+end_section()


def sidebar(state):
    nav=''.join(f'<a class="{"active" if state["view"]==key else ""}" href="{nav_url(key,state)}">{escape(label)}</a>' for label,key in NAV)
    branch_opts=''.join(f'<option {"selected" if x==state["branch"] else ""}>{escape(x)}</option>' for x in ['All UAE']+BRANCHES)
    role_opts=''.join(f'<option {"selected" if x==state["role"] else ""}>{x}</option>' for x in ['All','RM','SRM'])
    segment_opts=''.join(f'<option {"selected" if x==state["segment"] else ""}>{x}</option>' for x in ['All Segments','Corporate','Individual'])
    cohort_opts=''.join(f'<option {"selected" if x==state["cohort"] else ""}>{x}</option>' for x in ['All Cohorts','ETB','NTB'])
    quality_opts=''.join(f'<option {"selected" if x==state["quality"] else ""}>{x}</option>' for x in ['All Portfolio Quality','Stage 1','Stage 2','Stage 3'])
    if state['view']=='daily':
        daily_dates=available_daily_dates(DATA)
        latest=daily_dates[-1]
        date_opts=''.join(f'<option {"selected" if x==state["date"] else ""}>{x}</option>' for x in reversed(daily_dates))
        eligible_rms=eligible_rm_names(state['branch'],state['role'])
        rm_opts=''.join(f'<option {"selected" if x==state["daily_rm"] else ""}>{escape(x)}</option>' for x in ['All RMs']+eligible_rms)
        movement_opts=''.join(f'<option {"selected" if x==state["movement"] else ""}>{x}</option>' for x in ['All Movements','Inflows','Outflows'])
        latest_q={k:v for k,v in state.items() if k in {'branch','role','daily_rm','segment','cohort','movement','quality'} and v}
        latest_q.update({'view':'daily','date':latest})
        latest_url='/?'+urlencode(latest_q)
        reset_url='/?view=daily&date='+urlencode({'x':latest}).split('=',1)[1]
        filters=(
            '<div class="filter-group"><div class="filter-group-title">Reporting</div>'
            f'<label>Business date</label><select class="auto-submit" name="date" id="daily-date-select">{date_opts}</select>'
            f'<div class="filter-hint">Certified available business dates only. Weekends/holidays use the previous available reporting snapshot.</div>'
            f'<div class="filter-status"><span>Selected: {escape(state["date"])}</span><a href="{latest_url}">Latest available</a></div></div>'
            '<div class="filter-group"><div class="filter-group-title">Management scope</div>'
            f'<label>Branch</label><select class="auto-submit scope-aware" name="branch" id="branch-select" data-applied-value="{escape(state["branch"])}">{branch_opts}</select>'
            f'<label>Role</label><select class="auto-submit scope-aware" name="role" id="role-select" data-applied-value="{escape(state["role"])}">{role_opts}</select>'
            f'<label>RM focus</label><select class="auto-submit scope-aware" name="daily_rm" id="daily-rm-select" data-applied-value="{escape(state["daily_rm"])}">{rm_opts}</select>'
            '<div class="filter-hint">RM Focus shows only RMs relevant to the selected Branch and Role.</div></div>'
            '<div class="filter-group"><div class="filter-group-title">Customer filters</div>'
            f'<label>Customer segment</label><select class="auto-submit" name="segment">{segment_opts}</select>'
            f'<label>Relationship cohort</label><select class="auto-submit" name="cohort">{cohort_opts}</select>'
            f'<label>Portfolio quality</label><select class="auto-submit" name="quality">{quality_opts}</select>'
            f'<label>Movement direction</label><select class="auto-submit" name="movement">{movement_opts}</select>'
            '<div class="filter-hint">These filters refine customer-level deposits and movement analysis. Branch/RM headline positions continue to show the full book.</div></div>'
        )
        reset='/?view=daily'
    elif state['view']=='targets':
        mode=state['mode']; periods=available_periods(mode,DATA)
        mode_opts=''.join(f'<option {"selected" if x==mode else ""}>{x}</option>' for x in ['Quarter','Month'])
        period_opts=''.join(f'<option {"selected" if x==state["period"] else ""}>{escape(x)}</option>' for x in periods)
        period_label='Target month' if mode=='Month' else 'Target quarter'
        eligible_rms=eligible_rm_names(state['branch'],state['role'])
        rm_scope_opts=''.join(f'<option {"selected" if x==state["rm_scope"] else ""}>{escape(x)}</option>' for x in ['All RMs']+eligible_rms)
        access_opts=''.join(f'<option value="{escape(k)}" {"selected" if k==state["target_role"] else ""}>{escape(v)}</option>' for k,v in TARGET_ACCESS.items())
        metric_opts=''.join(f'<option value="{escape(k)}" {"selected" if k==state["target_metric"] else ""}>{escape(v["name"])}</option>' for k,v in TARGET_METRICS.items())
        filters=(
            '<div class="filter-group"><div class="filter-group-title">Target period</div>'
            f'<label>View by</label><select name="mode" id="mode-select">{mode_opts}</select>'
            f'<label>{period_label}</label><select class="auto-submit" name="period" id="period-select">{period_opts}</select>'
            f'<label>Metric</label><select class="auto-submit" name="target_metric">{metric_opts}</select></div>'
            '<div class="filter-group"><div class="filter-group-title">Target scope</div>'
            f'<label>Branch</label><select class="auto-submit scope-aware" name="branch" id="branch-select" data-applied-value="{escape(state["branch"])}">{branch_opts}</select>'
            f'<label>Role</label><select class="auto-submit scope-aware" name="role" id="role-select" data-applied-value="{escape(state["role"])}">{role_opts}</select>'
            f'<label>RM focus</label><select class="auto-submit scope-aware" name="rm_scope" id="rm-scope-select" data-applied-value="{escape(state["rm_scope"])}">{rm_scope_opts}</select>'
            '<div class="filter-hint">RM Focus cascades from Branch and Role. Select a specific Branch before creating or revising a target.</div></div>'
            '<div class="filter-group"><div class="filter-group-title">Access simulation</div>'
            f'<label>Target access</label><select class="auto-submit" name="target_role">{access_opts}</select>'
            '<div class="filter-hint">Prototype only. Production access must come from UBL SSO/AD groups and backend authorization, not a user-selectable control.</div></div>'
        )
        reset='/?view=targets&mode='+escape(mode)
    else:
        mode=state['mode']; periods=available_periods(mode,DATA)
        mode_opts=''.join(f'<option {"selected" if x==mode else ""}>{x}</option>' for x in ['Quarter','Month'])
        period_opts=''.join(f'<option {"selected" if x==state["period"] else ""}>{escape(x)}</option>' for x in periods)
        period_label='Reporting month' if mode=='Month' else 'Reporting quarter'
        eligible_rms=eligible_rm_names(state['branch'],state['role'])
        rm_scope_opts=''.join(f'<option {"selected" if x==state["rm_scope"] else ""}>{escape(x)}</option>' for x in ['All RMs']+eligible_rms)
        band_opts=''.join(f'<option {"selected" if x==state["perf_band"] else ""}>{escape(x)}</option>' for x in ['All Bands','Exceptional','Strong','Successful','Watch','Needs Review','Ramp-up'])
        filters=(
            '<div class="filter-group"><div class="filter-group-title">Reporting</div>'
            f'<label>View by</label><select name="mode" id="mode-select">{mode_opts}</select>'
            f'<label>{period_label}</label><select class="auto-submit" name="period" id="period-select">{period_opts}</select></div>'
            '<div class="filter-group"><div class="filter-group-title">Management scope</div>'
            f'<label>Branch</label><select class="auto-submit scope-aware" name="branch" id="branch-select" data-applied-value="{escape(state["branch"])}">{branch_opts}</select>'
            f'<label>Role</label><select class="auto-submit scope-aware" name="role" id="role-select" data-applied-value="{escape(state["role"])}">{role_opts}</select>'
            f'<label>RM focus</label><select class="auto-submit scope-aware" name="rm_scope" id="rm-scope-select" data-applied-value="{escape(state["rm_scope"])}">{rm_scope_opts}</select>'
            '<div class="filter-hint">RM Focus shows only RMs relevant to the selected Branch and Role.</div></div>'
            '<div class="filter-group"><div class="filter-group-title">Customer filters</div>'
            f'<label>Customer segment</label><select class="auto-submit" name="segment">{segment_opts}</select>'
            f'<label>Relationship cohort</label><select class="auto-submit" name="cohort">{cohort_opts}</select>'
            f'<label>Portfolio quality</label><select class="auto-submit" name="quality">{quality_opts}</select>'
            '<div class="filter-hint">These filters refine customer and relationship measures. RM performance, targets and direct employee cost continue to show the full RM position.</div></div>'
            '<div class="filter-group"><div class="filter-group-title">Assessment</div>'
            f'<label>Performance band</label><select class="auto-submit" name="perf_band">{band_opts}</select></div>'
        )
        reset=f'/?view={escape(state["view"])}&mode={escape(mode)}'
    return (f'<aside class="sidebar"><img class="logo" src="/ubl_logo.png" alt="UBL logo"><div class="brand">UBL UAE</div>'
            f'<div class="product">RM Cost &amp; Performance Management</div><nav class="nav">{nav}</nav><hr class="divider">'
            f'<form class="filter" method="get" id="management-filter-form"><input type="hidden" name="view" value="{escape(state["view"])}">'
            f'{filters}<button type="submit">Apply filters</button><a class="filter-reset" href="{reset}">Reset filters</a></form></aside>')


def header(title,subtitle,state):
    if state.get('view')=='daily':
        pills=(f'<span class="pill">Business date: {escape(state["date"])}</span>'
               f'<span class="pill">Branch: {escape(state["branch"])}</span>'
               f'<span class="pill">Role: {escape(state["role"])}</span>')
        if state.get('daily_rm')!='All RMs': pills+=f'<span class="pill">RM: {escape(state["daily_rm"])}</span>'
    else:
        period_label='Month' if state['mode']=='Month' else 'Quarter'
        pills=(f'<span class="pill">{period_label}: {escape(state["period"])}</span>'
               f'<span class="pill">Branch: {escape(state["branch"])}</span>'
               f'<span class="pill">Role: {escape(state["role"])}</span>')
        if state.get('rm_scope')!='All RMs': pills+=f'<span class="pill">RM: {escape(state["rm_scope"])}</span>'
        if state.get('perf_band')!='All Bands' and state.get('view')!='targets': pills+=f'<span class="pill">Band: {escape(state["perf_band"])}</span>'
        if state.get('view')=='targets': pills+=f'<span class="pill">Access: {escape(TARGET_ACCESS.get(state.get("target_role","Viewer"),"Management Viewer"))}</span>'
    if state.get('segment')!='All Segments': pills+=f'<span class="pill">Segment: {escape(state["segment"])}</span>'
    if state.get('cohort')!='All Cohorts': pills+=f'<span class="pill">Cohort: {escape(state["cohort"])}</span>'
    if state.get('quality')!='All Portfolio Quality': pills+=f'<span class="pill">Portfolio Quality: {escape(state["quality"])}</span>'
    return (f'<div class="eyebrow">UAE FINANCE · RELATIONSHIP MANAGEMENT</div><div class="title">{escape(title)}</div>'
            f'<div class="subtitle">{escape(subtitle)}</div><div>{pills}</div>')


def executive_page(state):
    perf=filtered_perf(state)
    if perf.empty:
        return header("Executive Overview","A concise management view of workforce productivity, sustainable portfolio growth, customer development, relationship economics, cost efficiency and the customer/account drivers behind the result.",state)+portfolio_slice_banner(state)+ '<div class="empty">No RMs match the selected Branch / Role / RM / Performance Band scope. Reset or broaden the assessment filters.</div>'
    ws=workforce_summary(perf)
    branch_perf_base=governed_perf(state['mode'],state['period'])
    if state['branch']!='All UAE': branch_perf_base=branch_perf_base[branch_perf_base.Branch.eq(state['branch'])]
    br=governed_branch_performance(state['mode'],state['period'],branch_perf_base)
    tr=governed_trend(state['mode'],state['period'],rm=None if state.get('rm_scope')=='All RMs' else state['rm_scope'],branch=None if state['branch']=='All UAE' else state['branch'],role=None if state['role']=='All' else state['role'])
    avg_score=float(perf.Performance_Index.mean())
    dist=["Exceptional","Strong","Successful","Watch","Needs Review","Ramp-up"]
    counts=[int((perf.Performance_Band==x).sum()) for x in dist]
    items=[
        ("Active RMs",str(int(perf.Employee_ID.nunique())),f"{int((perf.Role=='SRM').sum())} SRM · {int((perf.Role=='RM').sum())} RM"),
        ("Physical Branches",str(perf.Branch.nunique()),f"{perf.Employee_ID.nunique()/max(perf.Branch.nunique(),1):.1f} RM per Branch"),
        ("R3M Avg CASA",fmt_money(perf.Current_R3M_Avg_CASA_USDm.sum()),"sustainable balance lens"),
        ("R3M Growth",fmt_pct(perf.Current_R3M_Avg_CASA_USDm.sum()/perf.Prior_R3M_Avg_CASA_USDm.sum()-1),"vs prior non-overlapping R3M"),
        ("Funded NTB R3M",f"{int(perf.Funded_NTB_R3M.sum()):,}","funded acquisition"),
        ("Advances",fmt_money(perf.Advances_AEDm.sum(),"AED"),"period-end lending book"),
        ("Relationship Contribution",fmt_money(perf.Relationship_Contribution_AEDm.sum(),"AED",2),"after customer cost-to-serve"),
        ("Avg RM Index",f"{avg_score:.0f}",performance_band(avg_score)),
    ]
    labels={'Branch':'Branch','Active_RMs':'Active RMs','R3M_Avg_CASA_USDm':'R3M Avg CASA','R3M_Growth_pct':'R3M Growth','Funded_NTB_R3M':'Funded NTB R3M','Relationship_Contribution_AEDm':'Relationship Contribution','Branch_Performance_Index':'Branch Index','Performance_Band':'Band'}
    formats={'R3M_Avg_CASA_USDm':fmt_money,'R3M_Growth_pct':fmt_pct,'Funded_NTB_R3M':lambda v:f"{int(v):,}",'Relationship_Contribution_AEDm':lambda v:fmt_money(v,'AED',2),'Branch_Performance_Index':lambda v:f"{float(v):.0f}"}
    links={'Branch':lambda r: qlink('branch',r.Branch,state,branch=r.Branch)}
    # RM priority view uses score + driver, but remains management-language, no internal gate jargon.
    priority=perf.sort_values(['Performance_Index','R3M_Target_Attainment']).head(8)
    p_labels={'RM':'RM','Branch':'Branch','Role':'Role','Performance_Index':'Index','Performance_Band':'Band','R3M_Target_Attainment':'Target Attainment','Primary_Driver':'Primary Driver','Strength_Driver':'Strength'}
    p_formats={'Performance_Index':lambda v:f"{float(v):.0f}",'R3M_Target_Attainment':fmt_pct,'Performance_Band':lambda v:chip(v)}
    p_links={'RM':lambda r: qlink('rm360',r.RM,state,rm=r.RM),'Branch':lambda r: qlink('branch',r.Branch,state,branch=r.Branch)}
    return header("Executive Overview","A concise management view of workforce productivity, sustainable portfolio growth, customer development, relationship economics, cost efficiency and the customer/account drivers behind the result.",state)+portfolio_slice_banner(state)+cards(items)+section("Five-period trajectory","The selected Month/Quarter endpoint drives the historical comparison.")+f'<div class="grid2"><div class="panel">{svg_line(tr,"Period",[("R3M_Avg_CASA_USDm","R3M Avg CASA"),("R3M_Target_USDm","R3M Target")])}</div><div class="panel"><h3>Performance distribution</h3>{svg_bar(dist,counts)}</div></div>'+end_section()+section("Branch performance","Select a Branch to move directly into the Branch management view.")+table_html(br,['Branch','Active_RMs','R3M_Avg_CASA_USDm','R3M_Growth_pct','Funded_NTB_R3M','Relationship_Contribution_AEDm','Branch_Performance_Index','Performance_Band'],labels,formats,links,30)+end_section()+section("Priority RM review","Lowest composite results first. Select an RM to see the full calculation and customer drivers.")+table_html(priority,['RM','Branch','Role','Performance_Index','Performance_Band','R3M_Target_Attainment','Primary_Driver','Strength_Driver'],p_labels,p_formats,p_links,20)+end_section()+portfolio_slice_section(state)


def daily_page(state):
    base_dr=daily_rm_snapshot(state['date'],DATA)
    if state['branch']!='All UAE': base_dr=base_dr[base_dr.Branch.eq(state['branch'])]
    if state['role']!='All': base_dr=base_dr[base_dr.Role.eq(state['role'])]
    db=daily_branch_summary(state['date'],DATA,base_dr)
    dr=base_dr.copy()
    if state['daily_rm']!='All RMs': dr=dr[dr.RM.eq(state['daily_rm'])]
    dc=daily_customer_snapshot(state['date'],DATA,dr)
    if state['segment']!='All Segments': dc=dc[dc.Segment.eq(state['segment'])]
    if state['cohort']!='All Cohorts': dc=dc[dc.Cohort.eq(state['cohort'])]
    if state['quality']!='All Portfolio Quality' and 'Risk_Stage' in dc.columns: dc=dc[dc.Risk_Stage.eq(state['quality'])]
    if state['movement']=='Inflows': dc=dc[dc.DoD_Change_USDm.gt(0)]
    elif state['movement']=='Outflows': dc=dc[dc.DoD_Change_USDm.lt(0)]
    tr=daily_trend(state['date'],DATA,10,branch=None if state['branch']=='All UAE' else state['branch'],role=None if state['role']=='All' else state['role'])
    fresh=daily_data_freshness(state['date'])
    freshness=f'''<div class="info"><b>Data as of:</b> {fresh['Business_Date']:%d %b %Y} &nbsp;&middot;&nbsp; <b>Published:</b> {fresh['Available_Date']:%d %b %Y} &nbsp;&middot;&nbsp; <b>Status:</b> {fresh['Status']} &nbsp;&middot;&nbsp; <b>Previous available:</b> {fresh['Previous_Available_Date']:%d %b %Y}</div>'''
    items=[('Active RMs',str(base_dr.Employee_ID.nunique()),'selected Branch / Role scope'),('RM-attributed PE CASA',fmt_money(base_dr.PE_CASA_USDm.sum()),'certified EOD stock'),('Management PE CASA',fmt_money(db.Management_PE_USDm.sum()),'RM + BM-owned + unassigned + sundries'),('MTD Avg CASA',fmt_money(base_dr.MTD_Avg_CASA_USDm.sum()),'available daily snapshots MTD'),('Day-on-Day',signed_money(base_dr.DoD_Change_USDm.sum()),'vs previous available reporting date'),('vs Prior Month-End',signed_money(base_dr.Vs_Prior_Month_End_USDm.sum()),'movement from last month-end'),('Advances',fmt_money(base_dr.Advances_AEDm.sum(),'AED'),'daily operational lending position'),('Funded NTB YTD',f"{int(base_dr.Funded_NTB_YTD.sum()):,}",'acquisition pace; no daily employee score')]
    b_labels={'Branch':'Branch','Active_RMs':'Active RMs','RM_Attributed_USDm':'RM-attributed PE','Management_PE_USDm':'Management PE','MTD_Avg_CASA_USDm':'MTD Avg','DoD_Change_USDm':'DoD','Vs_Prior_Month_End_USDm':'vs Prior Month-End','Vs_Dec25_USDm':'vs Dec-25','Advances_AEDm':'Advances','Funded_NTB_YTD':'Funded NTB YTD'}
    b_formats={'RM_Attributed_USDm':fmt_money,'Management_PE_USDm':fmt_money,'MTD_Avg_CASA_USDm':fmt_money,'DoD_Change_USDm':lambda v:signed_money(v),'Vs_Prior_Month_End_USDm':lambda v:signed_money(v),'Vs_Dec25_USDm':lambda v:signed_money(v),'Advances_AEDm':lambda v:fmt_money(v,'AED'),'Funded_NTB_YTD':lambda v:f"{int(v):,}"}
    b_links={'Branch':lambda r:qlink('branch',r.Branch,state,branch=r.Branch)}
    r_labels={'RM':'RM','Branch':'Branch','Role':'Role','PE_CASA_USDm':'PE CASA','MTD_Avg_CASA_USDm':'MTD Avg','DoD_Change_USDm':'DoD','Vs_Prior_Month_End_USDm':'vs Prior Month-End','Vs_Dec25_USDm':'vs Dec-25','Advances_AEDm':'Advances','Funded_NTB_YTD':'Funded NTB YTD','NTB_Run_Rate':'NTB Run Rate'}
    r_formats={'PE_CASA_USDm':fmt_money,'MTD_Avg_CASA_USDm':fmt_money,'DoD_Change_USDm':lambda v:signed_money(v),'Vs_Prior_Month_End_USDm':lambda v:signed_money(v),'Vs_Dec25_USDm':lambda v:signed_money(v),'Advances_AEDm':lambda v:fmt_money(v,'AED'),'Funded_NTB_YTD':lambda v:f"{int(v):,}",'NTB_Run_Rate':lambda v:f"{float(v):.3f}/day"}
    r_links={'RM':lambda r:qlink('rm360',r.RM,state,rm=r.RM),'Branch':lambda r:qlink('branch',r.Branch,state,branch=r.Branch)}
    if not dc.empty: dc=dc.assign(AbsDoD=dc.DoD_Change_USDm.abs()).sort_values('AbsDoD',ascending=False).drop(columns='AbsDoD')
    c_labels={'Customer':'Customer','CIF':'CIF','RM':'RM','Branch':'Branch','Segment':'Segment','Cohort':'Cohort','Risk_Stage':'Portfolio Quality','Deposits_USDm':'PE CASA','DoD_Change_USDm':'DoD','MTD_Avg_Deposits_USDm':'MTD Avg','Advances_AEDm':'Advances'}
    c_formats={'Deposits_USDm':fmt_money,'DoD_Change_USDm':lambda v:signed_money(v),'MTD_Avg_Deposits_USDm':fmt_money,'Advances_AEDm':lambda v:fmt_money(v,'AED')}
    c_links={'Customer':lambda r:qlink('customer',r.Customer,state,rm=r.RM,cif=r.CIF),'RM':lambda r:qlink('rm360',r.RM,state,rm=r.RM)}
    driver_note=f"RM focus: {state['daily_rm']} | Segment: {state['segment']} | Cohort: {state['cohort']} | Portfolio quality: {state['quality']} | Movement: {state['movement']}"
    top_dep=dc.sort_values('Deposits_USDm',ascending=False).head(15).copy()
    top_dep.insert(0,'Rank',range(1,len(top_dep)+1))
    top_labels={**c_labels,'Rank':'Rank'}
    return header('Daily Management','Daily management pack combining portfolio deposits, RM/SRM position, advances and major customer movements for the selected certified business date.',state)+freshness+portfolio_slice_banner(state,daily=True)+cards(items)+section('10-business-day trajectory','PE and MTD average show the operating path; comparison uses the previous available reporting date.')+f'<div class="panel">{svg_line(tr,"Date",[("PE_CASA_USDm","PE CASA"),("MTD_Avg_CASA_USDm","MTD Avg CASA")])}</div>'+end_section()+section('Daily Branch portfolio','Daily deposit/advance management position by Branch; select a Branch for its full management view.')+table_html(db,['Branch','Active_RMs','RM_Attributed_USDm','Management_PE_USDm','MTD_Avg_CASA_USDm','DoD_Change_USDm','Vs_Prior_Month_End_USDm','Vs_Dec25_USDm','Advances_AEDm','Funded_NTB_YTD'],b_labels,b_formats,b_links,30)+end_section()+section('Top management portfolio deposits','Largest customer deposit relationships in the selected daily scope, with day-on-day and MTD context.')+table_html(top_dep,['Rank','Customer','CIF','RM','Branch','Segment','Cohort','Risk_Stage','Deposits_USDm','DoD_Change_USDm','MTD_Avg_Deposits_USDm'],top_labels,c_formats,c_links,20)+end_section()+section('RM / SRM daily position','Daily operational RM/SRM book and acquisition position. Month/Quarter/R3M remain the sustainable performance horizon.')+table_html(dr.sort_values('DoD_Change_USDm'),['RM','Branch','Role','PE_CASA_USDm','MTD_Avg_CASA_USDm','DoD_Change_USDm','Vs_Prior_Month_End_USDm','Vs_Dec25_USDm','Advances_AEDm','Funded_NTB_YTD','NTB_Run_Rate'],r_labels,r_formats,r_links,30)+end_section()+section('Major customer movements',driver_note)+table_html(dc.head(20),['Customer','CIF','RM','Branch','Segment','Cohort','Risk_Stage','Deposits_USDm','DoD_Change_USDm','MTD_Avg_Deposits_USDm','Advances_AEDm'],c_labels,c_formats,c_links,30)+end_section()


def rm_performance_page(state):
    perf=filtered_perf(state).sort_values('Performance_Index',ascending=False)
    if perf.empty:
        return header("RM Performance","The performance table combines sustainable portfolio delivery, customer development, economics, cost efficiency, controls and service into an explainable management index.",state)+portfolio_slice_banner(state)+ '<div class="empty">No RMs match the selected assessment scope.</div>'
    items=[
        ("Active RMs",str(perf.Employee_ID.nunique()),"selected management population"),
        ("R3M Avg CASA",fmt_money(perf.Current_R3M_Avg_CASA_USDm.sum()),"sustainable book"),
        ("Target R3M",fmt_money(perf.Target_R3M_CASA_USDm.sum()),"approved target register"),
        ("Avg RM Index",f"{perf.Performance_Index.mean():.0f}",performance_band(perf.Performance_Index.mean())),
        ("Funded NTB R3M",f"{int(perf.Funded_NTB_R3M.sum()):,}","funded acquisition"),
        ("ETB Retention",fmt_pct(perf.Current_ETB_R3M_USDm.sum()/perf.Prior_ETB_R3M_USDm.sum()),"portfolio retention"),
        ("Relationship Value",fmt_money(perf.Relationship_Value_AEDm.sum(),'AED',2),"deposit + lending + NFI"),
        ("RM Economics",fmt_money(perf.RM_Economics_AEDm.sum(),'AED',2),"after direct RM cost"),
    ]
    labels={'RM':'RM','Branch':'Branch','Role':'Role','Current_R3M_Avg_CASA_USDm':'R3M Avg CASA','Target_R3M_CASA_USDm':'Target','R3M_Target_Attainment':'Target Attainment','R3M_Growth_pct':'R3M Growth','ETB_Retention':'ETB Retention','Funded_NTB_R3M':'Funded NTB R3M','Performance_Index':'Index','Performance_Band':'Band','Primary_Driver':'Primary Driver'}
    formats={'Current_R3M_Avg_CASA_USDm':fmt_money,'Target_R3M_CASA_USDm':fmt_money,'R3M_Target_Attainment':fmt_pct,'R3M_Growth_pct':fmt_pct,'ETB_Retention':fmt_pct,'Funded_NTB_R3M':lambda v:f"{int(v):,}",'Performance_Index':lambda v:f"{float(v):.0f}",'Performance_Band':lambda v:chip(v)}
    links={'RM':lambda r:qlink('rm360',r.RM,state,rm=r.RM),'Branch':lambda r:qlink('branch',r.Branch,state,branch=r.Branch)}
    target_control='<div class="info"><b>Target control:</b> performance uses only the latest APPROVED target version for the selected RM and period. Draft, pending and rejected revisions remain in Target Management and do not affect this view.</div>'
    return header("RM Performance","The performance table combines sustainable portfolio delivery, customer development, economics, cost efficiency, controls and service into an explainable management index. Select any RM to see the calculation beneath the composite.",state)+portfolio_slice_banner(state)+target_control+cards(items)+section("RM performance table","Every displayed column has a defined business meaning and can be traced into RM 360.")+table_html(perf,['RM','Branch','Role','Current_R3M_Avg_CASA_USDm','Target_R3M_CASA_USDm','R3M_Target_Attainment','R3M_Growth_pct','ETB_Retention','Funded_NTB_R3M','Performance_Index','Performance_Band','Primary_Driver'],labels,formats,links,40)+end_section()+portfolio_slice_section(state)


def rm360_page(state):
    perf=governed_perf(state['mode'],state['period'])
    if state['rm'] not in perf.RM.values: rm=perf.RM.iloc[0]
    else: rm=state['rm']
    r=perf[perf.RM.eq(rm)].iloc[0]
    cust=aggregate_customer_period(state['mode'],state['period'],DATA); cust=cust[cust.RM.eq(rm)].copy()
    if state['segment']!='All Segments': cust=cust[cust.Segment.eq(state['segment'])]
    if state['cohort']!='All Cohorts': cust=cust[cust.Cohort.eq(state['cohort'])]
    if state['quality']!='All Portfolio Quality': cust=cust[cust.Risk_Stage.eq(state['quality'])]
    tr=governed_trend(state['mode'],state['period'],rm=rm)
    tab=state.get('tab','performance')
    kv=f'''<div class="kv"><div class="item"><div class="kk">RM Code</div><div class="vv">{escape(r.Employee_ID)}</div></div><div class="item"><div class="kk">Role</div><div class="vv">{escape(r.Role)}</div></div><div class="item"><div class="kk">Branch</div><div class="vv">{qlink('branch',r.Branch,state,branch=r.Branch)}</div></div><div class="item"><div class="kk">Manager</div><div class="vv">{escape(r.Manager)}</div></div><div class="item"><div class="kk">Performance</div><div class="vv">{r.Performance_Index:.0f} · {chip(r.Performance_Band)}</div></div></div>'''
    tabs=[('performance','Performance'),('portfolio','Portfolio & Drivers'),('economics','Economics & Cost'),('quality','Portfolio Quality'),('explain','Explainability')]
    tabhtml='<div class="tabs">'+''.join(f'<a class="{"active" if tab==k else ""}" href="/?{urlencode({**{x:y for x,y in state.items() if x in {"mode","period","branch","role","date","rm","rm_scope","segment","cohort","quality","perf_band"}},"view":"rm360","rm":rm,"tab":k})}">{lbl}</a>' for k,lbl in tabs)+'</div>'
    summary=cards([
        ("R3M Avg CASA",fmt_money(r.Current_R3M_Avg_CASA_USDm),f"prior R3M {fmt_money(r.Prior_R3M_Avg_CASA_USDm)}"),
        ("R3M Target",fmt_money(r.Target_R3M_CASA_USDm),f"approved · attainment {fmt_pct(r.R3M_Target_Attainment)}"),
        ("PE CASA",fmt_money(r.PE_CASA_USDm),f"net movement {signed_money(r.Net_Movement_USDm)}"),
        ("Advances",fmt_money(r.Advances_AEDm,'AED'),"period-end lending"),
        ("Funded NTB R3M",f"{int(r.Funded_NTB_R3M):,}",f"persistent {int(r.Persistent_Funded_NTB_R3M)}"),
        ("ETB Retention",fmt_pct(r.ETB_Retention),"existing book retention"),
        ("Relationship Contribution",fmt_money(r.Relationship_Contribution_AEDm,'AED',2),"after customer CTS"),
        ("RM Economics",fmt_money(r.RM_Economics_AEDm,'AED',2),"after direct RM cost"),
    ])
    content=''
    if tab=='performance':
        sb=score_breakdown(r)
        formats={'Actual':lambda v:fmt_num(v,2),'Target / Benchmark':lambda v:fmt_num(v,2),'Points':lambda v:fmt_num(v,1),'Weight %':lambda v:fmt_pct(v,0,True),'Weighted Contribution':lambda v:fmt_num(v,2)}
        tb=target_basis_display(r)
        ta=target_audit_row(state['mode'],state['period'],r.Branch,rm)
        ta_formats={'Approved Value':fmt_money,'Status':lambda v:approved_target_status_chip(v)}
        content=section("Performance calculation","The composite is decomposed into actual, target/benchmark, points, weight and weighted contribution.")+table_html(sb,['ID','Measure','Actual','Target / Benchmark','Points','Weight %','Calculation','Weighted Contribution'],formats=formats,max_rows=20)+end_section()+section("Approved target & audit","Only an APPROVED target version feeds performance. A pending revision remains outside the score until the authorised checker approves it.")+table_html(ta,['Target','Approved Value','Version','Effective From','Effective To','Approved By','Approval Date','Status'],formats=ta_formats,max_rows=5)+end_section()+section("Reference target basis","The model can calculate a transparent reference target from the prior sustainable book and explicit factors. This is a decision-support reference; the approved target register is the official target used above.")+table_html(tb,['Target Component','Value','Meaning'],max_rows=20)+end_section()+section("Five-period trajectory").replace('<div class="section">','<div class="section">')+f'<div class="panel">{svg_line(tr,"Period",[("R3M_Avg_CASA_USDm","R3M Avg CASA"),("R3M_Target_USDm","Approved Target")])}</div>'+end_section()
    elif tab=='portfolio':
        cust2=cust.copy(); cust2['AbsMove']=cust2.Movement_USDm.abs(); cust2=cust2.sort_values('AbsMove',ascending=False).drop(columns='AbsMove')
        labels={'Customer':'Customer','CIF':'CIF','Cohort':'Cohort','Segment':'Segment','Deposits_USDm':'Deposits','Avg_Deposits_USDm':'Average Deposits','Advances_AEDm':'Advances','Movement_USDm':'Movement','Movement_Reason':'Movement Driver','Relationship_Contribution_AEDm':'Relationship Contribution'}
        formats={'Deposits_USDm':fmt_money,'Avg_Deposits_USDm':fmt_money,'Advances_AEDm':lambda v:fmt_money(v,'AED'),'Movement_USDm':lambda v:signed_money(v),'Relationship_Contribution_AEDm':lambda v:fmt_money(v,'AED',2)}
        links={'Customer':lambda rr:qlink('customer',rr.Customer,state,rm=rm,cif=rr.CIF)}
        bridge=pd.DataFrame({'Movement':['Organic','Transfer','Maturity / Scheduled Outflow','New Funding','Net Movement'],'USDm':[r.Organic_Movement_USDm,r.Transfer_Adjustment_USDm,r.Maturity_Runoff_USDm,r.New_Funding_USDm,r.Net_Movement_USDm]})
        content=section("Movement bridge","Administrative transfer is separated from organic movement.")+table_html(bridge,['Movement','USDm'],formats={'USDm':lambda v:signed_money(v)},max_rows=10)+end_section()+section("Customer drivers","Select any customer for account/facility/Trade detail.")+table_html(cust2,['Customer','CIF','Cohort','Segment','Deposits_USDm','Avg_Deposits_USDm','Advances_AEDm','Movement_USDm','Movement_Reason','Relationship_Contribution_AEDm'],labels,formats,links,30)+end_section()
    elif tab=='economics':
        act=cost_activity_table(state['mode'],state['period'],DATA,rm=rm)
        econ=pd.DataFrame({'Component':['Deposit Funding Value','Lending Contribution','Fees / NFI','Relationship Value','Customer Cost-to-Serve','Relationship Contribution','Direct RM Cost','RM Economics'],'AEDm':[r.Deposit_Funding_Value_AEDm,r.Lending_Contribution_AEDm,r.NFI_AEDm,r.Relationship_Value_AEDm,-r.Cost_to_Serve_AEDm,r.Relationship_Contribution_AEDm,-r.Direct_RM_Cost_AEDm,r.RM_Economics_AEDm]})
        emp=employee_cost_breakdown(state['mode'],state['period'],DATA,rm=rm)
        ec_labels={'Base_Salary_AEDm':'Base Salary','Fixed_Allowances_AEDm':'Fixed Allowances','Medical_Insurance_AEDm':'Medical / Insurance','Employer_Benefits_AEDm':'Employer Benefits','EOS_Accrual_AEDm':'EOS / Gratuity Accrual','Visa_Other_Direct_AEDm':'Visa / Other Direct','Direct_RM_Cost_AEDm':'Total Direct RM Cost'}
        ec_formats={c:(lambda v:fmt_money(v,'AED',3)) for c in ['Base_Salary_AEDm','Fixed_Allowances_AEDm','Medical_Insurance_AEDm','Employer_Benefits_AEDm','EOS_Accrual_AEDm','Visa_Other_Direct_AEDm','Direct_RM_Cost_AEDm']}
        ci=pd.DataFrame({'Component':['Attributable Relationship Value','Direct RM Employee Cost','Employee Cost-to-Income','Customer Cost-to-Serve','RM Economics'],'Value':[fmt_money(r.Relationship_Value_AEDm,'AED',3),fmt_money(r.Direct_RM_Cost_AEDm,'AED',3),fmt_pct(r.Cost_to_Income_R3M),fmt_money(r.Cost_to_Serve_AEDm,'AED',3),fmt_money(r.RM_Economics_AEDm,'AED',3)]})
        content=section("Relationship and RM economics","Value and cost are shown in separate layers so management can see exactly where the RM economics comes from.")+table_html(econ,['Component','AEDm'],formats={'AEDm':lambda v:fmt_money(v,'AED',3)},max_rows=20)+end_section()+section("RM cost-to-income breakdown","Employee C/I uses direct RM employee cost against attributable relationship value. Customer CTS remains a separate relationship-cost layer.")+table_html(ci,['Component','Value'],max_rows=10)+end_section()+section("Direct RM cost breakdown","Direct employee cost components shown by RM for the selected reporting period.")+table_html(emp,['Base_Salary_AEDm','Fixed_Allowances_AEDm','Medical_Insurance_AEDm','Employer_Benefits_AEDm','EOS_Accrual_AEDm','Visa_Other_Direct_AEDm','Direct_RM_Cost_AEDm'],ec_labels,ec_formats,max_rows=5)+end_section()+section("Cost-to-serve drivers","Attributed through explicit activity volume × unit cost.")+table_html(act,['Activity','Activity Count','Unit Cost AED','Attributed Cost AED'],formats={'Activity Count':lambda v:f"{int(v):,}",'Unit Cost AED':lambda v:f"AED {float(v):,.0f}",'Attributed Cost AED':lambda v:f"AED {float(v):,.0f}"},max_rows=20)+end_section()
    elif tab=='quality':
        q=pd.DataFrame({'Measure':['Stage 2','Stage 3','Impairment','Controls Score','Service Score','Data Completeness'],'Value':[fmt_pct(r.Stage2_pct,1,True),fmt_pct(r.Stage3_pct,1,True),fmt_money(r.Impairment_AEDm,'AED',3),f"{r.Control_Score:.0f}",f"{r.Service_Score:.0f}",fmt_pct(r.Data_Completeness)]})
        content=section("Portfolio quality & controls").replace('<div class="section">','<div class="section">')+table_html(q,['Measure','Value'],max_rows=20)+end_section()+f'<div class="info">Portfolio quality is presented alongside commercial delivery so management can see whether growth is sustainable and controlled.</div>'
    else:
        actions=management_action_table(r)
        content=section("Management actions","The output of the product is a management decision/action, not only a score.")+table_html(actions,list(actions.columns),max_rows=20)+end_section()+f'<div class="info"><b>Traceability:</b> UAE → Branch → RM → CIF → Account / Facility / Trade-NFI. The Performance tab shows the target build and full score decomposition.</div>' 
    return header(f"RM 360 · {rm}","One RM view connecting portfolio ownership, sustainable performance, customer drivers, relationship economics, cost, portfolio quality and management action.",state)+kv+summary+tabhtml+content


def branch_page(state):
    branch=state['branch'] if state['branch']!='All UAE' else BRANCHES[0]
    full_perf=governed_perf(state['mode'],state['period'])
    full_branch_perf=full_perf[full_perf.Branch.eq(branch)].copy()
    bp=governed_branch_performance(state['mode'],state['period'],full_branch_perf)
    if bp.empty:
        return header(f"Branch Performance · {branch}","Branch roll-up from the same RM/customer facts, with approved targets and whole-Branch economics.",state)+'<div class="empty">No Branch data for the selected period.</div>'
    b=bp[bp.Branch.eq(branch)].iloc[0]
    rms=filtered_perf(state)
    rms=rms[rms.Branch.eq(branch)].copy().sort_values('Performance_Index',ascending=False)
    bridge=branch_population_bridge(state['mode'],state['period'],DATA); bridge=bridge[bridge.Branch.eq(branch)]
    tr=governed_trend(state['mode'],state['period'],branch=branch)
    ci=branch_cost_to_income_breakdown(state['mode'],state['period'],DATA,full_branch_perf)
    ci=ci[ci.Branch.eq(branch)]
    crow=ci.iloc[0]

    approved_target=float(b.Approved_Branch_Target_USDm) if pd.notna(b.Approved_Branch_Target_USDm) else np.nan
    allocated=float(b.Allocated_RM_Target_USDm) if pd.notna(b.Allocated_RM_Target_USDm) else np.nan
    unallocated=float(b.Unallocated_Target_USDm) if pd.notna(b.Unallocated_Target_USDm) else np.nan
    coverage=float(b.Allocation_Coverage) if pd.notna(b.Allocation_Coverage) else np.nan
    items=[
        ("Active RMs",str(int(b.Active_RMs)),"branch RM/SRM population"),
        ("R3M Avg CASA",fmt_money(b.R3M_Avg_CASA_USDm),"sustainable book"),
        ("Approved Branch Target",fmt_money(approved_target),f"V{int(b.Target_Version)}" if pd.notna(b.Target_Version) else "no approved target"),
        ("Target Attainment",fmt_pct(b.Branch_Target_Attainment),"actual ÷ approved Branch target"),
        ("RM Allocation Coverage",fmt_pct(coverage),f"unallocated {fmt_money(unallocated)}"),
        ("Total Branch OPEX",fmt_money(crow.Total_Branch_OPEX_AEDm,'AED',2),"people + premises + other OPEX"),
        ("Branch C/I",fmt_pct(b.Branch_Cost_to_Income),"whole-Branch OPEX ÷ relationship value"),
        ("Branch Index",f"{b.Branch_Performance_Index:.0f}",b.Performance_Band),
    ]
    labels={'RM':'RM','Role':'Role','Current_R3M_Avg_CASA_USDm':'R3M Avg CASA','Target_R3M_CASA_USDm':'Approved RM Target','R3M_Target_Attainment':'Target Attainment','Funded_NTB_R3M':'Funded NTB','Relationship_Contribution_AEDm':'Relationship Contribution','Performance_Index':'Index','Performance_Band':'Band'}
    formats={'Current_R3M_Avg_CASA_USDm':fmt_money,'Target_R3M_CASA_USDm':fmt_money,'R3M_Target_Attainment':fmt_pct,'Funded_NTB_R3M':lambda v:f"{int(v):,}",'Relationship_Contribution_AEDm':lambda v:fmt_money(v,'AED',2),'Performance_Index':lambda v:f"{float(v):.0f}",'Performance_Band':lambda v:chip(v)}
    links={'RM':lambda r:qlink('rm360',r.RM,state,rm=r.RM)}

    allocation=pd.DataFrame([{
        'Approved_Branch_Target_USDm':approved_target,
        'Allocated_RM_Target_USDm':allocated,
        'Unallocated_Target_USDm':unallocated,
        'Allocation_Coverage':coverage,
    }])
    allocation_labels={'Approved_Branch_Target_USDm':'Approved Branch Target','Allocated_RM_Target_USDm':'Approved RM Allocations','Unallocated_Target_USDm':'Unallocated / BM Management','Allocation_Coverage':'Allocation Coverage'}
    allocation_formats={'Approved_Branch_Target_USDm':fmt_money,'Allocated_RM_Target_USDm':fmt_money,'Unallocated_Target_USDm':fmt_money,'Allocation_Coverage':fmt_pct}

    ci_labels={
        'Relationship_Value_AEDm':'Relationship Value',
        'People_Cost_AEDm':'People Cost — all Branch staff incl. RMs',
        'Premises_Occupancy_AEDm':'Premises & Occupancy',
        'Other_Operating_Support_AEDm':'Other Operating & Support',
        'Total_Branch_OPEX_AEDm':'Total Branch OPEX',
        'Branch_Cost_to_Income':'Branch C/I',
        'Fully_Loaded_Branch_Economics_AEDm':'Fully-loaded Branch Economics',
        'Customer_CTS_Attribution_AEDm':'Customer CTS Attribution',
    }
    ci_formats={c:(lambda v:fmt_money(v,'AED',2)) for c in ['Relationship_Value_AEDm','People_Cost_AEDm','Premises_Occupancy_AEDm','Other_Operating_Support_AEDm','Total_Branch_OPEX_AEDm','Fully_Loaded_Branch_Economics_AEDm','Customer_CTS_Attribution_AEDm']}; ci_formats['Branch_Cost_to_Income']=fmt_pct
    cost_note=("People Cost includes RMs plus other Branch staff. Premises & Occupancy covers rent/lease, utilities and physical-Branch costs. "
               "Other Operating & Support captures technology, administration, operations, depreciation and approved shared support. "
               "Customer CTS is an attribution lens and is not added again to whole-Branch OPEX.")
    return (header(f"Branch Performance · {branch}","Branch roll-up from the same RM/customer facts, with approved targets, allocation coverage and a simple whole-Branch cost view.",state)
            +portfolio_slice_banner(state)+cards(items)
            +section("Approved target allocation","Branch target and RM allocations are separate governed records. Any unallocated/BM management amount remains explicit rather than being forced into RM targets.")
            +table_html(allocation,['Approved_Branch_Target_USDm','Allocated_RM_Target_USDm','Unallocated_Target_USDm','Allocation_Coverage'],allocation_labels,allocation_formats,max_rows=5)+end_section()
            +section("Five-period branch trajectory","Actual R3M is compared with the approved RM target roll-up for the selected Branch.")
            +f'<div class="panel">{svg_line(tr,"Period",[("R3M_Avg_CASA_USDm","R3M Avg CASA"),("R3M_Target_USDm","Approved RM Target Roll-up")])}</div>'+end_section()
            +section("Whole-Branch OPEX",cost_note)
            +table_html(ci,['Relationship_Value_AEDm','People_Cost_AEDm','Premises_Occupancy_AEDm','Other_Operating_Support_AEDm','Total_Branch_OPEX_AEDm','Branch_Cost_to_Income','Fully_Loaded_Branch_Economics_AEDm','Customer_CTS_Attribution_AEDm'],ci_labels,ci_formats,max_rows=5)+end_section()
            +section("RM team","Role, RM and Performance Band filters refine the team list. Each RM uses only its latest APPROVED target version.")
            +table_html(rms,['RM','Role','Current_R3M_Avg_CASA_USDm','Target_R3M_CASA_USDm','R3M_Target_Attainment','Funded_NTB_R3M','Relationship_Contribution_AEDm','Performance_Index','Performance_Band'],labels,formats,links,30)+end_section()
            +section("Population bridge","The Branch management total keeps RM-attributed, BM-owned, Unassigned and Margins & Sundries distinct.")
            +table_html(bridge,list(bridge.columns),formats={c:(fmt_money if c.endswith('USDm') else None) for c in bridge.columns if c.endswith('USDm')},max_rows=10)+end_section()+portfolio_slice_section(state))


def customer_page(state):
    cust=filtered_customer_period(state)
    if cust.empty:
        return header("Customer & Relationship","Customer/CIF detail connects the owned relationship to deposit accounts, lending facilities and Trade/NFI while preserving RM and Branch context.",state)+portfolio_slice_banner(state)+ '<div class="empty">No customer relationships match the selected management / portfolio filters.</div>'
    if state['cif'] and state['cif'] in cust.CIF.values: row=cust[cust.CIF.eq(state['cif'])].iloc[0]
    else:
        subset=cust[cust.RM.eq(state['rm'])]
        row=(subset.iloc[0] if not subset.empty else cust.iloc[0]); state=dict(state); state['cif']=row.CIF; state['rm']=row.RM
    cif=row.CIF
    ar=account_rows(cust[cust.CIF.eq(cif)]); fr=facility_rows(cust[cust.CIF.eq(cif)]); trd=trade_rows(cust[cust.CIF.eq(cif)])
    items=[("Deposits",fmt_money(row.Deposits_USDm),"period-end relationship deposits"),("Average Deposits",fmt_money(row.Avg_Deposits_USDm),"selected-period average"),("Advances",fmt_money(row.Advances_AEDm,'AED'),"facility outstanding"),("Relationship Value",fmt_money(row.Relationship_Value_AEDm,'AED',3),"deposit + lending + NFI"),("Customer CTS",fmt_money(row.Cost_to_Serve_AEDm,'AED',3),"activity-attributed"),("Relationship Contribution",fmt_money(row.Relationship_Contribution_AEDm,'AED',3),"after CTS"),("Movement",signed_money(row.Movement_USDm),row.Movement_Reason),("Cohort",row.Cohort,f"Opened {pd.Timestamp(row.Open_Date):%d %b %Y}")]
    kv=f'''<div class="kv"><div class="item"><div class="kk">Customer</div><div class="vv">{escape(row.Customer)}</div></div><div class="item"><div class="kk">CIF</div><div class="vv">{escape(row.CIF)}</div></div><div class="item"><div class="kk">RM</div><div class="vv">{qlink('rm360',row.RM,state,rm=row.RM)}</div></div><div class="item"><div class="kk">Branch</div><div class="vv">{qlink('branch',row.Branch,state,branch=row.Branch)}</div></div><div class="item"><div class="kk">Segment / Residency</div><div class="vv">{escape(row.Segment)} · {escape(row.R_NR)}</div></div></div>'''
    a_labels={'Account_No':'Account No','Product':'Product','Currency':'Currency','Cohort':'Cohort','Open_Date':'Open Date','Balance_USDm':'Balance','Avg_Balance_USDm':'Average Balance'}
    a_formats={'Balance_USDm':fmt_money,'Avg_Balance_USDm':fmt_money}
    def acc_link(rr):
        q={k:v for k,v in state.items() if k in {'mode','period','branch','role','rm','rm_scope','segment','cohort','quality','perf_band','cif'}}; q.update({'view':'customer','rm':row.RM,'cif':cif,'account':rr.Account_No}); return f'<a class="link" href="/?{urlencode(q)}">{escape(rr.Account_No)}</a>'
    account_detail=''
    if state.get('account') and not ar.empty and state['account'] in ar.Account_No.values:
        a=ar[ar.Account_No.eq(state['account'])].iloc[0]
        account_detail=f'<div class="info"><b>Account {escape(a.Account_No)}</b> · {escape(a.Product)} · {escape(a.Currency)} · Balance {fmt_money(a.Balance_USDm)} · Average {fmt_money(a.Avg_Balance_USDm)} · Opened {pd.Timestamp(a.Open_Date):%d %b %Y}</div>'
    return header("Customer & Relationship","Customer/CIF detail connects the owned relationship to deposit accounts, lending facilities and Trade/NFI while preserving RM and Branch context.",state)+portfolio_slice_banner(state)+kv+cards(items)+section("Deposit accounts","Select an account number for account-level detail.")+table_html(ar,['Account_No','Product','Currency','Cohort','Open_Date','Balance_USDm','Avg_Balance_USDm'],a_labels,a_formats,{'Account_No':acc_link},30)+account_detail+end_section()+section("Lending facilities","A customer with no lending is a valid state and renders cleanly.")+table_html(fr,['Facility_No','Outstanding_AEDm','Maturity_Date','Risk_Stage'],labels={'Facility_No':'Facility No','Outstanding_AEDm':'Outstanding','Maturity_Date':'Maturity','Risk_Stage':'Risk Stage'},formats={'Outstanding_AEDm':lambda v:fmt_money(v,'AED')},max_rows=30)+end_section()+section("Trade / NFI","Attributable non-funded activity where present.")+table_html(trd,['Transaction_Ref','Type','Income_AEDm'],labels={'Transaction_Ref':'Transaction Ref','Type':'Type','Income_AEDm':'Income'},formats={'Income_AEDm':lambda v:fmt_money(v,'AED',3)},max_rows=30)+end_section()


def cost_page(state):
    perf=filtered_perf(state)
    if perf.empty:
        return header("Cost & Economics","UAE Network → Branch → RM cost and value view, with a simple whole-Branch OPEX structure and separate RM economics.",state)+portfolio_slice_banner(state)+ '<div class="empty">No RMs match the selected assessment scope.</div>'
    branch_cost_perf=governed_perf(state['mode'],state['period'])
    if state['branch']!='All UAE': branch_cost_perf=branch_cost_perf[branch_cost_perf.Branch.eq(state['branch'])]
    ci=branch_cost_to_income_breakdown(state['mode'],state['period'],DATA,branch_cost_perf)
    act=cost_activity_table(state['mode'],state['period'],DATA,branch=None if state['branch']=='All UAE' else state['branch'])
    emp_cost=employee_cost_breakdown(state['mode'],state['period'],DATA,branch=None if state['branch']=='All UAE' else state['branch'])
    if not emp_cost.empty: emp_cost=emp_cost[emp_cost.RM.isin(perf.RM)]

    network_relationship=float(ci.Relationship_Value_AEDm.sum())
    network_cts=float(ci.Customer_CTS_Attribution_AEDm.sum())
    network_people=float(ci.People_Cost_AEDm.sum())
    network_premises=float(ci.Premises_Occupancy_AEDm.sum())
    network_other=float(ci.Other_Operating_Support_AEDm.sum())
    network_total=float(ci.Total_Branch_OPEX_AEDm.sum())
    network_ci=network_total/network_relationship if network_relationship>0 else np.nan
    network_econ=network_relationship-network_total
    items=[
        ("Relationship Value",fmt_money(network_relationship,'AED',2),"deposit + lending + NFI"),
        ("People Cost",fmt_money(network_people,'AED',2),"all Branch people including RMs"),
        ("Premises & Occupancy",fmt_money(network_premises,'AED',2),"rent/lease + utilities + physical costs"),
        ("Other Operating & Support",fmt_money(network_other,'AED',2),"technology + admin + operations + shared"),
        ("Total Branch OPEX",fmt_money(network_total,'AED',2),"people + premises + other"),
        ("UAE Network C/I",fmt_pct(network_ci),"whole-Branch OPEX ÷ relationship value"),
        ("Fully-loaded Economics",fmt_money(network_econ,'AED',2),"relationship value − whole-Branch OPEX"),
        ("Customer CTS Attribution",fmt_money(network_cts,'AED',2),"analytical allocation lens; not added again"),
    ]

    network_row={
        'Branch':'UAE Network','Relationship_Value_AEDm':network_relationship,
        'People_Cost_AEDm':network_people,'Premises_Occupancy_AEDm':network_premises,
        'Other_Operating_Support_AEDm':network_other,'Total_Branch_OPEX_AEDm':network_total,
        'Branch_Cost_to_Income':network_ci,'Fully_Loaded_Branch_Economics_AEDm':network_econ,
        'Customer_CTS_Attribution_AEDm':network_cts,
    }
    ci_show=pd.concat([pd.DataFrame([network_row]),ci],ignore_index=True)
    ci_labels={'Branch':'Level / Branch','Relationship_Value_AEDm':'Relationship Value','People_Cost_AEDm':'People Cost','Premises_Occupancy_AEDm':'Premises & Occupancy','Other_Operating_Support_AEDm':'Other Operating & Support','Total_Branch_OPEX_AEDm':'Total Branch OPEX','Branch_Cost_to_Income':'Cost / Income','Fully_Loaded_Branch_Economics_AEDm':'Fully-loaded Economics','Customer_CTS_Attribution_AEDm':'Customer CTS Attribution'}
    ci_formats={c:(lambda v:fmt_money(v,'AED',2)) for c in ['Relationship_Value_AEDm','People_Cost_AEDm','Premises_Occupancy_AEDm','Other_Operating_Support_AEDm','Total_Branch_OPEX_AEDm','Fully_Loaded_Branch_Economics_AEDm','Customer_CTS_Attribution_AEDm']}; ci_formats['Branch_Cost_to_Income']=fmt_pct
    ci_links={'Branch':lambda r: (escape(r.Branch) if r.Branch=='UAE Network' else qlink('branch',r.Branch,state,branch=r.Branch))}

    econ=perf[['RM','Branch','Relationship_Value_AEDm','Cost_to_Serve_AEDm','Relationship_Contribution_AEDm','Direct_RM_Cost_AEDm','RM_Economics_AEDm','Cost_to_Income_R3M']].sort_values('RM_Economics_AEDm',ascending=False)
    formats={c:(lambda v:fmt_money(v,'AED',2)) for c in ['Relationship_Value_AEDm','Cost_to_Serve_AEDm','Relationship_Contribution_AEDm','Direct_RM_Cost_AEDm','RM_Economics_AEDm']}; formats['Cost_to_Income_R3M']=fmt_pct
    labels={'Relationship_Value_AEDm':'Relationship Value','Cost_to_Serve_AEDm':'Customer CTS','Relationship_Contribution_AEDm':'Relationship Contribution','Direct_RM_Cost_AEDm':'Direct RM Cost','RM_Economics_AEDm':'RM Economics','Cost_to_Income_R3M':'Employee C/I'}
    links={'RM':lambda r:qlink('rm360',r.RM,state,rm=r.RM),'Branch':lambda r:qlink('branch',r.Branch,state,branch=r.Branch)}
    ec_labels={'Base_Salary_AEDm':'Base Salary','Fixed_Allowances_AEDm':'Fixed Allowances','Medical_Insurance_AEDm':'Medical / Insurance','Employer_Benefits_AEDm':'Employer Benefits','EOS_Accrual_AEDm':'EOS / Gratuity Accrual','Visa_Other_Direct_AEDm':'Visa / Other Direct','Direct_RM_Cost_AEDm':'Total Direct RM Cost'}
    ec_formats={c:(lambda v:fmt_money(v,'AED',3)) for c in ['Base_Salary_AEDm','Fixed_Allowances_AEDm','Medical_Insurance_AEDm','Employer_Benefits_AEDm','EOS_Accrual_AEDm','Visa_Other_Direct_AEDm','Direct_RM_Cost_AEDm']}

    return (header("Cost & Economics","UAE Network → Branch → RM value and cost, using three management OPEX buckets for the whole Branch and a separate RM economics lens.",state)
            +portfolio_slice_banner(state)+cards(items)
            +section("Whole-Branch OPEX by Branch","People Cost includes all Branch employees including RMs. Premises & Occupancy includes rent/lease, utilities and physical-Branch costs. Other Operating & Support includes technology, administration, operations, depreciation and approved shared support. Customer CTS is shown separately as an allocation lens so it is not double-counted.")
            +table_html(ci_show,['Branch','Relationship_Value_AEDm','People_Cost_AEDm','Premises_Occupancy_AEDm','Other_Operating_Support_AEDm','Total_Branch_OPEX_AEDm','Branch_Cost_to_Income','Fully_Loaded_Branch_Economics_AEDm','Customer_CTS_Attribution_AEDm'],ci_labels,ci_formats,ci_links,20)+end_section()
            +section("RM economics","Role, RM and Performance Band filters refine the RM economics view. Select an RM to open RM 360 and see approved target, customer drivers, direct employee cost and C/I.")
            +table_html(econ,['RM','Branch','Relationship_Value_AEDm','Cost_to_Serve_AEDm','Relationship_Contribution_AEDm','Direct_RM_Cost_AEDm','Cost_to_Income_R3M','RM_Economics_AEDm'],labels,formats,links,30)+end_section()
            +section("Direct RM employee cost","RM-level salary/allowance/benefit components remain visible separately. At Branch level these RM costs roll into the People Cost bucket together with other Branch staff.")
            +table_html(emp_cost,['RM','Branch','Role','Base_Salary_AEDm','Fixed_Allowances_AEDm','Medical_Insurance_AEDm','Employer_Benefits_AEDm','EOS_Accrual_AEDm','Visa_Other_Direct_AEDm','Direct_RM_Cost_AEDm'],ec_labels,ec_formats,{'RM':lambda r:qlink('rm360',r.RM,state,rm=r.RM)},40)+end_section()
            +section("Customer cost-to-serve attribution","Activity volume × unit cost provides a relationship-level allocation lens. In production the unit-cost pool must reconcile to Finance/operations cost pools before CTS is used formally.")
            +table_html(act,['RM','Branch','Activity','Activity Count','Unit Cost AED','Attributed Cost AED'],formats={'Activity Count':lambda v:f"{int(v):,}",'Unit Cost AED':lambda v:f"AED {float(v):,.0f}",'Attributed Cost AED':lambda v:f"AED {float(v):,.0f}"},max_rows=80)+end_section()+portfolio_slice_section(state))


def target_management_page(state):
    mode=state['mode']; period=state['period']; branch=state['branch']; metric=state['target_metric']
    metric_meta=TARGET_METRICS[metric]
    access=state['target_role']; user=TARGET_ACCESS[access]
    rows=rows_for_scope(mode=mode,period=period,branch=None if branch=='All UAE' else branch,metric=metric)
    pending=[r for r in rows if r.get('Status')=='PENDING_APPROVAL']

    # Latest approved records only for the operating summary.
    approved_branch=[]
    for br in BRANCHES:
        if branch!='All UAE' and br!=branch: continue
        rec=latest_approved(level='BRANCH',mode=mode,period=period,branch=br,metric=metric)
        if rec: approved_branch.append(rec)
    rm_map=latest_approved_rm_map(mode,period,metric)
    approved_rm=[r for r in rm_map.values() if branch=='All UAE' or r.get('Branch')==branch]
    branch_total=sum(float(r.get('TargetValue',0) or 0) for r in approved_branch)
    rm_total=sum(float(r.get('TargetValue',0) or 0) for r in approved_rm)
    unallocated=branch_total-rm_total if branch_total else np.nan
    coverage=rm_total/branch_total if branch_total>0 else np.nan

    items=[
        ('Approved Branch Target',fmt_money(branch_total),metric_meta['name']),
        ('Approved RM Allocations',fmt_money(rm_total),'latest approved RM versions'),
        ('Unallocated / BM Management',fmt_money(unallocated),'kept explicit; not forced to RMs'),
        ('Allocation Coverage',fmt_pct(coverage),'RM allocations ÷ Branch target'),
        ('Pending Approval',f"{len(pending):,}",'does not feed performance'),
        ('Approved Branch Records',f"{len(approved_branch):,}",'latest versions in scope'),
        ('Approved RM Records',f"{len(approved_rm):,}",'latest versions in scope'),
        ('Access',escape(user),'prototype role simulation'),
    ]

    notice=''
    if state.get('notice'):
        notice=f'<div class="info"><b>Target workflow:</b> {escape(state["notice"])}</div>'
    access_note=(f'<div class="access-box"><b>Current access:</b> {escape(user)}. '
                 'This selector exists only to demonstrate the workflow. In UBL production the role must come from SSO/Active Directory and be enforced again by the backend/database. '
                 '<b>Tableau remains read-only</b> and consumes only the approved-target view.</div>')

    # Latest approved register for the selected scope.
    latest_rows=[]
    latest_rows.extend(approved_branch)
    latest_rows.extend(sorted(approved_rm,key=lambda r:(r.get('Branch',''),r.get('RM',''))))
    latest_df=pd.DataFrame(latest_rows)
    if not latest_df.empty:
        latest_df=latest_df.rename(columns={'TargetLevel':'Level','TargetValue':'Target Value','EffectiveFrom':'Effective From','EffectiveTo':'Effective To','ApprovedBy':'Approved By','ApprovalDate':'Approval Date'})
        latest_df['Version']=latest_df['Version'].apply(lambda x:f"V{int(x)}")
    latest_formats={'Target Value':fmt_money,'Status':lambda v:approved_target_status_chip(v)}

    # Maker forms use the selected Branch; this keeps the workflow clear and prevents cross-Branch mis-entry.
    maker_html=''
    if access=='Maker':
        if branch=='All UAE':
            maker_html='<div class="warn"><b>Select a specific Branch</b> in the sidebar before creating or revising a Branch/RM target.</div>'
        else:
            ef,et=period_effective_dates(mode,period)
            br_rec=latest_approved(level='BRANCH',mode=mode,period=period,branch=branch,metric=metric)
            br_val=float(br_rec.get('TargetValue')) if br_rec else 0.0
            rm_options=eligible_rm_names(branch,state['role'])
            selected_rm=state['rm_scope'] if state['rm_scope']!='All RMs' and state['rm_scope'] in rm_options else ''
            rm_rec=latest_approved(level='RM',mode=mode,period=period,branch=branch,rm=selected_rm,metric=metric) if selected_rm else None
            rm_val=float(rm_rec.get('TargetValue')) if rm_rec else 0.0
            common=(f'<input type="hidden" name="view" value="targets"><input type="hidden" name="mode" value="{escape(mode)}">'
                    f'<input type="hidden" name="period" value="{escape(period)}"><input type="hidden" name="branch" value="{escape(branch)}">'
                    f'<input type="hidden" name="role" value="{escape(state["role"])}"><input type="hidden" name="rm_scope" value="{escape(state["rm_scope"])}"><input type="hidden" name="target_role" value="Maker">'
                    f'<input type="hidden" name="target_metric" value="{escape(metric)}"><input type="hidden" name="effective_from" value="{escape(ef)}"><input type="hidden" name="effective_to" value="{escape(et)}">')
            branch_form=(
                '<form class="target-form" method="post"><h3>Revise Branch target</h3><div class="target-muted">Creates a new pending version; the current approved target remains live until checker approval.</div>'
                +common+'<input type="hidden" name="action" value="create_target"><input type="hidden" name="target_level" value="BRANCH">'
                +f'<label>Branch</label><input value="{escape(branch)}" disabled><label>Metric</label><input value="{escape(metric_meta["name"])}" disabled>'
                +f'<label>Target value ({escape(metric_meta["unit"])})</label><input name="target_value" type="number" min="0.0001" step="0.0001" value="{br_val:.4f}" required>'
                +'<label>Reason for target / revision</label><textarea name="reason" required>Management target review</textarea><button type="submit">Submit Branch target for approval</button></form>'
            )
            if selected_rm:
                rm_form=(
                    '<form class="target-form" method="post"><h3>Revise RM target</h3><div class="target-muted">The RM is fixed by the cascaded RM Focus selection in the sidebar.</div>'
                    +common+'<input type="hidden" name="action" value="create_target"><input type="hidden" name="target_level" value="RM"><input type="hidden" name="rm" value="'+escape(selected_rm)+'">'
                    +f'<label>RM</label><input value="{escape(selected_rm)}" disabled><label>Metric</label><input value="{escape(metric_meta["name"])}" disabled>'
                    +f'<label>Target value ({escape(metric_meta["unit"])})</label><input name="target_value" type="number" min="0.0001" step="0.0001" value="{rm_val:.4f}" required>'
                    +'<label>Reason for target / revision</label><textarea name="reason" required>Management target review</textarea><button type="submit">Submit RM target for approval</button></form>'
                )
            else:
                rm_form='<div class="target-form"><h3>Revise RM target</h3><div class="warn"><b>Select an RM in RM Focus</b> to create or revise an RM target. The RM list is already restricted by the selected Branch and Role.</div></div>'
            maker_html='<div class="target-grid">'+branch_form+rm_form+'</div>'
    elif access=='Approver':
        if not pending:
            maker_html='<div class="info"><b>Approval queue:</b> no pending target revisions in the selected scope.</div>'
        else:
            blocks=[]
            for r in sorted(pending,key=lambda x:x.get('SubmittedAt',''),reverse=True):
                level=r.get('TargetLevel','')
                rm=r.get('RM') or '—'
                current=latest_approved(level=level,mode=mode,period=period,branch=r.get('Branch',''),rm=r.get('RM',''),metric=metric)
                current_val=float(current.get('TargetValue')) if current else np.nan
                proposed=float(r.get('TargetValue',0))
                meta=(f'<div><div class="target-strong">{escape(level.title())} · {escape(r.get("Branch",""))} · {escape(rm)}</div>'
                      f'<div class="target-muted">Current approved: {fmt_money(current_val)} · Proposed: {fmt_money(proposed)} · V{int(r.get("Version",1))}</div>'
                      f'<div class="target-muted">Reason: {escape(r.get("Reason",""))} · Submitted by {escape(r.get("CreatedBy",""))}</div></div>')
                hidden=(f'<input type="hidden" name="view" value="targets"><input type="hidden" name="mode" value="{escape(mode)}"><input type="hidden" name="period" value="{escape(period)}">'
                        f'<input type="hidden" name="branch" value="{escape(branch)}"><input type="hidden" name="role" value="{escape(state["role"])}"><input type="hidden" name="rm_scope" value="{escape(state["rm_scope"])}">'
                        f'<input type="hidden" name="target_role" value="Approver"><input type="hidden" name="target_metric" value="{escape(metric)}"><input type="hidden" name="target_id" value="{escape(r.get("TargetID",""))}">')
                actions=(f'<div class="approval-actions"><form method="post">{hidden}<input type="hidden" name="action" value="approve_target"><button class="action-btn" type="submit">Approve</button></form>'
                         f'<form method="post">{hidden}<input type="hidden" name="action" value="reject_target"><button class="action-btn reject" type="submit">Reject</button></form></div>')
                blocks.append(f'<div class="approval-row">{meta}{actions}</div>')
            maker_html='<div class="panel"><h3>Pending approval</h3><div class="panel-note">Only the designated checker can make a submitted target official.</div>'+''.join(blocks)+'</div>'
    else:
        maker_html='<div class="info"><b>View-only access.</b> You can review approved targets and history. Creating, approving or rejecting targets is not available for this role.</div>'

    # Audit history: latest activity first, including rejected and pending records.
    hist=pd.DataFrame(sorted(rows,key=lambda r:(r.get('SubmittedAt',''),int(r.get('Version',0) or 0)),reverse=True)[:40])
    if not hist.empty:
        hist=hist.rename(columns={'TargetLevel':'Level','TargetValue':'Target Value','SubmittedAt':'Submitted At','CreatedBy':'Created By','ApprovedBy':'Approved By','ApprovalDate':'Approval Date'})
        hist['Version']=hist['Version'].apply(lambda x:f"V{int(x)}")
    hist_formats={'Target Value':fmt_money,'Status':lambda v:approved_target_status_chip(v)}

    architecture='<div class="info"><b>Production architecture:</b> Target Management writes only to a product-owned target register. Maker → Pending Approval → Checker → Approved. Tableau connects read-only to an approved-target view; it does not write to core banking systems. Pending/rejected targets never enter performance calculations.</div>'
    return (header('Target Management','Governed Branch and RM target workflow with maker–checker approval, version history and a read-only Tableau consumption path.',state)
            +notice+access_note+cards(items)+section('Target workflow', 'Select the access simulation in the sidebar to see the Maker, Approver and Viewer experiences.')+maker_html+end_section()
            +section('Approved targets in scope','Only the latest approved version for each Branch/RM is shown here and consumed by the management performance layer.')
            +table_html(latest_df,['Level','Branch','RM','MetricName','Target Value','Version','Effective From','Effective To','Status','Approved By','Approval Date'],labels={'MetricName':'Metric'},formats=latest_formats,max_rows=40)+end_section()
            +section('Target audit history','Every proposal is retained. Approved, pending and rejected versions are auditable rather than overwritten.')
            +table_html(hist,['Level','Branch','RM','MetricName','Target Value','Version','Status','Created By','Submitted At','Approved By','Approval Date','Reason'],labels={'MetricName':'Metric'},formats=hist_formats,max_rows=40)+end_section()+architecture)


def methodology_page(state):
    mr=model_metric_register(); pl=period_logic_table(); pop=population_bridge_logic(); tm=tableau_semantic_model_register()
    formulas=[
        ("Current R3M Average CASA","Day-weighted average of the latest three monthly average-balance facts."),
        ("Prior R3M Average CASA","Immediately preceding non-overlapping three-month day-weighted window."),
        ("R3M Growth %","(Current R3M − Prior R3M) ÷ Prior R3M."),
        ("Management PE CASA","RM Attributed + BM Owned + Unassigned + Margins & Sundries."),
        ("Net Movement","Organic + Transfer Adjustment + Maturity / Scheduled Outflow + New Funding."),
        ("Approved R3M Target","Latest APPROVED target version for the selected Branch/RM, metric and period. Pending/rejected versions do not feed performance."),
        ("Reference Target Basis","Prior R3M + [Prior R3M × Base Strategy Growth × Branch Opportunity × Role × Availability × Tenure]; decision-support only until approved."),
        ("Performance Index","Σ(KPI Points × KPI Weight), with each KPI capped at 120 points."),
        ("Relationship Value","Deposit Funding Value + Lending Contribution + Attributable Fees/NFI."),
        ("Relationship Contribution","Relationship Value − Customer Cost-to-Serve."),
        ("Employee C/I","Direct RM Employee Cost ÷ Attributable Relationship Value."),
        ("RM Economics","Σ Relationship Contribution − Direct RM Employee Cost."),
        ("Branch OPEX","People Cost (all Branch staff incl. RMs) + Premises & Occupancy + Other Operating & Support."),
        ("Branch C/I","Total Branch OPEX ÷ Branch Relationship Value. Customer CTS is an allocation lens and is not added again."),
        ("Target Governance","Maker submits → Pending Approval → authorised Checker approves/rejects → only Approved_Targets feed Tableau."),
        ("Tableau Role","Read-only management/analytics consumption layer; no direct writes to core banking systems."),
        ("Daily Data Timing","Certified EOD business-date snapshot with Business Date and Published Date shown separately."),
        ("Daily Management","Operational portfolio/management pack only; sustainable employee performance remains Month/Quarter/R3M."),
        ("Filter Behaviour","Branch / Role / RM / Performance Band scope RM views. RM Focus cascades from the selected Branch and Role so only relevant RMs are shown. If an existing RM selection conflicts after a scope change, the user can align the scope or clear the RM filter before applying it. Segment / ETB-NTB / Portfolio Quality refine customer and relationship analysis while RM performance, targets and employee cost remain total RM measures."),
    ]
    fhtml='<div class="method-grid">'+''.join(f'<div class="panel"><h3>{escape(a)}</h3><div class="formula">{escape(b)}</div></div>' for a,b in formulas)+'</div>'
    return header("Methodology","The management product is designed so the calculation layer can move into a governed Tableau semantic model without rebuilding formulas independently by dashboard.",state)+section("Core formulas")+fhtml+end_section()+section("Metric register").replace('<div class="section">','<div class="section">')+table_html(mr,list(mr.columns),max_rows=40)+end_section()+section("Tableau-ready logical model","Dimensions/facts are separated by grain so Executive, Daily, Branch, RM and Customer views can consume the same governed calculations.")+table_html(tm,list(tm.columns),max_rows=30)+end_section()+section("Period logic").replace('<div class="section">','<div class="section">')+table_html(pl,list(pl.columns),max_rows=30)+end_section()+section("Population bridge logic").replace('<div class="section">','<div class="section">')+table_html(pop,list(pop.columns),max_rows=30)+end_section()+f'<div class="info"><b>Control framework:</b> permanent employee identity; effective-dated RM→Branch and CIF→RM ownership; target history; funded-NTB rule; revenue/cost attribution; controls and portfolio-quality rules; reconciliation; and data-quality monitoring.</div>'

def render_content(state):
    view=state['view']
    if view=='daily': return daily_page(state)
    if view=='rm-performance': return rm_performance_page(state)
    if view=='rm360': return rm360_page(state)
    if view=='branch': return branch_page(state)
    if view=='customer': return customer_page(state)
    if view=='cost': return cost_page(state)
    if view=='targets': return target_management_page(state)
    if view=='methodology': return methodology_page(state)
    return executive_page(state)


def render_page(params):
    state=resolve_state(params)
    content=render_content(state)
    rm_meta_json=json.dumps(RM_FILTER_META, ensure_ascii=False)
    period_context = state["date"] if state.get("view")=="daily" else state["period"]
    js=f"""
<script>
(function(){{
  const rmMeta={rm_meta_json};
  const periodContext={json.dumps(period_context)};
  const toast=()=>document.getElementById('loading-toast');
  const filterCheck=()=>document.getElementById('filter-check');
  function showLoading(title, sub){{
    const t=toast(); if(!t) return;
    const a=t.querySelector('[data-title]'); const b=t.querySelector('[data-sub]');
    if(a) a.textContent=title || 'Updating management view';
    if(b) b.textContent=sub || 'Applying the selected reporting scope';
    t.classList.add('show');
  }}
  function hideLoading(){{ const t=toast(); if(t) t.classList.remove('show'); }}
  function hideFilterCheck(){{ const p=filterCheck(); if(p) p.classList.remove('show'); }}
  function submitScope(form, sub){{
    hideFilterCheck();
    showLoading('Updating management view', sub || 'Applying the selected management scope');
    window.setTimeout(function(){{ if(form) form.requestSubmit(); }},60);
  }}
  function showScopeConflict(kind, rm, selectedValue, branchSel, roleSel, rmSel, form){{
    const meta=rmMeta[rm]; if(!meta) return false;
    const panel=filterCheck(); if(!panel) return false;
    const copy=panel.querySelector('[data-conflict-copy]');
    const primary=panel.querySelector('[data-use-rm]');
    const secondary=panel.querySelector('[data-use-scope]');
    const cancel=panel.querySelector('[data-cancel-conflict]');
    if(kind==='branch'){{
      copy.textContent=rm+' is mapped to '+meta.branch+' for '+periodContext+'. You selected '+selectedValue+'.';
      primary.textContent='Keep '+rm+' · use '+meta.branch;
      secondary.textContent='Use '+selectedValue+' · clear RM';
      primary.onclick=function(){{ branchSel.value=meta.branch; submitScope(form,'Aligning Branch to the selected RM'); }};
      secondary.onclick=function(){{ rmSel.value='All RMs'; submitScope(form,'Applying Branch and clearing the RM focus'); }};
    }} else {{
      copy.textContent=rm+' is '+meta.role+' for '+periodContext+'. You selected role '+selectedValue+'.';
      primary.textContent='Keep '+rm+' · use '+meta.role;
      secondary.textContent='Use '+selectedValue+' · clear RM';
      primary.onclick=function(){{ roleSel.value=meta.role; submitScope(form,'Aligning Role to the selected RM'); }};
      secondary.onclick=function(){{ rmSel.value='All RMs'; submitScope(form,'Applying Role and clearing the RM focus'); }};
    }}
    cancel.onclick=function(){{
      if(branchSel) branchSel.value=branchSel.dataset.appliedValue || 'All UAE';
      if(roleSel) roleSel.value=roleSel.dataset.appliedValue || 'All';
      if(rmSel) rmSel.value=rmSel.dataset.appliedValue || 'All RMs';
      hideFilterCheck();
    }};
    panel.classList.add('show');
    return true;
  }}
  function evaluateScopeChange(origin, form, branchSel, roleSel, rmSel){{
    const rm=rmSel ? rmSel.value : 'All RMs';
    if(!rm || rm==='All RMs' || !rmMeta[rm]){{ submitScope(form); return; }}
    const meta=rmMeta[rm];
    const branch=branchSel ? branchSel.value : 'All UAE';
    const role=roleSel ? roleSel.value : 'All';
    if(branch!=='All UAE' && branch!==meta.branch){{ showScopeConflict('branch',rm,branch,branchSel,roleSel,rmSel,form); return; }}
    if(role!=='All' && role!==meta.role){{ showScopeConflict('role',rm,role,branchSel,roleSel,rmSel,form); return; }}
    submitScope(form, origin==='rm' ? 'Applying RM focus' : 'Applying management scope');
  }}
  window.addEventListener('pageshow', hideLoading);
  document.addEventListener('DOMContentLoaded', function(){{
    hideLoading(); hideFilterCheck();
    const form=document.getElementById('management-filter-form');
    if(form){{
      form.addEventListener('submit', function(){{ showLoading('Updating management view','Applying filters and recalculating the selected scope'); }});
    }}
    const mode=document.getElementById('mode-select');
    if(mode){{
      mode.addEventListener('change', function(){{
        const u=new URL(window.location.href);
        u.searchParams.set('mode', mode.value);
        u.searchParams.delete('period');
        showLoading(mode.value==='Month' ? 'Switching to monthly view' : 'Switching to quarterly view','Loading the correct reporting periods');
        window.setTimeout(function(){{ window.location.assign(u.toString()); }},70);
      }});
    }}
    const branchSel=document.getElementById('branch-select');
    const roleSel=document.getElementById('role-select');
    const rmSel=document.getElementById('rm-scope-select') || document.getElementById('daily-rm-select');
    if(branchSel) branchSel.addEventListener('change',function(){{ evaluateScopeChange('branch',form,branchSel,roleSel,rmSel); }});
    if(roleSel) roleSel.addEventListener('change',function(){{ evaluateScopeChange('role',form,branchSel,roleSel,rmSel); }});
    if(rmSel) rmSel.addEventListener('change',function(){{ evaluateScopeChange('rm',form,branchSel,roleSel,rmSel); }});
    document.querySelectorAll('select.auto-submit').forEach(function(sel){{
      if(sel.classList.contains('scope-aware')) return;
      sel.addEventListener('change', function(){{
        const label=sel.previousElementSibling && sel.previousElementSibling.tagName==='LABEL' ? sel.previousElementSibling.textContent : 'selected';
        showLoading('Updating management view','Applying '+label+' filter');
        if(form){{ window.setTimeout(function(){{ form.requestSubmit(); }},60); }}
      }});
    }});
    document.querySelectorAll('a[href^="/?"]').forEach(function(a){{
      a.addEventListener('click', function(e){{
        if(e.metaKey||e.ctrlKey||e.shiftKey||e.altKey||e.button!==0) return;
        showLoading('Opening management detail','Loading the selected Branch, RM or relationship view');
      }});
    }});
  }});
}})();
</script>
"""
    loading='<div id="loading-toast" class="loading-toast" role="status" aria-live="polite"><div class="loading-spinner"></div><div class="loading-copy"><span data-title>Updating management view</span><span class="loading-sub" data-sub>Applying the selected reporting scope</span></div></div>'
    filter_check='<div id="filter-check" class="filter-check" role="dialog" aria-live="polite" aria-label="Filter combination check"><div class="filter-check-kicker">Filter check</div><div class="filter-check-title">Review filter combination</div><div class="filter-check-copy" data-conflict-copy></div><div class="filter-check-actions"><button type="button" class="primary" data-use-rm>Keep RM</button><button type="button" data-use-scope>Use selected scope</button><button type="button" data-cancel-conflict>Cancel</button></div></div>'
    return (f'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta http-equiv="Cache-Control" content="no-store"><title>UBL UAE | RM Cost & Performance Management</title><style>{CSS}</style></head>'
            f'<body>{loading}{filter_check}<div class="app">{sidebar(state)}<main class="main">{content}<div class="footer">Illustrative management data shown for product demonstration.</div></main></div>{js}</body></html>')


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body:bytes, ctype:str):
        self.send_response(code)
        self.send_header('Content-Type',ctype)
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma','no-cache')
        self.send_header('Expires','0')
        self.end_headers(); self.wfile.write(body)
    def _redirect(self, location: str):
        self.send_response(303)
        self.send_header('Location',location)
        self.send_header('Cache-Control','no-store')
        self.end_headers()

    def do_POST(self):
        u=urlparse(self.path)
        if u.path not in {'/','/index.html'}:
            self._send(404,b'not found','text/plain'); return
        try:
            length=int(self.headers.get('Content-Length','0') or 0)
            raw=self.rfile.read(length).decode('utf-8')
            form=parse_qs(raw,keep_blank_values=True)
            get=lambda k,d='': form.get(k,[d])[0]
            action=get('action')
            access=get('target_role','Viewer')
            if access not in TARGET_ACCESS: access='Viewer'
            mode=get('mode','Quarter')
            if mode not in {'Quarter','Month'}: mode='Quarter'
            periods=available_periods(mode,DATA)
            period=get('period',periods[-1])
            if period not in periods: period=periods[-1]
            branch=get('branch','All UAE')
            role=get('role','All')
            rm_scope=get('rm_scope','All RMs')
            metric=get('target_metric','R3M_CASA')
            if metric not in TARGET_METRICS: metric='R3M_CASA'
            message=''
            if action=='create_target':
                if access!='Maker': raise PermissionError('Only the Finance Target Maker can submit a target revision.')
                if branch=='All UAE' or branch not in BRANCHES: raise ValueError('Select a specific Branch before submitting a target.')
                level=get('target_level','').upper()
                rm=get('rm','') if level=='RM' else ''
                if level=='RM':
                    meta=RM_FILTER_META.get(rm)
                    if not meta or meta.get('branch')!=branch:
                        raise ValueError('The selected RM is not mapped to the selected Branch.')
                value=float(get('target_value','0'))
                ef,et=period_effective_dates(mode,period)
                rec=create_target(level=level,mode=mode,period=period,branch=branch,rm=rm,metric=metric,
                                  metric_name=TARGET_METRICS[metric]['name'],value=value,unit=TARGET_METRICS[metric]['unit'],
                                  effective_from=ef,effective_to=et,created_by=TARGET_ACCESS['Maker'],
                                  reason=get('reason','Management target review'),comments=get('comments',''))
                message=f"{level.title()} target {rec['TargetID']} submitted for approval. The current approved target remains live until checker approval."
            elif action in {'approve_target','reject_target'}:
                if access!='Approver': raise PermissionError('Only the Finance Target Approver can approve or reject targets.')
                decision='APPROVED' if action=='approve_target' else 'REJECTED'
                rec=decide_target(get('target_id'),decision=decision,approver=TARGET_ACCESS['Approver'])
                message=f"Target {rec['TargetID']} {decision.lower()}." + (' It is now eligible to feed the approved-target view.' if decision=='APPROVED' else ' The previous approved version remains in force.')
            else:
                raise ValueError('Unsupported target action')
            q={'view':'targets','mode':mode,'period':period,'branch':branch,'role':role,'rm_scope':rm_scope,
               'target_role':access,'target_metric':metric,'notice':message}
            self._redirect('/?'+urlencode(q))
        except Exception as exc:
            q={'view':'targets','target_role':form.get('target_role',['Viewer'])[0] if 'form' in locals() else 'Viewer',
               'notice':f"Action not completed: {str(exc)}"}
            self._redirect('/?'+urlencode(q))

    def do_GET(self):
        u=urlparse(self.path)
        if u.path=='/ubl_logo.png':
            if LOGO_PATH.exists(): self._send(200,LOGO_PATH.read_bytes(),'image/png')
            else: self._send(404,b'not found','text/plain')
            return
        if u.path not in {'/','/index.html'}:
            self._send(404,b'not found','text/plain'); return
        try:
            html=render_page(parse_qs(u.query,keep_blank_values=True)).encode('utf-8')
            self._send(200,html,'text/html; charset=utf-8')
        except Exception as exc:
            import traceback
            traceback.print_exc()
            msg=f'''<!doctype html><html><body style="font-family:system-ui;padding:40px"><h2>Application error</h2><p>{escape(str(exc))}</p><p>Check the terminal for the traceback.</p></body></html>'''.encode('utf-8')
            self._send(500,msg,'text/html; charset=utf-8')
    def log_message(self, fmt, *args):
        print('[web]',fmt%args)


def main():
    print(f"UBL UAE RM Cost & Performance Management running on http://0.0.0.0:{PORT}")
    print("Open forwarded port 8501 in GitHub Codespaces.")
    ThreadingHTTPServer(('0.0.0.0',PORT),Handler).serve_forever()

if __name__=='__main__': main()
