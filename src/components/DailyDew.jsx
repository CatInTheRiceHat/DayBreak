import { useState, useEffect } from 'react';
import { motion as MOTION, AnimatePresence } from 'motion/react';
import { Sun, Moon, RefreshCw, Calendar, Sparkles } from 'lucide-react';
import { FeedCard } from './FeedCard';

const API_URL = import.meta.env.VITE_API_URL ?? '';

function StatPill({ label, value, accent }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="font-body text-xs text-foreground/40 uppercase tracking-wider">{label}</span>
      <span className="font-heading text-xl" style={{ color: accent ?? 'inherit' }}>
        {value}
      </span>
    </div>
  );
}

function DropCard({ drop, label, Icon, accentColor, scheduledTime }) {
  const DropIcon = Icon;

  if (!drop) {
    return (
      <MOTION.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="liquid-glass rounded-2xl p-8 flex flex-col items-center justify-center gap-4 text-center min-h-[280px]"
        style={{ border: '1px solid rgba(147,142,151,0.3)' }}
      >
        <div
          className="w-12 h-12 rounded-full flex items-center justify-center"
          style={{ background: `${accentColor}22` }}
        >
          <DropIcon className="w-5 h-5" style={{ color: `${accentColor}99` }} />
        </div>
        <div className="flex flex-col gap-1">
          <p className="font-body font-medium text-sm text-foreground/45">{label} not yet delivered</p>
          <p className="font-body font-light text-xs text-foreground/30">Scheduled for {scheduledTime}</p>
        </div>
      </MOTION.div>
    );
  }

  return (
    <MOTION.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="liquid-glass rounded-2xl p-6 flex flex-col gap-5"
      style={{ border: '1px solid rgba(147,142,151,0.3)' }}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div
            className="w-10 h-10 rounded-full flex items-center justify-center"
          style={{ background: `${accentColor}22` }}
          >
            <DropIcon className="w-5 h-5" style={{ color: accentColor }} />
          </div>
          <div>
            <p className="font-body font-semibold text-sm text-foreground/80">{label}</p>
            <p className="font-body text-xs text-foreground/40">{drop.scheduled_at}</p>
          </div>
        </div>
        <span
          className="rounded-full px-3 py-1 font-body text-xs font-medium"
          style={{ background: 'rgba(124,109,140,0.14)', color: '#7C6D8C' }}
        >
          ✓ delivered
        </span>
      </div>

      {/* Feed scroll */}
      {drop.feed?.length > 0 && (
        <div className="scroll-x pb-2">
          {drop.feed.slice(0, 12).map((item, i) => (
            <FeedCard key={i} item={item} index={i} />
          ))}
        </div>
      )}

      {/* Stats */}
      <div
        className="rounded-xl px-4 py-3 flex items-center gap-5"
        style={{ background: 'rgba(250,249,246,0.52)', border: '1px solid rgba(147,142,151,0.28)' }}
      >
        <StatPill label="Items" value={drop.item_count} accent={accentColor} />
        <div className="w-px h-8 bg-foreground/8" />
        <StatPill label="Mode" value={<span className="capitalize text-foreground/60 font-body text-sm font-medium">{drop.mode}</span>} />
      </div>
    </MOTION.div>
  );
}

