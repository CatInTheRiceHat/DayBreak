# DayBreak website UI audit

Audit date: 2026-08-04  
Scope: `/Users/elaine/Documents/DayBreak/website`  
Runtime: local Vite server at `http://127.0.0.1:6767`, Playwright Chromium  
Screenshot catalog: [screenshot-index.md](screenshot-index.md)

## Evidence and scope

This is a read-only audit of the application source. The only repository additions are this report, the screenshot index, and screenshot files under `docs/ui-audit/`. Existing edits in `website/src/app-shell.css`, `website/src/home.css`, `website/src/index.css`, and `website/src/reels.css` were present before the audit and were not changed.

Findings use three evidence labels:

- **Runtime-confirmed** means the behavior or issue was observed in Chromium and, for visual claims, is linked to a captured screenshot.
- **Code-confirmed** means the relevant render path or CSS rule exists in source, but the state could not be reached safely in the local environment.
- **Inferred** means a likely result follows from the code but was not rendered; these are recommendations to verify, not claims of visual proof.

Commands and results:

- `npm run dev -- --host 127.0.0.1` started successfully on port 6767. Dependencies were already installed; none were added.
- `npm run test:unit` passed all 90 tests.
- `npm run lint` completed with 20 errors and 1 warning. The active-path errors include effect-driven synchronous state updates in `FirstRunGate.jsx`, `DiagnosticPage.jsx`, and `useVideoOrientation.js`; most remaining errors are unused imports/variables in dormant marketing components. The warning is an effect-cleanup ref warning in `CustomCursor.jsx`.
- A production build was not run because Vite would write `dist`; avoiding that write was the safest interpretation of the read-only requirement.
- Across the 84 baseline route/viewport captures, the automated geometry scan found no document-level horizontal overflow, no rendered element extending beyond either horizontal viewport edge, no rendered image lacking an `alt` attribute, no rendered unlabeled form control, and no uncaught page exception.
- Console output consisted of the two React Router v7 future-flag warnings on all routes, the expected HTTP 404 for the missing study API, and “No routes matched” on the deliberately unknown route.

Runtime limitations were not bypassed:

- No local Supabase configuration is present, so auth controls are disabled and authenticated Profile/Edit Profile states cannot be reached.
- The first-run funnel prevents access to the authenticated reel feed without completing diagnosis and signing in. No credentials or local-storage bypass was introduced.
- `/study` calls `/api/research/participants`; the local Vite server returned HTTP 404, so only its implemented unavailable state was observed.
- Populated Saved states need persisted feed data. No data was fabricated.
- Home, Community, Search, Inbox, public profiles, and the marketing `RebootPage` exist in source but are not mounted by the active router.

## A. Executive overview

DayBreak currently contains two overlapping products. The active product is a fixed-height social/feed application with a desktop sidebar, mobile top bar and bottom navigation, centered utility pages, a warm diagnostic funnel, and auth/profile/research states. A second, visually elaborate marketing site and several social pages remain in source but are unreachable. The router redirects their apparent routes back to `/`, while unmatched URLs render only the marketing navbar over an otherwise blank page.

The strongest foundation is the token layer in `src/index.css`: it accurately declares Midnight Horizon `#233A57`, Twilight Violet `#6D597A`, Horizon Rose `#CE6969`, Sunrise Coral `#E6866C`, and Morning Light `#FFDFAB`, plus semantic light/dark variables, spacing, containers, radii, shadows, focus treatments, reduced motion, and touch-target intent. The active diagnostic, challenge, study-unavailable, and app-shell surfaces generally feel warm, youthful, hopeful, and human. Friendly language, rounded surfaces, small illustrations/emojis, and restrained research copy support the intended tone.

Consistency is only moderate because that token system is not the only system in use. Auth/profile styling retains a legacy cream/plum palette; dormant marketing CSS uses another gray-purple vocabulary; many active components hard-code one-off colors, radii, shadows, and dimensions; and a complete primitive library is unused. The result is less a single design system than several generations layered together.

Desktop maturity is **medium**. Current accessible pages remain stable at 1440×900 and 1280×800, and the expanded desktop rail is legible. Narrow content pages, however, leave substantial unused space, route-level Challenges behaves like a constrained drawer, and several desktop controls lead to redirects rather than their labels’ destinations.

Mobile maturity is **medium**. The audited routes had no horizontal overflow at 390×844 or 360×800, the diagnostic adapts especially well, and fixed navigation remains readable. The major mobile risks are an internally scrolling Challenges panel behind persistent chrome, sub-44px controls, a sparse three-item bottom nav, incomplete dialog/tab keyboard behavior, and feed interactions that could not be runtime-verified.

The largest risks are:

1. **Route integrity:** Home, Community, Search, Inbox, and public profile routes redirect to the feed; unknown routes render a blank page; the marketing page is never mounted.
2. **Navigation truthfulness:** visible controls advertise destinations or actions that are not currently available.
3. **First-run accessibility:** the intro visually covers, but does not semantically hide or disable, the onboarding screen beneath it.
4. **Challenges usability:** the full route inherits a modal-like `max-height` and internal scrolling region, with multiple undersized action buttons.
5. **Design-system drift:** official tokens coexist with legacy auth/marketing colors and repeated one-off component styling.
6. **Unverified core experience:** the actual signed-in feed, live research session, populated collections, and authenticated profile workflows require services/state unavailable locally.

## B. Site map

Status terms: **Verified** = rendered at all five required viewports; **Partial** = a real fallback/empty/unavailable state rendered but the primary state was inaccessible; **Redirect** = route is declared but sends the user elsewhere; **Unreachable** = component exists but has no active route.

| Route | Purpose | Main layout | Desktop status | Mobile status | Notes |
| --- | --- | --- | --- | --- | --- |
| `/` | First-run entry and personalized reel feed | Fixed `ReelsPage`; desktop rail, mobile bars, snap feed | Partial | Partial | First-run intro verified; authenticated feed code-confirmed only. [Desktop](screenshots/desktop/home--desktop--first-run.png), [mobile](screenshots/mobile/home--mobile--first-run.png) |
| `/challenges` | IRL challenge list, streaks, points, badges, friend leaderboard | `HomeShell` + narrow internally scrolling `ChallengesPanel` | Verified | Verified | Default, completion form, dark mode, and scrolled-bottom states captured. [Desktop](screenshots/desktop/challenges--desktop--default.png), [mobile](screenshots/mobile/challenges--mobile--scrolled-bottom.png) |
| `/saved` | Device-local liked, saved, and reflection collections | `HomeShell` + 640px content column; tabs and media grid | Partial | Partial | Empty tabs verified; populated grid/player require persisted items. [Desktop](screenshots/desktop/saved--desktop--empty-liked.png), [mobile](screenshots/mobile/saved--mobile--empty-reflections.png) |
| `/login` | Email/password and Google sign-in | Centered `CxShell` auth card | Partial | Partial | Supabase-unconfigured state; controls disabled. [Desktop](screenshots/desktop/login--desktop--unconfigured.png), [mobile](screenshots/mobile/login--mobile--unconfigured.png) |
| `/signup` | Account creation | Centered `CxShell` auth card | Partial | Partial | Supabase-unconfigured state; long card uses document scrolling. [Desktop](screenshots/desktop/signup--desktop--unconfigured.png), [mobile](screenshots/mobile/signup--mobile--unconfigured.png) |
| `/forgot-password` | Request reset email | Centered `CxShell` auth card | Partial | Partial | Form present but disabled without Supabase; sent state is code-confirmed. |
| `/reset-password` | Set a new password | Centered `CxShell` auth card | Partial | Partial | Form present but disabled without Supabase; success/redirect is code-confirmed. |
| `/diagnostic` | Five-question wellbeing/feed-mode assessment and interest selection | Centered `CxShell`; staged quiz/result/interests | Verified | Verified | Question, result, and selected-interest states captured. [Desktop result](screenshots/desktop/diagnostic--desktop--result.png), [mobile interests](screenshots/mobile/diagnostic--mobile--interests-selected.png) |
| `/study` | Research participant feed and completion flow | Loading/error wrapper or research-configured `ReelsPage` | Partial | Partial | Local API 404 produced the genuine “Session unavailable” state. [Desktop](screenshots/desktop/study--desktop--unavailable.png), [mobile](screenshots/mobile/study--mobile--unavailable.png) |
| `/profile` | Signed-in user profile and local content summaries | Wide `CxShell`; status card or profile card | Partial | Partial | Supabase-unconfigured state verified; owner/private/not-found/auth states code-confirmed. [Desktop](screenshots/desktop/profile--desktop--unconfigured.png), [mobile](screenshots/mobile/profile--mobile--unconfigured.png) |
| `/profile/edit` | Avatar, identity, profile metadata, mode, website, and privacy settings | Wide `CxShell` form | Partial | Partial | Supabase-unconfigured state verified; full form code-confirmed. |
| `/algorithm` | Legacy feed alias | Redirect to `/` | Redirect | Redirect | Resolves to first-run intro. |
| `/reels` | Feed alias | Redirect to `/` | Redirect | Redirect | Resolves to first-run intro. |
| `/home` | Intended home/dashboard route | Redirect to `/` | Redirect | Redirect | A full `HomePage` exists but is not mounted. [Mobile redirect](screenshots/mobile/home-alias--mobile--redirect.png) |
| `/community` | Intended friends/challenges route | Redirect to `/` | Redirect | Redirect | A full `CommunityPage` exists but is not mounted. [Desktop redirect](screenshots/desktop/community--desktop--redirect.png) |
| `/search` | Intended discovery/search route | Redirect to `/` | Redirect | Redirect | A full `SearchPage` exists but is not mounted. |
| `/inbox` | Intended notifications/messages route | Redirect to `/` | Redirect | Redirect | A full `InboxPage` exists but is not mounted. |
| `/u/:username` | Intended public profile | Redirect to `/` | Redirect | Redirect | `ProfilePage` supports public mode, but the route never uses it. |
| Any unmatched path | Expected 404/not-found handling | Marketing navbar plus empty route outlet | Broken | Broken | No wildcard route. [Desktop](screenshots/desktop/not-found--desktop--unmatched.png), [mobile](screenshots/mobile/not-found--mobile--unmatched.png) |

