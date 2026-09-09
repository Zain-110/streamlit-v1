# Target Management — Production Design

## Decision
Tableau is not the system of record for targets and does not write to core banking systems.

The product owns a governed target register. An approved internal input/workflow application writes target proposals to it. Tableau reads only an approved-target view.

## Flow
```text
Finance Target Maker
        ↓
Create / revise Branch or RM target
        ↓
PENDING_APPROVAL
        ↓
Finance Target Approver
   ↙              ↘
REJECTED       APPROVED
                  ↓
          Approved_Targets view
                  ↓
       Governed metric / rule layer
                  ↓
                Tableau
```

## Target hierarchy
The application supports:
- Branch targets;
- RM targets;
- approved RM allocation vs approved Branch target;
- unallocated / BM-management amount;
- allocation coverage.

## Maker-checker rules
1. Maker may create/revise and submit.
2. Maker cannot approve own target.
3. Approver may approve or reject pending records.
4. Viewer cannot write.
5. Existing approved target remains in force until a replacement is approved.
6. Every revision creates a new version; history is retained.
7. Only `APPROVED` records are eligible for performance.

## Production security
Do not rely on hidden Tableau buttons. Authorization must be enforced by the target application/backend/database layer using approved UBL identity groups.

Recommended database posture:
- target application service: controlled INSERT / workflow UPDATE permissions;
- Tableau service account: SELECT only on governed/published views;
- no Tableau INSERT/UPDATE/DELETE on target or core-system tables.

## Technology
Do not hard-code Oracle/APEX or any other technology into the product requirement until UBL Architecture confirms the approved internal platform. If an existing on-prem workflow/low-code capability is already approved, reuse it rather than introducing a new external platform.