export function DailyDew() {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);

  const fetchDrops = async () => {
    setLoading(true); setError(null);
    try {
      const res = await fetch(`${API_URL}/api/migration/today`);
      if (res.status === 404) { setData({ empty: true }); return; }
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      setData(await res.json());
    } catch (e) {
      setError(e.message.includes('fetch') ? 'offline' : e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchDrops(); }, []);

  const today = new Date().toLocaleDateString('en-US', {
    weekday: 'long', month: 'long', day: 'numeric',
  });

  return (
    <div className="flex flex-col gap-6">

      {/* Top bar */}
      <div className="flex items-center justify-between">
        <div
          className="flex items-center gap-2 rounded-full px-4 py-2"
          style={{ background: 'rgba(250,249,246,0.72)', border: '1px solid rgba(147,142,151,0.34)' }}
        >
          <Calendar className="w-3.5 h-3.5 text-foreground/45" />
          <span className="font-body text-sm text-foreground/60">{today}</span>
        </div>
        <button
          onClick={fetchDrops}
          disabled={loading}
          className="flex items-center gap-1.5 font-body text-sm text-foreground/40 hover:text-foreground/70 transition-colors disabled:opacity-40"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Explainer strip */}
      <div
        className="rounded-2xl px-5 py-4 flex items-start gap-4"
        style={{
          background: 'linear-gradient(135deg, rgba(124,109,140,0.08), rgba(173,158,184,0.14))',
          border: '1px solid rgba(147,142,151,0.24)',
        }}
      >
        <Sparkles className="w-4 h-4 mt-0.5 flex-shrink-0" style={{ color: '#7C6D8C' }} />
        <p className="font-body font-light text-sm text-foreground/55 leading-relaxed">
          Daily Dew replaces your personalized feed with two non-personalized daily drops — one in the
          morning, one in the evening — curated for diversity and positivity. Same content for everyone.
        </p>
      </div>

      <AnimatePresence mode="wait">

        {loading && !data && (
          <MOTION.div
            key="loading"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="flex flex-col items-center justify-center gap-4 liquid-glass rounded-2xl p-16"
          >
            <div className="butterfly-spinner" />
            <p className="font-body font-light text-sm text-foreground/40">Fetching today's drops…</p>
          </MOTION.div>
        )}

        {error && (
          <MOTION.div
            key="error"
            initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="liquid-glass rounded-2xl p-8 flex flex-col gap-3 items-center text-center"
          >
            <p className="font-body font-medium text-sm text-foreground/70">
              {error === 'offline' ? 'Backend not running' : 'Could not load drops'}
            </p>
            {error === 'offline' && (
              <>
                <p className="font-body font-light text-sm text-foreground/45">
                  Start the FastAPI server to enable drops:
                </p>
                <code
                  className="rounded-lg px-4 py-2 font-mono text-sm text-foreground/60"
                  style={{ background: 'rgba(147,142,151,0.14)' }}
                >
                  python api.py
                </code>
              </>
            )}
            <button
              onClick={fetchDrops}
              className="flex items-center gap-1.5 font-body text-sm text-foreground/50 hover:text-foreground transition-colors"
            >
              <RefreshCw className="w-3.5 h-3.5" /> Try again
            </button>
          </MOTION.div>
        )}

        {data?.empty && (
          <MOTION.div
            key="empty"
            initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="liquid-glass rounded-2xl p-12 flex flex-col items-center gap-6 text-center"
          >
            <MOTION.div
              animate={{ y: [0, -6, 0] }}
              transition={{ repeat: Infinity, duration: 3, ease: 'easeInOut' }}
              className="algorithm-blank-mark"
            />
            <div className="flex flex-col gap-2">
              <p className="font-heading text-xl text-foreground/50">No drops yet today</p>
              <p className="font-body font-light text-sm text-foreground/35 max-w-sm">
                The morning drop delivers at <strong className="text-foreground/55">07:00</strong> and
                the evening drop at <strong className="text-foreground/55">19:00</strong>.
                Start the scheduler to enable automatic drops.
              </p>
            </div>
            <code
              className="rounded-xl px-5 py-3 font-mono text-sm text-foreground/50"
              style={{ background: 'rgba(147,142,151,0.14)', border: '1px solid rgba(147,142,151,0.22)' }}
            >
              python api.py
            </code>
          </MOTION.div>
        )}

        {data && !data.empty && (
          <MOTION.div
            key="drops"
            initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="grid lg:grid-cols-2 gap-6"
          >
            <DropCard
              drop={data.morning}
              label="Morning Drop"
              Icon={Sun}
              accentColor="#AD9EB8"
              scheduledTime="07:00"
            />
            <DropCard
              drop={data.evening}
              label="Evening Drop"
              Icon={Moon}
              accentColor="#7C6D8C"
              scheduledTime="19:00"
            />
          </MOTION.div>
        )}

      </AnimatePresence>
    </div>
  );
}
