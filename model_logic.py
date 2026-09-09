from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd

from model_data import (
    ACTIVITY_UNIT_COST_AED,
    BASE_STRATEGY_R3M_GROWTH,
    BRANCH_OPPORTUNITY_FACTOR,
    BRANCH_SCORE_WEIGHTS,
    COST_TO_INCOME_TARGET,
    ETB_RETENTION_TARGET,
    KPI_WEIGHTS,
    NTB_BALANCE_PERSISTENCE_TARGET,
    SCORE_CAP,
    TOP5_CONCENTRATION_CEILING,
    USD_TO_AED,
    DemoData,
)


def _score_ratio(ratio: float) -> float:
    if pd.isna(ratio):
        return np.nan
    return float(np.clip(ratio * 100.0, 0.0, SCORE_CAP))


def performance_band(score: float) -> str:
    if pd.isna(score):
        return "Ramp-up"
    if score >= 110:
        return "Exceptional"
    if score >= 100:
        return "Strong"
    if score >= 85:
        return "Successful"
    if score >= 70:
        return "Watch"
    return "Needs Review"


def available_periods(mode: str, data: DemoData) -> List[str]:
    # Six months of history is needed before the score engine becomes meaningful.
    visible = data.month_dim[data.month_dim["Month_Start"] >= pd.Timestamp("2025-07-01")].copy()
    if mode == "Month":
        return visible.sort_values("Month_Order")["Month_Label"].tolist()
    q = visible[["Quarter_Label", "Quarter_Order"]].drop_duplicates().sort_values("Quarter_Order")
    return q["Quarter_Label"].tolist()


def period_months(mode: str, label: str, data: DemoData) -> pd.DataFrame:
    col = "Month_Label" if mode == "Month" else "Quarter_Label"
    return data.month_dim[data.month_dim[col].eq(label)].sort_values("Month_Order").copy()


def period_end(mode: str, label: str, data: DemoData) -> pd.Timestamp:
    p = period_months(mode, label, data)
    return pd.Timestamp(p["As_Of_Date"].max())


def period_window(mode: str, selected_label: str, data: DemoData, count: int = 5) -> List[str]:
    periods = available_periods(mode, data)
    idx = periods.index(selected_label)
    return periods[max(0, idx - count + 1): idx + 1]


def _endpoint_month(mode: str, label: str, data: DemoData) -> pd.Timestamp:
    return pd.Timestamp(period_months(mode, label, data)["Month_Start"].max())


DAILY_PUBLICATION_LAG_BUSINESS_DAYS = 1

def daily_data_freshness(date_label: str) -> dict:
    business_date = pd.Timestamp(date_label)
    previous_date = pd.bdate_range(end=business_date - pd.Timedelta(days=1), periods=1)[0]
    available_date = business_date + pd.offsets.BDay(DAILY_PUBLICATION_LAG_BUSINESS_DAYS)
    return {"Business_Date": business_date, "Previous_Available_Date": pd.Timestamp(previous_date),
            "Available_Date": pd.Timestamp(available_date), "Status": "Certified EOD",
            "Lag_Label": "T+1 default" if DAILY_PUBLICATION_LAG_BUSINESS_DAYS == 1 else "Same-day"}

def available_daily_dates(data: DemoData, lookback_business_days: int = 45) -> List[str]:
    """Available operational reporting dates for the Daily Management view.

    The prototype uses available business dates (Mon-Fri). Production should use the
    actual source/reporting calendar, so a weekend/holiday is handled by source
    availability rather than by forcing a zero-movement day.
    """
    dates = pd.bdate_range(end=pd.Timestamp(data.month_dim["As_Of_Date"].max()), periods=lookback_business_days)
    return [pd.Timestamp(d).strftime("%d %b %Y") for d in dates]


def _daily_interp_value(prev_value: float, end_value: float, day: pd.Timestamp, phase: float = 0.0) -> float:
    """Smooth deterministic daily path between prior and current month-end values."""
    days_in_month = int((day + pd.offsets.MonthEnd(0)).day)
    frac = min(1.0, max(0.0, day.day / days_in_month))
    base = float(prev_value) + (float(end_value) - float(prev_value)) * frac
    # Small non-random intra-month movement that is zero at month end.
    amp = max(0.03, abs(float(end_value)) * 0.0025)
    wave = amp * np.sin(np.pi * frac) * np.sin(day.day * 0.73 + phase)
    return float(max(0.0, base + wave))


def daily_rm_snapshot(date_label: str, data: DemoData) -> pd.DataFrame:
    """RM operational snapshot for one available reporting date.

    Daily is intentionally an operational monitoring layer. It does not recompute the
    formal 10-component performance index or invent a daily target. Sustainable
    performance remains anchored to R3M/Month/Quarter measures.
    """
    day = pd.Timestamp(date_label)
    month_start = day.replace(day=1)
    prior_month_start = month_start - pd.DateOffset(months=1)
    dec25_start = pd.Timestamp("2025-12-01")

    end_rows = data.rm_monthly[data.rm_monthly["Month_Start"].eq(month_start)].copy()
    prior_rows = data.rm_monthly[data.rm_monthly["Month_Start"].eq(prior_month_start)].copy()
    dec_rows = data.rm_monthly[data.rm_monthly["Month_Start"].eq(dec25_start)].copy()
    if end_rows.empty or prior_rows.empty:
        return pd.DataFrame()

    end_rows = end_rows.set_index("Employee_ID")
    prior_rows = prior_rows.set_index("Employee_ID")
    dec_rows = dec_rows.set_index("Employee_ID") if not dec_rows.empty else pd.DataFrame()
    previous_available = pd.bdate_range(end=day - pd.Timedelta(days=1), periods=1)[0]
    business_days_mtd = pd.bdate_range(start=month_start, end=day)

    rows = []
    for idx, emp in enumerate(end_rows.index):
        cur = end_rows.loc[emp]
        prev = prior_rows.loc[emp]
        phase = idx * 0.61

        pe = _daily_interp_value(prev.PE_CASA_USDm, cur.PE_CASA_USDm, day, phase)
        prev_day_pe = _daily_interp_value(prev.PE_CASA_USDm, cur.PE_CASA_USDm, pd.Timestamp(previous_available), phase)
        daily_values = [_daily_interp_value(prev.PE_CASA_USDm, cur.PE_CASA_USDm, pd.Timestamp(d), phase) for d in business_days_mtd]
        mtd_avg = float(np.mean(daily_values)) if daily_values else pe

        # Preserve the month-end ETB/NTB mix while allowing the total balance to move daily.
        end_total = max(float(cur.ETB_PE_USDm + cur.NTB_PE_USDm), 1e-9)
        etb_share = float(cur.ETB_PE_USDm / end_total)
        etb = pe * etb_share
        ntb = pe - etb

        advances = _daily_interp_value(prev.Advances_AEDm, cur.Advances_AEDm, day, phase + 0.8)
        month_days = int((day + pd.offsets.MonthEnd(0)).day)
        frac = min(1.0, max(0.0, day.day / month_days))
        prev_ytd = int(prev.Funded_NTB_YTD)
        end_ytd = int(cur.Funded_NTB_YTD)
        # January would reset YTD; current demo daily dates are mid-year but keep the rule correct.
        if day.month == 1:
            prev_ytd = 0
        funded_ytd = int(round(prev_ytd + (end_ytd - prev_ytd) * frac))
        elapsed_prior_day = max(1, int((day - pd.Timestamp(year=day.year, month=1, day=1)).days))
        run_rate = funded_ytd / elapsed_prior_day

        dec25 = float(dec_rows.loc[emp].PE_CASA_USDm) if not isinstance(dec_rows, pd.DataFrame) or emp in dec_rows.index else float(prev.PE_CASA_USDm)
        if isinstance(dec_rows, pd.DataFrame) and not dec_rows.empty and emp in dec_rows.index:
            dec25 = float(dec_rows.loc[emp].PE_CASA_USDm)

        rows.append({
            "Reporting_Date": day,
            "Previous_Available_Date": pd.Timestamp(previous_available),
            "Employee_ID": emp,
            "RM": cur.RM,
            "Role": cur.Role,
            "Branch": cur.Branch,
            "Branch_Code": cur.Branch_Code,
            "PE_CASA_USDm": pe,
            "ETB_PE_USDm": etb,
            "NTB_PE_USDm": ntb,
            "MTD_Avg_CASA_USDm": mtd_avg,
            "Advances_AEDm": advances,
            "Funded_NTB_YTD": funded_ytd,
            "NTB_Run_Rate": run_rate,
            "DoD_Change_USDm": pe - prev_day_pe,
            "Vs_Prior_Month_End_USDm": pe - float(prev.PE_CASA_USDm),
            "Vs_Dec25_USDm": pe - dec25,
            "Data_Completeness": float(cur.Data_Completeness),
        })
    return pd.DataFrame(rows)


