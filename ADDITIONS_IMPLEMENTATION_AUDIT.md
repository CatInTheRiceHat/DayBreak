# Additions Implementation Audit

Audit date: 2026-08-04  
Repository: `/Users/elaine/Documents/DayBreak`  
Scope: every file under `additions/`, traced through the current application, backend, persistence, automation, tests, and deployment configuration.

## 1. Executive Summary

### Result

| Measure | Count |
| --- | ---: |
| Total independently verifiable requirements | 61 |
| Implemented | 12 |
| Partially Implemented | 28 |
| Missing | 10 |
| Unclear | 1 |
| Obsolete or Conflicting | 10 |
| Estimated completion | **43%** |

The completion estimate gives full credit to Implemented and half credit to Partially Implemented requirements: `(12 + 28 × 0.5) / 61 = 42.6%`. Excluding the ten requirements overtaken by the current homepage/product-route decision, the same weighted implementation is approximately 51%. Neither percentage treats a passing build as functional proof.

### Repository and application architecture

- `website/` is a React 19 single-page frontend built by Vite. `website/src/App.jsx` is the route composition point. The current `/` route renders the vertical reels product; several marketing and social-page components remain in the tree but are not reachable.
- `api.py` is the local FastAPI/SQLite service. `api/index.py` is the Vercel/PostgreSQL variant. Both expose feed and preference routes; `research_api.py` supplies the anonymous study API shared by the deployments.
- `core/` contains ranking, labeling, content-integrity, preferences, public-signal, and anonymous-research storage logic. `integrations/` contains YouTube ingestion and SQLite integration code.
- `migrations/` contains PostgreSQL/Supabase schema, RLS, feed, profile, usage-event, trusted-source, AI-curation, and research-session migrations. Local runtime data is present in `chrysalis.db` and `integrations/chrysalis.db`.
- Authentication is browser-side Supabase Auth (`website/src/lib/supabaseClient.js`, `AuthProvider.jsx`, profile components) with RLS-backed profile and usage-event tables. The anonymous research API uses server-validated bearer credentials and token hashes.
- Automation/deployment is split between `.github/workflows/youtube-feed-ingest.yml`, `api/index.py` cron handling, `vercel.json`, and a presently passive `automation/` scaffold. `vercel.json` schedules a route that the API does not implement.
- Tests are in `tests/` and colocated `website/src/**/*.test.js`; browser QA scripts are in `website/qa/`. There is no TypeScript/type-check command.
- Configuration includes root and frontend environment examples, `requirements.txt`, Vite/ESLint/PostCSS/Tailwind configuration, and Vercel configuration.

### `additions` inventory and normalization notes

The required folder exists at `additions/`. It contains exactly two files and no nested files:

1. `additions/DayBreak Website Style Guide.md` — brand, palette, typography, logo, UI, layout, imagery, voice, homepage, motion, and accessibility requirements. Its final line is embedded base64 image data; it was read but does not add a separate behavioral requirement.
2. `additions/DayBreak Problems and Solutions - Executive Summary.csv` — one overarching product thesis, six product principles, an evidence-strength scale, and a prioritization formula.

The style guide repeats the mission and core brand line in its final summary. Those repetitions were consolidated rather than double-counted. Its color prose says Sunrise Coral is used for primary calls to action (lines 53–55), while its exact primary-button specification says Morning Light (lines 158–163); the exact component rule was used for SG-12 and the conflict is recorded under SG-02. The CSV says there are 15 mapped problems, 36 sources, and seven Tier-1 priorities but does not enumerate them, so those numbers are contextual metadata, not verifiable implementation requirements. The evidence scale and priority formula are research-planning methodology, not runtime product requirements.

### Most important gaps

- **Privacy/authorization:** both preference APIs accept caller-supplied `user_id` or `session_id` and read/write records without authenticating or proving ownership. Coarse location fields are included. This is the highest-risk concrete implementation gap.
- **Youth safety:** the repository has only a demo, client-side friends-only predicate. Messaging is not deployed, there is no age model, and no backend adult-to-minor enforcement exists.
- **Wellbeing measurement:** persisted research events are almost entirely exposure/engagement/time events. Autonomy, satisfaction, direct session value, and the requested multidimensional wellbeing outcomes are absent. Diagnostic persistence references a database table for which no migration exists.
- **High-risk friction:** sharing has no misinformation pause; late-night behavior is not detected; repeated sensitive viewing has no per-user circuit breaker. Comment friction is local-only and can be bypassed by the absence of a real messaging/comment backend.
- **Spec/product conflict:** all nine required homepage sections are superseded by `/` rendering `ReelsPage`. The marketing page component is dead code and its copy does not match the requested headings anyway.
- **Visual conformance:** the exact five-color signature gradient is absent; button colors/borders do not meet the exact component rules; Montserrat weights and minimum body sizing are violated throughout the live UI; looping animation remains.

### Validation performed

| Command | Result |
| --- | --- |
| `python3 -m unittest tests.test_algorithm -q` | **Passed:** 87 tests. |
| `cd website && npm run test:unit` | **Passed:** 90 tests, 0 failures. |
| `cd website && npm run build` | **Passed:** Vite built 2,124 modules. It warned that the main JS chunk is 527.60 kB (162.33 kB gzip), above the 500 kB warning threshold. |
| `cd website && npm run lint` | **Failed:** 20 errors and 1 warning. Findings include unused imports in marketing components, state updates inside effects in `BlurText.jsx`, `FirstRunGate.jsx`, `DiagnosticPage.jsx`, and `useVideoOrientation.js`, a Fast Refresh export error in `PhaseIconCarousel.jsx`, and an unused catch binding in `events.js`. |
| `python3 -m pytest -q` | **Could not run:** `/opt/homebrew/opt/python@3.13/bin/python3.13: No module named pytest`. Dependencies were not installed, per the audit constraint. |

