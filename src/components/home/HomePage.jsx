import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, Film } from 'lucide-react';
import { HomeShell } from './HomeShell';
import { HomeProfilePanel } from './HomeProfilePanel';
import { SuggestedProfilesPanel } from './SuggestedProfilesPanel';
import { DailyWingsRow } from './DailyWingsRow';
import { DailyWingModal } from './DailyWingModal';
import { ACTIVITY_CARDS, TODAYS_RESET } from './homeData';

/**
 * Chrysalis Home — a calm, social home screen (left nav, center feed, right
 * profile + suggestions), inspired by the general social-app pattern but branded
 * for wellbeing: Daily Wings instead of flex stories, a "Today's reset" prompt,
 * gentle activity cards, and a clear way into the full short-form feed (Flutter).
 *
 * The vertical video experience itself stays on /algorithm; this page links to it.
 */
export function HomePage() {
  const navigate = useNavigate();
  const [openWing, setOpenWing] = useState(null);

  return (
    <HomeShell active="home">
      <div className="home-grid">
        <section className="home-center" aria-label="Home">
          <DailyWingsRow onOpen={setOpenWing} />

          <article className="reset-card" aria-label={TODAYS_RESET.title}>
            <span className="reset-card__emoji" aria-hidden="true">{TODAYS_RESET.emoji}</span>
            <div className="reset-card__body">
              <h2 className="reset-card__title">{TODAYS_RESET.title}</h2>
              <p className="reset-card__copy">{TODAYS_RESET.prompt}</p>
            </div>
            <span className="reset-card__time">{TODAYS_RESET.minutes} min</span>
          </article>

          <div className="home-cards">
            {ACTIVITY_CARDS.map((card) => (
              <article key={card.id} className="acard" data-accent={card.accent}>
                <header className="acard__head">
                  <span className="cx-avatar cx-avatar--sm" aria-hidden="true">
                    <span className="wing__emoji">{card.emoji}</span>
                  </span>
                  <span className="acard__who">
                    <span className="acard__name">{card.firstName}</span>
                    <span className="acard__activity">{card.activity}</span>
                  </span>
                </header>
                <p className="acard__body">{card.body}</p>
              </article>
            ))}
          </div>

          <button type="button" className="open-flutter" onClick={() => navigate('/algorithm')}>
            <Film size={18} aria-hidden="true" />
            <span>Open Flutter — your short-form feed</span>
            <ArrowRight size={18} aria-hidden="true" />
          </button>
        </section>

        <aside className="home-rail" aria-label="Your profile and suggestions">
          <HomeProfilePanel />
          <SuggestedProfilesPanel />
        </aside>
      </div>

      <DailyWingModal wing={openWing} onClose={() => setOpenWing(null)} />
    </HomeShell>
  );
}
