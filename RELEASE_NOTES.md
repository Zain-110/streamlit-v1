# Release Notes — Governed Targets + Whole-Branch OPEX

Compared with the previous cascading-filter release, this version adds:

1. Target Management navigation and full demo workflow.
2. Viewer / Finance Target Maker / Finance Target Approver access simulation.
3. Branch and RM target versioning, pending approval, approval/rejection and audit history.
4. Only approved targets feed RM and Branch performance calculations.
5. Branch target allocation coverage and explicit unallocated/BM-management amount.
6. RM 360 approved-target audit plus separate reference-target basis.
7. Three-bucket whole-Branch OPEX: People; Premises & Occupancy; Other Operating & Support.
8. People Cost includes all Branch staff including RMs; RM cost is not double counted.
9. Customer CTS is kept as an analytical attribution and is not added a second time into whole-Branch OPEX.
10. Tableau is explicitly positioned as a read-only consumption layer in the production architecture.
11. RMCode language is used as the permanent logical RM identity.
12. Previous cascading RM-filter UX and stale-scope conflict protection are retained.