The Playwright QA commands were not run because they require separately running preview/backend servers and write screenshots into the repository. Their source was reviewed; `qa/responsive-check.mjs` also targets `/algorithm`, which now redirects to `/` and contains selectors for an unused `.mode-tabs` component.

## 2. Requirement Audit Table

| ID | Requirement | Source in `additions` | Status | Evidence | Missing Work |
| -- | ----------- | --------------------- | ------ | -------- | ------------ |
| SG-01 | Present DayBreak as a teen-centered, thoughtful, warm, ethical, reflective, hopeful, intentional digital-wellbeing project. | Style Guide 1–33, 280–282 | **Implemented** | `website/src/brand.js:8-16`; `website/index.html:10-19`; live auth/feed copy and risk-aware ranking in `core/ranking/modes.py:29-38,213-247`. | None material. |
| SG-02 | Use the five exact core colors in their assigned semantic roles. | Style Guide 36–58 | **Partially Implemented** | Exact tokens exist in `website/src/index.css:18-77` and aliases in `website/src/reels.css:8-29`, but live UI adds non-brand colors and maps primary action to Coral. The guide itself conflicts on primary CTA color at lines 53–55 versus 158–163. | Reconcile the internal CTA-color conflict, remove/justify extra colors, and make semantic component use consistent. |
| SG-03 | Use the recommended 30/25/17/15/13 palette proportions. | Style Guide 60–70 | **Partially Implemented** | The ratios are documented as token comments in `website/src/index.css:18-33`; no implementation, visual test, or generated theme enforces or measures them. | Apply the ratios to the active route and add visual/token conformance checks. |
| SG-04 | Make the exact five-stop Midnight→Twilight→Rose→Coral→Morning linear gradient the central visual signature. | Style Guide 72–75 | **Missing** | Repository search found no gradient containing the five specified stops in order. Existing gradients in `website/src/App.css` and `website/src/reels.css` use subsets or unrelated colors. | Add a shared signature-gradient token and use it prominently in the active experience. |
| SG-05 | Use Abril Fatface selectively for hero headlines, page titles, and editorial statements. | Style Guide 79–91 | **Implemented** | Font is loaded in `website/index.html:20-22`, tokenized in `website/src/index.css:79-96`, and used for display/page title styles at `website/src/index.css:331-345` and live reels headings in `website/src/reels.css`. | None material. |
| SG-06 | Restrict Story Script to short decorative accents; never use it for nav, buttons, research, or long copy. | Style Guide 93–103 | **Partially Implemented** | Font is loaded and generally decorative, but `website/src/reels.css` assigns it to live tags/labels, broadening it beyond the specified accent roles. | Limit the font to explicit one-to-four-word decorative accents and test prohibited roles. |
| SG-07 | Use Montserrat weight 400 for all ordinary website text; create hierarchy without weight changes. | Style Guide 105–127 | **Partially Implemented** | Montserrat is the global sans font (`website/src/index.css:252-269`), but design-system headings, labels, and buttons use 500/600 (`index.css:347-400`; `components/ui/primitives.css:1-10,96-103`), and live styles include weights through 800. | Normalize ordinary UI text to 400 or formally revise the requirement. |
| SG-08 | Follow the specified type hierarchy, sizes, spacing, and line heights. | Style Guide 129–138 | **Partially Implemented** | Responsive type tokens exist in `website/src/index.css:79-96,322-410`, but card, label, and live feed sizes/weights depart substantially; numerous ordinary text rules are 10–15 px. | Align tokens and all active components with the prescribed ramp. |
| SG-09 | Use a DayBreak wordmark with a minimal horizon/rising-sun transition element, not a cartoon sun. | Style Guide 142–147 | **Implemented** | `website/public/favicon.svg:2-6` is an abstract layered horizon; `DayBreakLogo.jsx:7-15` centralizes it; navigation assembles mark plus wordmark at `Navbar.jsx:107-116`. | None material. |
| SG-10 | Make the visual system minimalist, editorial, research-inspired, warm, reflective, modern, and quietly optimistic. | Style Guide 150–154, 193–202 | **Partially Implemented** | The active feed uses a restrained branded system and abstract media wash, but dead marketing CSS retains a separate grayscale/glass/particle aesthetic, while social/demo pages use another visual language. | Consolidate the active visual system and remove/rework divergent legacy surfaces. |
| SG-11 | Avoid rainbow/neon tech palettes, stock teens-on-phones, alarmist imagery, literal cartoon suns, and excessive simultaneous colors. | Style Guide 203–210 | **Partially Implemented** | No stock teen-phone photography or cartoon sun was found, but live and legacy CSS introduce extra status/Google/dark-mode colors and multi-effect gradients/particles beyond the five-color direction. | Audit visual assets and define justified functional exceptions. |
| SG-12 | Primary button: Morning Light background, Midnight text, no border, 999 px radius. | Style Guide 156–164 | **Partially Implemented** | `components/ui/primitives.css:21-36` gives pill radius and an effectively transparent border, but `--db-color-action-primary` is Coral rather than Morning Light; legacy `.ct-button` is also nonconforming. | Correct the canonical primary variant and migrate active buttons to it. |
| SG-13 | Secondary button: transparent, Midnight text, 1.5 px Midnight border, 999 px radius. | Style Guide 165–170 | **Partially Implemented** | `components/ui/primitives.css:21-25,38-46` has transparent/pill styling but uses Twilight and the generic 1 px border token. | Use Midnight and an explicit 1.5 px border in the canonical variant. |
| SG-14 | Keep layout calm, breathable, uncluttered, and intentional. | Style Guide 174–180 | **Implemented** | Shared spacing/page/section tokens at `website/src/index.css:98-137,304-320` and active layout spacing in `app-shell.css`/`reels.css` provide responsive gutters and section rhythm. | None material. |
| SG-15 | Cards use Morning Light/white, rgba Midnight border, 20–28 px radius, subtle shadow, for research/features/principles/findings. | Style Guide 181–189 | **Partially Implemented** | Canonical `.db-card` uses surface, border, 24 px radius, and subtle shadow (`components/ui/primitives.css:86-99`), but many active cards use 12–16 px radii and do not use the primitive. | Migrate active card families or standardize their equivalent tokens. |
| SG-16 | Use clear, thoughtful, hopeful, research-based, teen-aware, non-preachy, non-fearmongering, nuanced writing. | Style Guide 214–232 | **Implemented** | Active onboarding, reflection, explanation, break, auth, and diagnostic copy consistently frames agency and tradeoffs rather than condemning all social media. Examples: `reelsData.js:22-43`, `sessionBreaks.js:8-18`, `AuthPage.jsx:86-99`. | None material. |
| SG-17 | Use the core tagline “A brighter way to scroll.” | Style Guide 234–236, 280–282 | **Implemented** | Exact wording appears in document title/metadata at `website/index.html:11-19` and `website/src/App.jsx:116-119`. | None material. |
| SG-18 | Homepage hero uses the exact eyebrow and headline. | Style Guide 239–243 | **Obsolete or Conflicting** | `/` renders `ReelsPage` (`App.jsx:92`). `MainPage`/`RebootPage` is dead (`App.jsx:28-30`), and its hero at `RebootPage.jsx:747-805` uses different rotating copy. | Decide whether a marketing homepage still exists; if yes, restore a route and implement exact copy. |
| SG-19 | Homepage Origin title: “How the idea evolved.” | Style Guide 244 | **Obsolete or Conflicting** | No reachable homepage; exact heading not found in the repository. | Same route/product decision as SG-18. |
| SG-20 | Homepage Problem title: “The feed is not neutral.” | Style Guide 245 | **Obsolete or Conflicting** | No reachable homepage; `RebootPage.jsx:846-872` has different problem copy. | Same route/product decision as SG-18. |
| SG-21 | Homepage Solution title: “Designing for a healthier digital rhythm.” | Style Guide 246 | **Obsolete or Conflicting** | No reachable homepage and exact heading not found. | Same route/product decision as SG-18. |
| SG-22 | Homepage Prototype title: “See the idea in action.” | Style Guide 247 | **Obsolete or Conflicting** | No reachable homepage and exact heading not found. | Same route/product decision as SG-18. |
| SG-23 | Homepage Research title: “Testing more than an idea.” | Style Guide 248 | **Obsolete or Conflicting** | No reachable homepage and exact heading not found. | Same route/product decision as SG-18. |
| SG-24 | Homepage Future title: “What I'm building next.” | Style Guide 249 | **Obsolete or Conflicting** | No reachable homepage and exact heading not found. | Same route/product decision as SG-18. |
| SG-25 | Homepage Creator title: “Built by Elaine.” | Style Guide 250 | **Obsolete or Conflicting** | No reachable homepage and exact heading not found; creator material only exists in the dead marketing composition. | Same route/product decision as SG-18. |
| SG-26 | Homepage final CTA: “Ready for a brighter feed?” | Style Guide 251 | **Obsolete or Conflicting** | No reachable homepage and exact heading not found. | Same route/product decision as SG-18. |
| SG-27 | Use standard transitions of 200–400 ms. | Style Guide 255–262 | **Partially Implemented** | Shared durations are tokenized in `website/src/index.css:118-137`; active feed uses a 350 ms transition (`ReelsPage.jsx:711-717`), but many rules/components use durations outside the band. | Normalize standard interactions and document intentional exceptions. |
| SG-28 | Use slow, smooth, natural, purposeful, calm entrances of 400–700 ms. | Style Guide 257–262 | **Partially Implemented** | Navbar uses 600 ms (`Navbar.jsx:99-103`) and marketing components often use this range, but active feed entrance is 350 ms and several effects are faster or ornamental. | Apply entrance tokens consistently to active route transitions. |
| SG-29 | Avoid looping or attention-grabbing animation. | Style Guide 263 | **Missing** | `website/src/App.css` contains infinite caret, wing, particle/cursor and related loops; live code imports the global stylesheet even though much of the marketing UI is dead. | Remove the loops/global legacy CSS or constrain every remaining loop to a necessary state indicator. |
| SG-30 | Respect reduced-motion preferences. | Style Guide 264 | **Implemented** | Global override disables animation/transition at `website/src/index.css:451-463`; components also use reduced-motion hooks, and study QA source asserts it. | None material. |
| SG-31 | Use the specified accessible foreground/background contrast pairs. | Style Guide 266–273 | **Partially Implemented** | Semantic tokens cover Midnight/Morning, light-on-Midnight, and white-on-Twilight combinations, but extra live/legacy colors and no contrast test prevent full confirmation. | Add automated contrast checks for every active semantic pair and state. |
| SG-32 | Do not use Coral, Rose, or Cream for body text. | Style Guide 273 | **Partially Implemented** | Global body text is Midnight (`website/src/index.css:261-269`), but accent/status styles are used on some sentence-length small copy and no semantic linting distinguishes body from labels. | Audit sentence-length copy and reserve accent colors for non-body roles. |
| SG-33 | Body text must be at least 16 px. | Style Guide 274 | **Missing** | Global body is 16 px, but canonical card descriptions are 15 px (`components/ui/primitives.css:97`), and active `reels.css`, `home.css`, `community.css`, `saved.css`, and auth CSS contain many 10–15 px sentence styles. | Raise all paragraph/descriptive text to at least 16 px; preserve smaller sizes only for true labels/captions if the requirement is revised. |
| SG-34 | Provide visible keyboard focus states. | Style Guide 275 | **Implemented** | Global focus-visible outline at `website/src/index.css:294-297`, forced-colors treatment at 466–469, and control-specific focus states in `components/ui/primitives.css:117,151,168`. | None material. |
| SG-35 | Do not communicate meaning through color alone. | Style Guide 276 | **Partially Implemented** | Likes, saved state, warnings, errors, and ranking reasons generally pair color with text/icon/ARIA (`ReelActionRail.jsx:111-164`), but there is no complete accessibility test and several graph/status treatments rely strongly on color. | Audit charts, badges, modes, and moderation states for text/pattern redundancy. |
| SG-36 | Add alt text to meaningful graphics. | Style Guide 277 | **Partially Implemented** | Central logo supports a meaningful alt (`DayBreakLogo.jsx:7-14`), and major marketing artifacts/portrait have descriptions, but some potentially meaningful creator/saved/video images use `alt=""`; routing also makes some audited images dead. | Classify each image as decorative or meaningful and correct ambiguous empty alts. |
| SG-37 | Keep paragraph width around 65–75 characters. | Style Guide 278 | **Partially Implemented** | Shared body/research utilities cap at 72ch (`website/src/index.css:361-366`), but many active components do not use them and use unrelated widths. | Apply a shared readable-measure token to all long-form copy. |
| PR-01 | Redesign specific harm mechanisms—engagement optimization, comparison, harmful amplification, weak privacy, opaque ranking, and moderation failures—rather than treating all use as harmful. | Executive Summary CSV 2 | **Partially Implemented** | Ranking has explicit positive/risk dimensions and gates (`core/ranking/modes.py:29-38,133-247`), explanations exist, and privacy/RLS exists, but real public-signal moderation is a stub and preference authorization is unsafe. | Close privacy/moderation gaps and validate end-to-end outcomes. |
| PR-02 | Preserve connection, identity exploration, creativity, learning, and community support. | Executive Summary CSV 2 | **Partially Implemented** | Educational, prosocial, novelty, and diversity signals affect ranking (`modes.py:213-237`); break activities promote creativity/connection (`sessionBreaks.js:43-54`). Community, connections, and messaging are mock/unreachable. | Implement real, safe connection/community capabilities or narrow the claim. |
| PR-03 | Optimize for session value—connect, learn, create, or recover—not session length. | Executive Summary CSV 8 | **Partially Implemented** | Ranking favors prosocial/educational/calm/reflection content and the feed has progressive breaks, but no session-value question, model target, stored metric, or optimization loop exists. | Define, collect, and use session-value outcomes without turning them into engagement proxies. |
| PR-04 | Let users control ranking goals such as Calm, Connect, Learn, Explore, or Chronological. | Executive Summary CSV 9 | **Partially Implemented** | Onboarding wires three selectable modes (`reelsData.js:22-46`; `ReelsPage.jsx:703-709`), but they are not the five examples, there is no chronological mode, and backend documentation says the source gate/score is shared (`core/ranking/modes.py:1-7,240-254`). | Define real goal semantics, implement goal-specific ordering, and add chronological/control coverage. |
| PR-05 | Explain why recommendations appear. | Executive Summary CSV 9 | **Implemented** | Backend feed items carry ranking/safety/context explanations; live `ReelActionRail.jsx:159-240` opens a “Why?” panel, wired from `ReelCard.jsx:287-310`. | None material. |
| PR-06 | Keep useful analytics private. | Executive Summary CSV 10 | **Implemented** | No public per-user analytics view was found. `usage_events` has insert-only owner RLS and service-role analysis (`migrations/013_usage_events.sql:1-25`); research tables expose no browser policies (`015_research_sessions_and_events.sql:85-90`). | None material for the stated scope. |
| PR-07 | Reduce/remove public like counts. | Executive Summary CSV 10 | **Implemented** | Live action rail shows a private boolean Like action without counts (`ReelActionRail.jsx:111-121`); `useLikedVideos.js` stores it locally and explicitly has no public backend source of truth. | None material. |
| PR-08 | Reduce streak pressure. | Executive Summary CSV 10 | **Obsolete or Conflicting** | `/challenges` is active (`App.jsx:97`) and explicitly implements points, streaks, badges, friend competition, and leaderboard (`ChallengesPage.jsx:7-17`); streak is also passed into feed chrome (`ReelsPage.jsx:346-347,678,696`). | Remove streak/leaderboard mechanics or formally revise the product principle with evidence and safeguards. |
| PR-09 | Reduce follower-based status and other public popularity signals. | Executive Summary CSV 10 | **Partially Implemented** | No follower count UI was found, and popularity boost is capped (`modes.py:41-61`), but an active friend leaderboard and “popular” presentation remain; demo social status data exists. | Remove status competition and audit every popularity surface, not just feed scoring. |
| PR-10 | Add friction before resharing misinformation. | Executive Summary CSV 11 | **Missing** | `ReelActionRail.jsx:87-108` immediately opens native share or copies the URL. Misinformation can be gated during ranking, but no pre-share context/pause exists. | Add risk-aware share interstitials, context, and auditable bypass handling. |
| PR-11 | Add friction before joining pile-ons/harassment. | Executive Summary CSV 11 | **Partially Implemented** | `commentSafety.js` and `CommentsPanel.jsx:48-89` block targeted harm and apply a five-second cooldown for heated language, but comments/reports are local demo state with no server persistence, identity, rate limit, moderation queue, or enforcement. | Build backend-enforced commenting/reporting safeguards and abuse tests. |
| PR-12 | Add friction for continuing late-night sessions. | Executive Summary CSV 11 | **Missing** | Diagnostic copy asks about bedtime use, but live breaks are based only on cumulative 60/90/120/150-minute thresholds (`sessionBreaks.js:8-34`). The older night-mode logic in `core/algorithm.py` is only used by the separate local algorithm runner, not `/api/feed/{mode}`. | Add local-time-aware, privacy-preserving night nudges to the active feed and test timezone/bypass cases. |
| PR-13 | Add circuit breakers for repeatedly viewing sensitive content. | Executive Summary CSV 11 | **Partially Implemented** | Active backend gates and balances risk/category/source, but it receives no per-user view history and has no repeated-sensitive exposure state. Older narrative-saturation logic in `core/algorithm.py` is not connected to the active feed endpoint. | Track minimal sensitive-exposure history and enforce a transparent per-session cap/break. |
| PR-14 | Minimize youth data collection. | Executive Summary CSV 12 | **Partially Implemented** | Auth avoids phone collection (`AuthPage.jsx:8-13`), profiles exclude contact fields and use RLS (`010_profiles.sql:5-13,75-99`), and anonymous research excludes direct identifiers (`015_research_sessions_and_events.sql:1-5`). However, preferences store coarse city/country and their APIs have no ownership authentication; public avatar URLs remain reachable after a profile becomes private (`010_profiles.sql:168-178`). | Authenticate preference access, remove unnecessary fields, define retention/deletion, and harden private avatars. |
| PR-15 | Restrict unsafe adult-to-minor contact. | Executive Summary CSV 12 | **Missing** | `messaging.js:1-33` is only a pure client-side friends check over `DEMO_FRIENDS`; `InboxPage` says messaging is coming soon and `/inbox` redirects to `/` (`App.jsx:100`). No ages, guardian/consent model, server authorization, or message store exist. | Design and enforce age-aware contact rules on the server before enabling messaging. |
| PR-16 | Avoid behavioral advertising to minors. | Executive Summary CSV 12 | **Implemented** | No advertising SDK, ad model, ad route, tracking pixel, or ad-selection code was found in frontend dependencies or repository search. | Maintain an explicit no-behavioral-ads policy and regression check if monetization is introduced. |
| PR-17 | Include young people in product design. | Executive Summary CSV 12 | **Unclear** | A survey/research presentation exists in the dead marketing page and an anonymous study flow exists, but repository code/data does not establish participant ages or youth co-design involvement. | Provide study protocol/recruitment evidence, consent/assent handling, and documented youth feedback incorporation. |
| PR-18 | Track autonomy. | Executive Summary CSV 13 | **Missing** | The research event allowlist (`core/research_storage.py:23-35`) has no autonomy measure. Mode choice is stored locally but not captured as an autonomy outcome. | Add a validated autonomy instrument/event and privacy-reviewed schema/analysis. |
| PR-19 | Track sleep disruption. | Executive Summary CSV 13 | **Partially Implemented** | Diagnostic questions include bedtime behavior and `diagnostics.js:11-25` tries to persist raw answers, but no `diagnostics` table migration exists, and sleep is not a research-event type or longitudinal measure. | Add the missing protected schema or redesign collection; define a privacy-safe longitudinal sleep metric. |
| PR-20 | Track harmful exposure. | Executive Summary CSV 13 | **Partially Implemented** | Research events persist post impressions/views with `content_category` (`015_research_sessions_and_events.sql:36-66`), enabling a coarse served-exposure proxy. They do not record risk dimensions, blocked candidates, duration of harmful exposure, or repeated exposure. | Define an exposure metric and persist the minimum risk/category context needed to compute it. |
| PR-21 | Track meaningful interaction. | Executive Summary CSV 13 | **Partially Implemented** | Research captures likes and meaningful visibility; comments, friendships, and messages are local demo-only and no interaction-quality measure exists. | Define meaningful interaction, instrument real connection actions, and distinguish them from generic likes. |
| PR-22 | Track satisfaction. | Executive Summary CSV 13 | **Missing** | Per-card reflection is stored only in localStorage; satisfaction is absent from usage and research event schemas. | Add a low-burden satisfaction measure and protected persistence. |
| PR-23 | Track session value directly. | Executive Summary CSV 8, 13 | **Missing** | No session-end value prompt/event/column or computation asks whether the user connected, learned, created, or recovered. `session_completed` only marks completion. | Add the four outcome dimensions and analysis plan. |
| PR-24 | Measure wellbeing and meaningful connection, not only engagement/time spent. | Executive Summary CSV 13 | **Missing** | The durable event allowlist is session, impression, view, like, skip, report, and break behavior (`core/research_storage.py:23-35`). Requested autonomy, satisfaction, direct connection, sleep, and session-value outcomes are not jointly implemented. | Expand instrumentation around validated wellbeing outcomes and document that ranking decisions use those results. |