def daily_customer_snapshot(date_label: str, data: DemoData, rm_daily: pd.DataFrame | None = None) -> pd.DataFrame:
    """Synthetic customer-level daily attribution that reconciles to the RM daily snapshot."""
    day = pd.Timestamp(date_label)
    month_start = day.replace(day=1)
    if rm_daily is None:
        rm_daily = daily_rm_snapshot(date_label, data)
    if rm_daily.empty:
        return pd.DataFrame()

    monthly = data.customer_monthly[data.customer_monthly["Month_Start"].eq(month_start)].copy()
    if monthly.empty:
        return pd.DataFrame()

    rows = []
    for emp, g in monthly.groupby("Employee_ID", sort=False):
        rmd = rm_daily[rm_daily["Employee_ID"].eq(emp)]
        if rmd.empty:
            continue
        rmd = rmd.iloc[0]
        dep_total = float(g["Deposits_USDm"].sum())
        adv_total = float(g["Advances_AEDm"].sum())
        dep_shares = g["Deposits_USDm"] / dep_total if dep_total > 0 else np.repeat(1/len(g), len(g))
        adv_shares = g["Advances_AEDm"] / adv_total if adv_total > 0 else np.repeat(1/len(g), len(g))
        for j, (_, cr) in enumerate(g.reset_index(drop=True).iterrows()):
            dep_share = float(dep_shares.iloc[j] if hasattr(dep_shares, 'iloc') else dep_shares[j])
            adv_share = float(adv_shares.iloc[j] if hasattr(adv_shares, 'iloc') else adv_shares[j])
            rows.append({
                "Reporting_Date": day,
                "Employee_ID": emp,
                "RM": cr.RM,
                "Branch": cr.Branch,
                "CIF": cr.CIF,
                "Customer": cr.Customer,
                "Segment": cr.Segment,
                "Cohort": "NTB" if pd.Timestamp(cr.Open_Date).year == day.year else "ETB",
                "Risk_Stage": cr.Risk_Stage,
                "Deposits_USDm": float(rmd.PE_CASA_USDm) * dep_share,
                "DoD_Change_USDm": float(rmd.DoD_Change_USDm) * dep_share,
                "MTD_Avg_Deposits_USDm": float(rmd.MTD_Avg_CASA_USDm) * dep_share,
                "Advances_AEDm": float(rmd.Advances_AEDm) * adv_share,
            })
    return pd.DataFrame(rows)


def daily_branch_summary(date_label: str, data: DemoData, rm_daily: pd.DataFrame | None = None) -> pd.DataFrame:
    if rm_daily is None:
        rm_daily = daily_rm_snapshot(date_label, data)
    if rm_daily.empty:
        return pd.DataFrame()
    day = pd.Timestamp(date_label)
    month_start = day.replace(day=1)
    branch_month = data.branch_monthly[data.branch_monthly["Month_Start"].eq(month_start)].set_index("Branch")
    rows = []
    for branch, g in rm_daily.groupby("Branch", sort=False):
        attributed = float(g.PE_CASA_USDm.sum())
        if branch in branch_month.index:
            bm = branch_month.loc[branch]
            denom = max(float(bm.RM_Attributed_USDm), 1e-9)
            bm_owned = attributed * float(bm.BM_Owned_USDm) / denom
            unassigned = attributed * float(bm.Unassigned_USDm) / denom
            margins = attributed * float(bm.Margins_Sundries_USDm) / denom
        else:
            bm_owned = unassigned = margins = 0.0
        rows.append({
            "Branch": branch,
            "Active_RMs": int(g.Employee_ID.nunique()),
            "RM_Attributed_USDm": attributed,
            "Management_PE_USDm": attributed + bm_owned + unassigned + margins,
            "MTD_Avg_CASA_USDm": float(g.MTD_Avg_CASA_USDm.sum()),
            "DoD_Change_USDm": float(g.DoD_Change_USDm.sum()),
            "Vs_Prior_Month_End_USDm": float(g.Vs_Prior_Month_End_USDm.sum()),
            "Vs_Dec25_USDm": float(g.Vs_Dec25_USDm.sum()),
            "Advances_AEDm": float(g.Advances_AEDm.sum()),
            "Funded_NTB_YTD": int(g.Funded_NTB_YTD.sum()),
            "BM_Owned_USDm": bm_owned,
            "Unassigned_USDm": unassigned,
            "Margins_Sundries_USDm": margins,
        })
    return pd.DataFrame(rows)


def daily_trend(date_label: str, data: DemoData, business_days: int = 10, branch: str | None = None, role: str | None = None) -> pd.DataFrame:
    day = pd.Timestamp(date_label)
    dates = pd.bdate_range(end=day, periods=business_days)
    rows = []
    for d in dates:
        x = daily_rm_snapshot(pd.Timestamp(d).strftime("%d %b %Y"), data)
        if branch is not None:
            x = x[x["Branch"].eq(branch)]
        if role is not None:
            x = x[x["Role"].eq(role)]
        if x.empty:
            continue
        rows.append({
            "Date": pd.Timestamp(d),
            "PE_CASA_USDm": float(x.PE_CASA_USDm.sum()),
            "MTD_Avg_CASA_USDm": float(x.MTD_Avg_CASA_USDm.sum()),
            "Advances_AEDm": float(x.Advances_AEDm.sum()),
        })
    return pd.DataFrame(rows)


