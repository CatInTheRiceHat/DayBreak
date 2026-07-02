import { BRAND } from '../../brand.js';
import { useEffect, useRef, useState } from 'react';
import { Ban, Flag, MessageCircle, Send, ShieldCheck, X } from 'lucide-react';
import { SEED_COMMENTS } from './commentsData';
import {
  SAFETY_BLOCK,
  SAFETY_CAUTION,
  SAFETY_OK,
  analyzeComment,
} from './commentSafety';
import { canMessage, FRIENDS_ONLY_MESSAGE } from './messaging';

/**
 * Comments sheet with safer-by-default behavior:
 *  - normal comments post immediately (with an occasional positive nudge)
 *  - harsh comments get a gentle rewrite prompt + a short cooldown before "post anyway"
 *  - targeted harm is asked to be rephrased (no shame, no public callout)
 *  - per-comment block / report controls
 *  - replies/DMs are friends-only
 */
export function CommentsPanel({ onClose, onStatus }) {
  const [comments, setComments] = useState(SEED_COMMENTS);
  const [text, setText] = useState('');
  const [pending, setPending] = useState(null); // { level, suggestion } for caution/block
  const [cooldownLeft, setCooldownLeft] = useState(0);
  const inputRef = useRef(null);

  useEffect(() => {
    if (cooldownLeft <= 0) return undefined;
    const id = window.setInterval(() => {
      setCooldownLeft((value) => Math.max(0, value - 1000));
    }, 1000);
    return () => window.clearInterval(id);
  }, [cooldownLeft]);

  const post = (body) => {
    setComments((previous) => [
      ...previous,
      { id: `you-${Date.now()}`, authorId: 'you', author: 'You', emoji: '🌊', text: body, isYou: true },
    ]);
    setText('');
    setPending(null);
    setCooldownLeft(0);
  };

  const handleSend = () => {
    const body = text.trim();
    if (!body) return;
    const result = analyzeComment(body);
    if (result.level === SAFETY_OK) {
      post(body);
      if (result.nudge) onStatus?.(result.nudge);
      return;
    }
    setPending(result);
    setCooldownLeft(result.cooldownMs || 0);
  };

  const handleRewrite = () => {
    setPending(null);
    setCooldownLeft(0);
    inputRef.current?.focus();
  };

  const handlePostAnyway = () => {
    if (cooldownLeft > 0) return;
    post(text.trim());
  };

  const handleMessage = (comment) => {
    if (comment.isYou) return;
    if (canMessage(comment.authorId)) {
      onStatus?.(`Message sent to ${comment.author} 💬`);
    } else {
      onStatus?.(FRIENDS_ONLY_MESSAGE);
    }
  };

  const handleBlock = (comment) => {
    setComments((previous) => previous.filter((item) => item.id !== comment.id));
    onStatus?.(`You won't see comments from ${comment.author}.`);
  };

  const handleReport = (comment) => {
    setComments((previous) => previous.filter((item) => item.id !== comment.id));
    onStatus?.(`Reported. Thanks for helping keep ${BRAND} kind.`);
  };

  return (
    <section className="comments" aria-label="Comments">
      <div className="comments__head">
        <div>
          <span className="comments__eyebrow">
            <ShieldCheck size={13} aria-hidden="true" />
            Safer comments
          </span>
          <h2>Comments</h2>
        </div>
        {onClose && (
          <button type="button" className="comments__close" onClick={onClose} aria-label="Close comments">
            <X size={16} aria-hidden="true" />
          </button>
        )}
      </div>

      <ul className="comments__list">
        {comments.map((comment) => {
          const friend = !comment.isYou && canMessage(comment.authorId);
          return (
            <li key={comment.id} className={`comment${comment.isYou ? ' is-you' : ''}`}>
              <span className="comment__avatar" aria-hidden="true">{comment.emoji}</span>
              <div className="comment__body">
                <span className="comment__author">
                  {comment.author}
                  {comment.isYou && <span className="comment__you-tag">you</span>}
                  {friend && <span className="comment__friend-tag">friend</span>}
                </span>
                <span className="comment__text">{comment.text}</span>
                {!comment.isYou && (
                  <div className="comment__controls">
                    <button type="button" onClick={() => handleMessage(comment)} title={friend ? `Message ${comment.author}` : 'Friends-only'}>
                      <MessageCircle size={13} aria-hidden="true" />
                      Message
                    </button>
                    <button type="button" onClick={() => handleBlock(comment)}>
                      <Ban size={13} aria-hidden="true" />
                      Block
                    </button>
                    <button type="button" onClick={() => handleReport(comment)}>
                      <Flag size={13} aria-hidden="true" />
                      Report
                    </button>
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ul>

      {pending && (
        <div className={`comment-guard comment-guard--${pending.level}`} role="alert">
          <p className="comment-guard__msg">{pending.suggestion}</p>
          <div className="comment-guard__actions">
            <button type="button" className="comment-guard__rewrite" onClick={handleRewrite}>
              Rewrite
            </button>
            {pending.level === SAFETY_CAUTION && (
              <button
                type="button"
                className="comment-guard__anyway"
                onClick={handlePostAnyway}
                disabled={cooldownLeft > 0}
              >
                {cooldownLeft > 0 ? `Post anyway (${Math.ceil(cooldownLeft / 1000)}s)` : 'Post anyway'}
              </button>
            )}
          </div>
          {pending.level === SAFETY_BLOCK && (
            <p className="comment-guard__note">We&apos;re not removing your voice — just asking for a kinder version.</p>
          )}
        </div>
      )}

      <div className="comments__composer">
        <input
          ref={inputRef}
          type="text"
          value={text}
          onChange={(event) => { setText(event.target.value); if (pending) setPending(null); }}
          onKeyDown={(event) => { if (event.key === 'Enter') handleSend(); }}
          placeholder="Add a kind comment…"
          maxLength={280}
          aria-label="Write a comment"
        />
        <button type="button" className="comments__send" onClick={handleSend} aria-label="Post comment">
          <Send size={16} aria-hidden="true" />
        </button>
      </div>
      <p className="comments__footnote">Chrysalis keeps conversations safe and respectful. Messaging is friends-only.</p>
    </section>
  );
}