## 3. Detailed Findings

### Brand system, palette, imagery, and components (SG-02–SG-04, SG-10–SG-13, SG-15)

The repository has a credible token foundation, but not a single enforced visual implementation. The exact five brand hexes and semantic aliases exist, while `reels.css`, `app-shell.css`, old `App.css`, and page-specific styles each introduce their own choices. The specified percentage ratio is a comment, not an applied layout or visual budget. Most importantly, the exact five-stop signature gradient is absent.

The component primitives are close structurally—pill buttons, cards, focus states—but the primary button maps to Coral, the secondary maps to Twilight with a 1 px border, and many pages bypass the primitives. This also exposes the additions document's internal contradiction: its general palette section calls Coral the primary CTA color while the exact button section calls for Morning Light. Before code changes, product/design should choose one canonical rule. Likely change areas are `website/src/index.css`, `website/src/components/ui/primitives.css`, `website/src/reels.css`, `website/src/app-shell.css`, and removal or isolation of `website/src/App.css`. The main risk is a broad regression across auth, study, feed, saved, and challenge surfaces because their styling is not fully centralized.

### Typography and accessibility (SG-06–SG-08, SG-27–SG-37)

- **SG-06–SG-08:** All three fonts are loaded and semantic type tokens exist, but actual usage contradicts the strict regular-weight rule. Montserrat 500–800 is common, Story Script appears on tags/labels, and ordinary descriptive copy drops below the prescribed 16 px body size. Resolving this requires a full active-route type inventory, not merely token edits.
- **SG-27–SG-29:** Some transitions and entrances fall into the requested ranges, but there is no universal motion contract. Infinite caret/wing/particle/cursor animations remain in the globally imported legacy stylesheet, so “avoid looping” is not satisfied even if those components are currently unreachable.
- **SG-30:** The global reduced-motion media query is comprehensive and is reinforced by component hooks. This is the strongest fully integrated motion requirement.
- **SG-31–SG-32:** The primary semantic contrast roles match the guide, but no automated contrast validation covers dark mode, status colors, hover/disabled states, or legacy pages. Accent colors are occasionally applied to sentence-length small text.
- **SG-33:** This is a direct failure, not a token-only discrepancy: live and canonical UI descriptions are frequently 10–15 px.
- **SG-34:** Global and component focus rules are connected and visible.
- **SG-35–SG-36:** Text labels, ARIA pressed state, icons, and alerts supplement much of the color usage, but graphs/status treatments have not been comprehensively checked. Image alts are mixed; some empty alts are clearly decorative and some are ambiguous.
- **SG-37:** The 72ch utility is correct, but it is not applied consistently to long copy.

