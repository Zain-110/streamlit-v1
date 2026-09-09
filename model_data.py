from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import numpy as np
import pandas as pd

AS_OF_DATE = pd.Timestamp("2026-08-31")
DATA_START = pd.Timestamp("2025-01-01")
USD_TO_AED = 3.6725
MANAGER_NAME = "Shahmeer Masud Khan"

BRANCHES = [
    "Deira Branch (0906)",
    "Bur Dubai Branch (0907)",
    "Sharjah Branch (0910)",
    "Gold & Diamond Park (0919)",
    "Muroor Branch (1207)",
    "Musaffah Branch (0901)",
    "Business Bay Branch (0925)",
]

BRANCH_CODES = {
    "Deira Branch (0906)": "0906",
    "Bur Dubai Branch (0907)": "0907",
    "Sharjah Branch (0910)": "0910",
    "Gold & Diamond Park (0919)": "0919",
    "Muroor Branch (1207)": "1207",
    "Musaffah Branch (0901)": "0901",
    "Business Bay Branch (0925)": "0925",
}

# Synthetic opportunity factors demonstrate the target-builder mechanic.
# They are intentionally close to 1.00 so the prototype does not fabricate
# structural advantages or disadvantages between branches.
BRANCH_OPPORTUNITY_FACTOR = {
    branch: 1.00 for branch in BRANCHES
}

TEAM_NAMES = [
    "Abdul Qudoos",
    "Abdul Rehman",
    "Arafat Siddiqui",
    "Hasan Ali",
    "Hassan Khan",
    "Kelash Kumar",
    "Khansa Junaid",
    "Muhammad Nofil",
    "Muhammad Rohaan Amir",
    "Muhammad Taha Zaman",
    "Muhammad Umer Soomro",
    "Osama Ali",
    "Palak Talreja",
    "Shamas U Din",
    "Shayan",
    "Umer Ahmed Siddiqui",
]

# Every physical branch is populated; only the user's requested team names are used.
ROSTER_SPEC = [
    ("Abdul Qudoos", "SRM", "Deira Branch (0906)", "2023-03-15"),
    ("Abdul Rehman", "RM", "Deira Branch (0906)", "2023-09-04"),
    ("Arafat Siddiqui", "RM", "Deira Branch (0906)", "2024-02-12"),
    ("Hasan Ali", "SRM", "Bur Dubai Branch (0907)", "2022-11-01"),
    ("Hassan Khan", "RM", "Bur Dubai Branch (0907)", "2023-07-17"),
    ("Kelash Kumar", "RM", "Bur Dubai Branch (0907)", "2024-01-08"),
    ("Khansa Junaid", "SRM", "Sharjah Branch (0910)", "2023-01-23"),
    ("Muhammad Nofil", "RM", "Sharjah Branch (0910)", "2024-04-01"),
    ("Muhammad Rohaan Amir", "SRM", "Gold & Diamond Park (0919)", "2022-08-15"),
    ("Muhammad Taha Zaman", "RM", "Gold & Diamond Park (0919)", "2024-03-11"),
    ("Muhammad Umer Soomro", "SRM", "Muroor Branch (1207)", "2023-05-22"),
    ("Osama Ali", "RM", "Muroor Branch (1207)", "2024-05-06"),
    ("Palak Talreja", "SRM", "Musaffah Branch (0901)", "2023-02-06"),
    ("Shamas U Din", "RM", "Musaffah Branch (0901)", "2024-06-03"),
    ("Shayan", "SRM", "Business Bay Branch (0925)", "2023-06-12"),
    ("Umer Ahmed Siddiqui", "RM", "Business Bay Branch (0925)", "2024-07-01"),
]

ACTIVITY_UNIT_COST_AED = {
    "Onboarding": 2200,
    "KYC Review": 950,
    "Credit Review": 3200,
    "Trade Transaction": 140,
    "Service / Exception": 90,
}