Unrouted page implementations:

| Implementation | Intended purpose | Relevant files | Current status |
| --- | --- | --- | --- |
| Marketing site | Hero, problem, journey, solution/mode carousel, future, creator/about, contact/footer | `src/components/RebootPage.jsx`, `Hero.jsx`, `Problem.jsx`, `Journey.jsx`, `Solution.jsx`, `FutureVision.jsx`, `AboutCreator.jsx`, `Contact.jsx`, `src/App.css` | Imported and wrapped by unused `MainPage`; no route mounts it. Navbar appears only on unknown URLs, without the page sections it targets. |
| Home dashboard | Daily Wings stories, today/activity cards, feed CTA, profile and suggestions rail | `src/components/home/HomePage.jsx`, `DailyWingsRow.jsx`, `DailyWingModal.jsx`, `HomeProfilePanel.jsx`, `SuggestedProfilesPanel.jsx`, `src/home.css` | Imported but `/home` redirects. |
| Community | Friend swipe deck, leaderboard, circle, safety note, challenge summary | `src/components/community/CommunityPage.jsx` and siblings, `src/community.css` | Imported but `/community` redirects. |
| Search | Search field, vibe filters, suggested searches, people/activity/collection results | `src/components/home/SearchPage.jsx`, `src/home.css` | Imported but `/search` redirects. |
| Inbox | Coming-soon empty state and demo preview rows | `src/components/home/InboxPage.jsx`, `src/home.css` | Imported but `/inbox` redirects. |
| Public profile | Username-based public profile, private/not-found states | `src/components/profile/ProfilePage.jsx`, `ProfileCard.jsx` | Component mode exists; `/u/:username` redirects. |

## C. Shared layout and component overview

### Application root and global shell

- `src/main.jsx` mounts React 19 in `StrictMode` and imports `src/index.css`.
- `src/App.jsx` wraps the router with `GlobalErrorBoundary`, `BrowserRouter`, and `AuthProvider`. `FirstRunGate` is mounted above every route outlet, although it acts only at `/`.
- `src/components/GlobalErrorBoundary.jsx` provides a branded reload state for uncaught render errors. This is a useful resilience layer, but it is not a 404 route.
- App routes use either the fixed `ReelsPage`, `HomeShell`, or centered `CxShell`. Marketing Lenis scrolling and `Navbar` are enabled only when `isAppPath()` returns false—which currently means unknown URLs rather than a real marketing route.
- No footer is present on active app routes. `Contact.jsx` contains the marketing footer, but `RebootPage` is unreachable.

### Navigation

- `src/components/home/HomeShell.jsx` provides the app chrome for Challenges and Saved: a desktop sidebar at 768px+, mobile top bar below 768px, and mobile bottom nav.
- `src/components/reels/AppSidebar.jsx` is 76px wide from 768–1179px and expands to 236px at 1180px. `src/components/reels/AppBottomNav.jsx` is fixed to the bottom on mobile.
- `src/components/reels/ChrysalisTopBar.jsx` is the mobile top bar. Its component name and comments retain legacy Chrysalis naming, although the visible brand is DayBreak.
- `src/components/reels/navSections.js` is the declared shared navigation source, but its comments still describe seven sections while the array contains only Reels, Challenges, Saved, and Profile. The mobile bar filters that to three items. Search and Inbox buttons exist in `HomeShell`; both point to redirect routes. Desktop “Inbox” and “Feed details” controls also route to `/`.
- `src/components/Navbar.jsx` is a separate marketing navigation system. Its full-screen dialog has initial focus, focus trapping, Escape handling, and focus restoration. Runtime capture confirms focus moves to “Close navigation menu.” Its section buttons target IDs that only exist in the unrouted marketing page. [Mobile dialog](screenshots/mobile/not-found--mobile--navigation-open.png)

### Containers and grids

- Global tokens declare narrow/default/wide containers of 42rem, 72rem, and 90rem in `src/index.css`, with responsive page gutters.
- `HomeShell` pages generally use `.home-narrow` at 640px, so large desktop screens retain a very narrow center column. This is calm and readable for forms/collections but leaves the Challenges dashboard feeling under-utilized.
- Feed CSS in `src/reels.css` changes substantially at 768, 1100, and 1180px: mobile overlay composition; tablet/icon-rail mode; then a wider desktop card/caption/action arrangement.
- Dormant Home uses a two-column main/rail layout around 1100px. Dormant Community adds column changes around 760 and 1040px. These breakpoints do not align cleanly with the global 768/1024/1440 model.
- Runtime scans at 1440×900, 1280×800, 768×1024, 390×844, and 360×800 found no horizontal overflow on accessible states. `body` has `min-width: 20rem`, so viewports below 320px are expected to overflow rather than continue compressing.

### Typography

- `index.html` and `src/index.css` both request Google fonts: Abril Fatface, League Spartan, Montserrat, Sanchez, and Story Script. The duplicate request is unnecessary.
- Active usage centers on Abril Fatface for display headings, Montserrat for UI/body text, and Story Script as an expressive accent. League Spartan and Sanchez appear to have little or no current visual role.
- The diagnostic has the clearest hierarchy: small progress label, strong serif display question, concise helper copy, then large answer cards. Challenges also has a clear title-to-stat-to-list flow but relies on 10–12px secondary labels in multiple places.
- `auth.css` declares Inter, but Inter is not requested. Depending on selector inheritance, those elements fall back to the available sans-serif stack rather than the declared face.

### Color and theme

- `src/index.css` is the canonical DayBreak system and exactly includes the five requested brand colors. It supplies semantic background, surface, text, border, action, selected, success/warning/error, focus, light/dark, and RGB companion variables.
- `src/lib/useAppTheme.js` persists the app theme, and `HomeShell`, `ReelsPage`, and `CxShell` mirror it through `data-theme`.
- `src/auth.css` remains a legacy token island (`#faf9f6`, `#2b2631`, `#938e97`, `#7c6d8c`, `#ad9eb8`, and dark values such as `#161320`). `src/app-shell.css` partially overrides presentation but does not replace every text/action color.
- `src/App.css` uses another older cream/plum system for the dormant marketing site. The open marketing menu is visibly attractive but reads cooler and more editorial than the warmer active app. [Mobile menu](screenshots/mobile/not-found--mobile--navigation-open.png)
- Hard-coded colors, alpha values, raw radii from roughly 8–24px plus pills, and component-specific shadows remain common in `reels.css`, `home.css`, `saved.css`, `auth.css`, and `App.css`, despite corresponding global tokens.

### Buttons, cards, and forms

- `src/components/ui/index.jsx` and `primitives.css` define a substantial accessible primitive set: buttons, cards, inputs, textarea, select, checkbox, radio, switch, badge, alert, native dialog, tooltip, tabs, progress, skeleton, and empty state.
- Application pages do not import those primitives. Auth, diagnostic, challenges, saved, feed, home, community, and marketing each define separate button/card/form styles. This is the central source of radius, shadow, state, and target-size drift.
- Runtime form inspection found labels on all rendered controls in the accessible states. Auth wrappers use visible labels and shared error descriptions; diagnostic answer controls have meaningful names.
- Several challenge actions render at 35px high, the invite action at 34px, the global theme toggle at 42px, and the onboarding “Skip for now” control at 34px. These conflict with the declared 44px touch target.

### Modals, drawers, tabs, and overlays

