import { BRAND } from '../../brand.js';
import { useState } from 'react';
import { motion as MOTION } from 'motion/react';
import { ArrowRight } from 'lucide-react';
import { MODES, DEFAULT_MODE } from './reelsData';

/**
 * First-run start screen for the Algorithm experience. The user chooses one
 * guided mode, then stays in that mode until they return here to change it.
 *
 * Props:
 *   initialMode — optional current mode to preselect when returning here.
 *   onStart(mode) — called with the chosen mode key when the user begins.
 */
export function OnboardingStartScreen({ initialMode = null, onStart }) {
  const [selectedMode, setSelectedMode] = useState(initialMode);
  const selected = MODES.find((mode) => mode.key === selectedMode);

  return (
    <MOTION.div
      className="reels-onboard"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="reels-onboard__head">
        <h1 className="reels-onboard__title">Choose your Chrysalis algorithm.</h1>
        <p className="reels-onboard__subtitle">
          Pick the mode you want the algorithm to guide you through today.
        </p>
      </div>

      <div className="mode-grid" role="group" aria-label={`Choose your ${BRAND} algorithm mode`}>
        {MODES.map((mode) => {
          const isSelected = mode.key === selectedMode;
          return (
            <button
              key={mode.key}
              type="button"
              className={`mode-card${isSelected ? ' is-selected' : ''}`}
              aria-pressed={isSelected}
              onClick={() => setSelectedMode(mode.key)}
            >
              <span className="mode-card__logo" aria-hidden="true">
                <img src={mode.logo} alt="" />
              </span>
              <span className="mode-card__title">{mode.label}</span>
              <span className="mode-card__desc">{mode.description}</span>
            </button>
          );
        })}
      </div>

      <div className="reels-onboard__actions">
        <button
          type="button"
          className="onboard-cta"
          disabled={!selected}
          aria-disabled={!selected}
          onClick={() => selected && onStart(selected.key)}
        >
          Start My Algorithm
          <ArrowRight size={17} aria-hidden="true" />
        </button>
        <button
          type="button"
          className="onboard-skip"
          onClick={() => onStart(DEFAULT_MODE)}
        >
          Skip for now
        </button>
      </div>

      <p className="reels-onboard__privacy">
        Your demo feed is set to English. No location access required — {BRAND} keeps personalization simple and privacy-friendly.
      </p>
    </MOTION.div>
  );
}
