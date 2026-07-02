# Social Media Diagnostic — Design

**Status:** Decisions confirmed with Elaine (2026-07-02). Ready to turn into an
implementation plan.

**Confirmed decisions:** diagnostic-style framing · 5 questions · gives a result +
recommended mode · shows after first sign-in, once · stored in Supabase with full
answers retained for later analysis.

## One-line

After a new user signs in, a short **diagnostic** identifies their relationship
with social media (their "type" + the patterns behind it) and recommends the
Chrysalis algorithm mode that fits — engaging and honest, without clinical claims.

## The framing decision

**Diagnostic-style, but not a medical diagnosis.** The experience should *feel*
like a real diagnostic — it gives you a clear result ("Your result: The Late-Night
Scroller") and names the patterns it sees. What it deliberately avoids is claiming
to diagnose a clinical disorder (it never says "you have an addiction / a
condition") — Chrysalis isn't a medical tool and the audience is teens.

- **User-facing name: "Diagnostic"** (working title — could be "Social Media
  Diagnostic," "Scroll Diagnostic"). Confirmed the diagnostic feel is wanted.
- Language names *behaviour patterns* ("late-night scrolling," "comparison spiral,"
  "doomscrolling") rather than *medical labels* ("addiction," "disorder").
- Result copy is direct and a little striking, but ends on agency: here's what
  helps, here's your mode.

## Output — what the user gets

**Not a label — a personalized setup. "Here's what we've unlocked for you."**

The diagnostic reads their answers and turns them into a set of **recommended
features that get switched on** for their feed, plus a mode. It's forward-looking
and empowering (what you *get*), never a negative verdict (what's *wrong with you*).

Result screen:

1. Headline: **"Your Chrysalis is ready."** + one warm sentence.
2. A short list of **unlocked features**, each tied to an answer pattern and phrased
   as a benefit (see feature map below). Typically 2–3 for a given user.
3. The **recommended mode** (Daily Dew / Metamorphosis / Cruisin'), shown as part of
   the setup ("Your mode: …") with a one-line why.
4. CTA — **"Start My Algorithm"** — applies the mode + feature flags and enters the feed.

### Feature map (answer pattern → unlocked feature)

| Signal (from answers)                    | Unlocked feature        | What it does (framing)                                  |
|------------------------------------------|-------------------------|--------------------------------------------------------|
| Late-night scrolling high                | 🌙 **Night Wind-Down**  | Feed eases off / calms after late hours                 |
| Comparison high                          | 🛡️ **Comparison Guard** | Down-weights appearance / highlight-reel content        |
| Doomscrolling high                       | 🌤️ **Doomscroll Breaker** | Down-weights distressing news/negativity spirals       |
| Compulsive opening / hard-to-stop high   | ⏸️ **Scroll Breaks**    | Gentle pause prompts after a while (awareness)          |
| Wants real connection (Q5)               | 🤝 **Prosocial Boost**  | Weights content by how it makes you feel, not just taps |
| Wants control/transparency (Q5)          | 🧭 **Feed Compass**     | Shows why things are recommended; more control          |

Everyone gets at least one unlock (if all signals are low → "Balanced" setup with
Feed Compass + Cruisin', framed as "you've got a healthy baseline — here's how to
keep it"). These map to real Chrysalis mode behaviors / existing panels
(FeedCompass, breaks, prosocial weighting) — v1 can wire the ones that exist and
stub the rest as saved flags.

## Placement & flow

**After first sign-in, once; retakeable later.**

```
sign up / first Google login
        │
        ▼
  /check-in  ── (only if not completed before)
        │
   6–8 quick questions, one card at a time
        │
        ▼
   result screen  ──►  "Start My Algorithm" sets recommended mode
        │
        ▼
   /algorithm feed (in the recommended mode)
```

- Gated by a "completed" flag so it shows **once** for new users. Existing users
  aren't forced through it.
- Retakeable anytime from profile/settings ("Redo my check-in").
- Does **not** replace the existing "Choose your intention" screen — the check-in
  *pre-selects* a mode; users can still change modes normally afterward.

## The questions (5)

Each is a single multiple-choice, 4-point scale
(*Rarely / Sometimes / Often / Almost always*) unless noted. Five dimensions,
chosen to spread across the distinct wellbeing patterns so the result and the mode
mapping are meaningful:

1. **Compulsive opening** — "How often do you open an app without really meaning to?"
2. **Late-night use** — "Do you scroll in bed when you meant to sleep?"
3. **Comparison** — "After scrolling, how often do you feel worse about yourself?"
4. **Doomscrolling** — "Do you get pulled into a spiral of upsetting posts/news?"
5. **What you want** — "What would make your feed feel better?" (multi-select of
   goals: *less comparison, calmer content, fewer late scrolls, real connection,
   more control/transparency*) → captures desired "features" for later analysis.

> Q1–Q4 are the scored diagnostic signals; Q5 captures intent/features. If you
> want a 5th *scored* signal instead of the goals question, swap in "How hard is it
> to put your phone down once you start?" (stopping) — but keeping the goals
> question gives you richer data to analyze.

## Scoring → unlocks + mode (heuristic, no ML)

Simple, transparent, tweakable:

1. **Per-signal threshold → unlock.** Each scored signal (late-night, comparison,
   doomscrolling, compulsive) that lands "Often/Almost always" flips on its mapped
   feature (see feature map). Q5 goals flip on Prosocial Boost / Feed Compass.
2. **Dominant signal → mode:**

| If answers lean toward…                              | Recommended mode |
|------------------------------------------------------|------------------|
| High compulsion / late-night / can't stop            | **Metamorphosis** (scroll awareness, breaks) |
| High comparison / doomscrolling                      | **Daily Dew** (calm, gentle reset)           |
| Lower distress, wants healthy variety/control        | **Cruisin'** (healthy personalized)          |

Ties break toward the gentler mode. The result screen's copy is assembled from the
unlocked features, so it always reads as "here's your setup," never a verdict.

## Data & privacy

**Store server-side in Supabase, RLS-protected. Full answers retained so patterns
can be analyzed later.**

- New table `diagnostics`:
  - `id` (uuid, pk)
  - `user_id` (uuid, fk → auth.users)
  - `answers` (jsonb) — every question's raw answer, kept for later analysis
  - `scores` (jsonb) — computed per-dimension scores
  - `unlocked_features` (jsonb) — array of feature keys turned on for this user
  - `recommended_mode` (text)
  - `created_at` (timestamptz, default now())
- **RLS:** a user can insert and read **only their own** rows (`user_id = auth.uid()`).
  Aggregate/analysis access happens through the service role, not the client.
- Keep a row per attempt (don't overwrite) so retakes form a history to analyze.
- Also mirror the chosen mode into the existing `localStorage` key
  `chrysalis-algorithm-mode` so the feed picks it up immediately (matches how
  ReelsPage already reads mode).
- **Privacy for minors:** answers live only in this RLS-protected table, never in
  the public `profiles` table and never exposed on a profile page — consistent with
  the existing email/phone privacy rule in `AuthPage`. Analysis is on your side
  (aggregate), not surfaced back to other users.
- **Manual setup you'll do (like Google):** create the `diagnostics` table + RLS
  policies in the Supabase dashboard (or a SQL snippet I'll give you). The client
  only needs the anon key it already has.

## Components (planned)

- `components/diagnostic/DiagnosticPage.jsx` — step controller (question → question → result)
- `components/diagnostic/diagnosticData.js` — questions, scale, scoring weights, result types
- `components/diagnostic/DiagnosticResult.jsx` — result + recommended-mode card
- `lib/diagnostics.js` — save/read helper wrapping Supabase (insert answers, fetch latest)
- Route `/diagnostic` in `App.jsx` (added to `isAppPath` for app chrome)
- Post-auth gate: after sign-in, if the user has no diagnostic row, redirect to `/diagnostic`
- Reuses `CxShell` + `cx-` card styling for visual consistency

## Non-goals (YAGNI)

- No clinical scoring / comparison to medical thresholds / disorder labels.
- No ML — pure heuristic mapping.
- No sharing/social features on results (can add later if you want the result to be
  shareable).

## Resolved

- **Framing:** diagnostic-style, no medical claims ✓
- **Output:** personalized "here's what we unlocked for you" — recommended features
  + mode, framed as a benefit, not a negative label ✓
- **Placement:** after first sign-in, once, retakeable ✓
- **Length:** 5 questions ✓
- **Storage:** Supabase, RLS, full answers retained for later analysis ✓
- **Name:** "Diagnostic" (working title) ✓

## Next step

Turn this into a phased implementation plan (writing-plans), then build.
