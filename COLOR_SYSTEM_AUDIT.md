# DayBreak Color System Audit

Audit date: 2026-08-04

Scope: the canonical Vite/React website, Tailwind configuration, global and route CSS, inline styles, SVG markup, responsive states, generated build, and the tracked duplicate website artifacts. Photographs, video thumbnails, user media, and native emoji artwork were not recolored.

## 1. Problems Found

### Fragmented palettes

- `website/src/App.css` still carried the retired marketing palette (`#2B2631`, `#393241`, `#7C6D8C`, `#938E97`, `#C9B8D8`, `#CFCBD3`, and related alpha variants) even though `index.css` already defined the approved DayBreak palette.
- `website/src/reels.css` mixed the brand system with unrelated green, teal, blue, gold, and pink topic colors. Examples included `#527765`, `#4D7182`, `#A66E2C`, `#9BC7B9`, `#E8A23D`, `#8BA989`, and `#EFA8B6`.
- `website/src/auth.css` implemented a second light/dark gray-purple theme rather than consuming the shared semantic tokens.
- Inline component styles in `About.jsx`, `Contact.jsx`, `FeedCard.jsx`, `PhaseIconCarousel.jsx`, and `RebootPage.jsx` bypassed the theme. The About divider used a neon purple/cyan/pink gradient, and Contact used an unrelated orange.
- The Google icon in `AuthPage.jsx` introduced four saturated third-party colors inside an otherwise controlled interface.

### Semantic and state problems

- Morning Light was assigned directly to the large `background-subtle` role. This made challenge rows, form inputs, stat cards, and surrounding surfaces merge into a large yellow field.
- Exact Horizon Rose (`#CE6969`) was used for some 12px labels. Rose on white is only 3.59:1, below WCAG AA for normal text.
- Several Coral action buttons used the general text token (`#233A57`) instead of the darker on-action token (`#172A42`). The former is only 4.40:1 on Coral; the corrected pair is 5.53:1.
- Dark-mode secondary and status fills used lightened colors with white foregrounds, creating weak contrast.
- Primary action hover behavior was inconsistent: some controls only moved, some darkened with black mixing, and others had no visible color change.
- Selected states varied between Coral, unrelated topic colors, and generic surface fills.
- A legacy `.research-session-controls` block in `reels.css` conflicted with the dedicated implementation in `components/research/research.css` and used an unrelated mint button.

### Obsolete and duplicate sources

- Tracked files suffixed with ` 2` duplicated website source, styles, config, public assets, and QA scripts. Several contained the retired palette and the prior brand name. They were verified as unreferenced and removed so source searches and future imports cannot reintroduce obsolete colors.
- Unused legacy marketing color variables (`--ct-aqua`, `--ct-paper-2`, `--ct-fog`, `--ct-charcoal`, `--ct-card-border`, and `--wing-green-rgb`) were removed.

### Color inventory

The initial inventory included the approved palette plus the legacy families listed above, black/white media neutrals, framework Google colors, and many hardcoded alpha variants. No chart library or separate component-library theme provider was found; Feed Compass bars are styled in `reels.css`.

The final canonical source inventory is:

- Approved brand: `#233A57`, `#6D597A`, `#CE6969`, `#E6866C`, `#FFDFAB`.
- Light surfaces/text: `#FFF9EF`, `#FFF1DC`, `#FFFFFF`, `#FFFDF9`, `#4B5563`, `#687181`, `#D7C9BA`, `#8E7D79`.
- Accessible light interaction derivatives: `#DE775F`, `#A84E55`, `#F8E3DF`, `#172A42`, `#ECE5DC`, `#747B86`.
- Light status derivatives: `#2F6F58`, `#8A5A16`, `#A33A46`.
- Dark surfaces/text: `#18263A`, `#20344E`, `#233A57`, `#2A4465`, `#FFF9EF`, `#EADCC9`, `#C5B8A8`, `#52667C`, `#8390A0`.
- Accessible dark interaction/status derivatives: `#F09A82`, `#C8B8D2`, `#ED929D`, `#A84E55`, `#553E4B`, `#79B89C`, `#E0B263`, `#2A3B50`, `#A99F93`, `#172A42`.
- Remaining raw black/white values and alpha variants are limited to masks, video-player wells, media scrims, text over video, and neutral shadows. All colored alpha variants are now generated from semantic or approved-palette custom properties.

## 2. Design Token System

The project continues to use its existing CSS custom properties plus Tailwind theme extension. No second styling system was introduced.

### Brand tokens

| Token | Value | Intended use |
| --- | --- | --- |
| `--db-color-midnight-horizon` | `#233A57` | Primary text, headings, navigation, dark surfaces |
| `--db-color-twilight-violet` | `#6D597A` | Links, secondary actions, icons, supporting UI |
| `--db-color-horizon-rose` | `#CE6969` | Decorative highlights and emotional emphasis |
| `--db-color-sunrise-coral` | `#E6866C` | Primary actions, active controls, progress |
| `--db-color-morning-light` | `#FFDFAB` | Warm accents, hero/decorative surfaces |

