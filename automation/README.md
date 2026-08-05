# Automation

This package is the boundary for scheduled and background work. It currently
contains configuration only; production entry points still live in `api/`, and
manual commands live in `scripts/`.

Add a file under `jobs/` only for orchestration that can be called by an API,
scheduler, or command without duplicating domain logic from `core/` or
`integrations/`.

The detailed automation inventory is archived at
`docs/reports/automation-inventory.md`.
