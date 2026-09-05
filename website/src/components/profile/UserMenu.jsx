import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { LogOut, Pencil, UserCircle, UserPlus } from 'lucide-react';
import { useAuth } from '../../lib/authContext';

/**
 * Compact account control: an avatar button that opens a small menu.
 * Logged in  -> View / Edit profile, Log out.
 * Logged out -> Log in, Create your space.
 * Self-contained (reads auth + router itself) so it can drop into the sidebar,
 * top bar, or profile page without prop wiring.
 */
export function UserMenu({ avatarUrl }) {
  const navigate = useNavigate();
  const { user, signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const onDown = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('pointerdown', onDown, true);
    window.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('pointerdown', onDown, true);
      window.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const go = (path) => { setOpen(false); navigate(path); };
  const handleSignOut = async () => {
    setOpen(false);
    await signOut();
    navigate('/login');
  };

  const initial = (user?.email || '?').trim().charAt(0).toUpperCase();

  return (
    <div className="cx-usermenu" ref={ref}>
      <button
        type="button"
        className="cx-usermenu__trigger"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Account menu"
      >
        <span className="cx-avatar cx-avatar--sm">
          {avatarUrl
            ? <img src={avatarUrl} alt="" aria-hidden="true" />
            : (user ? <span className="cx-avatar__initial">{initial}</span>
              : <UserCircle size={20} aria-hidden="true" />)}
        </span>
      </button>

      {open && (
        <div className="cx-usermenu__menu" role="menu">
          {user ? (
            <>
              <button type="button" role="menuitem" onClick={() => go('/profile')}>
                <UserCircle size={15} aria-hidden="true" /> View profile
              </button>
              <button type="button" role="menuitem" onClick={() => go('/profile/edit')}>
                <Pencil size={15} aria-hidden="true" /> Edit profile
              </button>
              <button type="button" role="menuitem" onClick={handleSignOut}>
                <LogOut size={15} aria-hidden="true" /> Log out
              </button>
            </>
          ) : (
            <>
              <button type="button" role="menuitem" onClick={() => go('/login')}>
                <UserCircle size={15} aria-hidden="true" /> Log in
              </button>
              <button type="button" role="menuitem" onClick={() => go('/signup')}>
                <UserPlus size={15} aria-hidden="true" /> Create your space
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
