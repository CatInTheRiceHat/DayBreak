import { BRAND } from '../../brand.js';
import { useEffect, useMemo, useRef, useState } from 'react';
import { motion as MOTION } from 'motion/react';
import { Check, Leaf, Pause, Play, RotateCcw } from 'lucide-react';
import { BREAK_ACTIVITIES, MINUTE_MS, formatCountdown } from './sessionBreaks';

/**
 * Calm, supportive screen-time break overlay. Shown when a progressive break is
 * due. Pauses the feed and invites a real-world reset — never shaming, never a
 * hard lockout. The user picks an activity, optionally reflects / runs a gentle
 * countdown, then returns refreshed.
 */
export function BreakScreen({ tier, elapsedMin, onComplete, onOpenChallenges }) {
  const breakMin = tier?.breakMin ?? 10;
  const [activity, setActivity] = useState(null);
  const [reflection, setReflection] = useState('');
  const [steppedAway, setSteppedAway] = useState(false);

  // Optional, opt-in countdown for the suggested away-time.
  const [remainingMs, setRemainingMs] = useState(breakMin * MINUTE_MS);
  const [timerRunning, setTimerRunning] = useState(false);
  const tickRef = useRef(null);

  useEffect(() => {
    if (!timerRunning) return undefined;
    tickRef.current = Date.now();
    const id = window.setInterval(() => {
      const now = Date.now();
      const delta = now - (tickRef.current ?? now);
      tickRef.current = now;
      setRemainingMs((value) => {
        const next = Math.max(0, value - delta);
        if (next === 0) setTimerRunning(false);
        return next;
      });
    }, 250);
    return () => window.clearInterval(id);
  }, [timerRunning]);

  const timerDone = remainingMs === 0;
  const roundedElapsed = Math.round(elapsedMin || 0);

  const heading = useMemo(() => {
    if (timerDone) return 'Welcome back 🌿';
    return 'Time for a little reset';
  }, [timerDone]);

  const handleComplete = () => {
    onComplete?.({
      activity: activity || null,
      reflection: reflection.trim() || null,
      steppedAway,
      usedTimer: timerRunning || timerDone,
    });
  };

  return (
    <MOTION.div
      className="break-screen"
      role="dialog"
      aria-modal="true"
      aria-label="Take a screen-time break"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.3 }}
    >
      <div className="break-screen__scrim" aria-hidden="true" />
      <MOTION.div
        className="break-screen__panel"
        initial={{ y: 24, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        exit={{ y: 24, opacity: 0 }}
        transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
      >
        <span className="break-screen__eyebrow">
          <Leaf size={14} aria-hidden="true" />
          {BRAND} reset
        </span>
        <h2 className="break-screen__title">{heading}</h2>
        <p className="break-screen__copy">
          You&apos;ve been scrolling for about {roundedElapsed} minutes. Step away for
          {' '}~{breakMin} minutes, then come back refreshed. Pick something real to do:
        </p>

        <div className="break-screen__activities" role="group" aria-label="Choose a reset activity">
          {BREAK_ACTIVITIES.map((option) => {
            const selected = activity === option.id;
            return (
              <button
                key={option.id}
                type="button"
                className={`break-activity${selected ? ' is-selected' : ''}`}
                aria-pressed={selected}
                onClick={() => setActivity(option.id)}
                title={option.blurb}
              >
                <span className="break-activity__emoji" aria-hidden="true">{option.emoji}</span>
                <span className="break-activity__label">{option.label}</span>
              </button>
            );
          })}
        </div>

        <div className="break-screen__timer">
          <div className="break-screen__timer-readout" aria-live="polite">
            {formatCountdown(remainingMs)}
          </div>
          <div className="break-screen__timer-controls">
            <button
              type="button"
              className="break-ghost-btn"
              onClick={() => setTimerRunning((running) => !running)}
              disabled={timerDone}
            >
              {timerRunning ? <Pause size={15} aria-hidden="true" /> : <Play size={15} aria-hidden="true" />}
              {timerRunning ? 'Pause timer' : 'Start timer'}
            </button>
            <button
              type="button"
              className="break-ghost-btn"
              onClick={() => { setRemainingMs(breakMin * MINUTE_MS); setTimerRunning(false); }}
            >
              <RotateCcw size={15} aria-hidden="true" />
              Reset
            </button>
            <span className="break-screen__timer-note">Optional — only if it helps.</span>
          </div>
        </div>

        <label className="break-screen__reflection">
          <span>How are you feeling? <em>(optional)</em></span>
          <textarea
            value={reflection}
            onChange={(event) => setReflection(event.target.value)}
            placeholder="A word or two is plenty…"
            rows={2}
            maxLength={280}
          />
        </label>

        <label className="break-screen__checkbox">
          <input
            type="checkbox"
            checked={steppedAway}
            onChange={(event) => setSteppedAway(event.target.checked)}
          />
          <span>I stepped away from the screen</span>
        </label>

        <button
          type="button"
          className="break-screen__done"
          onClick={handleComplete}
          disabled={!activity}
        >
          <Check size={16} aria-hidden="true" />
          {activity ? "I'm refreshed — back to my feed" : 'Pick an activity to continue'}
        </button>
        {onOpenChallenges && (
          <button type="button" className="break-screen__challenges-link" onClick={onOpenChallenges}>
            Want to make it count? Open IRL Challenges →
          </button>
        )}
        <p className="break-screen__footnote">
          No rush. Your feed will be here when you&apos;re ready.
        </p>
      </MOTION.div>
    </MOTION.div>
  );
}
