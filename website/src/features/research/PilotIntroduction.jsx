import { ArrowRight, ShieldCheck } from 'lucide-react';
import { DayBreakLogo } from '../../shared/components/DayBreakLogo';

export function PilotIntroduction({ onContinue }) {
  return (
    <main className="study-flow">
      <div className="study-flow__ambient" aria-hidden="true" />
      <article className="study-panel study-panel--introduction" aria-labelledby="pilot-title">
        <header className="study-panel__header">
          <DayBreakLogo className="study-panel__logo" />
          <p className="study-eyebrow">A more intentional scroll</p>
          <h1 id="pilot-title">Welcome to the DayBreak pilot</h1>
        </header>

        <div className="study-intro-copy">
          <p>
            DayBreak is testing whether choosing a limited feed session can make scrolling
            feel more intentional.
          </p>
          <p>
            You will choose how many videos you want to view. Afterward, you will answer
            three short questions and begin a break from the feed.
          </p>
          <p>
            DayBreak records your session choices, viewed posts, interactions, whether you
            reached your selected boundary, your checkout answers, and whether the break was
            completed or ended early.
          </p>
          <p>
            This pilot does not collect your name, government ID, precise location, private
            messages, or contacts. Participation is voluntary, and you may stop using the
            study at any time.
          </p>
          <p>
            DayBreak is an experimental prototype. It has not been proven to improve mental
            health, sleep, or self-control.
          </p>
        </div>

        <div className="study-panel__footer">
          <p className="study-privacy-note">
            <ShieldCheck aria-hidden="true" />
            Continuing only opens the planner. Nothing starts yet.
          </p>
          <button className="study-button study-button--primary" type="button" onClick={onContinue}>
            Continue
            <ArrowRight aria-hidden="true" />
          </button>
        </div>
      </article>
    </main>
  );
}
