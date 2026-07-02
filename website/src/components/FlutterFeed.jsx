import { BRAND } from '../brand.js';
import { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Play, Moon, Users, BarChart2, RefreshCw } from 'lucide-react';
import { FeedCard } from './FeedCard';

const API_URL = import.meta.env.VITE_API_URL ?? '';

const PRESETS = [
  { label: 'Entertain me',      val: 'entertainment' },
  { label: 'Inspire me',        val: 'inspiration'   },
  { label: 'Teach me something',val: 'learning'      },
];

const AGE_GROUPS = [
  { label: 'Anyone',     val: null    },
  { label: 'Teen 16–17', val: '16-17' },
  { label: 'Teen 13–15', val: '13-15' },
];

function WeightBar({ label, value, color }) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex justify-between">
        <span className="font-body text-xs text-foreground/60">{label}</span>
        <span className="font-body text-xs font-medium text-foreground/50">
          {(value * 100).toFixed(0)}%
        </span>
      </div>
      <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(147,142,151,0.2)' }}>
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${value * 100}%` }}
          transition={{ duration: 1, ease: 'easeOut' }}
          className="h-full rounded-full"
          style={{ background: color }}
        />
      </div>
    </div>
  );
}

function MetricCard({ label, subtitle, improved, baseline, suffix = '' }) {
  const better = parseFloat(improved) > parseFloat(baseline);
  return (
    <div className="liquid-glass rounded-xl p-4 flex flex-col gap-2">
      <span className="font-body text-xs text-foreground/45 font-medium uppercase tracking-wider">
        {label}
      </span>
      <div className="flex items-end gap-3">
        <span className="font-heading text-3xl iridescent-text">
          {improved}{suffix}
        </span>
        <div className="flex flex-col pb-1">
          <span className="font-body text-xs text-foreground/35">vs baseline</span>
          <span className="font-body text-xs text-foreground/45">{baseline}{suffix}</span>
        </div>
      </div>
      <span
        className="self-start rounded-full px-2 py-0.5 font-body text-xs"
        style={{
          background: better ? 'rgba(124,109,140,0.14)' : 'rgba(207,203,211,0.45)',
          color:      better ? '#7C6D8C'                : '#938E97',
        }}
      >
        {better ? '↑ improved' : '↓ reduced'}
      </span>
      {subtitle && (
        <span className="font-body text-xs text-foreground/35 leading-snug">{subtitle}</span>
      )}
    </div>
  );
}

export function FlutterFeed() {
  const [preset,    setPreset]    = useState('entertainment');
  const [nightMode, setNightMode] = useState(false);
  const [ageGroup,  setAgeGroup]  = useState(null);
  const [loading,   setLoading]   = useState(false);
  const [result,    setResult]    = useState(null);
  const [error,     setError]     = useState(null);

  const run = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch(`${API_URL}/api/run/local`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ preset, night_mode: nightMode, passive_streak: 0, age_group: ageGroup }),
      });
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      setResult(await res.json());
    } catch (e) {
      setError(e.message.includes('fetch') ? 'offline' : e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid lg:grid-cols-[340px_1fr] gap-8 items-start">

      {/* ── Controls ── */}
      <div className="liquid-glass-strong rounded-2xl p-6 flex flex-col gap-7">

        <p className="font-body text-sm text-foreground/50 leading-relaxed">
          Configure the algorithm and run it against a real dataset — see exactly what {BRAND} would recommend.
        </p>

        <div className="flex flex-col gap-3">
          <label className="font-body text-xs font-medium text-foreground/45 uppercase tracking-wider">
            What brings you here?
          </label>
          <div className="flex flex-col gap-2">
            {PRESETS.map(({ label, val }) => (
              <button
                key={val}
                onClick={() => setPreset(val)}
                className={`rounded-full px-4 py-2 font-body text-sm font-medium text-left transition-all duration-200 ${
                  preset === val
                    ? 'liquid-glass-strong text-foreground'
                    : 'text-foreground/50 hover:text-foreground hover:bg-secondary/35'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex flex-col gap-3">
          <label className="font-body text-xs font-medium text-foreground/45 uppercase tracking-wider flex items-center gap-1.5">
            <Users className="w-3 h-3" /> Who's watching?
          </label>
          <div className="flex flex-col gap-2">
            {AGE_GROUPS.map(({ label, val }) => (
              <button
                key={label}
                onClick={() => setAgeGroup(val)}
                className={`rounded-full px-4 py-2 font-body text-sm font-medium text-left transition-all duration-200 ${
                  ageGroup === val
                    ? 'liquid-glass-strong text-foreground'
                    : 'text-foreground/50 hover:text-foreground hover:bg-secondary/35'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <label className="font-body text-sm font-medium text-foreground/60 flex items-center gap-2">
              <Moon className="w-4 h-4" /> Late-night mode
            </label>
            <button
              onClick={() => setNightMode(!nightMode)}
              className={`relative w-10 h-5 rounded-full transition-all duration-300 ${
                nightMode ? 'bg-primary' : 'bg-foreground/15'
              }`}
            >
              <span
                className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-all duration-300 ${
                  nightMode ? 'left-5' : 'left-0.5'
                }`}
              />
            </button>
          </div>
          <p className="font-body text-xs text-foreground/35">Reduces high-stimulation content after 10pm.</p>
        </div>

        <button
          onClick={run}
          disabled={loading}
          className="liquid-glass-strong rounded-full py-3 font-body font-medium text-sm text-foreground flex items-center justify-center gap-2 hover:scale-105 transition-transform duration-200 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {loading
            ? <><div className="butterfly-spinner scale-75" /> Running…</>
            : <><Play className="w-4 h-4" /> Run the Algorithm</>}
        </button>
      </div>

      {/* ── Results ── */}
      <div className="flex flex-col gap-6 min-h-[400px]">
        <AnimatePresence mode="wait">

          {!result && !error && !loading && (
            <motion.div
              key="idle"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="flex-1 flex flex-col items-center justify-center gap-4 liquid-glass rounded-2xl p-12 text-center"
            >
              <div className="butterfly-spinner" />
              <p className="font-body font-light text-sm text-foreground/40">
                Configure and run the algorithm to see live results
              </p>
            </motion.div>
          )}

          {error && (
            <motion.div
              key="error"
              initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
              className="liquid-glass rounded-2xl p-8 flex flex-col gap-3"
            >
              {error === 'offline' ? (
                <>
                  <p className="font-body font-medium text-sm text-foreground/70">Backend not running</p>
                  <p className="font-body font-light text-sm text-foreground/50">Start the FastAPI server:</p>
                  <code className="rounded-lg px-4 py-2 font-mono text-sm text-foreground/70" style={{ background: 'rgba(147,142,151,0.14)' }}>
                    python api.py
                  </code>
                </>
              ) : (
                <p className="font-body text-sm text-foreground/60">{error}</p>
              )}
              <button onClick={run} className="self-start flex items-center gap-1.5 font-body text-sm text-foreground/50 hover:text-foreground transition-colors">
                <RefreshCw className="w-3.5 h-3.5" /> Try again
              </button>
            </motion.div>
          )}

          {result && (
            <motion.div
              key="results"
              initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
              className="flex flex-col gap-6"
            >
              {result.weights && (
                <div className="liquid-glass rounded-xl p-5 flex flex-col gap-4">
                  <p className="font-body text-xs font-medium text-foreground/45 uppercase tracking-wider flex items-center gap-1.5">
                    <BarChart2 className="w-3 h-3" /> Here's how {BRAND} scored your feed:
                  </p>
                  <WeightBar label="Relevance"   value={result.weights.e ?? 0} color="#7C6D8C" />
                  <WeightBar label="Diversity"   value={result.weights.d ?? 0} color="#AD9EB8" />
                  <WeightBar label="Prosocial"   value={result.weights.p ?? 0} color="#938E97" />
                  <WeightBar label="Risk shield" value={result.weights.r ?? 0} color="#2B2631" />
                </div>
              )}

              {result.improved_metrics && result.baseline_metrics && (
                <div className="grid grid-cols-3 gap-3">
                  <MetricCard
                    label="Prosocial ratio"
                    subtitle="Share of posts that build up rather than tear down"
                    improved={(result.improved_metrics.prosocial_ratio * 100).toFixed(0)}
                    baseline={(result.baseline_metrics.prosocial_ratio * 100).toFixed(0)}
                    suffix="%"
                  />
                  <MetricCard
                    label="Diversity@10"
                    subtitle="How many different topics in your first 10 posts"
                    improved={result.improved_metrics.diversity_at_10?.toFixed(1) ?? '—'}
                    baseline={result.baseline_metrics.diversity_at_10?.toFixed(1) ?? '—'}
                  />
                  <MetricCard
                    label="Max streak"
                    subtitle="Longest unbroken run of the same topic (lower = better)"
                    improved={result.improved_metrics.max_streak ?? '—'}
                    baseline={result.baseline_metrics.max_streak ?? '—'}
                  />
                </div>
              )}

              {result.improved_feed?.length > 0 && (
                <div className="flex flex-col gap-3">
                  <p className="font-body text-xs font-medium text-foreground/45 uppercase tracking-wider">
                    Your top recommendations:
                  </p>
                  <div className="scroll-x pb-2">
                    {result.improved_feed.slice(0, 10).map((item, i) => (
                      <FeedCard key={i} item={item} index={i} />
                    ))}
                  </div>
                </div>
              )}
            </motion.div>
          )}

        </AnimatePresence>
      </div>
    </div>
  );
}
