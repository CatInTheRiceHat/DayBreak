import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion as MOTION } from 'motion/react';
import { ArrowLeft, ArrowRight, Loader2 } from 'lucide-react';
import { useAuth } from '../../lib/authContext';
import { CxShell } from '../profile/CxShell';
import { DiagnosticResult } from './DiagnosticResult';
import { QUESTIONS, SCALE, scoreDiagnostic } from './diagnosticData';

// Keys shared with the feed so the diagnostic can set the recommended mode and
// skip the redundant "Choose your intention" onboarding.
const MODE_KEY = 'chrysalis-algorithm-mode';
const ONBOARDED_KEY = 'chrysalis-algorithm-onboarded';
const DONE_KEY = 'chrysalis-diagnostic-done';
// Answers captured before login; FirstRunGate persists them once the user signs in.
const PENDING_KEY = 'chrysalis-diagnostic-pending';

/**
 * Social-media diagnostic. Runs before login in the first-run flow: five quick
 * questions, then a personalized "here's what we unlocked for you" result. The
 * answers are held locally and saved to Supabase the moment the user signs in.
 */
export function DiagnosticPage() {
  const navigate = useNavigate();
  const { loading, user } = useAuth();

  const [phase, setPhase] = useState('checking'); // checking | quiz | result
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState({});
  const [result, setResult] = useState(null);

  // Gate: someone who already finished doesn't retake it.
  useEffect(() => {
    if (loading || typeof window === 'undefined') return;
    if (window.localStorage.getItem(DONE_KEY) === '1') {
      navigate(user ? '/' : '/login', { replace: true });
      return;
    }
    setPhase('quiz');
  }, [loading, user, navigate]);

  const finish = (finalAnswers) => {
    const scored = scoreDiagnostic(finalAnswers);
    setResult(scored);
    setPhase('result');
    // Hold the answers + result locally; FirstRunGate saves them after sign-in.
    window.localStorage.setItem(PENDING_KEY, JSON.stringify({
      answers: finalAnswers,
      scores: scored.scores,
      unlockedFeatures: scored.unlockedFeatures,
      recommendedMode: scored.recommendedMode,
    }));
    // Pre-set the feed so it opens straight into the recommended mode later.
    window.localStorage.setItem(MODE_KEY, scored.recommendedMode);
    window.localStorage.setItem(ONBOARDED_KEY, '1');
    window.localStorage.setItem(DONE_KEY, '1');
  };

  const answerScale = (value) => {
    const q = QUESTIONS[step];
    const next = { ...answers, [q.id]: value };
    setAnswers(next);
    if (step < QUESTIONS.length - 1) setStep(step + 1);
    else finish(next);
  };

  const toggleGoal = (value) => {
    const q = QUESTIONS[step];
    const current = answers[q.id] || [];
    const next = current.includes(value)
      ? current.filter((v) => v !== value)
      : [...current, value];
    setAnswers({ ...answers, [q.id]: next });
  };

  // Login is the last step: signed-in users go straight to the feed (FirstRunGate
  // persists the pending answers there); everyone else signs in first.
  const start = () => navigate(user ? '/' : '/login');

  if (phase === 'checking') {
    return (
      <CxShell center>
        <div className="cx-card cx-card--auth" style={{ alignItems: 'center' }}>
          <Loader2 size={22} className="cx-spin" aria-hidden="true" />
          <p className="cx-card__lede">Getting things ready…</p>
        </div>
      </CxShell>
    );
  }

  if (phase === 'result' && result) {
    return (
      <CxShell center>
        <DiagnosticResult result={result} ctaLabel={user ? 'Start My Algorithm' : 'Sign in to save & start'} onStart={start} />
      </CxShell>
    );
  }

  // quiz
  const q = QUESTIONS[step];
  const isMulti = q.type === 'multi';
  const selectedGoals = answers[q.id] || [];
  const progress = Math.round(((step) / QUESTIONS.length) * 100);

  return (
    <CxShell center>
      <div className="cx-card cx-card--auth diag-quiz">
        <div className="diag-progress" aria-hidden="true">
          <span className="diag-progress__bar" style={{ width: `${progress}%` }} />
        </div>
        <p className="diag-quiz__count">Question {step + 1} of {QUESTIONS.length}</p>

        <MOTION.div
          key={q.id}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
        >
          <h1 className="cx-card__title diag-quiz__prompt">{q.prompt}</h1>
          {q.hint && <p className="cx-card__lede">{q.hint}</p>}

          {isMulti ? (
            <>
              <div className="diag-options">
                {q.options.map((opt) => {
                  const on = selectedGoals.includes(opt.value);
                  return (
                    <button
                      key={opt.value}
                      type="button"
                      className={`diag-option${on ? ' is-selected' : ''}`}
                      aria-pressed={on}
                      onClick={() => toggleGoal(opt.value)}
                    >
                      {opt.label}
                    </button>
                  );
                })}
              </div>
              <button type="button" className="cx-btn cx-btn--primary" onClick={() => finish({ ...answers, [q.id]: selectedGoals })}>
                See my setup
                <ArrowRight size={16} aria-hidden="true" />
              </button>
            </>
          ) : (
            <div className="diag-options">
              {SCALE.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  className={`diag-option${answers[q.id] === opt.value ? ' is-selected' : ''}`}
                  onClick={() => answerScale(opt.value)}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          )}
        </MOTION.div>

        {step > 0 && (
          <button type="button" className="diag-back" onClick={() => setStep(step - 1)}>
            <ArrowLeft size={15} aria-hidden="true" /> Back
          </button>
        )}
      </div>
    </CxShell>
  );
}
