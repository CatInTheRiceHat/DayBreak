# Frontend source layout

- `app/` — router and application-wide boundaries
- `features/` — user-facing code grouped by product area
- `lib/` — shared services, adapters, and hooks
- `shared/` — reusable visual components and UI primitives
- `styles/` — global and cross-feature styles
- `brand.js` — shared product naming constants
- `main.jsx` — Vite entry point

Add feature-specific components, tests, and helpers inside the matching feature.
Move code to `shared/` only after more than one feature genuinely uses it.