- `src/components/reels/useDialogFocus.js` centralizes initial focus, trapping, Escape callback, and focus restoration. It is used by feed details, Break Screen, Comments, and Saved playback in varying ways.
- Feed Details becomes a side drawer on desktop and a bottom sheet on mobile. Comments is modal-like, but Escape closure is not wired through its current caller. Reel “Why?” and reflection overlays declare dialog semantics without equivalent focus management.
- `src/components/home/DailyWingModal.jsx` supports scrim and Escape closure but does not use the shared focus utility; it is currently unreachable.
- Saved uses manually authored `role="tab"` buttons. Selection works, but there is no roving tab stop, ArrowLeft/ArrowRight behavior, or `aria-controls` relationship.
- The first-run intro is a fixed visual overlay, not a modal. It leaves the underlying onboarding DOM interactive and exposed to assistive technology.

### Feed components

- `src/components/reels/ReelsPage.jsx` owns feed loading, mode onboarding, pagination, saving/liking/reflections, session breaks, profile/challenge drawers, comments, and responsive shell integration.
- `ReelCard.jsx`, `ReelCaption.jsx`, `ReelActionRail.jsx`, `ModeTabs.jsx`, `CroppedYouTubePlayer.jsx`, and `useVideoOrientation.js` form the responsive media unit. Desktop uses an adjacent caption/action composition; mobile places information and actions over the media.
- `FeedDetailsDrawer.jsx` explains personalization. `BreakScreen.jsx` inserts a required wellbeing activity prompt. `CommentsPanel.jsx` uses safety filtering and local comment state.
- The normal feed can fall back to bundled data; research mode intentionally requires live participant/session content. Because the signed-in flow was inaccessible, these layouts are code-confirmed rather than visually confirmed in this audit.

### Research-study components

- `src/components/research/ResearchPage.jsx` has explicit loading, unavailable/error, active-session, and completion branches. It supplies study-specific copy/provenance and mounts `ReelsPage` in a research configuration when data exists.
- `research.css` adds a fixed completion control that accounts for desktop/mobile chrome. Visibility tracking is separated into `useMeaningfulPostVisibility.js` and tested helpers.
- The repository includes `qa/study-check.mjs` and a prior `qa/DAYBREAK_STUDY_QA.md`, but that script mocks network state. This audit did not use mocked data as visual proof.

### Assets and performance surface

- `public/favicon.svg` uses the sunrise palette; `favicon 2.svg` is a duplicate. Lucide supplies most interface icons, while emoji is common in Challenges and diagnostic choices.
- Several raster assets are unusually large for web delivery: `me.png` is about 15 MB, `hero-butterfly.png` about 6.4 MB, `butterfly.png` about 3.1 MB, `poster.png` about 2.2 MB, and multiple feed/mode assets are around 1–1.4 MB. Most belong to dormant marketing or onboarding surfaces, but they remain part of the deployable public folder unless build/deployment excludes them.
- `src` and `qa` contain many duplicate files suffixed with ` 2` (`App 2.jsx`, `main 2.jsx`, CSS copies, `brand 2.js`, QA scripts). `brand 2.js` explicitly contains Chrysalis branding. These are not active imports but make source search and future maintenance hazardous.

## D. Page-by-page findings

### `/` — first run and reel feed

**Relevant files:** `src/App.jsx`, `src/components/FirstRunGate.jsx`, `IntroScreen.jsx`, `src/components/reels/ReelsPage.jsx`, `OnboardingStartScreen.jsx`, `ReelCard.jsx`, `ReelCaption.jsx`, `ReelActionRail.jsx`, `FeedDetailsDrawer.jsx`, `CommentsPanel.jsx`, `BreakScreen.jsx`, `src/reels.css`, `src/app-shell.css`.

**Current structure.** `FirstRunGate` overlays a timed branded intro for a new visitor and then routes to the diagnostic. Behind it, `ReelsPage` still renders its mode-selection onboarding. After diagnosis and authentication, the code supports a mode chooser, top/side/bottom navigation, vertically snapping feed cards, captions, action rail, mode tabs, feed-explanation drawer, comments, challenge/profile panels, and session-break prompts.

**Desktop.** The first-run overlay is centered, spacious, and typographically expressive at 1440×900. The feed code uses a left rail from 768px, expands it at 1180px, and changes the content/card composition at 1100px. This produces three desktop/tablet arrangements rather than a single fluid layout.

**Tablet.** At exactly 768px, the mobile bars are replaced by the 76px icon rail. Code indicates the wider feed arrangement waits until 1100px, so 768–1099px is a hybrid tablet/icon-rail layout.

**Mobile.** The intro scales cleanly at both 390×844 and 360×800 with no overflow. The feed code switches to full-height media, overlay captions/actions, mobile top bar, and fixed three-item bottom nav. Safe-area values are incorporated into bottom spacing.

**States.** Implemented states include first run, diagnostic redirect, auth redirect, mode selection, feed loading, API error/fallback, empty feed, active media, saved/liked/reflected, comments, feed details, scheduled breaks, and research-configured feed. Only first-run was runtime-accessible.

**Strengths.** The intro is one of the most on-brand moments: warm sunrise graphics, confident display type, plain-language promise, and good small-screen fit. Feed architecture explicitly distinguishes mobile and desktop composition and has tested data helpers.

**Problems.** **Runtime-confirmed:** the intro screenshot looks like a single page, but DOM inspection found two visible `h1` elements and seven interactives because the covered mode selector remains exposed underneath. The underlying theme toggle and 34px “Skip for now” button are still treated as visible/focusable. [Desktop 1440×900](screenshots/desktop/home--desktop--first-run.png), [mobile 390×844](screenshots/mobile/home--mobile--first-run.png). **Code-confirmed:** feed action popups have inconsistent dialog behavior; Comments has no reliably wired Escape close; the “Why?” and reflection dialogs lack the shared focus lifecycle; `BreakScreen` requires an activity selection and has no cancel path despite copy/comments describing breaks as non-locking. Some mobile controls are coded below the 44px target. **Not runtime-verified:** the primary signed-in feed’s cropping, caption legibility, keyboard order, and content loading.

**Recommended improvements.** Make the intro a true modal layer (`inert`/`aria-hidden` on the background or render only one branch); decide whether the feed onboarding should exist before or after the intro; standardize all dialogs on one accessible overlay primitive; restore a respectful dismiss/defer path for breaks; then run a signed-in visual pass at every breakpoint before changing media geometry.

### `/challenges` — IRL challenges

**Relevant files:** `src/components/challenges/ChallengesPage.jsx`, `src/components/reels/ChallengesPanel.jsx`, `useChallenges.js`, `challengesData.js`, `src/components/home/HomeShell.jsx`, `src/reels.css`, `src/app-shell.css`.

**Current structure.** A branded eyebrow and “Touch grass, together” heading lead into three stats, ten daily challenge rows, inline completion forms, badges, a friend leaderboard, invite action, and safety footnote. Progress persists in local storage.

**Desktop.** Content is centered in a 640px column while the app rail occupies the left. The layout is clear but visually narrow for a dashboard on 1280–1440px screens. More importantly, the reused `.challenges` panel is capped at `min(82dvh, 720px)` and scrolls internally: measured at 718px client height versus 1,618px content height at 1440×900. The page therefore behaves like an embedded drawer rather than a normal route. [Default](screenshots/desktop/challenges--desktop--default.png), [internal bottom](screenshots/desktop/challenges--desktop--scrolled-bottom.png).

**Tablet.** The 768×1024 capture shows the icon-only rail and a stable centered panel with no horizontal clipping. The internal scrolling behavior remains.

**Mobile.** The top bar and bottom nav are fixed around a rounded internal scroll surface. At 390×844 the panel measured 690px client height versus 1,844px content height. Reaching badges and friends requires scrolling that nested region; the fixed nav remains visually close to its rounded lower edge. [Default 390×844](screenshots/mobile/challenges--mobile--default.png), [bottom 390×844](screenshots/mobile/challenges--mobile--scrolled-bottom.png). At 360×800 there was still no horizontal overflow.

**States.** Default, partially completed, all-completed, streak/badge changes, inline proof/note form, invite, and dark theme are implemented. Default, completion form, dark theme, and scrolled-bottom states were visually captured. [Completion form](screenshots/mobile/challenges--mobile--completion-form.png), [dark](screenshots/mobile/challenges--mobile--dark.png).

**Strengths.** Hierarchy is immediately understandable, tone is motivating without being academic, light and dark themes both retain the sunrise identity, and the leaderboard avoids follower-count framing. Cards collapse reliably without horizontal overflow.

**Problems.** **Runtime-confirmed:** route-level nested scrolling hides more than half the content and makes the bottom-nav relationship awkward. Ten “Complete” buttons are 35px high and “Invite a friend” is 34px high, below the 44px touch target. The route begins with `h2`; no `h1` is present. The smallest badges, points, and footnote text are visually delicate. [Mobile default](screenshots/mobile/challenges--mobile--default.png). **Code-confirmed:** the same panel styles are shared between a route and overlay context, which caused the height constraint.

