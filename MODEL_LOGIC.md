# Final Management Model Logic

## 1. Decision path
UAE → Branch → RM → CIF → Account / Facility / Trade-NFI

`RMCode` is the permanent canonical RM key in the production logical model.

## 2. Daily management
Daily is an operational management layer, not a daily employee score. It combines:
- Branch portfolio deposits and advances;
- RM/SRM daily position and averages;
- Top Management Portfolio Deposits;
- major customer inflow/outflow drivers;
- previous available reporting date, prior month-end and Dec-25 comparisons.

## 3. Sustainable performance horizon
PE CASA = current stock.

Current R3M Average CASA = day-weighted latest three monthly average-balance facts.

Prior R3M Average CASA = immediately preceding non-overlapping three-month window.

R3M Growth = Current R3M − Prior R3M.

## 4. Governed target logic
The official target is no longer assumed to be the model-calculated reference target.

Production operating model:

**Target Maker → Pending Approval → Authorised Checker → Approved Target → Tableau**

Target grain:

**Period × Target Level × Branch/RM × Metric × Version**

Minimum target controls:
- TargetID
- TargetLevel (`BRANCH` / `RM`)
- BranchCode
- RMCode where applicable
- MetricCode
- Period / effective dates
- TargetValue
- Version
- Status
- CreatedBy / SubmittedAt
- ApprovedBy / ApprovalDate or rejected audit
- Reason / comments

Only the latest `APPROVED` version for the selected key feeds performance. A pending or rejected revision cannot supersede the existing approved target.

### Branch target allocation
Approved Branch Target can be compared with approved RM allocations:

Unallocated / BM Management = Approved Branch Target − Sum(Approved RM Targets)

Allocation Coverage = Sum(Approved RM Targets) ÷ Approved Branch Target

The model does not force Branch Target = sum of RM targets because a legitimate BM-owned / management / unallocated amount may exist.

### Reference target basis
The model may still calculate a transparent reference target:

Final Growth Reference = Prior R3M × Base Strategy Growth × Branch Opportunity × Role × Availability × Tenure

Reference R3M Target = Prior R3M + Final Growth Reference

This remains decision support until Business approves a target into the governed register.

## 5. Movement bridge
Net Movement = Organic + Transfer Adjustment + Maturity / Scheduled Outflow + New Funding.

Administrative transfers remain separate from organic performance.

## 6. Performance index
The existing V1 ten-component demonstration architecture is retained. Each measure produces 0–120 points against its approved target/benchmark, then:

Weighted Contribution = Points × Weight

The target-dependent components recalculate when a new approved target becomes effective.

## 7. Portfolio quality
Portfolio quality is shown with Stage 2, Stage 3, impairment, controls, service and data completeness. Production risk attribution requires approved source/grain and attribution rules.

## 8. Relationship / RM economics
Relationship Value = Deposit Funding Value + Lending Contribution + Fees/NFI.

Relationship Contribution = Relationship Value − Customer CTS.

RM Employee C/I = Direct RM Employee Cost ÷ Attributable Relationship Value.

RM Economics = Relationship Contribution − Direct RM Employee Cost.

Production direct employee-cost grain:

**RMCode × Month × CostComponent**

Potential components include salary, allowances, approved benefits, medical/insurance, EOS/gratuity accrual and other approved direct employment costs.

## 9. Customer cost-to-serve
Customer CTS = Σ(Activity Count × Unit Cost).

Current prototype activity drivers: Onboarding, KYC Review, Credit Review, Trade Transaction, Service / Exception.

No defendable driver → do not force an arbitrary customer allocation.

**Important:** Customer CTS is an analytical attribution of operating resources. At Branch level it is not added a second time when those underlying resources are already included in whole-Branch OPEX.

## 10. Whole-Branch OPEX
Management view uses three buckets:

### People Cost
All Branch people cost, including RMs, Branch Manager and operations/service/support staff.

### Premises & Occupancy
Rent/lease, utilities, maintenance, security, cleaning and approved physical-Branch costs.

### Other Operating & Support
Technology/connectivity, administration, operations/processing, depreciation and approved shared support.

Total Branch OPEX = People Cost + Premises & Occupancy + Other Operating & Support

Branch C/I = Total Branch OPEX ÷ Branch Relationship Value

Fully-loaded Branch Economics = Branch Relationship Value − Total Branch OPEX

At RM level, Direct RM Cost remains separate; at Branch level it rolls into People Cost. This prevents double-counting.

Prototype structural-cost allocation is synthetic: non-RM staff, premises and other operating/support are generated solely to make the management experience testable. Production must use Finance GL/CRC/cost-centre mappings and approved allocation logic.

## 11. Tableau production posture
Target architecture separates logical dimensions/facts such as:
- DimDate
- DimRM
- DimBranch
- DimCustomer
- DimProduct
- FactOwnership
- FactDepositDaily
- FactAverageBalance
- FactLending
- FactNFI
- FactActivityCost
- FactEmployeeCost
- FactBranchCost
- FactTarget

Tableau is the **read-only consumption layer**. It should consume governed calculations / views rather than independently recreating business rules in each workbook.

Target workflow writes to a product-owned target register through an approved internal application/workflow. Tableau reads an approved-target view; it does not write to core banking systems.

## 12. Filter governance
- Management scope: Branch, Role, RM Focus and Performance Band.
- Customer filters: Customer Segment, Relationship Cohort (ETB/NTB) and Portfolio Quality.
- Daily-only diagnostic: Movement Direction.
- RM Focus cascades from selected Branch and Role.
- RM target, performance index and direct employee cost continue to show the full RM position when customer filters are used.
- Branch OPEX and Branch C/I continue to show the whole Branch position under RM-level analytical filtering.
