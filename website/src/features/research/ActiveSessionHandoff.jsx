import { CheckCircle2, Clock3, Film, Sparkles } from 'lucide-react';
import { INTENTIONS } from './sessionContract.js';

const INTENTION_LABELS = Object.freeze([
  'Relax',
  'Learn',
  'Feel inspired',
  'Catch up',
  'Take a quick break',
]);

function intentionLabel(intention) {
  const index = INTENTIONS.indexOf(intention);
  return index >= 0 ? INTENTION_LABELS[index] : 'Intentional break';
}

function minutes(seconds) {
  return Number.isFinite(seconds) ? Math.round(seconds / 60) : '—';
}

export function ActiveSessionHandoff({ journey }) {
  const showDebugId = import.meta.env?.DEV && import.meta.env?.VITE_SHOW_STUDY_DEBUG === 'true';

  return (
    <main className="study-flow">
      <div className="study-flow__ambient" aria-hidden="true" />
      <section className="study-panel study-panel--handoff" aria-labelledby="active-session-title">
        <div className="study-handoff-icon" aria-hidden="true">
          <CheckCircle2 />
        </div>
        <header className="study-panel__header">
          <p className="study-eyebrow">Session active</p>
          <h1 id="active-session-title">Your DayBreak has started</h1>
          <p>Your finite feed is ready. The viewing experience is being connected to this new session flow.</p>
        </header>

        <dl className="study-session-facts">
          <div>
            <dt><Sparkles aria-hidden="true" /> Intention</dt>
            <dd>{intentionLabel(journey.intention)}</dd>
          </div>
          <div>
            <dt><Film aria-hidden="true" /> Your boundary</dt>
            <dd>{journey.planned_video_count} videos</dd>
          </div>
          <div>
            <dt><Clock3 aria-hidden="true" /> Estimated session</dt>
            <dd>about {minutes(journey.estimated_duration_seconds)} minutes</dd>
          </div>
          <div>
            <dt><Clock3 aria-hidden="true" /> Time away afterward</dt>
            <dd>{minutes(journey.selected_cooldown_seconds)} minutes</dd>
          </div>
        </dl>

        <p className="study-handoff-note">
          Keep this page open. Feed access will appear here in the next implementation stage.
        </p>
        {showDebugId && <code className="study-debug-id">Active session ID: {journey.session_id}</code>}
      </section>
    </main>
  );
}