**Recommended improvements.** Split route and drawer wrappers so the route scrolls the document/content area normally; retain a constrained scroller only when used as a panel. Promote the page title to `h1`, raise all actions to 44px minimum, increase the smallest secondary text, and consider a wider desktop composition that can place stats/badges or social content alongside the daily list.

### `/saved` — liked, saved, and reflections

**Relevant files:** `src/components/saved/SavedPage.jsx`, `src/components/home/HomeShell.jsx`, `src/components/reels/useLikedVideos.js`, `useSavedVideos.js`, `useReflections.js`, `useDialogFocus.js`, `src/saved.css`, `src/app-shell.css`.

**Current structure.** Header copy and per-category counts sit above tabs for Liked, Saved, and Reflections. Empty states explain how data is created. Populated media uses an auto-filling portrait grid; selecting an item opens a playback/detail dialog.

**Desktop.** The 640px center column is readable but leaves most of the canvas unused. Empty-state hierarchy is calm and coherent. [1440×900](screenshots/desktop/saved--desktop--empty-liked.png).

**Tablet.** At 768px the icon rail appears; the grid is coded to fill available width with 160px minimum tiles. The empty state remains centered and stable.

**Mobile.** At 390px the three tabs wrap into two rows (Liked/Saved, then Reflections). This avoids overflow but makes the navigation feel less intentional. Empty-state copy remains readable, and the bottom nav does not cover the content. [390×844 default](screenshots/mobile/saved--mobile--empty-liked.png), [Reflections empty](screenshots/mobile/saved--mobile--empty-reflections.png).

**States.** Empty Liked/Saved/Reflections were observed. Populated tiles, missing-video fallbacks, reflection text, and the media dialog are code-confirmed only because no local feed data was fabricated.

**Strengths.** Clear category language, sensible empty-state guidance, 44px tab height, responsive grid rules, and a shared focus utility for the playback dialog.

**Problems.** **Runtime-confirmed:** tabs wrap on mobile and the wide-screen empty page is under-composed. [Mobile](screenshots/mobile/saved--mobile--empty-liked.png), [desktop](screenshots/desktop/saved--desktop--empty-liked.png). **Code-confirmed:** tabs provide `role="tab"` and `aria-selected` but no roving focus, arrow-key behavior, tabpanel relationship, or `aria-controls`. Modal and card styling is page-specific rather than based on shared primitives.

**Recommended improvements.** Use a three-equal-column tab strip or horizontally scrollable tablist on narrow phones, implement the complete tabs keyboard pattern, and verify populated cards/player at all breakpoints before widening the page. A wider desktop grid should activate only when content exists.

### `/login` and `/signup` — authentication

**Relevant files:** `src/components/profile/AuthPage.jsx`, `CxShell.jsx`, `DayBreakAuthBrand.jsx`, `src/lib/AuthProvider.jsx`, `supabaseClient.js`, `src/auth.css`, `src/app-shell.css`.

**Current structure.** DayBreak branding, heading/lede, provider button, divider, labeled email/password fields, submit, route links, shared error/notice region, and configuration warning. Signup adds display name and confirmation copy.

**Desktop.** A 440px card is centered in a warm full-height field. Login is compact; signup is taller but balanced. [Login 1440×900](screenshots/desktop/login--desktop--unconfigured.png), [signup 1440×900](screenshots/desktop/signup--desktop--unconfigured.png).

**Tablet.** The same constrained card remains centered with generous margins. This is appropriate for auth rather than stretching to the viewport.

**Mobile.** The card loses excess outer framing and uses document scrolling for the taller signup form. Both 390 and 360px captures fit without horizontal overflow. [Login 390×844](screenshots/mobile/login--mobile--unconfigured.png), [signup 390×844](screenshots/mobile/signup--mobile--unconfigured.png).

**States.** Unconfigured, submitting/disabled, validation error, provider error, email-confirmation notice, and successful navigation are implemented. Only the genuine unconfigured state was observed.

**Strengths.** Inputs have visible labels, error descriptions are associated, keyboard-native elements are used, and the centered layout is responsive. Disabled controls correctly prevent a false sign-in attempt without service configuration.

**Problems.** **Runtime-confirmed:** the configuration warning says the user can keep exploring the feed, but this fresh-user flow cannot proceed to the feed because root sends the user through diagnosis and back to disabled auth. [Login mobile](screenshots/mobile/login--mobile--unconfigured.png). **Code/contrast-confirmed:** legacy muted text `#938e97` on white is 3.20:1 and fails WCAG AA for normal text. Disabled placeholder gray `#9ca3af` over Morning Light is only 1.98:1; disabled controls are not strictly subject to contrast requirements, but the field state is difficult to read. The page pulls from legacy auth tokens rather than the canonical palette. The declared Inter font is not loaded.

**Recommended improvements.** Make environment messaging accurate and actionable, migrate auth semantics to the DayBreak tokens, select an AA-compliant muted text value, either load or remove Inter, and validate all error/success/provider states in a configured staging environment.

### `/forgot-password` and `/reset-password`

**Relevant files:** `src/components/profile/ForgotPasswordPage.jsx`, `ResetPasswordPage.jsx`, `CxShell.jsx`, `src/auth.css`, `src/app-shell.css`.

**Current structure.** Forgot Password offers a labeled email field, send action, and sent confirmation. Reset Password offers password/confirmation fields, mismatch/server errors, a success state, and delayed redirect.

**Desktop/tablet/mobile.** Both reuse the same responsive 440px auth shell. The unconfigured forms were stable at all required viewports and produced no overflow. Their visual strengths and legacy-token issues match Login/Signup.

**States.** The disabled unconfigured state was observed; request-sent, mismatch, loading, backend error, success, and redirect are code-confirmed only.

**Strengths.** Focused single-task layouts, explicit field labels, clear recovery links, and plain-language state copy.

**Problems.** **Code-confirmed:** live recovery cannot be validated without Supabase, and feedback styling duplicates AuthPage rather than using the existing Alert primitive. Password requirements are not surfaced proactively in the audited source presentation.

**Recommended improvements.** Share one auth form/alert vocabulary, expose password requirements before submit, and run keyboard/screen-reader validation against a configured backend.

### `/diagnostic` — quiz, result, and interests

**Relevant files:** `src/components/diagnostic/DiagnosticPage.jsx`, `DiagnosticResult.jsx`, `InterestPicker.jsx`, `diagnosticData.js`, `src/lib/diagnostics.js`, `src/auth.css`, `src/app-shell.css`.

**Current structure.** A checking/loading phase leads into five questions. Four frequency questions auto-advance; the final multi-select submits to a recommendation result. The result explains the selected feed mode, then the user picks at least three interests before continuing to auth.

**Desktop.** Centered cards have a strong top-to-bottom rhythm and keep lines comfortably short. The result uses a clear branded mode panel and next action. [Question](screenshots/desktop/diagnostic--desktop--question-1.png), [result](screenshots/desktop/diagnostic--desktop--result.png).

**Tablet.** The centered layout remains appropriately constrained, with answer cards large enough for touch and no abrupt grid transition.

**Mobile.** This is the most mature responsive route. Questions, results, and the two-column interest grid use the full width without feeling cramped at 390 or 360px. The result’s full-page height expands naturally rather than clipping. [Result 390×844](screenshots/mobile/diagnostic--mobile--result.png), [interests 390×844](screenshots/mobile/diagnostic--mobile--interests-selected.png).

**States.** Loading, each question type, back navigation, result, interest validation, selected interests, and auth redirect are implemented. Representative question, result, and valid-interest states were captured without bypassing auth.

**Strengths.** Excellent hierarchy, warm but trustworthy language, generous answer targets, clear selected states, coherent imagery/color, and strong behavior across all five viewports.

**Problems.** **Code-confirmed:** the progress calculation uses `step / QUESTIONS.length`, so the question screens show 0%, 20%, 40%, 60%, and 80% but never 100% before switching to Result. `DiagnosticPage` also triggers a lint error for synchronous state setting in an effect. The final multi-select appears submittable with zero goals; that may be intentional, but the UI does not explain whether selection is optional.

**Recommended improvements.** Calculate progress from completed/current question semantics so the last step communicates completion, clarify whether goals are optional, and resolve the effect lifecycle lint issue without changing the funnel’s successful responsive composition.

### `/study` — research experience

**Relevant files:** `src/components/research/ResearchPage.jsx`, `research.css`, `researchParticipantCopy.js`, `researchProvenance.js`, `useMeaningfulPostVisibility.js`, `src/components/reels/ReelsPage.jsx`, `src/lib/researchEvents.js`.

**Current structure.** The route checks participant/session data, shows loading or an unavailable/error card, mounts a research-configured feed for a valid active session, and displays completion messaging/control when appropriate.

**Desktop/tablet/mobile.** The observed “Session unavailable” card remains centered, readable, and compact at every viewport. The Retry control meets the 44px target. [Desktop 1440×900](screenshots/desktop/study--desktop--unavailable.png), [tablet 768×1024](screenshots/tablet/study--tablet--unavailable.png), [mobile 390×844](screenshots/mobile/study--mobile--unavailable.png).

