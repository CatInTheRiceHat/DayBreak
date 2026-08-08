# DayBreak Pilot-Readiness Roadmap

**Roadmap version:** v0.12  
**Prepared:** August 5, 2026  
**Target pilot opening:** Week of August 12, 2026  
**Pilot type:** Small closed formative pilot  
**Primary build:** Intentional Break Loop

---

## 1. Pilot Goal

The first school-year pilot should determine whether DayBreak can reliably deliver one complete intentional session:

1. A participant enters through the research route.
2. The participant chooses an intention.
3. The participant chooses a finite number of videos.
4. DayBreak enforces that limit.
5. The participant reaches a real stopping screen.
6. The participant completes a three-question checkout.
7. The participant begins a visible cooldown.
8. DayBreak records whether the plan was completed or overridden.

This pilot is for technical validation, usability, and early behavioral patterns. It is not large enough to prove that DayBreak improves wellbeing.

---

## 2. Scope Lock

### Must be included

- Anonymous or pseudonymous participant entry
- One feed condition for all participants
- Intention selection
- Finite video choices
- Estimated session duration
- Recommended and adjustable cooldown
- Server-enforced content limit
- Progress indicator
- Finish-early option
- Real end-of-session screen
- Three-question checkout
- Cooldown screen
- Soft early-return confirmation
- Persistent state across refresh
- Ordered, retryable research events
- Mobile-safe layout
- Accurate product language
- Preference identity and ownership protection

### Must not be included

- Sunrise Ritual implementation
- Morning-photo sharing
- Direct messaging
- Public comments
- Friend discovery
- Leaderboards or streak pressure
- Creator profiles
- Full sleep-protection system
- Exposure-memory circuit breakers
- A regular-versus-balanced A/B comparison
- Major visual redesign
- New recommendation objectives

These features remain in the roadmap, but they should not delay or contaminate the first pilot.

---

## 3. First-Pilot Product Flow

### Participant entry

- Open the dedicated `/study` route.
- Display a brief study explanation and data summary.
- Create or resume an anonymous participant credential.
- Do not require a public profile.
- Do not collect raw government identification.
- Keep social and network routes unavailable.

### Session planning

The participant chooses:

**Intention**

- Relax
- Learn
- Feel inspired
- Catch up
- Take a break

**Video count**

Recommended first-pilot options:

- 5
- 10
- 20
- 40

Keep the 5–100 custom range in the long-term specification, but omit custom values from the first pilot unless the standard choices are already stable. Fewer choices make failures easier to diagnose.

**Cooldown**

- Display estimated feed time.
- Recommend approximately twice the estimated time away.
- Allow adjustment before the session begins.
- Record the suggested and selected values separately.

### Finite session

- The server stores the selected video limit.
- The API never returns more than the remaining allowance.
- The client displays progress such as `7 of 20`.
- Refresh resumes the same session.
- Finishing early is allowed.
- The system never silently changes to an infinite fallback.
- Autoplay stops when the allowance ends.

### Checkout

Ask:

1. Was this break worth your time?
2. How in control did you feel?
3. Do you feel better, the same, or worse?

### Cooldown

- Display time remaining.
- Do not display feed previews.
- Offer one optional offline activity.
- Allow an early return only after a short pause and deliberate confirmation.
- Record an override without punishing the participant.

---

## 4. Research Design for the First Pilot

### Participants

- Begin with approximately 5–8 known participants.
- Use a closed invitation rather than a school-wide release.
- Ask each participant to complete approximately three sessions across three to five days.
- Use the appropriate school, parent, mentor, or participant approval process for the setting.

### Experimental focus

Use one consistent feed condition. Do not simultaneously test:

- balanced versus regular ranking;
- sunrise access;
- different cooldown formulas;
- social sharing;
- multiple recommendation modes.

The first question is whether the Intentional Break Loop works and is understandable.

### Primary measures

- Sessions ending at or before the selected boundary
- Selected boundaries successfully enforced
- Cooldown-completion rate
- Perceived-control score
- Worthwhile-session response

### Secondary measures

