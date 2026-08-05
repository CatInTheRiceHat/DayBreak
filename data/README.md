# Project data

- `curation/` — reviewed or generated curation inputs
- `datasets/` — algorithm fixtures and generated datasets
- `local/` — local SQLite databases
- `schema/` — schema snapshots; ordered production changes remain in `migrations/`

`data/local/chrysalis.db` is the default local database. Set `DATABASE_PATH` to
override it; relative overrides are resolved from the repository root.