**States.** **Runtime-confirmed:** the actual local request to `/api/research/participants` returned 404 and the route presented its designed unavailable state. **Code-confirmed only:** loading, active feed, post tracking, completion request, completion success, and session-specific error variants.

**Strengths.** The failure state is honest, calm, concise, and gives a clear retry action. Research implementation separates participant-safe copy/provenance and meaningful-visibility logic, reinforcing a research-informed feel without making the UI overly academic.

**Problems.** The route cannot perform its primary purpose in the local Vite-only environment. The console records the 404 resource error. The active research feed and fixed completion control therefore have no current visual evidence in this audit.

**Recommended improvements.** Document the required local backend/proxy and environment variables; validate the real study flow in a non-production test session; and capture completion/failure variants there without committing mock behavior to production.

### `/profile` — signed-in profile

**Relevant files:** `src/components/profile/ProfilePage.jsx`, `ProfileCard.jsx`, `UserMenu.jsx`, `CxShell.jsx`, `src/lib/profileApi.js`, `useProfile.js`, `src/auth.css`, `src/app-shell.css`.

**Current structure.** Auth/config loading gates lead to unavailable, unauthenticated redirect, error, not-found, private, empty-profile, or full owner/public profile states. A full owner view includes identity, mode/privacy metadata, edit/logout actions, and saved/reflection summary panels.

**Desktop.** The observed unavailable card sits near the top of a 620px column and leaves substantial empty space below. [1440×900](screenshots/desktop/profile--desktop--unconfigured.png).

**Tablet/mobile.** The state card narrows cleanly. Mobile spacing is readable and has no overflow. [390×844](screenshots/mobile/profile--mobile--unconfigured.png).

**States.** Only Supabase-unconfigured was observed. Auth loading, redirect, loading, error, private, empty, not found, complete profile, edit/logout, and collection summaries are code-confirmed.

**Strengths.** State coverage is unusually complete in source, private/not-found distinctions are explicit, and the shell participates in the shared light/dark preference.

**Problems.** **Runtime/contrast-confirmed:** muted unavailable copy uses the legacy `#938e97` on white at 3.20:1. The state page feels visually sparse compared with auth and diagnostic. **Code-confirmed:** the full profile styling cannot be evaluated without auth, and the route inherits a separate token system.

**Recommended improvements.** Correct muted contrast immediately, align status/empty cards with the shared Alert/EmptyState vocabulary, and run a credentialed audit of owner, public, private, missing, image-error, and long-content states.

### `/profile/edit` — edit profile

**Relevant files:** `src/components/profile/EditProfileForm.jsx`, `AvatarUploader.jsx`, `CxShell.jsx`, `src/lib/profileApi.js`, `src/auth.css`, `src/app-shell.css`.

**Current structure.** The authenticated form contains avatar upload, username, display name, bio, pronouns, location, feed mode, website, privacy switches, validation errors, save progress, and return navigation. Two-column rows collapse below roughly 540px.

**Desktop/tablet/mobile.** The observed unconfigured state uses the same 620px shell and fits at every viewport. The full form’s column collapse and input widths are code-confirmed, not visually verified.

**States.** Unconfigured was observed. Auth redirect, loading, prefilled form, avatar state, validation errors, save error, and success navigation are code-confirmed.

**Strengths.** Fields are visibly labeled, layout code anticipates narrow screens, and privacy is represented as an explicit setting rather than hidden behavior.

**Problems.** The unconfigured presentation is less informative than `/profile`; authenticated responsive behavior, long bio/location/URL wrapping, upload progress/errors, and switch keyboard interaction remain unverified. The page repeats legacy form CSS instead of shared primitives.

**Recommended improvements.** Use the same configuration/status component as Profile, migrate the form to shared tokens/primitives, and test long internationalized content plus avatar failures in a configured environment.

### Redirect aliases — `/algorithm`, `/reels`, `/home`, `/community`, `/search`, `/inbox`, `/u/:username`

**Relevant files:** `src/App.jsx`, `src/components/reels/navSections.js`, `AppSidebar.jsx`, `AppBottomNav.jsx`, `src/components/home/HomeShell.jsx`.

**Current structure and behavior.** Every listed route is explicitly declared, but each immediately navigates to `/`. At fresh state, that means every alias shows the same first-run intro. Desktop and mobile redirects were captured for all seven route patterns. [Community desktop](screenshots/desktop/community--desktop--redirect.png), [Search mobile](screenshots/mobile/search--mobile--redirect.png), [public profile desktop](screenshots/desktop/u-sample-user--desktop--redirect.png).

**Strengths.** Redirects prevent stale URLs from crashing and centralize the current feed entry.

**Problems.** **Runtime-confirmed:** the redirects erase route meaning and can mislead users. Search, Inbox, the logo/Home control, and public-profile-shaped URLs do not reach the implementations their labels imply. Back/forward history and shared URLs lose context. **Code-confirmed:** full page implementations for four of these destinations remain imported in `App.jsx`, so the redirect behavior looks transitional rather than deliberate product information architecture.

**Recommended improvements.** Make an explicit route decision for each destination: mount and support it, remove the corresponding navigation affordance and dead import, or show an honest coming-soon page. Preserve legacy redirects only where the destination truly is a synonym for `/`.

### Unmatched routes — missing 404

**Relevant files:** `src/App.jsx`, `src/components/Navbar.jsx`, `src/App.css`.

**Current structure.** There is no wildcard `Route`. Because an unknown pathname is not recognized by `isAppPath`, the marketing navbar and Lenis layer mount, but the route outlet is empty.

**Desktop.** A full desktop marketing navbar floats over an otherwise blank light page. [1440×900](screenshots/desktop/not-found--desktop--unmatched.png).

**Mobile.** Only the compact brand/menu header appears above blank space. [390×844](screenshots/mobile/not-found--mobile--unmatched.png). Opening its navigation reveals a polished full-screen menu, but Problem/Journey/Solution/Future/About/Contact all target absent section IDs. [Open menu](screenshots/mobile/not-found--mobile--navigation-open.png).

**Strengths.** The menu dialog itself has good focus management, a 44px close target, and readable mobile scaling.

**Problems.** **Runtime-confirmed P0:** unknown URLs show no error, explanation, recovery path, or page content, and the visible menu offers mostly nonfunctional in-page links. React Router logs “No routes matched location.”

**Recommended improvements.** Add an explicit branded 404 route with Home/Back actions. Separately mount the marketing page at a deliberate route or ensure marketing chrome never appears without its sections.

### Unrouted marketing site — `RebootPage`

**Relevant files:** `src/components/RebootPage.jsx`, `Navbar.jsx`, `Hero.jsx`, `Problem.jsx`, `Journey.jsx`, `Solution.jsx`, `FutureVision.jsx`, `AboutCreator.jsx`, `Contact.jsx`, `CustomCursor.jsx`, `ButterflyCanvas.jsx`, `src/App.css`.

**Current structure.** The source defines a complete narrative page: floating navbar; cinematic hero; problem framing; sticky desktop journey/mobile journey list; solution and mode carousel; future vision; creator/about; contact/footer; artifact preview modal; custom cursor and extensive animation. `MainPage` returns this component but `MainPage` is never used by `Routes`.

**Desktop/tablet/mobile.** Not runtime-verifiable as a page without changing routing. Code includes numerous media queries and explicit mobile alternatives, but those are **inferred**, not visual evidence. The navbar dialog alone was observed on an unknown route.

**Strengths.** Distinct narrative structure, memorable display typography, thoughtful long-form pacing, reduced-motion considerations in the global layer, and a coherent editorial voice.

**Problems.** **Code-confirmed:** the page is unreachable, its navigation is orphaned, several components fail lint, and its cream/charcoal/lilac system diverges from the five-color DayBreak direction. It also references the largest raster assets and multiple animation libraries, raising load and motion cost. `DailyWingModal`-style focus concerns do not directly apply here, but the artifact preview/modal behavior needs a dedicated keyboard review before reactivation.

**Recommended improvements.** First decide whether this is the public landing page, an archive, or dead code. If retained, mount it intentionally and audit it visually before redesign. Then migrate its semantic colors and shared controls while preserving the distinctive editorial composition; optimize imagery and test reduced motion. If retired, remove it and its assets in a separate, explicitly authorized cleanup—not as part of a styling pass.

### Unrouted `/home` implementation — Home dashboard

**Relevant files:** `src/components/home/HomePage.jsx`, `HomeShell.jsx`, `DailyWingsRow.jsx`, `DailyWingModal.jsx`, `HomeProfilePanel.jsx`, `SuggestedProfilesPanel.jsx`, `homeData.js`, `src/home.css`.

**Current structure.** Daily Wings story cards lead into a “Today” activity feed, a feed CTA, and—on wider screens—profile and suggested-profile panels. Daily Wing details open in a modal.

