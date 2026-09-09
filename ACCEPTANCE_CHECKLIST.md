# Acceptance Checklist — Final Governed Target & OPEX Application

## Technical
- [x] Core Python files compile.
- [x] Model/reconciliation smoke suite passes.
- [x] Server-rendered UI suite passes.
- [x] Live HTTP GET/POST workflow tests pass.
- [x] All management pages render in Month and Quarter views.
- [x] Daily available-date selector and operational filters render.
- [x] No Streamlit frontend dependency; stable server-rendered Python application.
- [x] Flat package; local UBL logo; no required subfolders.

## Filters / scope
- [x] Month/Quarter expose Branch, Role, RM, Segment, ETB/NTB, Portfolio Quality and Performance Band filters.
- [x] RM Focus cascades from Branch and Role so only eligible RMs are listed.
- [x] Existing stale RM-to-Branch / RM-to-Role conflicts trigger a non-blocking confirmation panel before scope changes.
- [x] Conflict actions support: align scope to RM; keep Branch/Role and clear RM; or cancel with current result unchanged.
- [x] Customer filters refine relationship/customer analysis without silently recutting full-RM target/direct-cost measures.
- [x] Branch C/I remains a whole-Branch measure under RM/Role/Band filtering.

## Target governance
- [x] Target Management module exists.
- [x] Viewer, Finance Target Maker and Finance Target Approver experiences exist.
- [x] Maker can submit Branch target revisions.
- [x] Maker can submit RM target revisions for the selected valid RM/Branch scope.
- [x] Submitted target receives a new version and `PENDING_APPROVAL` status.
- [x] Existing approved target stays live while a revision is pending.
- [x] Approver can approve or reject pending targets.
- [x] Backend maker-checker rule prevents the maker from approving their own target.
- [x] Viewer cannot approve or reject targets.
- [x] Rejected/pending target versions remain in audit history.
- [x] Only latest `APPROVED` targets feed RM/Branch performance.
- [x] Branch target allocation shows approved Branch target, approved RM allocations, unallocated/BM-management amount and allocation coverage.
- [x] Target page explicitly positions Tableau as read-only in production.

## Management UX
- [x] Executive → Branch → RM → CIF → Account drill-down.
- [x] RM 360 tabs: Performance, Portfolio & Drivers, Economics & Cost, Portfolio Quality, Explainability.
- [x] RM Performance uses approved R3M target register.
- [x] RM 360 shows approved target audit/version and separately shows the reference target basis.
- [x] RM Economics exposes direct employee-cost components and employee C/I.
- [x] Branch Performance shows approved Branch target and RM allocation coverage.
- [x] Cost & Economics shows UAE Network → Branch → RM hierarchy.
- [x] Daily Management integrates Branch portfolio, RM/SRM position, Top Management Portfolio Deposits and major customer movements.
- [x] Methodology includes target governance and Tableau read-only posture.

## Branch OPEX / economics
- [x] Whole-Branch cost uses three management buckets: People Cost; Premises & Occupancy; Other Operating & Support.
- [x] People Cost includes direct RM cost plus other Branch staff cost.
- [x] Premises & Occupancy includes rent/lease/utilities/physical Branch cost concept.
- [x] Other Operating & Support captures technology/admin/operations/depreciation/approved shared-support concept.
- [x] The three OPEX buckets reconcile to Total Branch OPEX.
- [x] Customer CTS is displayed as an attribution lens and is not double-counted into whole-Branch OPEX.
- [x] Branch C/I = Total Branch OPEX ÷ Branch Relationship Value.
- [x] Fully-loaded Branch Economics = Branch Relationship Value − Total Branch OPEX.

## Reconciliation
- [x] Customer → RM deposits and advances reconcile.
- [x] Account → CIF deposits reconcile.
- [x] Relationship Value, Relationship Contribution and RM Economics identities reconcile.
- [x] Direct employee components reconcile to total Direct RM Cost.
- [x] Whole-Branch People Cost includes RM and non-RM staff once.
- [x] Movement bridge reconciles and transfers net to zero.
- [x] Management PE population bridge reconciles.

## Production decisions still required
- [ ] Authoritative RM master and effective-dated RM org history.
- [ ] Authoritative effective-dated CIF → RM ownership history.
- [ ] Final target-setting policy, metrics, approver(s) and delegated approval rules.
- [ ] Approved internal target-entry/workflow technology and product target schema.
- [ ] UBL SSO/AD groups and backend authorization mapping for Viewer/Maker/Approver.
- [ ] Tableau live vs extract refresh design for approved targets.
- [ ] Finance-approved deposit/lending/NFI economics and FTP treatment.
- [ ] Payroll/Finance approved direct employee-cost feed.
- [ ] Finance GL/CRC mapping into People / Premises & Occupancy / Other Operating & Support.
- [ ] Approved treatment of shared/central costs and any allocation drivers.
- [ ] Approved risk/controls/service inputs.
- [ ] UAT, DQ monitoring and governance before formal employee consequences.