BASE_STRATEGY_R3M_GROWTH = 0.045
ETB_RETENTION_TARGET = 1.00
NTB_BALANCE_PERSISTENCE_TARGET = 0.70
COST_TO_INCOME_TARGET = 0.50
TOP5_CONCENTRATION_CEILING = 0.40
SCORE_CAP = 120.0

KPI_WEIGHTS = {
    "K01 R3M Average CASA Growth": 0.25,
    "K02 ETB Retention": 0.15,
    "K03 NTB Sustainable Average": 0.15,
    "K04 Persistent Funded NTB": 0.10,
    "K05 CASA Funding Value": 0.10,
    "K06 Cost-to-Income": 0.10,
    "K07 NTB Balance Persistence": 0.05,
    "K08 Portfolio Concentration": 0.05,
    "K09 Controls & Conduct": 0.03,
    "K10 Service Quality": 0.02,
}


ACCOUNT_COLUMNS = [
    "RM", "Branch", "CIF", "Customer", "Account_No", "Product", "Currency",
    "Cohort", "Open_Date", "Balance_USDm", "Avg_Balance_USDm",
]
FACILITY_COLUMNS = [
    "RM", "Branch", "CIF", "Customer", "Facility_No", "Outstanding_AEDm",
    "Maturity_Date", "Risk_Stage",
]
TRADE_COLUMNS = [
    "RM", "Branch", "CIF", "Customer", "Transaction_Ref", "Type", "Income_AEDm",
]

BRANCH_SCORE_WEIGHTS = {
    "Branch Growth": 0.25,
    "ETB Retention": 0.10,
    "NTB Sustainable Balance": 0.10,
    "Economics / C&I": 0.20,
    "Team Median": 0.10,
    "Team Health": 0.10,
    "Attribution Discipline": 0.05,
    "Controls / Service": 0.10,
}


@dataclass(frozen=True)
class DemoData:
    roster: pd.DataFrame
    rm_monthly: pd.DataFrame
    customer_monthly: pd.DataFrame
    branch_monthly: pd.DataFrame
    month_dim: pd.DataFrame


def _month_label(ts: pd.Timestamp) -> str:
    return ts.strftime("%b %Y")


def _quarter_label(ts: pd.Timestamp) -> str:
    q = (ts.month - 1) // 3 + 1
    current_q = (AS_OF_DATE.month - 1) // 3 + 1
    suffix = " Current" if ts.year == AS_OF_DATE.year and q == current_q else ""
    return f"Q{q} {ts.year}{suffix}"


def _tenure_factor(days: int) -> float:
    if days <= 30:
        return 0.00
    if days <= 60:
        return 0.25
    if days <= 90:
        return 0.50
    if days <= 180:
        return 0.75
    return 1.00


def _normalise(v: np.ndarray) -> np.ndarray:
    v = np.clip(v.astype(float), 1e-9, None)
    return v / v.sum()


def _build_roster() -> pd.DataFrame:
    rows = []
    for i, (name, role, branch, joining) in enumerate(ROSTER_SPEC, start=1):
        rows.append(
            {
                "Employee_ID": f"EMP-{1000+i}",
                "RM": name,
                "Role": role,
                "Branch": branch,
                "Branch_Code": BRANCH_CODES[branch],
                "Manager": MANAGER_NAME,
                "Joining_Date": pd.Timestamp(joining),
            }
        )
    out = pd.DataFrame(rows)
    assert out["RM"].tolist() == TEAM_NAMES
    assert out["Branch"].nunique() == len(BRANCHES)
    assert out["Employee_ID"].is_unique
    return out


