import { BRAND } from '../../brand.js';
import { Lock } from 'lucide-react';
import { HomeShell } from './HomeShell';
import { INBOX_PREVIEWS } from './homeData';

/**
 * Inbox — a polished placeholder.
 *
 * Real-time messaging isn't built yet, and Chrysalis is teen-centered, so this is
 * deliberately a calm "coming soon" with demo preview cards only. The preview cards
 * are clearly labelled demo and don't open a real thread. When messaging ships it
 * will be friends-only (see messaging.js) — surfaced here as reassurance, not a
 * locked-out feeling.
 */
export function InboxPage() {
  return (
    <HomeShell active="inbox">
      <div className="home-narrow">
        <h1 className="page-title">Inbox</h1>

        <section className="inbox-empty" aria-label="Messages coming soon">
          <span className="inbox-empty__mark" aria-hidden="true"><img src="/images/logo.png" alt="" /></span>
          <h2 className="inbox-empty__title">Messages are coming soon.</h2>
          <p className="inbox-empty__copy">
            {BRAND} messages are designed for safer, more intentional connection.
          </p>
          <span className="inbox-empty__safe">
            <Lock size={13} aria-hidden="true" /> Friends-only, when it arrives
          </span>
        </section>

        <section className="inbox-preview" aria-label="Demo previews">
          <h2 className="section-title">Preview <span className="suggested__hint">demo</span></h2>
          <ul className="result-list">
            {INBOX_PREVIEWS.map((msg) => (
              <li key={msg.id}>
                <div className="result-row is-static" aria-disabled="true">
                  <span className="cx-avatar cx-avatar--sm" aria-hidden="true">
                    <span className="wing__emoji">{msg.emoji}</span>
                  </span>
                  <span className="result-meta">
                    <span className="result-name">{msg.firstName}</span>
                    <span className="result-sub">{msg.preview}</span>
                  </span>
                  <span className="result-when">{msg.when}</span>
                </div>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </HomeShell>
  );
}