**Desktop/tablet/mobile.** Code defines a single-column mobile experience and adds the right rail around 1100px. Story cards scroll horizontally. This behavior is **inferred** because `/home` redirects.

**Strengths.** The structure supports a gentler dashboard alternative to an infinite feed; story/activity/suggestion groupings have clear roles.

**Problems.** **Code-confirmed:** unreachable route, duplicated card/button styles, modal without the shared focus-trap/restoration hook, and breakpoint logic that adds another 1100px convention. The Home logo itself currently links to this redirect route.

**Recommended improvements.** Resolve whether Home is part of the intended IA. If activated, adopt shared modal focus behavior, verify horizontal story scrolling and right-rail collapse on touch devices, and replace demo/profile content with honest loading/empty states before visual polish.

### Unrouted `/community` implementation

**Relevant files:** `src/components/community/CommunityPage.jsx`, `CommunityHeader.jsx`, `FriendSwipeDeck.jsx`, `GoodThingsLeaderboard.jsx`, `YourCircle.jsx`, `SafetyNote.jsx`, `TouchGrassChallenges.jsx`, `communityData.js`, `src/community.css`.

**Current structure.** Header and community framing lead through a friend swipe deck, challenge snapshot, friendly leaderboard, user circle, and safety note. The source uses bundled demo data.

**Desktop/tablet/mobile.** CSS adds columns at approximately 760px and 1040px and collapses to stacked cards below them. Swipe interactions are touch-oriented. All visual conclusions are **inferred** because the route redirects.

**Strengths.** The safety note and “good things” framing are strongly human-centered and align with DayBreak’s healthier-social intent.

**Problems.** **Code-confirmed:** the route is unavailable; demo content is not clearly separated from live state; hover/swipe affordances and keyboard equivalents need validation; community CSS forms another card/shadow/radius system; and the 760px breakpoint nearly conflicts with the app shell’s 768px rail switch.

**Recommended improvements.** Decide whether Community is a product surface or prototype. Before activation, define real loading/empty/private/error states, add explicit non-gesture controls for swipe decisions, align the breakpoint with the shell, and test the deck with keyboard and screen readers.

### Unrouted `/search` implementation

**Relevant files:** `src/components/home/SearchPage.jsx`, `src/components/home/HomeShell.jsx`, `homeData.js`, `src/home.css`.

**Current structure.** A constrained search page provides a text field, vibe filter chips, suggested queries, and grouped people/activity/collection results.

**Desktop/tablet/mobile.** Code uses the same narrow shell and wraps chips/results on smaller screens. This is **inferred** because `/search` redirects.

**Strengths.** Search categories fit the product’s discovery model and avoid presenting a single undifferentiated result stream.

**Problems.** Search is visible in active top navigation but cannot be used. The source needs verified keyboard behavior for chips/results, debounced/live state semantics, loading/no-results/error states, and long-result wrapping.

**Recommended improvements.** Until functional, remove or relabel the active search control. If activated, establish a real search-state model and screen-reader announcement strategy before styling edge cases.

### Unrouted `/inbox` implementation

**Relevant files:** `src/components/home/InboxPage.jsx`, `src/components/home/HomeShell.jsx`, `homeData.js`, `src/home.css`.

**Current structure.** A coming-soon empty state is paired with demo preview rows for notification/message concepts.

**Desktop/tablet/mobile.** It uses the narrow Home shell and stacked rows; responsive behavior is **inferred** because `/inbox` redirects.

**Strengths.** Acknowledges incompleteness instead of pretending a live messaging backend exists.

**Problems.** The active desktop navigation still exposes Inbox but takes the user to `/`, so even the honest coming-soon page is unavailable. Demo rows may be mistaken for real activity if mounted without stronger labeling.

**Recommended improvements.** Either route the control to the coming-soon page with unmistakable preview labeling or remove it until implementation. Do not leave the control silently redirecting to the feed.

### Unrouted public profile implementation — `/u/:username`

**Relevant files:** `src/components/profile/ProfilePage.jsx`, `ProfileCard.jsx`, `src/lib/profileApi.js`, `src/auth.css`.

**Current structure.** `ProfilePage` supports a public username mode with loading, missing, private, error, and full profile branches, but `App.jsx` redirects the public route before that mode can render.

**Desktop/tablet/mobile.** The same wide `CxShell` would apply. All full-profile layout conclusions are **inferred**.

**Strengths.** Source anticipates privacy and not-found states rather than exposing owner-only data indiscriminately.

**Problems.** Shared profile URLs do not work, and redirecting a private/missing username to the feed gives no explanation. Public view contrast, long names/bios, broken avatars, and action permissions are unverified.

**Recommended improvements.** Either mount public mode with explicit privacy/not-found behavior or remove all share/profile-link affordances until it is supported.

## E. Cross-site problems

### Responsive layout

| Viewport band | Confirmed behavior | Main risks |
| --- | --- | --- |
| Large desktop, 1440px+ | Expanded 236px app rail; narrow pages remain centered; no overflow at 1440×900 | 42rem content columns leave large unused fields; Challenges still behaves as a 720px-tall embedded scroller; no evidence beyond 1440 for live feed/marketing |
| Standard laptop, 1024–1439px | 1280 capture uses expanded rail; code uses 76px rail from 768–1179 and expands at 1180; feed composition changes at 1100 | Two major changes at 1100 and 1180 occur close together; 1024–1099, 1100–1179, and 1180+ can feel like three different desktop systems |
| Tablet, 768–1023px | Exactly 768 switches immediately to icon-only rail; accessible routes had no clipping at 768×1024 | Abrupt shell change at the boundary; Community’s dormant 760px breakpoint conflicts conceptually; full feed and populated grids were not visually verified |
| Mobile, 375–767px | Fixed top/bottom app chrome, stable centered forms, no document overflow at 390×844 | Challenges nested scrolling; three-item bottom nav; tabs wrap; several 34–42px controls; fixed chrome needs validation with real feed keyboards/video |
| Small mobile, below 375px | All accessible states fit at 360×800 without horizontal overflow | Global `min-width: 20rem` guarantees overflow below 320px; compact text and fixed controls have little remaining margin; populated media/dialog states were unavailable |

Repeated responsive issues:

- The code has a sound global breakpoint vocabulary, but local CSS adds 540, 760, 1040, 1100, and 1180px transitions. Each component may work alone while the site changes shell, grid, and card composition at unrelated thresholds.
- Full routes and overlay panels share layout constraints. Challenges is the clearest runtime-confirmed example.
- Active narrow pages use essentially the same width from tablet through large desktop. This protects line length but prevents dashboard/content-rich pages from using space meaningfully.
- Mobile fixed chrome appears stable in empty/error states, but feed captions, open keyboards, populated dialogs, very long content, landscape phone layout, and browser zoom remain unverified.
- No horizontal overflow was observed at the five required viewports. That is a meaningful strength and should be protected with regression tests.

### Navigation and information architecture

- `App.jsx` imports complete page implementations while redirecting their routes. Navigation labels, route declarations, and mounted content disagree.
- Mobile bottom navigation has only Reels, Challenges, and Profile; Saved and Search live in the top bar, while Inbox is exposed inconsistently. The stale seven-section comment in `navSections.js` makes intended IA unclear.
- The DayBreak logo/Home affordance links to `/home`, which immediately redirects to `/`. Search and Inbox do the same. Desktop “Feed details” also behaves like a route-to-feed action instead of opening details.
- The marketing navbar is only visible when no active route matches the app-path list. Thus it appears on blank unknown pages but never alongside the marketing content it controls.
- There is no 404 route, and public profile URLs silently lose their identity.

### Typography

- Display/body/accent roles are recognizable and on-brand, especially in Intro and Diagnostic.
- Five font families are requested twice even though only about three have clear active roles. Auth declares an unloaded font.
- Heading scale is not consistently semantic: Challenges has no `h1`; the covered first-run composition exposes two `h1`s.
- Challenges and feed metadata contain repeated 10–12px text. That size is risky for low-vision users and for sunny/outdoor mobile contexts—the exact environment implied by IRL challenges.
- Page-specific CSS continues to declare raw font sizes rather than consistently consuming the global type ramp.

### Spacing and containers

- Global gutters and spacing tokens are thoughtfully defined, but many page rules use unique clamp values and fixed margins.
- Auth, Diagnostic, Profile, Home/Saved, Reels, and Marketing each have separate container conventions.
- Section spacing is coherent within individual pages but inconsistent across systems: diagnostic is airy and intentional; status pages can feel sparse; Challenges is compressed inside a scroll box; dormant marketing uses cinematic vertical spacing.
- Fixed top/bottom chrome uses safe-area compensation in important places, but overlay and keyboard scenarios require a second runtime pass with real content.

### Color and branding

