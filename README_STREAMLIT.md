# UBL UAE RM Cost & Performance Management — Streamlit Cloud Demo

This package is the shareable Streamlit version of the latest governed-targets + Branch OPEX prototype.

## GitHub Codespaces
```bash
bash start.sh
```
Open forwarded port 8501.

## Streamlit Community Cloud
1. Create / use a GitHub repository.
2. Upload all files from this ZIP to the repository root.
3. Open Streamlit Community Cloud and create an app from that repository.
4. Main file path: `streamlit_app.py`
5. Deploy.

## Included
- Executive Overview
- Daily Management
- Cascading Branch → Role → RM filters
- RM Performance
- RM 360
- Branch Performance
- Customer & Relationship
- Cost & Economics
- Three-bucket Branch OPEX:
  - People Cost (includes RMs and all Branch staff)
  - Premises & Occupancy (rent/lease, utilities, physical Branch costs)
  - Other Operating & Support
- Target Management
  - Branch and RM targets
  - Maker / checker
  - Pending / Approved / Rejected
  - Version history
  - Only APPROVED targets feed performance
- Methodology / Tableau architecture

## Demo persistence
The prototype target register uses `target_data.json`. On a hosted demo this is only prototype persistence and may reset on app restart/redeploy. Production should use a UBL-approved database/workflow and expose an approved-target view to Tableau.

## Confidentiality
Use synthetic/demo data only on a public Streamlit deployment. Do not upload real UBL customer, employee, Finance, HR or source-system data to a public hosting environment.