def _six_month_windows(endpoint: pd.Timestamp) -> tuple[list[pd.Timestamp], list[pd.Timestamp]]:
    current = [endpoint - pd.DateOffset(months=i) for i in (2, 1, 0)]
    prior = [endpoint - pd.DateOffset(months=i) for i in (5, 4, 3)]
    return [pd.Timestamp(x) for x in current], [pd.Timestamp(x) for x in prior]


def _weighted_mean(g: pd.DataFrame, col: str) -> float:
    """Day-weight monthly average-balance facts so R3M represents the underlying daily balance population."""
    if g.empty:
        return np.nan
    if "Days_Available" in g.columns:
        weights = g["Days_Available"].astype(float)
        if weights.sum() > 0:
            return float(np.average(g[col].astype(float), weights=weights))
    return float(g[col].mean())


def _primary_driver(row: pd.Series) -> str:
    pairs = [
        (row.K01_Points, "R3M growth"),
        (row.K02_Points, "ETB retention"),
        (row.K03_Points, "NTB balance"),
        (row.K04_Points, "Persistent NTB"),
        (row.K05_Points, "Funding value"),
        (row.K06_Points, "Cost-to-income"),
        (row.K07_Points, "NTB persistence"),
        (row.K08_Points, "Concentration"),
        (row.K09_Points, "Controls"),
        (row.K10_Points, "Service"),
    ]
    pairs = [(p, n) for p, n in pairs if not pd.isna(p)]
    pairs.sort(key=lambda x: x[0])
    return " + ".join([n for _, n in pairs[:2]]) if pairs else "—"


def _strength_driver(row: pd.Series) -> str:
    pairs = [
        (row.K01_Points, "R3M growth"),
        (row.K02_Points, "ETB retention"),
        (row.K03_Points, "NTB balance"),
        (row.K04_Points, "Persistent NTB"),
        (row.K05_Points, "Funding value"),
        (row.K06_Points, "Cost-to-income"),
        (row.K07_Points, "NTB persistence"),
        (row.K08_Points, "Concentration"),
        (row.K09_Points, "Controls"),
        (row.K10_Points, "Service"),
    ]
    pairs = [(p, n) for p, n in pairs if not pd.isna(p)]
    pairs.sort(key=lambda x: -x[0])
    return " + ".join([n for _, n in pairs[:2]]) if pairs else "—"