def build_demo_data(seed: int = 260906) -> DemoData:
    rng = np.random.default_rng(seed)
    roster = _build_roster()

    months = pd.date_range(DATA_START, AS_OF_DATE.replace(day=1), freq="MS")
    month_dim = pd.DataFrame({"Month_Start": months})
    month_dim["As_Of_Date"] = month_dim["Month_Start"] + pd.offsets.MonthEnd(0)
    month_dim.loc[month_dim["As_Of_Date"] > AS_OF_DATE, "As_Of_Date"] = AS_OF_DATE
    month_dim["Month_Label"] = month_dim["Month_Start"].map(_month_label)
    month_dim["Quarter_Label"] = month_dim["Month_Start"].map(_quarter_label)
    month_dim["Month_Order"] = np.arange(len(month_dim))
    month_dim["Quarter_Order"] = month_dim["Month_Start"].dt.year * 4 + ((month_dim["Month_Start"].dt.month - 1) // 3)

    # Stable customer master: eight synthetic relationships per RM.
    customer_master: Dict[str, pd.DataFrame] = {}
    adjectives = ["Orion", "Cedar", "Vertex", "Harbour", "Silver", "Marina", "Crescent", "Nexa"]
    nouns = ["Trading", "Logistics", "Services", "Holdings", "Manufacturing", "Solutions", "Industries", "Enterprises"]
    suffixes = ["LLC", "FZE", "LLC", "LLC", "FZE", "LLC", "LLC", "FZE"]

    for idx, rr in roster.reset_index(drop=True).iterrows():
        dep_shares = _normalise(rng.dirichlet(np.ones(8) * 1.7))
        adv_shares = _normalise(rng.dirichlet(np.ones(8) * 1.4))
        income_shares = _normalise(0.55 * dep_shares + 0.45 * adv_shares)
        # Each RM has a mix of legacy and recent relationships.
        open_dates = [
            pd.Timestamp("2022-03-15") + pd.Timedelta(days=30 * ((idx + 2*j) % 18))
            for j in range(5)
        ] + [
            pd.Timestamp("2025-02-01") + pd.Timedelta(days=35 * ((idx + j) % 9))
            for j in range(2)
        ] + [
            pd.Timestamp("2026-01-15") + pd.Timedelta(days=24 * (idx % 6))
        ]
        rows = []
        for j in range(8):
            cif = f"CIF-{idx+1:02d}-{j+1:03d}"
            company = f"{adjectives[j]} {nouns[(idx+j)%len(nouns)]} {suffixes[j]}"
            rows.append(
                {
                    "CIF": cif,
                    "Customer": company,
                    "Open_Date": open_dates[j],
                    "Segment": "Corporate" if (idx + j) % 3 else "Individual",
                    "R_NR": "Resident" if (idx + j) % 4 else "Non-Resident",
                    "Industry": ["Trading", "Services", "Manufacturing", "Logistics"][((idx*2)+j) % 4],
                    "Deposit_Share": dep_shares[j],
                    "Advance_Share": adv_shares[j],
                    "Income_Share": income_shares[j],
                }
            )
        customer_master[rr.Employee_ID] = pd.DataFrame(rows)

    rm_rows: List[Dict] = []
    customer_rows: List[Dict] = []
    branch_rows: List[Dict] = []

    # Per-RM trend profiles create a realistic spread of performance outcomes.
    monthly_growth_profiles = np.array([
        0.021, 0.013, 0.008, 0.007, 0.003, -0.001, 0.012, 0.006,
        0.015, 0.004, -0.002, 0.009, 0.011, 0.001, 0.014, 0.007,
    ])
    base_book = np.array([62, 54, 43, 71, 49, 36, 58, 41, 76, 39, 66, 34, 52, 31, 57, 44], dtype=float)

    prior_pe: Dict[str, float] = {}
    ytd_funded: Dict[tuple[int, str], int] = {}

    for mi, md in month_dim.iterrows():
        month = pd.Timestamp(md.Month_Start)
        as_of = pd.Timestamp(md.As_Of_Date)
        year = int(as_of.year)
        elapsed_prior_day = max(1, int((as_of - pd.Timestamp(year=year, month=1, day=1)).days))
        month_frac = min(1.0, as_of.day / as_of.days_in_month)

        for idx, rr in roster.reset_index(drop=True).iterrows():
            months_since_start = mi
            growth = monthly_growth_profiles[idx]
            seasonal = 1 + 0.018 * np.sin((month.month - 1) / 12 * 2 * np.pi + idx / 4)
            # Two controlled performance shocks create credible management cases.
            shock = 1.0
            if idx in (5, 13) and month >= pd.Timestamp("2026-04-01"):
                shock *= 0.94
            if idx in (8, 14) and month >= pd.Timestamp("2026-05-01"):
                shock *= 1.05
            avg_casa = base_book[idx] * ((1 + growth) ** months_since_start) * seasonal * shock
            avg_casa *= 1 + rng.normal(0, 0.012)
            avg_casa = float(max(8.0, avg_casa))
            pe_casa = float(max(7.0, avg_casa * (1 + rng.normal(0.004, 0.025))))

            # Advances are separate from CASA and intentionally not a fixed percentage of deposits.
            advances_aed = float(max(15.0, (24 + idx * 4.8) * (1 + 0.0045 * months_since_start) * (0.92 + 0.15 * rng.random())))

            # Allocate the RM book to active customers and derive ETB/NTB from opening date dynamically.
            cm = customer_master[rr.Employee_ID].copy()
            cm = cm[cm["Open_Date"] <= as_of].copy()
            dep_w = _normalise(cm["Deposit_Share"].to_numpy())
            adv_w = _normalise(cm["Advance_Share"].to_numpy())
            inc_w = _normalise(cm["Income_Share"].to_numpy())

            # Relationship balances.
            customer_dep = pe_casa * dep_w
            customer_avg = avg_casa * dep_w
            customer_adv = advances_aed * adv_w

            # Current-year new-to-bank cohort; recalculated for each reporting month.
            cohort = np.where(cm["Open_Date"].dt.year == as_of.year, "NTB", "ETB")
            etb_avg = float(customer_avg[cohort == "ETB"].sum())
            ntb_avg = float(customer_avg[cohort == "NTB"].sum())
            etb_pe = float(customer_dep[cohort == "ETB"].sum())
            ntb_pe = float(customer_dep[cohort == "NTB"].sum())

            # Acquisition and persistence mechanics.
            funded_month = int(max(1, round((4.2 + (idx % 4) * 0.8 + rng.normal(0, 0.8)) * month_frac)))
            key = (year, rr.Employee_ID)
            if month.month == 1:
                ytd_funded[key] = 0
            ytd_funded[key] = ytd_funded.get(key, 0) + funded_month
            funded_ytd = int(ytd_funded[key])
            run_rate = funded_ytd / elapsed_prior_day
            ntb_balance_persistence = float(np.clip(0.64 + 0.022 * (idx % 6) + rng.normal(0, 0.025), 0.55, 0.94))
            persistent_funded_month = int(round(funded_month * np.clip(ntb_balance_persistence + 0.05, 0.55, 0.97)))

            # Customer/activity economics. Values are synthetic, internally consistent and fully reconciled.
            funding_spread = 0.0125 + 0.00045 * (idx % 5)
            deposit_value = avg_casa * USD_TO_AED * funding_spread / 12.0 * month_frac
            lending_margin = 0.023 + 0.001 * (idx % 4)
            lending_value = advances_aed * lending_margin / 12.0 * month_frac
            nfi = float((0.030 + 0.006 * (idx % 5) + rng.uniform(0.002, 0.010)) * month_frac)

            onboarding = int(max(0, round((1.5 + (idx % 3) * 0.6 + rng.normal(0, 0.5)) * month_frac)))
            kyc = int(max(1, round((3.5 + (idx % 4) * 0.7 + rng.normal(0, 0.7)) * month_frac)))
            credit = int(max(0, round((1.2 + (idx % 3) * 0.5 + rng.normal(0, 0.4)) * month_frac)))
            trade = int(max(2, round((10 + (idx % 5) * 2.0 + rng.normal(0, 2.0)) * month_frac)))
            service = int(max(1, round((5 + (idx % 6) + rng.normal(0, 1.2)) * month_frac)))
            cts_aed = (
                onboarding * ACTIVITY_UNIT_COST_AED["Onboarding"]
                + kyc * ACTIVITY_UNIT_COST_AED["KYC Review"]
                + credit * ACTIVITY_UNIT_COST_AED["Credit Review"]
                + trade * ACTIVITY_UNIT_COST_AED["Trade Transaction"]
                + service * ACTIVITY_UNIT_COST_AED["Service / Exception"]
            ) / 1_000_000.0
            # Synthetic direct employment cost decomposed into transparent components.
            if rr.Role == "RM":
                monthly_cost_components = {
                    "Base_Salary_AEDm": 0.0310, "Fixed_Allowances_AEDm": 0.0100,
                    "Medical_Insurance_AEDm": 0.0020, "Employer_Benefits_AEDm": 0.0030,
                    "EOS_Accrual_AEDm": 0.0040, "Visa_Other_Direct_AEDm": 0.0020,
                }
            else:
                monthly_cost_components = {
                    "Base_Salary_AEDm": 0.0410, "Fixed_Allowances_AEDm": 0.0120,
                    "Medical_Insurance_AEDm": 0.0025, "Employer_Benefits_AEDm": 0.0035,
                    "EOS_Accrual_AEDm": 0.0050, "Visa_Other_Direct_AEDm": 0.0020,
                }
            cost_components = {k: float(v * month_frac) for k, v in monthly_cost_components.items()}
            direct_rm_cost = float(sum(cost_components.values()))
            relationship_value = deposit_value + lending_value + nfi
            relationship_contribution = relationship_value - cts_aed
            rm_economics = relationship_contribution - direct_rm_cost
            all_in_cost = cts_aed + direct_rm_cost
            cost_to_income = all_in_cost / relationship_value if relationship_value > 0 else np.nan

            top5_concentration = float(np.clip(0.28 + 0.022 * (idx % 8) + rng.normal(0, 0.015), 0.22, 0.56))
            control_score = float(np.clip(92 + (idx % 5) * 4 + rng.normal(0, 3.0), 78, 115))
            service_score = float(np.clip(90 + ((idx + 2) % 6) * 4 + rng.normal(0, 3.0), 78, 115))
            stage2 = float(np.clip(3.5 + (idx % 5) * 0.8 + rng.normal(0, 0.7), 1.0, 9.0))
            stage3 = float(np.clip(0.45 + (idx % 4) * 0.25 + rng.normal(0, 0.2), 0.0, 2.5))
            impairment = advances_aed * (stage2 / 100 * 0.012 + stage3 / 100 * 0.10)

            prev = prior_pe.get(rr.Employee_ID, pe_casa * 0.995)
            net_move = pe_casa - prev
            transfer = 0.0
            # Paired administrative transfer events; net to zero at UAE level.
            if month in (pd.Timestamp("2026-03-01"), pd.Timestamp("2026-07-01")):
                if idx == 1:
                    transfer = -3.5
                elif idx == 9:
                    transfer = 3.5
            maturity = float(-abs(rng.normal(0.55, 0.20)))
            new_funding = float(max(0.4, rng.normal(1.35 + (idx % 3) * 0.20, 0.25)))
            organic = net_move - transfer - maturity - new_funding
            prior_pe[rr.Employee_ID] = pe_casa

            tenure_days = int((as_of - rr.Joining_Date).days)
            tenure_factor = _tenure_factor(tenure_days)

            rm_rows.append(
                {
                    "Month_Start": month,
                    "As_Of_Date": as_of,
                    "Month_Label": md.Month_Label,
                    "Quarter_Label": md.Quarter_Label,
                    "Days_Available": int(as_of.day),
                    "Employee_ID": rr.Employee_ID,
                    "RM": rr.RM,
                    "Role": rr.Role,
                    "Branch": rr.Branch,
                    "Branch_Code": rr.Branch_Code,
                    "Manager": rr.Manager,
                    "Joining_Date": rr.Joining_Date,
                    "Tenure_Days": tenure_days,
                    "Tenure_Factor": tenure_factor,
                    "PE_CASA_USDm": pe_casa,
                    "Avg_CASA_USDm": avg_casa,
                    "ETB_Avg_USDm": etb_avg,
                    "NTB_Avg_USDm": ntb_avg,
                    "ETB_PE_USDm": etb_pe,
                    "NTB_PE_USDm": ntb_pe,
                    "Funded_NTB_Month": funded_month,
                    "Persistent_Funded_NTB_Month": persistent_funded_month,
                    "Funded_NTB_YTD": funded_ytd,
                    "NTB_Run_Rate": run_rate,
                    "NTB_Balance_Persistence": ntb_balance_persistence,
                    "Advances_AEDm": advances_aed,
                    "Deposit_Funding_Value_AEDm": deposit_value,
                    "Lending_Contribution_AEDm": lending_value,
                    "NFI_AEDm": nfi,
                    "Relationship_Value_AEDm": relationship_value,
                    "Cost_to_Serve_AEDm": cts_aed,
                    **cost_components,
                    "Direct_RM_Cost_AEDm": direct_rm_cost,
                    "All_In_Cost_AEDm": all_in_cost,
                    "Relationship_Contribution_AEDm": relationship_contribution,
                    "RM_Economics_AEDm": rm_economics,
                    "Cost_to_Income": cost_to_income,
                    "Top5_Concentration": top5_concentration,
                    "Control_Score": control_score,
                    "Service_Score": service_score,
                    "Stage2_pct": stage2,
                    "Stage3_pct": stage3,
                    "Impairment_AEDm": impairment,
                    "Onboarding_Count": onboarding,
                    "KYC_Reviews": kyc,
                    "Credit_Reviews": credit,
                    "Trade_Transactions": trade,
                    "Service_Exceptions": service,
                    "Organic_Movement_USDm": organic,
                    "Transfer_Adjustment_USDm": transfer,
                    "Maturity_Runoff_USDm": maturity,
                    "New_Funding_USDm": new_funding,
                    "Net_Movement_USDm": net_move,
                    "Data_Completeness": 1.0,
                }
            )

            # Allocate economics and balances to customers so drill-down reconciles to the RM.
            for j, cr in cm.reset_index(drop=True).iterrows():
                dep = float(customer_dep[j])
                avg_dep = float(customer_avg[j])
                adv = float(customer_adv[j])
                inc_share = float(inc_w[j])
                dep_value_c = deposit_value * float(dep_w[j])
                lend_value_c = lending_value * float(adv_w[j])
                nfi_c = nfi * inc_share
                rel_value_c = dep_value_c + lend_value_c + nfi_c
                cts_c = cts_aed * inc_share
                rel_con_c = rel_value_c - cts_c
                risk_stage = "Stage 3" if (j == 0 and stage3 > 1.1) else ("Stage 2" if (j in (1,2) and stage2 > 5.5) else "Stage 1")
                movement_c = net_move * float(dep_w[j])
                movement_reason = "Administrative transfer" if transfer != 0 and j == 0 else ("Maturity / scheduled outflow" if movement_c < -0.5 else ("New funding" if movement_c > 0.8 else "Organic movement"))
                customer_rows.append(
                    {
                        "Month_Start": month,
                        "As_Of_Date": as_of,
                        "Month_Label": md.Month_Label,
                        "Quarter_Label": md.Quarter_Label,
                        "Days_Available": int(as_of.day),
                        "Employee_ID": rr.Employee_ID,
                        "RM": rr.RM,
                        "Branch": rr.Branch,
                        "CIF": cr.CIF,
                        "Customer": cr.Customer,
                        "Open_Date": cr.Open_Date,
                        "Segment": cr.Segment,
                        "R_NR": cr.R_NR,
                        "Industry": cr.Industry,
                        "Cohort": "NTB" if cr.Open_Date.year == as_of.year else "ETB",
                        "Deposits_USDm": dep,
                        "Avg_Deposits_USDm": avg_dep,
                        "Advances_AEDm": adv,
                        "Deposit_Funding_Value_AEDm": dep_value_c,
                        "Lending_Contribution_AEDm": lend_value_c,
                        "NFI_AEDm": nfi_c,
                        "Relationship_Value_AEDm": rel_value_c,
                        "Cost_to_Serve_AEDm": cts_c,
                        "Relationship_Contribution_AEDm": rel_con_c,
                        "Risk_Stage": risk_stage,
                        "Movement_USDm": movement_c,
                        "Movement_Reason": movement_reason,
                    }
                )

        # Build Branch population bridge from the same RM facts.
        rm_month_df = pd.DataFrame([x for x in rm_rows if x["Month_Start"] == month])
        for bi, branch in enumerate(BRANCHES):
            sub = rm_month_df[rm_month_df["Branch"] == branch]
            attributed = float(sub["PE_CASA_USDm"].sum())
            bm_owned = attributed * (0.025 + 0.007 * (bi % 4))
            unassigned = attributed * (0.006 + 0.003 * ((bi + 1) % 3))
            margins_sundries = attributed * (0.012 + 0.002 * (bi % 3))
            management_pe = attributed + bm_owned + unassigned + margins_sundries
            branch_structural_cost = float((0.18 + 0.018 * bi) * month_frac)
            branch_rows.append(
                {
                    "Month_Start": month,
                    "As_Of_Date": as_of,
                    "Month_Label": md.Month_Label,
                    "Quarter_Label": md.Quarter_Label,
                    "Branch": branch,
                    "RM_Attributed_USDm": attributed,
                    "BM_Owned_USDm": bm_owned,
                    "Unassigned_USDm": unassigned,
                    "Margins_Sundries_USDm": margins_sundries,
                    "Management_PE_USDm": management_pe,
                    "Structural_Cost_AEDm": branch_structural_cost,
                }
            )

    rm_monthly = pd.DataFrame(rm_rows)
    customer_monthly = pd.DataFrame(customer_rows)
    branch_monthly = pd.DataFrame(branch_rows)

    _validate_data(roster, rm_monthly, customer_monthly, branch_monthly)
    return DemoData(roster, rm_monthly, customer_monthly, branch_monthly, month_dim)


def _validate_data(roster: pd.DataFrame, rm: pd.DataFrame, cust: pd.DataFrame, branch: pd.DataFrame) -> None:
    assert roster["RM"].nunique() == len(TEAM_NAMES)
    assert roster["Branch"].nunique() == len(BRANCHES)
    assert set(roster["RM"]) == set(TEAM_NAMES)
    assert not roster["RM"].str.contains("Placeholder", case=False).any()

    # Customer → RM reconciliation by month.
    c = cust.groupby(["Month_Start", "Employee_ID"], as_index=False).agg(
        Dep=("Deposits_USDm", "sum"),
        Adv=("Advances_AEDm", "sum"),
        RelValue=("Relationship_Value_AEDm", "sum"),
        CTS=("Cost_to_Serve_AEDm", "sum"),
        RelCon=("Relationship_Contribution_AEDm", "sum"),
    )
    x = rm.merge(c, on=["Month_Start", "Employee_ID"], how="left")
    assert np.allclose(x["PE_CASA_USDm"], x["Dep"], atol=1e-8)
    assert np.allclose(x["Advances_AEDm"], x["Adv"], atol=1e-8)
    assert np.allclose(x["Relationship_Value_AEDm"], x["RelValue"], atol=1e-8)
    assert np.allclose(x["Cost_to_Serve_AEDm"], x["CTS"], atol=1e-8)
    assert np.allclose(x["Relationship_Contribution_AEDm"], x["RelCon"], atol=1e-8)

    # Economic equations.
    assert np.allclose(
        rm["Relationship_Value_AEDm"],
        rm["Deposit_Funding_Value_AEDm"] + rm["Lending_Contribution_AEDm"] + rm["NFI_AEDm"],
        atol=1e-10,
    )
    assert np.allclose(
        rm["Relationship_Contribution_AEDm"],
        rm["Relationship_Value_AEDm"] - rm["Cost_to_Serve_AEDm"],
        atol=1e-10,
    )
    assert np.allclose(
        rm["RM_Economics_AEDm"],
        rm["Relationship_Contribution_AEDm"] - rm["Direct_RM_Cost_AEDm"],
        atol=1e-10,
    )
    assert np.allclose(
        rm["Net_Movement_USDm"],
        rm["Organic_Movement_USDm"] + rm["Transfer_Adjustment_USDm"] + rm["Maturity_Runoff_USDm"] + rm["New_Funding_USDm"],
        atol=1e-10,
    )
    assert rm.groupby("Month_Start")["Transfer_Adjustment_USDm"].sum().abs().max() < 1e-10

    # Branch management PE bridge.
    assert np.allclose(
        branch["Management_PE_USDm"],
        branch["RM_Attributed_USDm"] + branch["BM_Owned_USDm"] + branch["Unassigned_USDm"] + branch["Margins_Sundries_USDm"],
        atol=1e-10,
    )


def account_rows(customer_period: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for r in customer_period.itertuples(index=False):
        shares = [0.64, 0.36]
        products = ["Current Account", "Term Deposit"]
        currencies = ["AED", "USD"]
        for i, sh in enumerate(shares, start=1):
            rows.append(
                {
                    "RM": r.RM,
                    "Branch": r.Branch,
                    "CIF": r.CIF,
                    "Customer": r.Customer,
                    "Account_No": f"{BRANCH_CODES[r.Branch]}-XXXX-{r.CIF[-3:]}-{i}",
                    "Product": products[i-1],
                    "Currency": currencies[i-1],
                    "Cohort": r.Cohort,
                    "Open_Date": r.Open_Date,
                    "Balance_USDm": r.Deposits_USDm * sh,
                    "Avg_Balance_USDm": r.Avg_Deposits_USDm * sh,
                }
            )
    return pd.DataFrame(rows, columns=ACCOUNT_COLUMNS)


def facility_rows(customer_period: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for r in customer_period.itertuples(index=False):
        if r.Advances_AEDm <= 1.0:
            continue
        rows.append(
            {
                "RM": r.RM,
                "Branch": r.Branch,
                "CIF": r.CIF,
                "Customer": r.Customer,
                "Facility_No": f"FAC-{r.CIF[-6:]}",
                "Outstanding_AEDm": r.Advances_AEDm,
                "Maturity_Date": (pd.Timestamp(r.As_Of_Date) + pd.Timedelta(days=180 + int(r.Advances_AEDm) % 540)).date(),
                "Risk_Stage": r.Risk_Stage,
            }
        )
    return pd.DataFrame(rows, columns=FACILITY_COLUMNS)


def trade_rows(customer_period: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for i, r in enumerate(customer_period.itertuples(index=False), start=1):
        if r.NFI_AEDm <= 0.005:
            continue
        rows.append(
            {
                "RM": r.RM,
                "Branch": r.Branch,
                "CIF": r.CIF,
                "Customer": r.Customer,
                "Transaction_Ref": f"TRX-{r.CIF[-6:]}-{i:02d}",
                "Type": ["Trade Fee", "FX", "Remittance"][i % 3],
                "Income_AEDm": r.NFI_AEDm,
            }
        )
    return pd.DataFrame(rows, columns=TRADE_COLUMNS)