### Core semantic tokens

| Role | Light value | Dark value | Notes |
| --- | --- | --- | --- |
| Page background | `#FFF9EF` | `#18263A` | Warm, low-saturation canvas |
| Subtle background | `#FFF1DC` | `#20344E` | Softened Morning Light for large surfaces |
| Card / surface | `#FFFFFF` | `#233A57` | Default cards and panels |
| Elevated surface | `#FFFDF9` | `#2A4465` | Menus, dialogs, raised controls |
| Primary text | `#233A57` | `#FFF9EF` | Body and headings |
| Secondary text | `#4B5563` | `#EADCC9` | Supporting copy |
| Muted text | `#687181` | `#C5B8A8` | Captions/placeholders |
| Border | `#D7C9BA` | `#52667C` | Default dividers and outlines |
| Strong border | `#8E7D79` | `#8390A0` | Inputs and high-definition edges |
| Primary action | `#E6866C` | `#E6866C` | Buttons and active controls |
| Primary hover | `#DE775F` | `#F09A82` | Visible hover without unrelated colors |
| On primary | `#172A42` | `#172A42` | AA text on Coral |
| Secondary action | `#6D597A` | `#C8B8D2` | Outlined/secondary controls |
| Link | `#6D597A` | `#FFDFAB` | Replaces browser-default blue |
| Link hover | `#A84E55` | `#F09A82` | Distinct hover treatment |
| Highlight text | `#A84E55` | `#ED929D` | Accessible text counterpart to Rose |
| Selected | `#A84E55` | `#A84E55` | Selected tabs, controls, and cards |
| Selected subtle | `#F8E3DF` | `#553E4B` | Selected-state surface |
| Focus ring | `#6D597A` | `#FFDFAB` | 3px high-visibility keyboard ring |
| Input background | `#FFFFFF` | `#20344E` | Form fields |
| Disabled background | `#ECE5DC` | `#2A3B50` | Disabled controls without opacity-only styling |
| Disabled text | `#747B86` | `#A99F93` | Discernible disabled labels |
| Navigation / footer | `#233A57` | `#172A42` | Stable dark brand framing |
| Overlay | Midnight-derived 68% | Midnight-derived 76% | Dialog and media scrims |

Status tokens remain carefully derived neutrals/tones for usability: success `#2F6F58` / `#79B89C`, warning `#8A5A16` / `#E0B263`, and error `#A33A46` / `#ED929D`. Dark status foregrounds switch to `#172A42` so light status fills retain AA contrast.

Tailwind aliases now expose link, link-hover, highlight text, input background, disabled background/foreground, navigation, footer, and tokenized on-color RGB channels.

## 3. Files Changed

| File | Change |
| --- | --- |
| `website/src/index.css` | Refined light/dark semantic tokens, link/hover/highlight roles, inputs, disabled states, navigation/footer roles, on-colors, and global link hover behavior. |
| `website/tailwind.config.js` | Added semantic utilities and removed hardcoded on-color channel values. |
| `website/src/components/ui/primitives.css` | Corrected input/disabled styles, selected tabs, and dark-safe tooltip text. |
| `website/src/App.css` | Migrated the full marketing system from the retired gray/lavender palette to DayBreak tokens; updated gradients, illustrations, decorative alpha colors, and footer framing; removed unused color variables. |
| `website/src/app-shell.css` | Tokenized navigation and corrected hover/active chrome colors. |
| `website/src/reels.css` | Replaced unrelated topic/status colors and hardcoded fallbacks, corrected action/selected/hover states, tokenized shadows/overlays, and removed conflicting research controls. |
| `website/src/home.css` | Standardized primary action hover behavior. |
| `website/src/auth.css` | Removed the parallel auth palette and wired auth/profile pages to shared light/dark tokens. |
| `website/src/saved.css` | Replaced legacy near-black overlay values with Midnight-derived media neutrals. |
| `website/src/components/profile/public-auth.css` | Added accessible highlight/hover aliases and corrected auth button/eyebrow states. |
| `website/src/components/profile/AuthPage.jsx` | Recolored inline Google SVG paths to the inherited semantic interface color. |
| `website/src/components/About.jsx` | Replaced neon gradient and purple border with approved palette tokens. |
| `website/src/components/Contact.jsx` | Replaced unrelated orange and invalid alpha concatenation with token-based color mixing. |
| `website/src/components/FeedCard.jsx` | Replaced hardcoded card palettes and badges with semantic color mixes. |
| `website/src/components/PhaseIconCarousel.jsx` | Tokenized the violet drop shadow. |
| `website/src/components/RebootPage.jsx` | Tokenized animated depth shadows. |
| `website/qa/color-audit-capture.mjs` | Added a reproducible matched-route screenshot matrix. |
| `website/* 2.*`, `website/src/* 2.*`, `website/qa/* 2.mjs`, `website/public/favicon 2.svg` | Removed verified unreferenced duplicate artifacts that retained obsolete source/theme values. |

