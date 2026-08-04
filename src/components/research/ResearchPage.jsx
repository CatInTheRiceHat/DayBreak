import { useEffect, useState } from 'react';
import { ReelsPage } from '../reels/ReelsPage';
import { getResearchEventService } from '../../lib/researchEvents';

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
    return <main className="algorithm-loading">Starting anonymous research session…</main>;
  }
  if (state.status === 'error') {
    return (
      <main className="algorithm-loading">
        <p>We could not start the anonymous research session.</p>
        <button type="button" onClick={retry}>Try again</button>
      </main>
    );
  }
  if (state.status === 'completed') {
    return (
      <main className="algorithm-loading">
        <h1>Session complete</h1>
        <p>Your anonymous research events were saved.</p>
      </main>
    );
  }

  return (
    <>
      <ReelsPage
        researchSession={state.session}
        researchTracker={researchTracker}
      />
      <div className="research-session-controls">
        <button type="button" onClick={complete} disabled={state.status === 'completing'}>
          {state.status === 'completing' ? 'Saving…' : 'Complete test session'}
        </button>
        {state.error && <span role="alert">{state.error.message}</span>}
      </div>
    </>
  );
}