def aggregate_rm_period(mode: str, label: str, data: DemoData) -> pd.DataFrame:
    endpoint = _endpoint_month(mode, label, data)
    selected_months = period_months(mode, label, data)["Month_Start"].tolist()
    current_months, prior_months = _six_month_windows(endpoint)

    rows = []
    for emp, hist in data.rm_monthly.groupby("Employee_ID", sort=False):
        hist = hist.sort_values("Month_Start")
        cur = hist[hist["Month_Start"].isin(current_months)]
        prev = hist[hist["Month_Start"].isin(prior_months)]
        period_scope = hist[hist["Month_Start"].isin(selected_months)]
        latest = hist[hist["Month_Start"].eq(endpoint)]
        if len(cur) < 3 or len(prev) < 3 or latest.empty or period_scope.empty:
            continue
        latest = latest.iloc[-1]

        current_r3m = _weighted_mean(cur, "Avg_CASA_USDm")
        prior_r3m = _weighted_mean(prev, "Avg_CASA_USDm")
        current_etb = _weighted_mean(cur, "ETB_Avg_USDm")
        prior_etb = _weighted_mean(prev, "ETB_Avg_USDm")
        current_ntb = _weighted_mean(cur, "NTB_Avg_USDm")

        active_months = min(3.0, max(0.0, (pd.Timestamp(latest.As_Of_Date) - pd.Timestamp(latest.Joining_Date)).days / 30.4))
        availability_factor = min(1.0, active_months / 3.0)
        role_factor = 1.0
        branch_factor = float(BRANCH_OPPORTUNITY_FACTOR[latest.Branch])
        tenure_factor = float(latest.Tenure_Factor)

        target_growth = prior_r3m * BASE_STRATEGY_R3M_GROWTH * branch_factor * role_factor * availability_factor * tenure_factor
        target_r3m = prior_r3m + target_growth
        actual_growth = current_r3m - prior_r3m
        growth_attainment = actual_growth / target_growth if target_growth > 0 else np.nan

        etb_retention = current_etb / prior_etb if prior_etb > 0 else np.nan
        ntb_target = prior_r3m * 0.07 * branch_factor * max(0.75, tenure_factor)
        ntb_attainment = current_ntb / ntb_target if ntb_target > 0 else np.nan

        funded_r3m = int(cur["Funded_NTB_Month"].sum())
        persistent_funded_r3m = int(cur["Persistent_Funded_NTB_Month"].sum())
        persistent_account_target = int(round((12 if latest.Role == "RM" else 14) * branch_factor * max(0.75, tenure_factor)))
        persistent_account_attainment = persistent_funded_r3m / persistent_account_target if persistent_account_target > 0 else np.nan

        funding_value_r3m = float(cur["Deposit_Funding_Value_AEDm"].sum())
        funding_value_target = target_r3m * USD_TO_AED * 0.0135 / 12.0 * 3.0
        funding_value_attainment = funding_value_r3m / funding_value_target if funding_value_target > 0 else np.nan

        r3m_income = float(cur["Relationship_Value_AEDm"].sum())
        # K06 follows the V1 employee-economics definition: direct all-in RM employee cost
        # divided by attributable relationship value. Customer cost-to-serve remains a
        # separate relationship-cost layer and is not double-counted in the employee KPI.
        r3m_employee_cost = float(cur["Direct_RM_Cost_AEDm"].sum())
        cost_to_income = r3m_employee_cost / r3m_income if r3m_income > 0 else np.nan
        ntb_persistence = float(cur["NTB_Balance_Persistence"].mean())
        concentration = float(cur["Top5_Concentration"].mean())
        control_score = float(cur["Control_Score"].mean())
        service_score = float(cur["Service_Score"].mean())

        k01 = _score_ratio(growth_attainment)
        k02 = _score_ratio(etb_retention / ETB_RETENTION_TARGET)
        k03 = _score_ratio(ntb_attainment)
        k04 = _score_ratio(persistent_account_attainment)
        k05 = _score_ratio(funding_value_attainment)
        k06 = _score_ratio(COST_TO_INCOME_TARGET / cost_to_income) if cost_to_income > 0 else np.nan
        k07 = _score_ratio(ntb_persistence / NTB_BALANCE_PERSISTENCE_TARGET)
        k08 = _score_ratio(TOP5_CONCENTRATION_CEILING / concentration) if concentration > 0 else np.nan
        k09 = float(np.clip(control_score, 0, SCORE_CAP))
        k10 = float(np.clip(service_score, 0, SCORE_CAP))

        components = {
            "K01 R3M Average CASA Growth": k01,
            "K02 ETB Retention": k02,
            "K03 NTB Sustainable Average": k03,
            "K04 Persistent Funded NTB": k04,
            "K05 CASA Funding Value": k05,
            "K06 Cost-to-Income": k06,
            "K07 NTB Balance Persistence": k07,
            "K08 Portfolio Concentration": k08,
            "K09 Controls & Conduct": k09,
            "K10 Service Quality": k10,
        }
        score = sum(components[k] * KPI_WEIGHTS[k] for k in KPI_WEIGHTS)

        tenure_days = int(latest.Tenure_Days)
        score_available = bool(tenure_days > 90 and len(cur) == 3 and len(prev) == 3 and latest.Data_Completeness >= 0.95)
        final_score = float(score) if score_available else np.nan

        row = {
            "Period_Mode": mode,
            "Period": label,
            "As_Of_Date": latest.As_Of_Date,
            "Employee_ID": emp,
            "RM": latest.RM,
            "Role": latest.Role,
            "Branch": latest.Branch,
            "Branch_Code": latest.Branch_Code,
            "Manager": latest.Manager,
            "Joining_Date": latest.Joining_Date,
            "Tenure_Days": tenure_days,
            "Tenure_Months": int(round(tenure_days / 30.4)),
            "PE_CASA_USDm": float(latest.PE_CASA_USDm),
            "Current_R3M_Avg_CASA_USDm": current_r3m,
            "Prior_R3M_Avg_CASA_USDm": prior_r3m,
            "R3M_Net_Growth_USDm": actual_growth,
            "R3M_Growth_pct": actual_growth / prior_r3m if prior_r3m > 0 else np.nan,
            "Base_Strategy_Growth_pct": BASE_STRATEGY_R3M_GROWTH,
            "Branch_Opportunity_Factor": branch_factor,
            "Role_Factor": role_factor,
            "Availability_Factor": availability_factor,
            "Tenure_Factor": tenure_factor,
            "Target_Growth_USDm": target_growth,
            "Target_R3M_CASA_USDm": target_r3m,
            "R3M_Target_Attainment": current_r3m / target_r3m if target_r3m > 0 else np.nan,
            "Growth_Attainment": growth_attainment,
            "Current_ETB_R3M_USDm": current_etb,
            "Prior_ETB_R3M_USDm": prior_etb,
            "ETB_Retention": etb_retention,
            "Current_NTB_R3M_USDm": current_ntb,
            "NTB_Target_USDm": ntb_target,
            "NTB_Attainment": ntb_attainment,
            "Funded_NTB_R3M": funded_r3m,
            "Persistent_Funded_NTB_R3M": persistent_funded_r3m,
            "Persistent_Account_Target": persistent_account_target,
            "Persistent_Account_Attainment": persistent_account_attainment,
            "Funded_NTB_Period": int(period_scope["Funded_NTB_Month"].sum()),
            "Funded_NTB_YTD": int(latest.Funded_NTB_YTD),
            "NTB_Run_Rate": float(latest.NTB_Run_Rate),
            "NTB_Balance_Persistence": ntb_persistence,
            "Funding_Value_R3M_AEDm": funding_value_r3m,
            "Funding_Value_Target_AEDm": funding_value_target,
            "Funding_Value_Attainment": funding_value_attainment,
            "Cost_to_Income_R3M": cost_to_income,
            "Top5_Concentration": concentration,
            "Control_Score": control_score,
            "Service_Score": service_score,
            "Advances_AEDm": float(latest.Advances_AEDm),
            "Stage2_pct": float(latest.Stage2_pct),
            "Stage3_pct": float(latest.Stage3_pct),
            "Impairment_AEDm": float(latest.Impairment_AEDm),
            "Deposit_Funding_Value_AEDm": float(period_scope["Deposit_Funding_Value_AEDm"].sum()),
            "Lending_Contribution_AEDm": float(period_scope["Lending_Contribution_AEDm"].sum()),
            "NFI_AEDm": float(period_scope["NFI_AEDm"].sum()),
            "Relationship_Value_AEDm": float(period_scope["Relationship_Value_AEDm"].sum()),
            "Cost_to_Serve_AEDm": float(period_scope["Cost_to_Serve_AEDm"].sum()),
            "Relationship_Contribution_AEDm": float(period_scope["Relationship_Contribution_AEDm"].sum()),
            "Direct_RM_Cost_AEDm": float(period_scope["Direct_RM_Cost_AEDm"].sum()),
            "RM_Economics_AEDm": float(period_scope["RM_Economics_AEDm"].sum()),
            "Organic_Movement_USDm": float(period_scope["Organic_Movement_USDm"].sum()),
            "Transfer_Adjustment_USDm": float(period_scope["Transfer_Adjustment_USDm"].sum()),
            "Maturity_Runoff_USDm": float(period_scope["Maturity_Runoff_USDm"].sum()),
            "New_Funding_USDm": float(period_scope["New_Funding_USDm"].sum()),
            "Net_Movement_USDm": float(period_scope["Net_Movement_USDm"].sum()),
            "Data_Completeness": float(latest.Data_Completeness),
            "K01_Points": k01,
            "K02_Points": k02,
            "K03_Points": k03,
            "K04_Points": k04,
            "K05_Points": k05,
            "K06_Points": k06,
            "K07_Points": k07,
            "K08_Points": k08,
            "K09_Points": k09,
            "K10_Points": k10,
            "Performance_Index": final_score,
            "Performance_Band": performance_band(final_score),
        }
        sr = pd.Series(row)
        row["Primary_Driver"] = _primary_driver(sr)
        row["Strength_Driver"] = _strength_driver(sr)
        rows.append(row)

    return pd.DataFrame(rows)


