import { useRef } from 'react';

/**
 * Floating tab bar that sits over the Algorithm experience and switches mode.
 * Implements the WAI-ARIA tabs pattern: a tablist of role="tab" buttons with
 * roving focus and Left/Right/Home/End keyboard navigation.
 *
 * Props:
 *   modes      — array of { key, label, blurb }
 *   activeMode — currently selected mode key
 *   onChange(key) — called when a tab is activated
 */
export function ModeTabs({ modes, activeMode, onChange }) {
  const tabsRef = useRef([]);

  const onKeyDown = (e, index) => {
    let next = null;
    if (e.key === 'ArrowRight') next = (index + 1) % modes.length;
    else if (e.key === 'ArrowLeft') next = (index - 1 + modes.length) % modes.length;
    else if (e.key === 'Home') next = 0;
    else if (e.key === 'End') next = modes.length - 1;
    if (next === null) return;
    e.preventDefault();
    onChange(modes[next].key);
    tabsRef.current[next]?.focus();
  };

  return (
    <div className="reels-tabs" role="tablist" aria-label="Algorithm modes">
      {modes.map((mode, index) => {
        const isActive = mode.key === activeMode;
        return (
          <button
            key={mode.key}
            ref={(el) => (tabsRef.current[index] = el)}
            type="button"
            role="tab"
            id={`reels-tab-${mode.key}`}
            aria-selected={isActive}
            tabIndex={isActive ? 0 : -1}
            title={mode.blurb}
            className={`reels-tab${isActive ? ' is-active' : ''}`}
            onClick={() => onChange(mode.key)}
            onKeyDown={(e) => onKeyDown(e, index)}
          >
            {mode.label}
          </button>
        );
      })}
    </div>
  );
}