Likely files are `website/src/index.css`, every active route stylesheet, `components/ui/primitives.css`, image-rendering components, and Playwright accessibility/visual tests. Risks include responsive overflow after increasing text sizes and layout shifts if regular weights change perceived hierarchy.

### Homepage specification conflict (SG-18–SG-26)

All nine homepage requirements conflict with the current route architecture. `MainPage` still returns `RebootPage`, but no route renders `MainPage`; `/` is the product feed and former app routes redirect there. Even if `RebootPage` were restored, its hero/problem copy and section labels do not match the exact additions text. This is not safely classifiable as merely “missing,” because the code shows a deliberate product pivot that made the entire homepage plan obsolete while leaving the old implementation behind.

A decision is required before implementation: either restore a public marketing route (possibly `/about`) and implement SG-18–SG-26 there, or revise/remove the homepage portion of the additions. Likely files are `website/src/App.jsx`, `RebootPage.jsx`, `Navbar.jsx`, and `App.css`. The risks are URL/SEO changes, onboarding flow conflicts, and substantially increasing the already oversized bundle if both experiences remain eagerly loaded.

### Product goals and ranking (PR-01–PR-04, PR-09)

The ranking pipeline is real and connected: the frontend calls `/api/feed/{mode}`, both APIs load the active video table, `build_feed_payload` invokes shared ranking, and the action rail exposes reasons. The scorer explicitly rewards calm, prosocial, educational, reflective, novelty, and diversity signals while penalizing comparison, ragebait, shame, appearance, misinformation, and other risk.

