import { useState } from 'react';
import { motion as MOTION, AnimatePresence } from 'motion/react';
import { Clock, ArrowRight, CheckCircle2, RefreshCw, ChevronRight } from 'lucide-react';

const API_URL = import.meta.env.VITE_API_URL ?? '';
const GRADUATION_THRESHOLD = 45;
const DECAY_RATE           = 0.8;

function computeWeeklyCaps(startMinutes) {
  const caps = [];
  let n = 0;
  while (n <= 50) {
    const cap = Math.floor(startMinutes * Math.pow(DECAY_RATE, n));
    caps.push(cap);
    if (cap <= GRADUATION_THRESHOLD) break;
    n++;
  }
  return caps;
}

function DecayCurve({ startMinutes, currentWeek }) {
  const caps = computeWeeklyCaps(startMinutes);
  const W = 300, H = 80;

  const xOf = (i) => caps.length > 1 ? (i / (caps.length - 1)) * W : W / 2;
  const yOf = (cap) => H - (cap / caps[0]) * H * 0.9;

  const points = caps.map((c, i) => `${xOf(i).toFixed(1)},${yOf(c).toFixed(1)}`).join(' ');
  const areaPoints = `0,${H} ${points} ${xOf(caps.length - 1).toFixed(1)},${H}`;

  const thresholdY = yOf(GRADUATION_THRESHOLD);

  return (
    <svg
      width={W}
      height={H + 20}
      viewBox={`0 0 ${W + 24} ${H + 20}`}
      overflow="visible"
      style={{ display: 'block' }}
    >
      <defs>
        <linearGradient id="ccLine" x1="0" y1="0" x2={W} y2="0" gradientUnits="userSpaceOnUse">
          <stop offset="0%"   stopColor="#7C6D8C" />
          <stop offset="50%"  stopColor="#AD9EB8" />
          <stop offset="100%" stopColor="#938E97" />
        </linearGradient>
        <linearGradient id="ccFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stopColor="#7C6D8C" stopOpacity="0.22" />
          <stop offset="100%" stopColor="#7C6D8C" stopOpacity="0" />
        </linearGradient>
      </defs>

      {/* Threshold line */}
      <line
        x1={0} y1={thresholdY} x2={W} y2={thresholdY}
        stroke="rgba(124,109,140,0.48)" strokeWidth="1" strokeDasharray="4 3"
      />
      <text
        x={W + 5} y={thresholdY + 4}
        fill="rgba(124,109,140,0.58)" fontSize="8"
        fontFamily="system-ui, -apple-system, sans-serif"
      >
        45m
      </text>

      {/* Area */}
      <polygon points={areaPoints} fill="url(#ccFill)" />

      {/* Line */}
      <polyline
        points={points}
        fill="none"
        stroke="url(#ccLine)"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Week dots + labels */}
      {caps.map((cap, i) => {
        const cx = xOf(i);
        const cy = yOf(cap);
        const isCurrent = i === currentWeek;
        const isPast    = i < currentWeek;
        return (
          <g key={i}>
            <circle
              cx={cx} cy={cy}
              r={isCurrent ? 5 : 3}
              fill={isCurrent ? '#7C6D8C' : isPast ? '#AD9EB8' : 'rgba(207,203,211,0.72)'}
              stroke={isCurrent ? 'white' : 'none'}
              strokeWidth="1.5"
            />
            <text
              x={cx} y={H + 14}
              textAnchor="middle"
              fill={isCurrent ? '#7C6D8C' : 'rgba(147,142,151,0.58)'}
              fontSize="8"
              fontWeight={isCurrent ? 'bold' : 'normal'}
              fontFamily="system-ui, -apple-system, sans-serif"
            >
              W{i}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export function Metamorphosis() {
  const [userId,        setUserId]        = useState('');
  const [startMinutes,  setStartMinutes]  = useState(180);
  const [profile,       setProfile]       = useState(null);
  const [loading,       setLoading]       = useState(false);
  const [advLoading,    setAdvLoading]    = useState(false);
  const [error,         setError]         = useState(null);

  const mergeProfile = (prev, data) => {
    const next = { ...(prev ?? {}), ...data };
    next.graduated     = next.graduated     ?? false;
    next.should_graduate = next.graduated || (next.daily_cap != null && next.daily_cap <= GRADUATION_THRESHOLD);
    return next;
  };

  const enroll = async () => {
    if (!userId.trim()) return;
    setLoading(true); setError(null);
    try {
      const res = await fetch(`${API_URL}/api/cocoon/enroll`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId.trim(), current_daily_minutes: startMinutes }),
      });
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      setProfile(mergeProfile(null, await res.json()));
    } catch (e) {
      setError(e.message.includes('fetch') ? 'offline' : e.message);
    } finally {
      setLoading(false);
    }
  };

  const checkStatus = async () => {
    if (!profile) return;
    setLoading(true); setError(null);
    try {
      const res = await fetch(`${API_URL}/api/cocoon/status/${encodeURIComponent(profile.user_id)}`);
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const data = await res.json();
      setProfile(prev => mergeProfile(prev, data));
    } catch (e) {
      setError(e.message.includes('fetch') ? 'offline' : e.message);
    } finally {
      setLoading(false);
    }
  };

  const advanceWeek = async () => {
    if (!profile) return;
    setAdvLoading(true); setError(null);
    try {
      const res = await fetch(`${API_URL}/api/cocoon/advance/${encodeURIComponent(profile.user_id)}`, {
        method: 'POST',
      });
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const advData = await res.json();
      setProfile(prev => mergeProfile(prev, advData));
    } catch (e) {
      setError(e.message.includes('fetch') ? 'offline' : e.message);
    } finally {
      setAdvLoading(false);
    }
  };

  const weeklyCaps     = profile ? computeWeeklyCaps(profile.start_minutes) : [];
  const graduationWeek = weeklyCaps.length - 1;
  const taperProgress  = profile
    ? Math.max(0, Math.min(100,
        ((profile.start_minutes - (profile.daily_cap ?? profile.start_minutes))
          / Math.max(1, profile.start_minutes - GRADUATION_THRESHOLD)) * 100))
    : 0;

  return (
    <div className="grid lg:grid-cols-[340px_1fr] gap-8 items-start">

      {/* ── Controls ── */}
      <div className="liquid-glass-strong rounded-2xl p-6 flex flex-col gap-6">

        <div className="flex flex-col gap-2">
          <label className="font-body text-xs font-medium text-foreground/45 uppercase tracking-wider">
            User ID
          </label>
          <input
            type="text"
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !profile && enroll()}
            placeholder="e.g. elaine_2026"
            disabled={!!profile}
            className="rounded-full px-4 py-2.5 font-body text-sm text-foreground placeholder:text-foreground/30 outline-none transition-all duration-200 disabled:opacity-50"
            style={{ background: 'rgba(250,249,246,0.78)', border: '1px solid rgba(147,142,151,0.34)' }}
          />
        </div>

        <div className="flex flex-col gap-3">
          <div className="flex justify-between items-center">
            <label className="font-body text-xs font-medium text-foreground/45 uppercase tracking-wider flex items-center gap-1.5">
              <Clock className="w-3 h-3" /> Daily screen time
            </label>
            <span className="font-body text-sm font-medium text-foreground/70">
              {startMinutes} min
            </span>
          </div>
          <input
            type="range"
            min={60} max={360} step={10}
            value={startMinutes}
            onChange={(e) => setStartMinutes(Number(e.target.value))}
            disabled={!!profile}
            className="w-full disabled:opacity-50"
            style={{ accentColor: '#7C6D8C' }}
          />
          <div className="flex justify-between font-body text-xs text-foreground/30">
            <span>60 min</span><span>360 min</span>
          </div>
        </div>

        {!profile ? (
          <button
            onClick={enroll}
            disabled={loading || !userId.trim()}
            className="liquid-glass-strong rounded-full py-3 font-body font-medium text-sm text-foreground flex items-center justify-center gap-2 hover:scale-105 transition-transform duration-200 disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {loading
              ? <><div className="butterfly-spinner scale-75" /> Enrolling…</>
              : <><ArrowRight className="w-4 h-4" /> Start Metamorphosis</>}
          </button>
        ) : (
          <div className="flex flex-col gap-2">
            <button
              onClick={checkStatus}
              disabled={loading}
              className="liquid-glass-strong rounded-full py-2.5 font-body font-medium text-sm text-foreground flex items-center justify-center gap-2 hover:scale-105 transition-transform duration-200 disabled:opacity-60"
            >
              {loading
                ? <div className="butterfly-spinner scale-75" />
                : <RefreshCw className="w-3.5 h-3.5" />}
              Refresh Status
            </button>

            <button
              onClick={advanceWeek}
              disabled={advLoading || profile.should_graduate || profile.graduated}
              className="rounded-full py-2.5 font-body font-medium text-sm text-foreground/60 flex items-center justify-center gap-2 hover:text-foreground transition-all duration-200 disabled:opacity-35 disabled:cursor-not-allowed"
              style={{ border: '1px solid rgba(147,142,151,0.3)' }}
            >
              {advLoading
                ? <div className="butterfly-spinner scale-75" />
                : <ChevronRight className="w-3.5 h-3.5" />}
              Advance Week
            </button>

            <button
              onClick={() => { setProfile(null); setUserId(''); setError(null); }}
              className="text-center font-body text-xs text-foreground/35 hover:text-foreground/60 transition-colors pt-1"
            >
              ← New user
            </button>
          </div>
        )}

        {error && (
          <p className="font-body text-xs text-center" style={{ color: '#7C6D8C' }}>
            {error === 'offline' ? 'Backend offline — run python api.py' : error}
          </p>
        )}
      </div>

      {/* ── Results ── */}
      <AnimatePresence mode="wait">

        {!profile && (
          <MOTION.div
            key="idle"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="liquid-glass rounded-2xl p-10 flex flex-col items-center gap-8 text-center min-h-[420px] justify-center"
          >
            <div className="flex flex-col items-center gap-4">
              <MOTION.div
                animate={{ scale: [1, 1.05, 1] }}
                transition={{ repeat: Infinity, duration: 3, ease: 'easeInOut' }}
                className="algorithm-blank-mark"
              />
              <div className="flex flex-col gap-1.5">
                <p className="font-heading text-xl text-foreground/55">Enter your details to begin</p>
                <p className="font-body font-light text-sm text-foreground/35 max-w-xs">
                  Set your current daily screen time, choose a user ID, and enroll to start tapering.
                </p>
              </div>
            </div>

            <div
              className="glass-card rounded-2xl px-6 py-5 flex flex-col gap-3 w-full max-w-xs"
              style={{ border: '1px solid rgba(147,142,151,0.28)' }}
            >
              <p className="font-body text-xs text-foreground/40 uppercase tracking-wider">Decay formula</p>
              <p className="font-heading text-2xl text-foreground/70">
                T(n) = T(0) × 0.8<sup className="text-sm">n</sup>
              </p>
              <p className="font-body text-xs text-foreground/35 leading-relaxed">
                Your cap reduces by 20% each week until it reaches 45 min/day,
                at which point you graduate to Daily Dew.
              </p>
              <div className="h-px w-full" style={{ background: 'linear-gradient(90deg, #7C6D8C, #AD9EB8, transparent)', opacity: 0.35 }} />
              <div className="flex justify-between">
                {[180, 144, 115, 92, '…', '≤45'].map((v, i) => (
                  <div key={i} className="flex flex-col items-center gap-1">
                    <span className="font-heading text-xs iridescent-text">{v}</span>
                    <span className="font-body text-xs text-foreground/25">W{i}</span>
                  </div>
                ))}
              </div>
            </div>
          </MOTION.div>
        )}

        {profile && (
          <MOTION.div
            key="profile"
            initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="flex flex-col gap-5"
          >
            {/* Graduation banner */}
            <AnimatePresence>
              {profile.should_graduate && (
                <MOTION.div
                  initial={{ opacity: 0, scale: 0.96, y: -8 }}
                  animate={{ opacity: 1, scale: 1, y: 0 }}
                  className="rounded-2xl p-5 flex items-center gap-4"
                  style={{
                    background: 'linear-gradient(135deg, rgba(124,109,140,0.12), rgba(173,158,184,0.16))',
                    border: '1px solid rgba(124,109,140,0.28)',
                  }}
                >
                  <MOTION.span
                    animate={{ rotate: [0, 10, -10, 0] }}
                    transition={{ repeat: Infinity, duration: 2.5 }}
                    className="text-3xl"
                  >
                    <span className="algorithm-blank-mark algorithm-blank-mark--small" />
                  </MOTION.span>
                  <div>
                    <p className="font-body font-semibold text-sm text-foreground/80">
                      Ready for Daily Dew
                    </p>
                    <p className="font-body font-light text-xs text-foreground/50">
                      Daily cap has reached ≤ 45 min — you've completed Metamorphosis.
                    </p>
                  </div>
                  <CheckCircle2 className="w-5 h-5 ml-auto flex-shrink-0" style={{ color: '#7C6D8C' }} />
                </MOTION.div>
              )}
            </AnimatePresence>

            {/* Week + cap header */}
            <div className="liquid-glass rounded-2xl p-6 flex flex-col gap-5">
              <div className="flex items-start justify-between">
                <div className="flex flex-col gap-0.5">
                  <span className="font-body text-xs font-medium text-foreground/40 uppercase tracking-wider">
                    Current week
                  </span>
                  <span className="font-heading text-4xl iridescent-text">
                    Week {profile.current_week}
                  </span>
                </div>
                <div className="flex flex-col items-end gap-0.5">
                  <span className="font-body text-xs font-medium text-foreground/40 uppercase tracking-wider">
                    Daily cap
                  </span>
                  <div className="flex items-end gap-1.5">
                    <span className="font-heading text-4xl iridescent-text">
                      {profile.daily_cap ?? '…'}
                    </span>
                    <span className="font-body text-base text-foreground/30 pb-1">min</span>
                  </div>
                </div>
              </div>

              {/* Taper progress bar */}
              <div className="flex flex-col gap-2">
                <div className="flex justify-between font-body text-xs text-foreground/40">
                  <span>{profile.start_minutes} min start</span>
                  <span>45 min goal</span>
                </div>
                <div className="h-2 rounded-full overflow-hidden" style={{ background: 'rgba(147,142,151,0.2)' }}>
                  <MOTION.div
                    initial={{ width: 0 }}
                    animate={{ width: `${taperProgress}%` }}
                    transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1] }}
                    className="h-full rounded-full"
                    style={{ background: 'linear-gradient(90deg, #7C6D8C, #AD9EB8)' }}
                  />
                </div>
                <p className="font-body text-xs text-foreground/30 text-right">
                  {taperProgress.toFixed(0)}% complete
                </p>
              </div>

              {/* Decay sparkline */}
              <div className="flex flex-col gap-2">
                <span className="font-body text-xs font-medium text-foreground/40 uppercase tracking-wider">
                  Taper schedule
                </span>
                <div style={{ overflow: 'visible' }}>
                  <DecayCurve startMinutes={profile.start_minutes} currentWeek={profile.current_week} />
                </div>
              </div>
            </div>

            {/* Stats row */}
            <div className="grid grid-cols-3 gap-3">
              {[
                { label: 'Started',          val: `${profile.start_minutes}m` },
                { label: 'Weeks elapsed',    val: profile.current_week },
                { label: 'Est. graduation',  val: `Wk ${graduationWeek}` },
              ].map(({ label, val }) => (
                <div key={label} className="liquid-glass rounded-xl p-4 flex flex-col gap-1">
                  <span className="font-body text-xs text-foreground/40 uppercase tracking-wider">{label}</span>
                  <span className="font-heading text-2xl iridescent-text">{val}</span>
                </div>
              ))}
            </div>

            {/* Weekly caps table */}
            <div className="liquid-glass rounded-xl p-5 flex flex-col gap-3">
              <p className="font-body text-xs font-medium text-foreground/40 uppercase tracking-wider">
                Full taper schedule
              </p>
              <div className="grid grid-cols-4 gap-2">
                {weeklyCaps.map((cap, i) => (
                  <div
                    key={i}
                    className="rounded-xl p-3 flex flex-col gap-0.5 transition-all duration-200"
                    style={{
                      background: i === profile.current_week
                        ? 'linear-gradient(135deg, rgba(124,109,140,0.16), rgba(173,158,184,0.18))'
                        : i < profile.current_week
                          ? 'rgba(124,109,140,0.08)'
                          : 'rgba(147,142,151,0.12)',
                      border: i === profile.current_week
                        ? '1px solid rgba(124,109,140,0.3)'
                        : '1px solid transparent',
                    }}
                  >
                    <span className="font-body text-xs text-foreground/35">Wk {i}</span>
                    <span
                      className="font-heading text-sm"
                      style={{ color: i === profile.current_week ? '#7C6D8C' : i < profile.current_week ? 'rgba(124,109,140,0.6)' : 'rgba(43,38,49,0.44)' }}
                    >
                      {cap}m
                    </span>
                    {i === weeklyCaps.length - 1 && (
                      <span className="algorithm-blank-mark algorithm-blank-mark--tiny" />
                    )}
                  </div>
                ))}
              </div>
            </div>
          </MOTION.div>
        )}

      </AnimatePresence>
    </div>
  );
}
