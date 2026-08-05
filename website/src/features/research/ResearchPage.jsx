import { useEffect, useState } from 'react';
import { CheckCircle2, LoaderCircle, RefreshCw } from 'lucide-react';
import { ReelsPage } from '../reels/ReelsPage';
import { getResearchEventService } from '../../lib/researchEvents';
import './research.css';

function StudyStateScreen({ status, onRetry }) {
  const isLoading = status === 'loading';

  return (
    <main className={`study-state study-state--${status}`}>
      <section
        className="study-state__card"
        aria-labelledby="study-state-title"
        aria-busy={isLoading ? 'true' : undefined}
      >
        <p className="study-state__eyebrow">DayBreak research</p>
        <div className="study-state__icon" aria-hidden="true">
          {isLoading ? <LoaderCircle /> : status === 'completed' ? <CheckCircle2 /> : <RefreshCw />}
        </div>

        {isLoading && (
          <>
            <h1 id="study-state-title">Preparing your session</h1>
            <p className="study-state__message" role="status" aria-live="polite">
              Starting anonymous research session…
            </p>
          </>
        )}

        {status === 'error' && (
          <>
            <h1 id="study-state-title">Session unavailable</h1>
            <p className="study-state__message" role="alert">
              We could not start the anonymous research session.
            </p>
            <button className="study-state__action" type="button" onClick={onRetry}>
              Try again
            </button>
          </>
        )}

        {status === 'completed' && (
          <>
            <h1 id="study-state-title">Session complete</h1>
            <p className="study-state__message" role="status">
              Your anonymous research events were saved.
            </p>
          </>
        )}
      </section>
    </main>
  );
}

export function ResearchPage() {
  const [state, setState] = useState({ status: 'loading', session: null, error: null });
  const researchTracker = getResearchEventService();

  useEffect(() => {
    let active = true;
    const stopRecovery = researchTracker.startNetworkRecovery();
    researchTracker.initialize()
      .then(({ session, completed }) => {
        if (active) setState({ status: completed ? 'completed' : 'active', session, error: null });
      })
      .catch((error) => {
        if (active) setState({ status: 'error', session: null, error });
      });
    return () => {
      active = false;
      stopRecovery();
    };
  }, [researchTracker]);

  const retry = async () => {
    setState((current) => ({ ...current, status: 'loading', error: null }));
    try {
      const { session, completed } = await researchTracker.initialize();
      setState({ status: completed ? 'completed' : 'active', session, error: null });
    } catch (error) {
      setState({ status: 'error', session: null, error });
    }
  };

  const complete = async () => {
    setState((current) => ({ ...current, status: 'completing', error: null }));
    try {
      await researchTracker.complete();
      setState((current) => ({ ...current, status: 'completed', error: null }));
    } catch (error) {
      setState((current) => ({ ...current, status: 'active', error }));
    }
  };

  if (state.status === 'loading') {
    return <StudyStateScreen status="loading" />;
  }
  if (state.status === 'error') {
    return <StudyStateScreen status="error" onRetry={retry} />;
  }
  if (state.status === 'completed') {
    return <StudyStateScreen status="completed" />;
  }

  return (
    <div className="study-route">
      <h1 className="study-visually-hidden">DayBreak anonymous research session</h1>
      <ReelsPage
        researchSession={state.session}
        researchTracker={researchTracker}
      />
      <aside
        className="research-session-controls"
        aria-label="Research session controls"
        aria-busy={state.status === 'completing' ? 'true' : undefined}
      >
        <div className="research-session-controls__label" aria-hidden="true">
          <span>DayBreak research</span>
          <strong>Study session</strong>
        </div>
        <button
          type="button"
          onClick={complete}
          disabled={state.status === 'completing'}
        >
          {state.status === 'completing' ? 'Saving…' : 'Complete test session'}
        </button>
        {state.error && (
          <span className="research-session-controls__error" role="alert">
            {state.error.message}
          </span>
        )}
      </aside>
    </div>
  );
}