## 4. Accessibility Review

Representative WCAG contrast ratios after correction:

| Pair | Light | Dark |
| --- | ---: | ---: |
| Primary text / page | 11.05:1 | 14.56:1 |
| Secondary text / page | 7.22:1 | 11.31:1 |
| Muted text / card | 4.92:1 | 5.95:1 |
| Link / page | 5.97:1 | 11.90:1 |
| Link hover / page | 5.16:1 | 7.01:1 |
| Accessible highlight / page | 5.16:1 | 6.68:1 |
| On-action text / Coral | 5.53:1 | 5.53:1 |
| On-action text / hover | 4.78:1 | 6.67:1 |
| Selected text / selected fill | 5.40:1 | 5.40:1 |
| Status foreground / success | 5.94:1 | 6.33:1 |
| Status foreground / warning | 5.91:1 | 7.41:1 |
| Status foreground / error | 6.46:1 | 6.36:1 |

Fixes include replacing small Rose/Coral copy with accessible semantic text colors, avoiding opacity-only disabled fields, retaining a 3px focus ring, standardizing hover colors, and using darker text on light dark-mode status/secondary fills.

Remaining limitations:

- Text over externally loaded videos still depends partly on source imagery. Midnight scrims and text shadows reduce this risk, but per-frame contrast cannot be guaranteed without analyzing the media itself.
- Native emoji colors are platform-controlled and intentionally preserved as content, not interface color.
- Disabled controls are intentionally lower emphasis; they remain visually discernible but are not required to meet normal text contrast under WCAG.

## 5. Before-and-After Screenshots

Matched screenshots are stored in:

- `color-audit-screenshots/before/`
- `color-audit-screenshots/after/`

The same script, routes, themes, viewport sizes, reduced-motion setting, and deterministic local state were used for both sets.

| Screenshot case | Route | Viewport/theme |
| --- | --- | --- |
| `feed-desktop-light` | `/` | 1440×900 light |
| `feed-laptop-light` | `/` | 1280×800 light |
| `feed-tablet-light` | `/` | 768×1024 light |
| `feed-mobile-light` | `/` | 390×844 light |
| `feed-mobile-dark` | `/` | 390×844 dark |
| `challenges-desktop-light` | `/challenges` | 1440×900 light |
| `challenges-mobile-dark` | `/challenges` | 390×844 dark |
| `saved-tablet-light` | `/saved` | 768×1024 light |
| `login-desktop-light` | `/login` | 1440×900 light |
| `login-mobile-dark` | `/login` | 390×844 dark |
| `diagnostic-mobile-light` | `/diagnostic` | 390×844 light |
| `profile-tablet-light` | `/profile` | 768×1024 light |
| `study-desktop-light` | `/study` | 1440×900 light |

Additional responsive and study-state screenshots are generated by `website/qa/responsive-check.mjs` and `website/qa/study-check.mjs` under `website/qa/screenshots/`.

## 6. Validation

- Unit tests: 90/90 passed.
- Production build: passed (`vite build`). Vite reports the existing large-chunk advisory for the 527.73 kB JavaScript bundle.
- Responsive QA: 16/16 onboarding/feed cases passed from 390×844 through 2560×1440, with zero measured overflow and zero browser errors.
- Study QA: passed at 320×568, 375×667, 768×1024, 1024×768, and 1440×900, including loading, reduced motion, error/retry, focus, hidden-condition, and completion states.
- `git diff --check`: passed.
- Type checking: not configured; the website is JavaScript-only and has no `tsconfig`, `jsconfig`, or type-check script.
- Python tests: could not run in this environment because `python` is unavailable and `python3` does not have `pytest` installed. No backend code was modified.
- ESLint: ran and remains blocked by 20 pre-existing, non-color React/unused-variable errors and one warning in legacy components. No reported item points to the color changes. Representative existing failures are in `BlurText.jsx`, `FirstRunGate.jsx`, `DiagnosticPage.jsx`, `useVideoOrientation.js`, and `events.js`.

## 7. Remaining Recommendations

- When the dormant marketing `RebootPage` is routed publicly again, perform a designer-led screenshot pass of its long-form hero, story, and footer sequence. Its code is now tokenized, but the current router exposes the feed at `/`, so those sections cannot be captured without changing product routing.
- Decide whether native challenge/diagnostic emoji should remain part of the visual voice or eventually be replaced by a bespoke DayBreak illustration set. This is an art-direction decision, not a color-system defect.
- If the product later supports user-selectable themes beyond light/dark, extend the same semantic contract rather than adding route-local palettes.