def apply_approved_rm_targets(perf: pd.DataFrame, approved_targets: dict[str, dict] | None) -> pd.DataFrame:
    """Overlay governed APPROVED RM targets onto a calculated performance frame.

    The base model still creates a transparent reference target. In the management
    product, an approved target record supersedes that reference. Pending/rejected
    records never affect performance. Only target-dependent score components are
    recalculated here; all actuals remain unchanged.
    """
    x = perf.copy()
    if x.empty:
        return x
    x["Target_Source"] = "Reference target"
    x["Target_Version"] = np.nan
    x["Target_Status"] = "REFERENCE"
    approved_targets = approved_targets or {}
    for idx, row in x.iterrows():
        rec = approved_targets.get(str(row.RM))
        if not rec:
            continue
        try:
            target_r3m = float(rec.get("TargetValue"))
        except (TypeError, ValueError):
            continue
        if not np.isfinite(target_r3m) or target_r3m <= 0:
            continue

        prior = float(row.Prior_R3M_Avg_CASA_USDm)
        actual_growth = float(row.R3M_Net_Growth_USDm)
        target_growth = target_r3m - prior
        growth_attainment = actual_growth / target_growth if target_growth > 0 else np.nan
        k01 = _score_ratio(growth_attainment)

        funding_target = target_r3m * USD_TO_AED * 0.0135 / 12.0 * 3.0
        funding_attainment = float(row.Funding_Value_R3M_AEDm) / funding_target if funding_target > 0 else np.nan
        k05 = _score_ratio(funding_attainment)

        x.at[idx, "Target_Growth_USDm"] = target_growth
        x.at[idx, "Target_R3M_CASA_USDm"] = target_r3m
        x.at[idx, "R3M_Target_Attainment"] = float(row.Current_R3M_Avg_CASA_USDm) / target_r3m
        x.at[idx, "Growth_Attainment"] = growth_attainment
        x.at[idx, "Funding_Value_Target_AEDm"] = funding_target
        x.at[idx, "Funding_Value_Attainment"] = funding_attainment
        x.at[idx, "K01_Points"] = k01
        x.at[idx, "K05_Points"] = k05
        x.at[idx, "Target_Source"] = "Approved target"
        x.at[idx, "Target_Version"] = int(rec.get("Version", 1) or 1)
        x.at[idx, "Target_Status"] = "APPROVED"

        # Preserve Ramp-up / unavailable state; otherwise recalculate the composite.
        if not pd.isna(row.Performance_Index):
            components = {
                "K01 R3M Average CASA Growth": x.at[idx, "K01_Points"],
                "K02 ETB Retention": x.at[idx, "K02_Points"],
                "K03 NTB Sustainable Average": x.at[idx, "K03_Points"],
                "K04 Persistent Funded NTB": x.at[idx, "K04_Points"],
                "K05 CASA Funding Value": x.at[idx, "K05_Points"],
                "K06 Cost-to-Income": x.at[idx, "K06_Points"],
                "K07 NTB Balance Persistence": x.at[idx, "K07_Points"],
                "K08 Portfolio Concentration": x.at[idx, "K08_Points"],
                "K09 Controls & Conduct": x.at[idx, "K09_Points"],
                "K10 Service Quality": x.at[idx, "K10_Points"],
            }
            score = float(sum(float(components[k]) * KPI_WEIGHTS[k] for k in KPI_WEIGHTS))
            x.at[idx, "Performance_Index"] = score
            x.at[idx, "Performance_Band"] = performance_band(score)
            sr = x.loc[idx]
            x.at[idx, "Primary_Driver"] = _primary_driver(sr)
            x.at[idx, "Strength_Driver"] = _strength_driver(sr)
    return x


def aggregate_customer_period(mode: str, label: str, data: DemoData) -> pd.DataFrame:
    selected = period_months(mode, label, data)
    endpoint = pd.Timestamp(selected["Month_Start"].max())
    scope = data.customer_monthly[data.customer_monthly["Month_Start"].isin(selected["Month_Start"])].copy()
    latest_scope = data.customer_monthly[data.customer_monthly["Month_Start"].eq(endpoint)].copy()
    if scope.empty or latest_scope.empty:
        return pd.DataFrame()
    flow = scope.groupby("CIF", as_index=False).agg(
        Relationship_Value_AEDm=("Relationship_Value_AEDm", "sum"),
        Cost_to_Serve_AEDm=("Cost_to_Serve_AEDm", "sum"),
        Relationship_Contribution_AEDm=("Relationship_Contribution_AEDm", "sum"),
        Movement_USDm=("Movement_USDm", "sum"),
        Deposit_Funding_Value_AEDm=("Deposit_Funding_Value_AEDm", "sum"),
        Lending_Contribution_AEDm=("Lending_Contribution_AEDm", "sum"),
        NFI_AEDm=("NFI_AEDm", "sum"),
    )
    # A selected-quarter customer average must represent the full selected period,
    # not merely the latest month's average. Day weighting is equivalent to
    # recomputing from daily facts when monthly average-balance facts are the input.
    avg = (
        scope.assign(_weighted_avg=scope["Avg_Deposits_USDm"] * scope["Days_Available"])
        .groupby("CIF", as_index=False)
        .agg(_weighted_sum=("_weighted_avg", "sum"), _days=("Days_Available", "sum"))
    )
    avg["Avg_Deposits_USDm"] = avg["_weighted_sum"] / avg["_days"].replace(0, np.nan)
    avg = avg[["CIF", "Avg_Deposits_USDm"]]
    snap = latest_scope[[
        "As_Of_Date", "Employee_ID", "RM", "Branch", "CIF", "Customer", "Open_Date", "Segment", "R_NR", "Industry", "Cohort",
        "Deposits_USDm", "Advances_AEDm", "Risk_Stage", "Movement_Reason",
    ]].copy()
    return snap.merge(avg, on="CIF", how="left").merge(flow, on="CIF", how="left")


def branch_population_bridge(mode: str, label: str, data: DemoData) -> pd.DataFrame:
    endpoint = _endpoint_month(mode, label, data)
    return data.branch_monthly[data.branch_monthly["Month_Start"].eq(endpoint)].copy().reset_index(drop=True)


def workforce_summary(perf: pd.DataFrame) -> dict:
    return {
        "Active_RMs": int(perf["Employee_ID"].nunique()),
        "Branches": int(perf["Branch"].nunique()),
        "RM_per_Branch": float(perf["Employee_ID"].nunique() / max(1, perf["Branch"].nunique())),
        "SRMs": int((perf["Role"] == "SRM").sum()),
        "RMs": int((perf["Role"] == "RM").sum()),
    }