However, the current three mode names are not Calm/Connect/Learn/Explore/Chronological, no chronological option exists, and the backend's own module documentation says all modes use one shared gate and score. Mode profiles exist, but the active gate wrapper returns the shared gate and the active pipeline mainly varies explanation/pacing and popular-lane budget. Consequently user-control semantics are thinner than the UI suggests. Connection/community preservation is also mostly represented as content scoring and demo data, not a usable social system.

The active challenge leaderboard conflicts with the stated reduction of public status, even though follower counts are absent and popularity has a small capped ranking influence. Likely changes span `reelsData.js`, onboarding, `core/ranking/modes.py`, `core/ranking/feed.py`, challenges, research policy assignment, and tests. Any new goal-specific ranking needs offline evaluation so “Calm” or “Learn” does not become a simplistic content silo.

### High-risk friction and moderation (PR-10–PR-13)

- **PR-10:** Sharing is immediate. Ranking-time misinformation filtering is useful but not equivalent to friction at the moment of reshare.
- **PR-11:** The client performs a meaningful targeted-harm block and heated-language cooldown. It is not enforceable because all comments, reports, identities, and relationships are local seed/demo state.
- **PR-12:** Session-duration breaks are connected and tested, but late-night is not a trigger. Diagnostic recognition and an old algorithm test do not connect to the live feed.
- **PR-13:** Content gates and mix balancing reduce exposure globally, but there is no per-user/session state that detects repeated sensitive viewing. Old narrative-saturation code belongs to another execution path.