- Planned versus actual video count
- Finish-early rate
- Cooldown-override rate
- Time until the next session
- Mood change
- Setup abandonment
- Event-upload failures
- Refresh recovery

### Qualitative debrief

After the pilot, ask each participant:

- What part felt most natural?
- What part felt annoying or controlling?
- Did the video count match how you think about a break?
- Did the cooldown help you notice your behavior?
- What would make you use DayBreak again?
- Did anything feel unclear, unsafe, or misleading?

---

## 5. Seven-Day Build Plan

## Day 1 — Wednesday, August 5  
### Freeze and map

- Freeze the v0.12 specification.
- Run an observation-only repository pass.
- Map the current `/study` route, feed request, session state, fallback path, event queue, and database tables.
- Identify every file that must change.
- Assign file ownership before coding.
- Define the exact event names and required fields.
- Create a pilot feature branch and separate agent worktrees.

**Deliverable:** Code map, dependency map, event contract, and file-ownership plan.

---

## Day 2 — Thursday, August 6  
### Backend session contract

- Create the session-plan model.
- Store selected intention, video count, duration estimate, and cooldown.
- Make the server derive participant identity from the research credential.
- Enforce the remaining video allowance in the feed API.
- Add database fields or migrations for the new events.
- Make cooldown state survive refresh.
- Fix preference ownership and row-level-security gaps used by the pilot path.

**Deliverable:** Tested API contract that cannot return content beyond the selected limit.

---

## Day 3 — Friday, August 7  
### Frontend planning and finite feed

- Build the intention and video-count planner.
- Display the estimated duration and cooldown recommendation.
- Build the confirmation card.
- Connect the planner to the server-created session.
- Add the session progress indicator.
- Remove automatic loading beyond the selected boundary.
- Add finish-early behavior.

**Deliverable:** A participant can create and complete a finite session in the browser.

---

## Day 4 — Saturday, August 8  
### Ending, checkout, and cooldown

- Build the real end-of-session screen.
- Stop autoplay at the boundary.
- Build the three-question checkout.
- Persist checkout responses.
- Build the cooldown state.
- Add the early-return pause and confirmation.
- Ensure refresh resumes checkout or cooldown correctly.

**Deliverable:** Complete planner-to-cooldown user journey.

---

## Day 5 — Sunday, August 9  
### Integration and claim accuracy

- Integrate frontend and backend branches.
- Remove or qualify Night Wind-Down claims.
- Remove exact-looking wellness claims that are not measured.
- Disable comments, messaging, challenges, leaderboards, and unrelated routes in the study experience.
- Confirm that no synthetic fallback can hide a failed finite-feed request.
- Verify event ordering, idempotency, and retry behavior.

**Deliverable:** One honest and isolated pilot experience.

---

## Day 6 — Monday, August 10  
### QA and internal dogfooding

Test:

- 5-, 10-, 20-, and 40-video sessions
- Early finish
- Exact boundary finish
- Refresh during feed
- Refresh during checkout
- Refresh during cooldown
- Early cooldown override
- Offline interruption and reconnect
- Duplicate event submissions
- Expired or invalid credentials
- Mobile width at 375 px
- Tablet and desktop layouts
- Browser back button
- API failure
- Empty-content response

Run the complete journey yourself multiple times and with one or two trusted internal testers who are not counted as the formal pilot.

**Deliverable:** Completed QA matrix with screenshots, event records, and documented defects.

---

## Day 7 — Tuesday, August 11  
### Launch decision

- Fix all pilot-blocking defects.
- Prepare participant instructions.
- Prepare the short data-use explanation.
- Prepare the debrief form.
- Create participant codes or invitation links.
- Verify the production deployment.
- Perform a fresh-account test.
- Apply the launch gate below.

**Deliverable:** Signed go/no-go checklist and release candidate.

---

## 6. Multi-Agent Codebase Plan

Do not allow several agents to freely edit the same codebase at once.

### Agent A — Architecture and integration owner

Responsibilities:

- Read-only code map
- Shared interfaces
- Session contract
- File ownership
- Merge review
- Scope enforcement
- Final integration

This agent should not independently rewrite every feature. It protects consistency.

### Agent B — Backend and data