def branch_performance(mode: str, label: str, data: DemoData, perf: pd.DataFrame | None = None) -> pd.DataFrame:
    if perf is None:
        perf = aggregate_rm_period(mode, label, data)
    bridge = branch_population_bridge(mode, label, data)
    rows = []
    for branch, g in perf.groupby("Branch", sort=False):
        b = bridge[bridge["Branch"].eq(branch)].iloc[0]
        current_r3m = float(g["Current_R3M_Avg_CASA_USDm"].sum())
        prior_r3m = float(g["Prior_R3M_Avg_CASA_USDm"].sum())
        growth = current_r3m - prior_r3m
        target_growth = float(g["Target_Growth_USDm"].sum())
        branch_growth_points = _score_ratio(growth / target_growth) if target_growth > 0 else np.nan

        current_etb = float(g["Current_ETB_R3M_USDm"].sum())
        prior_etb = float(g["Prior_ETB_R3M_USDm"].sum())
        etb_points = _score_ratio((current_etb / prior_etb) / ETB_RETENTION_TARGET) if prior_etb > 0 else np.nan

        current_ntb = float(g["Current_NTB_R3M_USDm"].sum())
        ntb_target = float(g["NTB_Target_USDm"].sum())
        ntb_points = _score_ratio(current_ntb / ntb_target) if ntb_target > 0 else np.nan

        relationship_value = float(g["Relationship_Value_AEDm"].sum())
        structural = float(data.branch_monthly[
            (data.branch_monthly["Branch"].eq(branch))
            & (data.branch_monthly["Month_Start"].isin(period_months(mode, label, data)["Month_Start"]))
        ]["Structural_Cost_AEDm"].sum())
        direct_rm = float(g["Direct_RM_Cost_AEDm"].sum())
        # Whole-Branch OPEX is intentionally simple for management: People (including RMs)
        # + Premises & Occupancy + Other Operating & Support. Customer CTS remains an
        # attribution lens and is not added again here, preventing double counting.
        total_cost = direct_rm + structural
        branch_ci = total_cost / relationship_value if relationship_value > 0 else np.nan
        economics_points = _score_ratio(COST_TO_INCOME_TARGET / branch_ci) if branch_ci > 0 else np.nan

        team_median = float(g["Performance_Index"].median())
        successful_share = float((g["Performance_Index"] >= 85).mean())
        strong_share = float((g["Performance_Index"] >= 100).mean())
        team_health = float(np.clip(100 * successful_share + 20 * strong_share, 0, SCORE_CAP))

        unassigned_share = float(b.Unassigned_USDm / b.Management_PE_USDm) if b.Management_PE_USDm > 0 else np.nan
        attribution_points = _score_ratio(0.02 / unassigned_share) if unassigned_share > 0 else SCORE_CAP
        controls_service = float(np.clip((g["Control_Score"].mean() + g["Service_Score"].mean()) / 2, 0, SCORE_CAP))

        components = {
            "Branch Growth": branch_growth_points,
            "ETB Retention": etb_points,
            "NTB Sustainable Balance": ntb_points,
            "Economics / C&I": economics_points,
            "Team Median": team_median,
            "Team Health": team_health,
            "Attribution Discipline": attribution_points,
            "Controls / Service": controls_service,
        }
        branch_score = sum(components[k] * BRANCH_SCORE_WEIGHTS[k] for k in BRANCH_SCORE_WEIGHTS)
        rm_econ = float(g["RM_Economics_AEDm"].sum())

        rows.append(
            {
                "Branch": branch,
                "Active_RMs": int(g["Employee_ID"].nunique()),
                "R3M_Avg_CASA_USDm": current_r3m,
                "Prior_R3M_USDm": prior_r3m,
                "R3M_Growth_pct": growth / prior_r3m if prior_r3m > 0 else np.nan,
                "R3M_per_RM_USDm": current_r3m / max(1, g["Employee_ID"].nunique()),
                "Funded_NTB_R3M": int(g["Funded_NTB_R3M"].sum()),
                "Relationship_Contribution_AEDm": float(g["Relationship_Contribution_AEDm"].sum()),
                "Branch_Cost_to_Income": branch_ci,
                "Team_Median_Score": team_median,
                "RM_Economics_AEDm": rm_econ,
                "Structural_Cost_AEDm": structural,
                "Fully_Loaded_Branch_Economics_AEDm": rm_econ - structural,
                "BM_Owned_USDm": float(b.BM_Owned_USDm),
                "Unassigned_USDm": float(b.Unassigned_USDm),
                "Unassigned_Share": unassigned_share,
                "Management_PE_USDm": float(b.Management_PE_USDm),
                "Branch_Growth_Points": branch_growth_points,
                "Branch_ETB_Points": etb_points,
                "Branch_NTB_Points": ntb_points,
                "Branch_Economics_Points": economics_points,
                "Branch_Team_Median_Points": team_median,
                "Branch_Team_Health_Points": team_health,
                "Branch_Attribution_Points": attribution_points,
                "Branch_Controls_Service_Points": controls_service,
                "Branch_Performance_Index": float(branch_score),
                "Performance_Band": performance_band(branch_score),
            }
        )
    return pd.DataFrame(rows)


def trend_by_period(mode: str, selected_label: str, data: DemoData, rm: str | None = None, branch: str | None = None, role: str | None = None) -> pd.DataFrame:
    rows = []
    for p in period_window(mode, selected_label, data, 5):
        x = aggregate_rm_period(mode, p, data)
        if rm is not None:
            x = x[x["RM"].eq(rm)]
        if branch is not None:
            x = x[x["Branch"].eq(branch)]
        if role is not None:
            x = x[x["Role"].eq(role)]
        if x.empty:
            continue
        rows.append(
            {
                "Period": p,
                "R3M_Avg_CASA_USDm": float(x["Current_R3M_Avg_CASA_USDm"].sum()),
                "R3M_Target_USDm": float(x["Target_R3M_CASA_USDm"].sum()),
                "Advances_AEDm": float(x["Advances_AEDm"].sum()),
                "Relationship_Contribution_AEDm": float(x["Relationship_Contribution_AEDm"].sum()),
                "Performance_Index": float(x["Performance_Index"].mean()),
            }
        )
    return pd.DataFrame(rows)


def score_breakdown(r: pd.Series) -> pd.DataFrame:
    rows = [
        ["K01", "R3M Average CASA Growth", r.R3M_Net_Growth_USDm, r.Target_Growth_USDm, r.K01_Points, 25, "Current non-overlapping R3M avg − prior R3M avg; divided by target growth"],
        ["K02", "ETB Retention", r.ETB_Retention, ETB_RETENTION_TARGET, r.K02_Points, 15, "Current comparable ETB R3M ÷ prior ETB R3M"],
        ["K03", "NTB Sustainable Average", r.Current_NTB_R3M_USDm, r.NTB_Target_USDm, r.K03_Points, 15, "Current NTB R3M average ÷ NTB target"],
        ["K04", "Persistent Funded NTB", r.Persistent_Funded_NTB_R3M, r.Persistent_Account_Target, r.K04_Points, 10, "Persistent funded NTB accounts ÷ target"],
        ["K05", "CASA Funding Value", r.Funding_Value_R3M_AEDm, r.Funding_Value_Target_AEDm, r.K05_Points, 10, "R3M funding value ÷ funding value target"],
        ["K06", "Cost-to-Income", r.Cost_to_Income_R3M, COST_TO_INCOME_TARGET, r.K06_Points, 10, "Target employee C/I ÷ actual employee C/I; lower is better"],
        ["K07", "NTB Balance Persistence", r.NTB_Balance_Persistence, NTB_BALANCE_PERSISTENCE_TARGET, r.K07_Points, 5, "Persistent NTB balance share ÷ target"],
        ["K08", "Portfolio Concentration", r.Top5_Concentration, TOP5_CONCENTRATION_CEILING, r.K08_Points, 5, "Concentration ceiling ÷ actual top-5 concentration; lower is better"],
        ["K09", "Controls & Conduct", r.Control_Score, 100, r.K09_Points, 3, "Approved control score"],
        ["K10", "Service Quality", r.Service_Score, 100, r.K10_Points, 2, "Approved service score"],
    ]
    out = pd.DataFrame(rows, columns=["ID", "Measure", "Actual", "Target / Benchmark", "Points", "Weight %", "Calculation"])
    out["Weighted Contribution"] = out["Points"] * out["Weight %"] / 100.0
    return out