These changes would touch the action rail, comments, feed-session state, API event/interaction schemas, ranking inputs, and moderation operations. They depend on a policy taxonomy for misinformation/sensitive content, reliable user/session identity, timezone handling, rate limiting, appeals, and an operational moderation queue. The greatest risk is giving the appearance of safety with client-side controls that a malicious caller can bypass.

### Privacy and youth safety (PR-14–PR-17)

The profile and anonymous-study designs show privacy intent: credentials remain in Supabase Auth, profile rows have owner RLS, research bearer tokens are hashed, and research schemas omit direct identifiers. The preference endpoints break that pattern. They accept arbitrary identifiers, query directly by those identifiers, and perform updates with no auth dependency or owner check. In production this can disclose or alter another user's language/region/coarse location preferences if an identifier is learned. The frontend appears not to call these routes now, but the deployed endpoints still exist and are usable.

Adult-to-minor protection is not implemented. A client-only `canMessage` function over hardcoded friends cannot enforce a safety boundary, and the inbox route is disabled. Avoidance of behavioral advertising is confirmed by absence of an ad subsystem. Youth participation remains unclear because source code cannot prove participant age, recruitment, assent, or co-design. Likely changes include authenticated API middleware, preference schemas/retention, private avatar delivery, a future server-side relationship/messaging authorization layer, and governance documentation. Age collection itself creates privacy risk, so contact policy should be designed with data minimization rather than indiscriminate birthdate storage.