Owns:

- Session-plan API
- Finite feed enforcement
- Database migrations
- Research-event schema
- Credential-derived identity
- Cooldown persistence
- Preference-security fixes

### Agent C — Frontend session experience

Owns:

- Planner
- Confirmation card
- Progress UI
- Finite-feed behavior
- Ending screen
- Checkout
- Cooldown and override UI

### Agent D — QA and security

Owns:

- Automated tests
- Adversarial refresh and API tests
- Responsive screenshots
- Event-integrity validation
- Claim audit
- Route isolation
- Launch-gate report

### Working rules

- Use separate branches or worktrees.
- Assign files before edits begin.
- Define API types before frontend and backend implementation.
- Merge backend contract first, frontend second, QA fixes third.
- No agent may introduce a new feature outside v0.12.
- Every behavior change must include or update a test.
- The integration owner resolves conflicts; agents do not overwrite one another.
- Record every changed decision in the project notebook.

---

## 7. Pilot Launch Gate

### Required for GO

- The server enforces the selected video count.
- Refresh cannot reset or increase the allowance.
- The feed visibly ends.
- Autoplay stops at the end.
- Checkout responses persist.
- Cooldown survives refresh.
- Early return is recorded.
- Events remain ordered and deduplicated.
- No participant can access unfinished social routes.
- Participant identity is not trusted from a caller-supplied user ID.
- Pilot data is stored under the intended access policies.
- Unsupported feature claims are removed or qualified.
- Production build passes.
- Pilot-path tests pass.
- No lint errors remain in files used by the pilot.
- Mobile testing has no blocking overlap.
- Participant instructions and debrief materials are ready.

### Automatic NO-GO conditions

- The feed can become infinite after refresh or API fallback.
- Events are lost or attached to the wrong participant.
- A participant can access another participant’s preferences.
- The checkout can be skipped without recording why.
- Cooldown state disappears on reload.
- The mobile interface prevents completion.
- Night, safety, or wellness features are presented as active when they are not.
- Social routes remain reachable in the pilot.
- The deployed build differs from the tested release candidate.

Cosmetic imperfections may remain. Data-integrity, privacy, boundary-enforcement, and completion failures may not.

---

## 8. Pilot-Week Operating Rules

During the pilot:

- Do not change the ranking algorithm.
- Do not add Sunrise Ritual or social sharing.
- Do not change event definitions.
- Do not silently repair or delete participant records.
- Fix only critical bugs that block participation, corrupt data, or create a safety/privacy risk.
- Record every deployment as a patch version.
- Check data quality daily.
- Keep a defect log.
- Do not interpret results until the planned pilot window ends.
- Do not make causal wellbeing claims from the small sample.

---

## 9. Versioning Plan

### v0.12 — Pilot-Readiness Roadmap

The current plan and scope lock.

### v0.13 — Pilot Release Candidate

The finite-session build has passed internal QA but has no real pilot users.

### v1.0 — First Closed Pilot Opens

Use this version when the first real participant begins using DayBreak, consistent with the journal rule that v1.0 requires real users.

### v1.0.x — Critical Pilot Patches

Only bugs, data-integrity fixes, safety fixes, and blocking usability fixes.

### v1.1 — Pilot Findings and Revised Intentional Break Loop

Record:

- what participants actually did;
- which assumptions failed;
- satisfaction and control responses;
- completion and override patterns;
- defects;
- changes recommended for the next build.

### v1.2 or later — Sunrise Ritual Prototype

Build the morning micro-journaling and optional close-friend connection layer only after the finite-session pilot has produced usable evidence.

---

## 10. Definition of Pilot Success

The first pilot succeeds when:

- real participants can complete the full journey without assistance;
- the finite boundary is reliably enforced;
- the event dataset is complete enough to reconstruct each session;
- participants understand what the cooldown means;
- the checkout captures perceived control and worthwhile use;
- the project produces a clear list of changes for v1.1.

The first pilot does not need to prove that DayBreak improves mental health, sleep, productivity, or long-term self-control. Its job is to show that the core intervention is real, measurable, understandable, and safe enough to continue testing.