def target_basis(r: pd.Series) -> pd.DataFrame:
    return pd.DataFrame(
        [
            ["Prior non-overlapping R3M average", r.Prior_R3M_Avg_CASA_USDm, "Starting sustainable book"],
            ["Base strategy growth", r.Base_Strategy_Growth_pct, "Common strategy expectation"],
            ["Branch opportunity factor", r.Branch_Opportunity_Factor, "Opportunity adjustment"],
            ["Role factor", r.Role_Factor, "Role adjustment"],
            ["Availability factor", r.Availability_Factor, "Time available in the measurement window"],
            ["Tenure factor", r.Tenure_Factor, "Ramp adjustment"],
            ["Final growth target", r.Target_Growth_USDm, "Prior R3M × base growth × approved factors"],
            ["Target R3M CASA", r.Target_R3M_CASA_USDm, "Prior R3M + final growth target"],
        ],
        columns=["Target Component", "Value", "Meaning"],
    )


def cost_activity_table(mode: str, label: str, data: DemoData, rm: str | None = None, branch: str | None = None) -> pd.DataFrame:
    months = period_months(mode, label, data)["Month_Start"].tolist()
    x = data.rm_monthly[data.rm_monthly["Month_Start"].isin(months)].copy()
    if rm is not None:
        x = x[x["RM"].eq(rm)]
    if branch is not None:
        x = x[x["Branch"].eq(branch)]
    rows = []
    mapping = [
        ("Onboarding", "Onboarding_Count"),
        ("KYC Review", "KYC_Reviews"),
        ("Credit Review", "Credit_Reviews"),
        ("Trade Transaction", "Trade_Transactions"),
        ("Service / Exception", "Service_Exceptions"),
    ]
    for (rm_name, branch_name), g in x.groupby(["RM", "Branch"], sort=False):
        for activity, col in mapping:
            count = int(g[col].sum())
            unit_cost = ACTIVITY_UNIT_COST_AED[activity]
            rows.append(
                {
                    "RM": rm_name,
                    "Branch": branch_name,
                    "Activity": activity,
                    "Activity Count": count,
                    "Unit Cost AED": unit_cost,
                    "Attributed Cost AED": count * unit_cost,
                }
            )
    return pd.DataFrame(rows)


def employee_cost_breakdown(mode: str, label: str, data: DemoData, rm: str | None = None, branch: str | None = None) -> pd.DataFrame:
    months = period_months(mode, label, data)["Month_Start"].tolist()
    x = data.rm_monthly[data.rm_monthly["Month_Start"].isin(months)].copy()
    if rm is not None: x = x[x["RM"].eq(rm)]
    if branch is not None: x = x[x["Branch"].eq(branch)]
    cols=["Base_Salary_AEDm","Fixed_Allowances_AEDm","Medical_Insurance_AEDm","Employer_Benefits_AEDm","EOS_Accrual_AEDm","Visa_Other_Direct_AEDm","Direct_RM_Cost_AEDm"]
    if x.empty: return pd.DataFrame(columns=["RM","Branch","Role"]+cols)
    return x.groupby(["RM","Branch","Role"],as_index=False)[cols].sum()


def branch_cost_to_income_breakdown(mode: str, label: str, data: DemoData, perf: pd.DataFrame | None = None) -> pd.DataFrame:
    """Management-facing whole-Branch OPEX decomposition.

    Main management buckets:
      1) People Cost — all Branch people, including RMs
      2) Premises & Occupancy — rent/lease, utilities, maintenance, security, etc.
      3) Other Operating & Support — technology, administration, operations, depreciation, shared support

    Customer CTS is shown as an analytical attribution lens but is not added to Branch OPEX
    again. In production, all three OPEX buckets must reconcile to Finance GL/CRC/cost-centre
    facts and approved allocations.
    """
    if perf is None:
        perf = aggregate_rm_period(mode, label, data)
    months = period_months(mode, label, data)["Month_Start"].tolist()
    rows = []
    for branch, g in perf.groupby("Branch", sort=False):
        structural = float(data.branch_monthly[
            (data.branch_monthly["Branch"].eq(branch))
            & (data.branch_monthly["Month_Start"].isin(months))
        ]["Structural_Cost_AEDm"].sum())
        relationship_value = float(g["Relationship_Value_AEDm"].sum())
        customer_cts = float(g["Cost_to_Serve_AEDm"].sum())
        direct_rm = float(g["Direct_RM_Cost_AEDm"].sum())

        # Synthetic prototype split of the structural pool only. Production maps GL/CRC.
        non_rm_staff = structural * 0.42
        premises = structural * 0.38
        other_opex = structural * 0.20
        people = direct_rm + non_rm_staff
        total_branch_opex = people + premises + other_opex
        ci = total_branch_opex / relationship_value if relationship_value > 0 else np.nan
        fully_loaded = relationship_value - total_branch_opex
        rows.append({
            "Branch": branch,
            "Relationship_Value_AEDm": relationship_value,
            "Customer_CTS_Attribution_AEDm": customer_cts,
            "Direct_RM_Cost_AEDm": direct_rm,
            "Non_RM_Staff_Cost_AEDm": non_rm_staff,
            "People_Cost_AEDm": people,
            "Premises_Occupancy_AEDm": premises,
            "Other_Operating_Support_AEDm": other_opex,
            "Structural_Cost_AEDm": structural,
            "Total_Branch_OPEX_AEDm": total_branch_opex,
            "Branch_Cost_to_Income": ci,
            "Fully_Loaded_Branch_Economics_AEDm": fully_loaded,
        })
    return pd.DataFrame(rows)


def tableau_semantic_model_register() -> pd.DataFrame:
    """Logical production model that maps cleanly into a Tableau semantic layer."""
    return pd.DataFrame([
        ["DimDate", "Business Date / Month / Quarter", "Business date, month, quarter, current-period flag, available-date flag", "Calendar / reporting calendar"],
        ["DimRM", "RMCode", "RM/SRM, role, grade, manager, joining date, effective dates", "HR / RM master"],
        ["DimBranch", "Branch Code", "Branch, unit, business hierarchy", "Approved branch hierarchy"],
        ["DimCustomer", "CIF", "Customer, segment, residency, industry", "Customer master"],
        ["FactOwnership", "CIF × RMCode × Effective Date", "Historical CIF→RM and RM→Branch ownership", "Approved ownership history"],
        ["FactDepositDaily", "Business Date × Account", "PE CASA, ETB/NTB, daily movement", "Deposit Portfolio / daily RM facts"],
        ["FactAverageBalance", "Month × Account/CIF", "MTD/R3M average-balance facts", "Daily balance-derived"],
        ["FactLending", "Period × Facility", "Outstanding, contribution, risk context", "Authoritative lending source"],
        ["FactNFI", "Transaction × CIF", "Trade/FX/payment fees and attributable NFI", "Transaction sources"],
        ["FactActivityCost", "Period × CIF × Activity", "Activity count, unit cost, customer CTS allocation lens", "Operations / activity facts"],
        ["FactEmployeeCost", "Month × RMCode × Cost Component", "Direct RM employment-cost components", "HR/Payroll + Finance reconciliation"],
        ["FactBranchCost", "Month × Branch × GL/CRC × Cost Category", "People, premises/occupancy, other operating/support cost", "Finance GL / CRC / cost centre"],
        ["FactTarget", "Period × Target Level × Branch/RM × Measure × Version", "Target, status, maker, approver, effective dates, reason", "Product-owned approved target register"],
    ], columns=["Tableau Layer", "Grain / Key", "Core Content", "Production Source"])

