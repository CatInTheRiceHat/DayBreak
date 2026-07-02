import { ShieldCheck } from 'lucide-react';
import { SAFETY_NOTES, SAFETY_COPY } from './communityData';

/**
 * Footer card explaining the Community safety model: avatar-first profiles,
 * goal-based matching, no follower/popularity counts, limited discovery, guided
 * messaging, and Dewdrops that reward healthy actions over engagement.
 */
export function SafetyNote() {
  return (
    <section className="cmty-section cmty-safety" aria-label="How Community keeps connection safe">
      <header className="cmty-safety__head">
        <ShieldCheck size={20} aria-hidden="true" />
        <h2 className="cmty-section__title">Built to be lower-pressure</h2>
      </header>
      <p className="cmty-safety__copy">{SAFETY_COPY}</p>
      <ul className="cmty-tags cmty-safety__tags">
        {SAFETY_NOTES.map((note) => (
          <li key={note} className="cmty-tag cmty-tag--shared">{note}</li>
        ))}
      </ul>
    </section>
  );
}