- The canonical five-color palette is correctly encoded and prominent in active shell/diagnostic/challenges surfaces.
- Auth/profile and dormant marketing use recognizable but different cream/plum systems. This makes components appear to come from adjacent rather than identical brands.
- Contrast checks on actual CSS values found `#938e97` on white at 3.20:1 and `#CE6969` on `#FFF9EF` at 3.43:1—both fail 4.5:1 for normal-size text. Morning Light with Midnight is excellent at 9.04:1. White on Twilight Violet is 6.25:1.
- Horizon Rose is often used for tiny eyebrow/accent text, where its 3.43:1 pairing is not sufficient. It is safer as decoration, large text, borders, or on a darker/lighter paired surface chosen by contrast testing.
- Internal `chrysalis-*` storage keys and component names remain for compatibility. The more serious legacy artifact is duplicate `brand 2.js`, which still visibly defines Chrysalis if accidentally imported. No SunScreen branding was found.

### Component consistency

- A full primitive library exists but is effectively unused by application pages. Buttons, cards, inputs, alerts, tabs, dialogs, switches, and empty states are repeatedly reimplemented.
- Button heights range from 34px to 44px+, radii range across many raw values, and shadows vary by page family.
- Modal behavior is inconsistent: Navbar and Saved have stronger focus lifecycles; Daily Wing, inline Reel dialogs, Comments, and Break interactions vary.
- Empty/error/loading states are generally present but visually independent. Study unavailable, Profile unavailable, auth warnings, Saved empty, and Global Error could share a common semantic state family.
- Dark mode is structurally supported, but only Challenges was directly captured in dark mode during this audit. Other active and dormant surfaces require a systematic dark-mode pass.

### Accessibility and usability

Positive confirmed/code evidence:

- Global `:focus-visible` styling and `prefers-reduced-motion` rules exist.
- Runtime-rendered forms had labels; runtime-rendered images had `alt` attributes.
- Navbar’s modal focus lifecycle worked in the captured state.
- Diagnostic answer targets and Study Retry meet comfortable touch sizing.
- Error, loading, empty, private, and unavailable branches are broadly represented in source.

Issues:

- First-run overlay does not make the covered screen inert or assistive-technology-hidden.
- Challenge heading semantics and multiple touch targets fail the intended heading/44px conventions.
- Saved tabs do not implement the complete keyboard interaction pattern.
- Feed modal/popover behaviors are inconsistent, particularly Escape handling and focus restoration.
- Hover is used to reveal some media affordances; equivalent whole-card labels/click behavior exists in Saved, but every feed hover affordance needs touch verification.
- Muted legacy text and small Horizon Rose labels fail normal-text contrast.
- The break prompt’s required selection and lack of defer/dismiss can feel coercive and may impede users who cannot perform the offered actions.
- Status/error copy is generally kind, but the unconfigured login message gives a recovery path that is not actually available in the fresh-user funnel.

### Performance

- The largest public images range from roughly 1 MB to 15 MB, and the dormant marketing experience combines them with Three, Motion, Swiper, Lenis, HLS, and a custom cursor. Even if code-splitting removes unused JavaScript, assets in `public` remain deployable/static unless separately managed.
- Google fonts are requested twice, and more families/weights are loaded than the active experience appears to use.
- `App.jsx` statically imports dormant pages and marketing code. Without route-level lazy loading, they can inflate the initial module graph even though routes redirect away from them.
- Video and YouTube orientation logic has caching/testing, but the signed-in feed could not be profiled for LCP, media decode, network waterfall, or memory behavior.

### Maintainability and quality controls

- Duplicate ` 2` files, stale comments, legacy component names, unused imports, and unreachable components obscure the canonical implementation.
- Tailwind 3.4, `@tailwindcss/vite` 4.2, PostCSS Tailwind configuration, and a Vite config that does not load the Tailwind Vite plugin create unnecessary tooling ambiguity. Most visual work is plain CSS, so the intended ownership should be clarified.
- The shared token and primitive layers are more mature than their adoption. Without migration, adding tokens alone will not reduce drift.
- Unit coverage is strong for feed helpers, challenges, diagnostics, research provenance/visibility, saved state, and YouTube helpers: 90 tests passed. Visual/routes/accessibility behavior has less automated coverage.
- Lint is not currently a clean quality gate (20 errors, 1 warning), including active lifecycle issues.

## F. Priority matrix

| Priority | Issue | Affected routes | Relevant files | Suggested fix |
| --- | --- | --- | --- | --- |
| **P0 — Broken** | Unknown URLs render a blank page with unrelated marketing chrome and nonfunctional section links. [Desktop proof](screenshots/desktop/not-found--desktop--unmatched.png), [open mobile menu](screenshots/mobile/not-found--mobile--navigation-open.png) | Any unmatched route | `src/App.jsx`, `Navbar.jsx`, `App.css` | Add a wildcard 404 with clear recovery; do not mount marketing navigation without marketing sections. |
| **P0 — Broken** | Intended pages are present but route definitions prevent them from ever rendering; visible Search/Inbox/Home/public-profile destinations silently become `/`. [Community redirect](screenshots/desktop/community--desktop--redirect.png) | `/home`, `/community`, `/search`, `/inbox`, `/u/:username` | `src/App.jsx`, `HomeShell.jsx`, `navSections.js` | Decide route-by-route whether to mount, honestly mark unavailable, or remove the affordance; retain only true aliases. |
| **P1 — Major** | First-run intro visually covers but does not semantically isolate onboarding, exposing duplicate `h1`s and hidden focus targets. [Mobile proof](screenshots/mobile/home--mobile--first-run.png) | `/` | `FirstRunGate.jsx`, `IntroScreen.jsx`, `ReelsPage.jsx` | Render a single state or make background inert/`aria-hidden`; restore focus when the intro ends. |
| **P1 — Major** | Route-level Challenges is constrained to an internal 690–718px scroller despite 1,618–1,844px content. [Desktop bottom](screenshots/desktop/challenges--desktop--scrolled-bottom.png), [mobile bottom](screenshots/mobile/challenges--mobile--scrolled-bottom.png) | `/challenges` | `ChallengesPage.jsx`, `ChallengesPanel.jsx`, `reels.css` | Separate full-page and panel containers; use normal route scrolling and preserve fixed-nav clearance. |
| **P1 — Major** | Several feed dialogs/popups have incomplete Escape/focus behavior; Break requires a choice with no defer path. | `/` and `/study` active feed | `CommentsPanel.jsx`, `ReelActionRail.jsx`, `BreakScreen.jsx`, `useDialogFocus.js`, `ReelsPage.jsx` | Use one dialog primitive/focus lifecycle; define explicit Escape/cancel/defer behavior consistent with product intent. |
| **P1 — Major** | Normal muted text fails AA (`#938e97` on white = 3.20:1); small Horizon Rose on warm white is 3.43:1. [Profile proof](screenshots/desktop/profile--desktop--unconfigured.png) | Auth, Profile, Edit Profile, Challenges and other rose-label surfaces | `auth.css`, `app-shell.css`, `reels.css`, `index.css` | Introduce tested semantic muted/accent-text tokens and reserve lower-contrast brand colors for large/decorative use. |
| **P1 — Major** | Core signed-in feed, authenticated profile, live study, and populated saved states cannot be validated in the local audit environment. [Study unavailable](screenshots/mobile/study--mobile--unavailable.png), [login unconfigured](screenshots/mobile/login--mobile--unconfigured.png) | `/`, `/study`, `/profile`, `/profile/edit`, `/saved`, auth | `.env.example`, `supabaseClient.js`, research API integration | Document and provide a safe staging/test environment and non-sensitive test account/session for regression QA; do not add production bypasses. |
| **P1 — Major** | Login configuration copy promises feed exploration that the first-run/auth gate does not allow in this environment. [Proof](screenshots/mobile/login--mobile--unconfigured.png) | `/login`, `/signup`, first-run `/` | `AuthPage.jsx`, `FirstRunGate.jsx`, `App.jsx` | Make configuration/fallback copy match actual navigation, or provide an intentional guest experience. |
| **P2 — Moderate** | Repeated 34–42px controls miss the declared 44px touch target. [Challenge proof](screenshots/mobile/challenges--mobile--default.png) | `/challenges`, `/`, shared app chrome | `ChallengesPanel.jsx`, `ChrysalisTopBar.jsx`, `ThemeToggle.jsx`, `OnboardingStartScreen.jsx`, related CSS | Apply a shared min-size token to all interactive controls; preserve visual density with padding/icon sizing. |
| **P2 — Moderate** | Challenges has no page `h1`; first run exposes two `h1`s. | `/challenges`, `/` | `ChallengesPanel.jsx`, `IntroScreen.jsx`, `OnboardingStartScreen.jsx` | Establish one primary heading per rendered page/state and correct section levels. |
| **P2 — Moderate** | Saved tab semantics are incomplete; tabs wrap awkwardly at 390px. [Proof](screenshots/mobile/saved--mobile--empty-liked.png) | `/saved` | `SavedPage.jsx`, `saved.css` | Implement roving focus/arrow keys/tabpanel associations and a deliberate narrow tab layout. |
| **P2 — Moderate** | Official tokens, legacy auth tokens, dormant marketing tokens, and hard-coded component values coexist. | Cross-site | `index.css`, `auth.css`, `App.css`, `reels.css`, `home.css`, `saved.css` | Inventory semantic usages, map them to one token source, and migrate by component family with contrast regression checks. |
| **P2 — Moderate** | Comprehensive UI primitives exist but pages reimplement the same controls and states. | Cross-site | `components/ui/index.jsx`, `primitives.css`, all page CSS | Validate the primitive API, then adopt it incrementally for Button/Input/Alert/EmptyState/Tabs/Dialog/Card. |
| **P2 — Moderate** | Breakpoints are fragmented (540/760/768/1024/1040/1100/1180/1440). | Feed, Home, Community, Saved, Profile Edit | `index.css`, `tailwind.config.js`, `reels.css`, `home.css`, `community.css`, `auth.css` | Define shell/content breakpoint responsibilities and consolidate near-duplicates after visual regression captures. |
| **P2 — Moderate** | Diagnostic progress never reaches 100% on question screens. | `/diagnostic` | `DiagnosticPage.jsx` | Base progress on current/completed question count and clarify final multi-select optionality. |
| **P2 — Moderate** | Large raster assets and eager dormant imports create likely payload risk. | First run/feed modes and dormant marketing | `public/images/*`, `App.jsx`, marketing components | Convert/resize responsive images, remove accidental duplicates when authorized, lazy-load route families, and measure a production build. |
| **P2 — Moderate** | Route families have inconsistent empty/error/loading visual treatments. | `/saved`, `/study`, auth, `/profile`, global errors | `SavedPage.jsx`, `ResearchPage.jsx`, profile pages, `GlobalErrorBoundary.jsx`, UI primitives | Create shared semantic state components with consistent icon, title, copy, action, and ARIA patterns. |
| **P2 — Moderate** | Tiny 10–12px labels/metadata reduce readability, especially in IRL/mobile contexts. [Challenge proof](screenshots/mobile/challenges--mobile--default.png) | `/challenges`, feed metadata | `reels.css`, `ChallengesPanel.jsx`, feed caption/action CSS | Raise essential text to at least the small-body token; use tiny type only for nonessential decorative metadata with sufficient contrast. |
| **P2 — Moderate** | Lint has 20 errors and 1 warning, including active effect lifecycle findings. | Build-wide | Files listed in the lint section above | Make lint clean in scoped batches; do not suppress lifecycle rules without analysis. |
| **P2 — Moderate** | Dormant pages rely on demo data and lack fully defined live loading/empty/error/privacy states. | Intended `/home`, `/community`, `/search`, `/inbox` | Home/community components and data modules | Define state contracts before reactivating routes; visibly label previews/demo content. |
| **P3 — Polish** | Narrow content columns leave large desktop canvases under-composed. [Saved proof](screenshots/desktop/saved--desktop--empty-liked.png), [Profile proof](screenshots/desktop/profile--desktop--unconfigured.png) | `/saved`, `/challenges`, `/profile`, `/profile/edit` | `app-shell.css`, `saved.css`, `auth.css` | Keep readable line lengths but introduce optional rails/wider grids for content-rich states. |
| **P3 — Polish** | Font resources are duplicated and include unclear/unused roles; auth declares unloaded Inter. | Cross-site | `index.html`, `index.css`, `auth.css`, Tailwind config | Load one deliberate family set once; document display/body/accent roles and remove stale declarations. |
| **P3 — Polish** | Duplicate ` 2` source/QA files and legacy Chrysalis names create accidental-import risk. | Repository-wide | `src/* 2*`, `qa/* 2.mjs`, `brand 2.js`, `ChrysalisTopBar.jsx`, local-storage keys | In a separately authorized cleanup, identify canonical files, archive/remove duplicates, and preserve storage migrations where needed. |
| **P3 — Polish** | React Router emits two future-flag warnings on every route. | All routes | Router setup in `App.jsx` | Opt into/test the v7 future behaviors or upgrade deliberately after route cleanup. |
| **P3 — Polish** | Tailwind tooling versions/configuration imply more than one integration path. | Build-wide | `package.json`, `vite.config.js`, `postcss.config.js`, `tailwind.config.js` | Choose PostCSS Tailwind 3, upgrade coherently to Tailwind 4, or remove unused integration; document the decision. |