def model_metric_register() -> pd.DataFrame:
    rows = [
        ["K01", "R3M Average CASA Growth", "25%", "Higher", "Current non-overlapping R3M average − prior non-overlapping R3M average", "Target Builder"],
        ["K02", "ETB Retention", "15%", "Higher", "Current comparable ETB R3M ÷ prior ETB R3M", "Ownership + Balance History"],
        ["K03", "NTB Sustainable Average", "15%", "Higher", "Current NTB R3M average ÷ NTB target", "Account Cohort + Balance History"],
        ["K04", "Persistent Funded NTB", "10%", "Higher", "Persistent funded NTB accounts ÷ target", "Account Activity"],
        ["K05", "CASA Funding Value", "10%", "Higher", "Average CASA × funding spread × time", "Finance Economics"],
        ["K06", "Cost-to-Income", "10%", "Lower", "Direct all-in RM employee cost ÷ attributable relationship value", "HR + Finance + Activity Cost"],
        ["K07", "NTB Balance Persistence", "5%", "Higher", "Persistent NTB balance ÷ originated NTB balance", "Account Cohort History"],
        ["K08", "Portfolio Concentration", "5%", "Lower", "Top-5 average CASA ÷ total average CASA", "Customer / Account Fact"],
        ["K09", "Controls & Conduct", "3%", "Higher", "Approved severity-weighted control score", "Compliance / Operations"],
        ["K10", "Service Quality", "2%", "Higher", "Approved controllable service score", "Service / Operations"],
    ]
    return pd.DataFrame(rows, columns=["KPI", "Measure", "Weight", "Direction", "Calculation", "Data Domain"])


def period_logic_table() -> pd.DataFrame:
    return pd.DataFrame(
        [
            ["Daily PE CASA / Advances", "Daily snapshot", "Latest available source snapshot for selected reporting date; compare with previous available day and prior month-end"],
            ["Daily MTD Average CASA", "Daily average stock", "Average of available daily balance snapshots from month start through selected reporting date; production calendar convention to be approved"],
            ["Daily target / score", "Not calculated", "Daily view is operational monitoring; formal target attainment and performance index remain on sustainable Month/Quarter and R3M measures"],
            ["PE CASA / Advances", "Period snapshot", "Latest available period-end value"],
            ["MTD / Period Average CASA", "Average stock", "Day-weighted average of monthly average-balance facts for selected period"],
            ["Current R3M Average", "Rolling average", "Day-weighted selected month and previous two months"],
            ["Prior R3M Average", "Rolling comparison", "Day-weighted three months immediately before current R3M; no overlap"],
            ["Funded NTB", "Flow", "Count in selected month/quarter; YTD maintained separately"],
            ["NTB Run Rate", "Pace", "Funded NTB YTD ÷ elapsed YTD calendar days up to previous day"],
            ["Movement", "Flow bridge", "Organic + Transfer + Maturity / Scheduled Outflow + New Funding = Net Movement"],
            ["Economics", "Flow", "Summed over the selected month/quarter"],
            ["Risk / concentration", "Snapshot / rolling", "Latest or R3M average depending on metric definition"],
        ],
        columns=["Measure", "Type", "Rule"],
    )


def population_bridge_logic() -> pd.DataFrame:
    return pd.DataFrame(
        [
            ["RM Attributed Book", "Customers/accounts assigned to RMs for the period"],
            ["BM Owned Book", "Relationships explicitly owned by the Branch Manager"],
            ["Unassigned Book", "Temporary/mapping exception population kept separate from BM-owned"],
            ["Margins & Sundries", "Management population component outside the RM source-book definition"],
            ["Management PE", "RM Attributed + BM Owned + Unassigned + Margins & Sundries"],
        ],
        columns=["Population", "Definition"],
    )


def management_action_table(r: pd.Series) -> pd.DataFrame:
    """Create a deterministic management-action view from the RM result.

    This is a product workflow demonstration: actions are driven by the model's
    primary diagnostic and customer-driver review, not by hidden AI commentary.
    """
    driver = str(r.Primary_Driver)
    driver_actions = {
        "R3M Average CASA Growth": "Review sustainable CASA growth gap, largest negative customer movements and renewal pipeline.",
        "ETB Retention": "Review ETB outflows, maturities and pricing; agree retention/deepening actions for priority relationships.",
        "NTB Sustainable Average": "Improve NTB balance quality by focusing on funded relationships that build sustainable average balances.",
        "Persistent Funded NTB": "Review funded NTB activation and persistence; remove low-quality account-opening activity from the action plan.",
        "CASA Funding Value": "Review pricing and balance mix to improve the economic value of the deposit book.",
        "Cost-to-Income": "Review attributable relationship value versus direct RM employee cost and identify revenue/deepening opportunities.",
        "NTB Balance Persistence": "Review NTB cohorts with early balance attrition and agree 90/180-day retention actions.",
        "Portfolio Concentration": "Diversify the book and deepen under-penetrated relationships to reduce dependence on the largest customers.",
        "Controls & Conduct": "Close attributable control/conduct issues and confirm remediation before the next review.",
        "Service Quality": "Resolve controllable service issues and confirm follow-up with affected relationships.",
    }
    first = driver_actions.get(driver, f"Review {driver} and agree the corrective or growth action.")
    if str(r.Performance_Band) in ("Exceptional", "Strong"):
        first = f"Maintain current performance and address the lowest-scoring component: {driver}."

    as_of = pd.Timestamp(r.As_Of_Date)
    rows = [
        [1, first, "RM + Branch Manager", (as_of + pd.Timedelta(days=15)).date(), "Open"],
        [2, "Review the top positive and negative CIF/account drivers and confirm which movements are organic, maturity-related or transfer-related.", "RM", (as_of + pd.Timedelta(days=10)).date(), "Open"],
        [3, "Select the highest-value relationship opportunities for retention, cross-sell, repricing or lending/fee deepening and track the outcome.", "RM + Product / Business", (as_of + pd.Timedelta(days=30)).date(), "Open"],
    ]
    return pd.DataFrame(rows, columns=["Priority", "Management Action", "Owner", "Due Date", "Status"])
