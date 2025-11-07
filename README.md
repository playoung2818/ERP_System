## Lead Time Assignment Workflow
<img width="1691" height="567" alt="image" src="https://github.com/user-attachments/assets/995b4df0-06fe-4c86-86a8-ba2ff2670364" />

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