## G. Recommended implementation phases

### Phase 1 — Route and product-surface decisions

1. Decide the canonical public entry: authenticated feed, marketing landing page, or an explicit split such as `/` and `/app`.
2. Decide the status of Home, Community, Search, Inbox, and public profiles individually.
3. Add a real 404 and ensure every visible navigation item has an honest destination.
4. Document the required Supabase and research-service setup for safe staging QA.

**Exit criteria:** no blank route, no misleading redirect, no orphaned marketing navbar, and a site map that matches `App.jsx`.

### Phase 2 — Global design tokens and layout foundations

1. Confirm `index.css` as the canonical semantic token source.
2. Add contrast-safe semantic text/accent tokens derived from the approved palette.
3. Define which breakpoints belong to global shell, content grid, and component-local adaptation.
4. Establish route, narrow-form, dashboard, and immersive-feed container patterns.
5. Resolve font loading/roles and Tailwind integration ownership.

**Exit criteria:** light/dark tokens pass contrast checks, container/breakpoint responsibilities are documented, and new component CSS no longer introduces raw palette substitutes without a reason.

### Phase 3 — Navigation and responsive shell

1. Rebuild the navigation source of truth from the approved IA.
2. Align desktop rail, mobile top bar, mobile bottom nav, brand/Home action, and route active states.
3. Make the 768/1024/1180 behavior deliberate and test intermediate widths around each breakpoint.
4. Standardize safe-area and content clearance for fixed chrome.

**Exit criteria:** every item routes correctly, all targets are at least 44px, keyboard focus is visible, and 360/390/768/1024/1280/1440 widths pass overflow checks.

### Phase 4 — Shared component standardization

1. Validate the existing `components/ui` primitives rather than replacing them reflexively.
2. Migrate Button, Input, Alert, Card, EmptyState, Tabs, Dialog/Drawer, and Switch one family at a time.
3. Centralize focus trap, initial focus, Escape, restoration, scroll lock, and background inertness.
4. Create a shared status-state pattern for unavailable/loading/error/empty/success views.

**Exit criteria:** component variants cover active use cases, duplicated state CSS declines, and keyboard/touch behavior is consistent.

### Phase 5 — High-priority page fixes

1. Correct first-run modal semantics and single-heading structure.
2. Separate Challenges route layout from panel layout; fix touch sizes and heading order.
3. Complete Saved tabs and narrow-phone behavior.
4. Correct auth/profile contrast and configuration messaging.
5. Correct diagnostic progress semantics.

**Exit criteria:** all P0/P1 items that do not depend on external credentials are resolved and have focused regression screenshots.

### Phase 6 — Core-state and mobile verification

1. In an authorized staging environment, capture the signed-in feed, every feed mode, media orientations, comments, feed details, reflections, breaks, loaded/error/empty pagination, and long captions.
2. Capture populated Saved, owner/public/private/missing Profile, Edit Profile validation/upload, auth error/success, and the live Study completion path.
3. Test mobile keyboard, landscape, browser zoom, reduced motion, slow network, media failure, and touch-only interaction.
4. Reassess desktop use of space using populated rather than empty pages.

**Exit criteria:** every primary and conditional state has current desktop/tablet/mobile evidence and no essential interaction depends on hover.

### Phase 7 — Accessibility, performance, and regression review

1. Run automated accessibility checks, then keyboard and screen-reader walkthroughs; automation alone is insufficient.
2. Verify heading order, names/descriptions, live errors, tab/dialog patterns, focus restoration, target size, contrast, and reduced motion.
3. Optimize raster assets and font requests, introduce route-level lazy loading, and measure LCP/CLS/interaction cost in a production build.
4. Make unit tests and lint clean; add route smoke tests, viewport overflow assertions, and screenshot regression coverage.
5. Only after canonical files are confirmed, perform a separately authorized cleanup of duplicate ` 2` files and legacy names/assets.

**Exit criteria:** clean lint/tests, measured performance budgets, accessibility acceptance notes, and a final five-viewport regression set linked to resolved priority items.

## Final assessment

DayBreak already has a credible visual identity and a stronger token/accessibility foundation than the page CSS currently reveals. Its accessible routes survive the required viewport range without horizontal breakage, and Diagnostic demonstrates that the intended warm, reflective, hopeful character can work consistently on both desktop and mobile. The next work should not begin with broad visual redesign. It should first make routing and navigation truthful, isolate first-run and modal semantics, remove the Challenges nested-scroll trap, and converge the active page families on the design system that already exists. Once a safe authenticated test environment is available, the feed and profile workflows need an equally rigorous visual pass before they can be called mature.
