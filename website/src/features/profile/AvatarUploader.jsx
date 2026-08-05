import { useRef, useState } from 'react';
import { Camera, Loader2 } from 'lucide-react';
import { uploadAvatar, validateAvatarFile } from '../../lib/profileApi';

/**
 * Avatar picker + uploader. Validates (image-only, <= 5 MB) before sending, shows
 * an instant local preview, uploads to avatars/{user_id}/avatar.<ext> (replacing
 * any previous file), and reports the new public URL upward.
 */
export function AvatarUploader({ currentUrl, displayName, onUploaded }) {
  const inputRef = useRef(null);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const shownUrl = preview || currentUrl;

  const handleFile = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = ''; // allow re-selecting the same file later
    if (!file) return;

    const validationError = validateAvatarFile(file);
    if (validationError) {
      setError(validationError);
      return;
    }
    setError(null);
    const localPreview = URL.createObjectURL(file);
    setPreview(localPreview);
    setBusy(true);
    try {
      const url = await uploadAvatar(file);
      onUploaded?.(url);
    } catch (err) {
      setError(err?.message || 'Could not upload that image. Please try again.');
      setPreview(null);
    } finally {
      setBusy(false);
      URL.revokeObjectURL(localPreview);
    }
  };

  return (
    <div className="cx-avataruploader">
      <button
        type="button"
        className="cx-avataruploader__btn"
        onClick={() => inputRef.current?.click()}
        disabled={busy}
        aria-label="Change your profile picture"
      >
        <span className="cx-avatar cx-avatar--lg">
          {shownUrl
            ? <img src={shownUrl} alt={displayName ? `${displayName}'s avatar` : 'Your avatar'} />
            : <span className="cx-avatar__fallback" aria-hidden="true">🌊</span>}
        </span>
        <span className="cx-avataruploader__overlay" aria-hidden="true">
          {busy ? <Loader2 size={18} className="cx-spin" /> : <Camera size={18} />}
        </span>
      </button>
      <div className="cx-avataruploader__text">
        <span className="cx-avataruploader__label">{busy ? 'Uploading…' : 'Change photo'}</span>
        <span className="cx-avataruploader__hint">PNG, JPG, WEBP or GIF · up to 5 MB</span>
      </div>
      <input
        ref={inputRef}
        type="file"
        accept="image/png,image/jpeg,image/webp,image/gif"
        className="cx-visually-hidden"
        onChange={handleFile}
      />
      {error && <p className="cx-form__error" role="alert">{error}</p>}
    </div>
  );
}
