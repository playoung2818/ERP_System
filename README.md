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



