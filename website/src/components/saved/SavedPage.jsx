import { useEffect, useState } from 'react';
import { Bookmark, Heart, Play, Sparkles, X } from 'lucide-react';
import { HomeShell } from '../home/HomeShell';
import { useSavedVideos } from '../reels/useSavedVideos';
import { useLikedVideos } from '../reels/useLikedVideos';
import { useReflections } from '../reels/useReflections';
import { buildYouTubeEmbedUrl } from '../reels/youtubeEmbed';
import '../../saved.css';

/**
 * Liked / Saved — a personal collection (not a public flex), with tabs for the
 * three things a card can capture: Liked, Saved, and Reflections. All three are
 * device-local (localStorage) snapshots taken at the moment you tapped — there is
 * no backend. Tapping a tile opens an in-app modal player; the corner button
 * removes the item from that collection.
 *
 * Route stays /saved (active key "saved") so existing links keep working.
 */
const TABS = [
  { key: 'liked', label: 'Liked', Icon: Heart },
  { key: 'saved', label: 'Saved', Icon: Bookmark },
  { key: 'reflections', label: 'Reflections', Icon: Sparkles },
];

export function SavedPage() {
  const { saved, removeSave } = useSavedVideos();
  const { liked, removeLike } = useLikedVideos();
  const { reflections, removeReflection } = useReflections();
  const [tab, setTab] = useState('liked');
  const [active, setActive] = useState(null);

  const counts = { liked: liked.length, saved: saved.length, reflections: reflections.length };

  return (
    <HomeShell active="saved">
      <div className="home-narrow saved-page">
        <header className="saved-head">
          <h1 className="saved-head__title">Your collection</h1>
          <p className="saved-head__sub">Liked, saved, and reflected — kept just for you, only on this device.</p>
        </header>

        <div className="lib-tabs" role="tablist" aria-label="Collection tabs">
          {TABS.map((t) => {
            const TabIcon = t.Icon;
            return (
              <button
                key={t.key}
                type="button"
                role="tab"
                aria-selected={tab === t.key}
                className={`lib-tab${tab === t.key ? ' is-active' : ''}`}
                onClick={() => setTab(t.key)}
              >
                <TabIcon size={16} aria-hidden="true" />
                <span>{t.label}</span>
                <span className="lib-tab__count">{counts[t.key]}</span>
              </button>
            );
          })}
        </div>

        {tab === 'liked' && (
          <CollectionGrid
            items={liked}
            emptyIcon={<Heart size={28} />}
            emptyTitle="No likes yet"
            emptyNote="Tap the heart on a video to keep your favourites here."
            onOpen={setActive}
            onRemove={removeLike}
            removeLabel="like"
          />
        )}

        {tab === 'saved' && (
          <CollectionGrid
            items={saved}
            emptyIcon={<Bookmark size={28} />}
            emptyTitle="Nothing saved yet"
            emptyNote="Tap the bookmark on any video in your feed to keep it here."
            onOpen={setActive}
            onRemove={removeSave}
            removeLabel="saved item"
          />
        )}

        {tab === 'reflections' && (
          <CollectionGrid
            items={reflections}
            emptyIcon={<Sparkles size={28} />}
            emptyTitle="No reflections yet"
            emptyNote="Use Reflect on a video to note how it left you feeling — Calmer, Curious, or Not for me."
            onOpen={setActive}
            onRemove={removeReflection}
            removeLabel="reflection"
            showReflection
          />
        )}
      </div>

      {active && <SavedVideoModal video={active} onClose={() => setActive(null)} />}
    </HomeShell>
  );
}

function CollectionGrid({ items, emptyIcon, emptyTitle, emptyNote, onOpen, onRemove, removeLabel, showReflection }) {
  if (items.length === 0) {
    return (
      <div className="saved-empty">
        <span className="saved-empty__icon" aria-hidden="true">{emptyIcon}</span>
        <p className="saved-empty__title">{emptyTitle}</p>
        <p className="saved-empty__note">{emptyNote}</p>
      </div>
    );
  }

  return (
    <ul className="saved-grid" aria-label="Collection items">
      {items.map((item) => (
        <li key={item.id} className="saved-tile">
          <button
            type="button"
            className="saved-tile__open"
            onClick={() => onOpen(item)}
            aria-label={`Play ${item.title}`}
          >
            <span className="saved-tile__thumb">
              {item.thumbnail ? (
                <img src={item.thumbnail} alt="" loading="lazy" />
              ) : (
                <span className="saved-tile__thumb-fallback" aria-hidden="true" />
              )}
              <span className="saved-tile__play" aria-hidden="true">
                <Play size={20} fill="currentColor" />
              </span>
              {showReflection && item.reflection && (
                <span className="saved-tile__reflection">{item.reflection}</span>
              )}
            </span>
            <span className="saved-tile__title">{item.title}</span>
            {item.source && <span className="saved-tile__source">{item.source}</span>}
          </button>
          <button
            type="button"
            className="saved-tile__remove"
            onClick={() => onRemove(item.id)}
            aria-label={`Remove ${item.title} from ${removeLabel}`}
          >
            <X size={16} aria-hidden="true" />
          </button>
        </li>
      ))}
    </ul>
  );
}

function SavedVideoModal({ video, onClose }) {
  useEffect(() => {
    const onKey = (event) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const origin = typeof window !== 'undefined' ? window.location.origin : undefined;
  const src = buildYouTubeEmbedUrl(video.embedUrl || video.youtubeId, {
    autoplay: true,
    muted: false,
    controls: true,
    origin,
  });

  return (
    <div
      className="saved-modal"
      role="dialog"
      aria-modal="true"
      aria-label={video.title}
      onClick={onClose}
    >
      <div className="saved-modal__panel" onClick={(event) => event.stopPropagation()}>
        <button
          type="button"
          className="saved-modal__close"
          onClick={onClose}
          aria-label="Close player"
        >
          <X size={18} aria-hidden="true" />
        </button>
        <div className="saved-modal__stage">
          {src ? (
            <iframe
              className="saved-modal__embed"
              src={src}
              title={video.title}
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
              allowFullScreen
              referrerPolicy="strict-origin-when-cross-origin"
            />
          ) : (
            <p className="saved-modal__missing">This video can’t be played here anymore.</p>
          )}
        </div>
        <p className="saved-modal__title">{video.title}</p>
        {video.source && <p className="saved-modal__source">{video.source}</p>}
      </div>
    </div>
  );
}
