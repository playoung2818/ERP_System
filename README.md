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


<img width="1691" height="567" alt="image" src="https://github.com/user-attachments/assets/29e73d09-1542-4eba-897a-8347ffe51688" />