### Wellbeing measurement (PR-18–PR-24)

The anonymous research infrastructure is technically substantial: server-issued opaque credentials, condition assignment, idempotent ordered events, RLS, API validation, visibility thresholds, and session completion all connect. Its event vocabulary does not match the requested outcomes. It records exposure and interaction proxies—impression, view, like, skip, report, break response—and no direct autonomy, satisfaction, meaningful-connection quality, sleep outcome, or session-value dimensions.

Sleep has the beginnings of a diagnostic question, but the adapter writes to a `diagnostics` table absent from every migration. That makes successful durable collection unprovisionable from this repository. Harmful exposure can only be approximated from a coarse content category, and meaningful interaction is essentially likes because comments/messages/connections are local demo data. Implementing these requirements needs an instrument/design decision before schema work: validated, low-burden measures; consent and retention rules; event schema migration; API validation; UI prompts; analysis definitions; and tests. The main risk is collecting sensitive teen wellbeing data without a clear minimization, access, deletion, and interpretation plan.

## 4. Potential False Implementations

| Apparent implementation | Why it is not a complete implementation |
| --- | --- |
| `MainPage` / `RebootPage` marketing homepage | `MainPage` is never routed; `/` renders `ReelsPage`. Much of the polished marketing UI and its exact sections are dead code. |
| `ModeTabs.jsx` | The component exists but no active component imports it. Onboarding is the only current mode selector. The responsive QA script still looks for `.mode-tabs`, which can pass vacuously when no element exists. |
| Three distinct ranking modes | Mode UI and `MODE_PROFILES` exist, but active ranking documentation and `passes_gate` use a shared source gate/score. Differences are primarily framing, fallback cards, and a small popularity budget. |
| “Live” feed during backend failure | `ReelsPage.jsx:441-480` replaces an empty or failed first page with hardcoded synthetic cards, which can make the UI appear healthy while API/data ingestion is unavailable. |
| Public-signal moderation | `core/public_signals/provider.py:1-7,26-100` is explicitly a no-network stub with fictional sample IDs and neutral output for real unknown targets. The feed normally reads only whatever is already cached. |
| Comments, reports, connections, messaging, and community | These use in-memory seeds/localStorage/hardcoded friends. Community/inbox routes redirect to `/`; there is no corresponding backend persistence or authorization. |
| Challenge social ranking | Points, streaks, badges, and leaderboard are deterministic local demo data (`challengesData.js`); they are nevertheless presented on an active route and conflict with the additions principle. |
| Diagnostic persistence | `website/src/lib/diagnostics.js` claims an RLS-protected `diagnostics` table, but no migration creates it. First-run behavior treats persistence as best effort, so failure can be hidden from the user. |
| Night-mode/repeated-narrative safeguards in `core/algorithm.py` | These are exercised by legacy algorithm tests and `/api/run/local`, not by the active `/api/feed/{mode}` ranking path. |
| Friends-only youth safety | `messaging.js` is a pure client predicate over `DEMO_FRIENDS`; it has no age concept and cannot enforce server requests. |
| Optional Supabase auth | The app deliberately remains usable when Supabase variables are absent (`supabaseClient.js:10-35`). That resilience is useful, but it means auth-dependent claims cannot be assumed in an unconfigured deployment. |
| Vercel cron automation | `vercel.json:9-12` calls `/api/cron/drop`, but `api/index.py` implements `/api/cron/extract` instead. The scheduled production route is unconnected. |
| `automation/` scaffold | It documents a desired orchestrator, but jobs are empty/passive and the package is not the active Vercel or GitHub workflow path. |
| Duplicate files ending in ` 2` | Multiple migrations, CSS files, tests, and integration files have duplicate ` 2` variants. Canonical imports/configuration generally use the non-suffixed versions; the duplicates are stale-looking, not additional deployed implementations. |
| Swallowed analytics errors | `website/src/lib/events.js:8-12` intentionally swallows insert failures, so the UI cannot prove usage telemetry was persisted. |

## 5. Recommended Next Steps

### P0 — Critical functionality or security

