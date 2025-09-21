## Lead Time Assignment Workflow

```text
[Receiving WO]
       ↓
[Check Inventory Status: available > 0 and ATP > 0?]
       ├── Yes → [Check Labor Hour]
       │          ├── Yes → [Assign LT]
       │          └── No  → [Wait until labor available]
       │
       └── No  → [Check if PO for short items exists]
                  ├── Yes → [Assign LT = Vendor Ship Date +7]
                  └── No  → [Ask Brenda to place order]



flowchart TD
    Q1["Does the SO have every item in stock?<br/>(Available, ATP, Counted in Warehouse) [By SO]"]
    Ready["✅ SO is Ready to Ship"]
    Q2["Does the short item have a POD? [By Item]"]
    NoCommit["❌ Cannot commit date (no POD)"]
    Q3["When will the short item arrive? [By Item]"]
    Q4["If sales want to pull in a SO,<br/>what is the earliest date we can give?"]
    Assign["📅 Assign ETA / Latest arrival date"]

    Q1 -->|Yes| Ready
    Q1 -->|No| Q2
    Q2 -->|Yes| Q3
    Q2 -->|No| NoCommit
    Q3 --> Q4
    Q4 --> Assign