| Task | Requirements | Likely files | Dependencies | Complexity |
| --- | --- | --- | --- | --- |
| Authenticate and authorize all preference reads/writes; bind identity server-side and stop accepting untrusted owner IDs. | PR-01, PR-14 | `api.py`, `api/index.py`, `core/preferences.py`, `migrations/009_user_content_preferences.sql`, API tests | Supabase/JWT verification design; anonymous session-token policy; migration/rollout plan | **Large** |
| Define a youth-safe contact authorization model before enabling messaging; enforce relationships/age policy/rate limits on the server. | PR-15 | Future API/service and migrations; `messaging.js`, `CommentsPanel.jsx`, `InboxPage.jsx`, routing | Legal/safety policy, minimized age assurance, blocking/reporting/moderation operations | **Large** |
| Resolve missing diagnostic storage safely: either add a consented, RLS-protected schema and retention/deletion policy or stop claiming durable persistence. | PR-14, PR-19 | `website/src/lib/diagnostics.js`, `FirstRunGate.jsx`, new migration, tests | Data-governance decision for teen wellbeing answers | **Medium** |

### P1 — Required missing or broken features

| Task | Requirements | Likely files | Dependencies | Complexity |
| --- | --- | --- | --- | --- |
| Add direct session-value and wellbeing outcome collection for autonomy, sleep, harmful exposure, meaningful interaction, and satisfaction. | PR-03, PR-18–PR-24 | `migrations/015_*`, `core/research_storage.py`, `research_api.py`, research tracker/components, analysis docs/tests | Validated instruments, consent, privacy review, analysis definitions | **Large** |
| Implement targeted, backend-aware circuit breakers for misinformation resharing, late-night use, repeated sensitive exposure, and pile-ons. | PR-10–PR-13 | `ReelActionRail.jsx`, comments, session timer, ranking/feed API, research events, new moderation storage | Risk taxonomy, timezone approach, interaction service, moderation queue | **Large** |
| Make selectable ranking goals materially change ordering and add a chronological/control option. | PR-01–PR-04 | `reelsData.js`, onboarding, `core/ranking/modes.py`, `core/ranking/feed.py`, API and ranking tests | Product semantics and offline safety/fairness evaluation | **Large** |
| Decide whether the marketing homepage is required; restore and implement exact copy, or formally retire SG-18–SG-26 and remove dead code. | SG-18–SG-26 | `App.jsx`, `RebootPage.jsx`, `Navbar.jsx`, `App.css` | Product/SEO decision | **Medium** |
| Repair production ingestion scheduling so configured cron paths match implemented authenticated routes. | Supports PR-01–PR-05 | `vercel.json`, `api/index.py`, `.github/workflows/youtube-feed-ingest.yml`, automation docs/tests | Deployment ownership and secret configuration | **Small** |

### P2 — Edge cases, validation, tests, and polish

| Task | Requirements | Likely files | Dependencies | Complexity |
| --- | --- | --- | --- | --- |
| Converge the active UI on exact button/card/palette rules and introduce the signature five-color gradient after resolving the CTA color contradiction. | SG-02–SG-04, SG-12, SG-13, SG-15 | `index.css`, `primitives.css`, `reels.css`, `app-shell.css`, active page CSS | Design decision on Coral vs Morning primary action | **Medium** |
| Complete the typography/accessibility pass: regular Montserrat hierarchy, ≥16 px body copy, restricted Story Script, readable measures, alt audit, color redundancy, and contrast checks. | SG-06–SG-08, SG-31–SG-37 | All active CSS/components; Playwright/a11y checks | Responsive regression testing | **Large** |
| Remove attention loops and standardize transitions/entrances on shared motion tokens while retaining reduced-motion behavior. | SG-27–SG-30 | `App.css`, animation components, `index.css`, route CSS | Decision whether dead marketing code remains | **Medium** |
| Replace the public-signal stub with an approved, privacy/legal-reviewed provider or remove UI claims that imply live external moderation context. | PR-01, PR-10, PR-13 | `core/public_signals/*`, ingestion, cache migrations, feed explanations/tests | Approved data source, review/appeal policy, operational monitoring | **Large** |
| Make lint green and run full Python/Playwright validation in the documented environment. | Cross-cutting | Lint-listed components, Python environment, `website/qa/*` | Existing dependencies installed in CI; preview/backend fixtures | **Medium** |

### P3 — Cleanup and maintainability

| Task | Requirements | Likely files | Dependencies | Complexity |
| --- | --- | --- | --- | --- |
| Remove or archive unreachable components, unused `ModeTabs`, stale social pages, and duplicate ` 2` files after confirming none are external deployment inputs. | SG-10, SG-18–SG-29; reduces false evidence | `website/src`, `migrations`, `integrations`, `tests` | Product decision on marketing/community roadmap; migration history review | **Medium** |
| Split the oversized frontend bundle with route-level lazy loading and keep marketing-only CSS out of the feed bundle. | Maintainability/performance | `App.jsx`, imports, CSS entry points, Vite configuration | Final route architecture | **Medium** |
| Add a requirements-to-tests matrix covering design tokens, accessibility, ranking semantics, privacy authorization, event schemas, and deployment routes. | All | `tests/`, `website/src/**/*.test.js`, `website/qa/`, CI workflow | Stable requirement IDs from this report | **Medium** |
| Revise `additions` to resolve the primary-action color contradiction, record the homepage pivot, define measurable acceptance criteria, and supply the referenced 15-problem/7-priority inventory if it is still authoritative. | SG-02, SG-12, SG-18–SG-26; CSV metadata | `additions/*` (specification-only follow-up) | Product/design/research owners | **Small** |

