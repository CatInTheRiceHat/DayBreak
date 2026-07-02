import { Home, Film, Users, Trophy, Search, Bookmark, UserCircle } from 'lucide-react';

/**
 * Single source of truth for the Chrysalis app's main sections and their order.
 * Both the desktop rail (AppSidebar) and the mobile bottom bar (AppBottomNav) read
 * from this so the structure is identical everywhere.
 *
 * Order is intentional and must match the product spec:
 *   Home · Reels · Community · Challenges · Search · Saved · Profile
 *
 * `route` is the canonical path; consumers may override behavior per-key (e.g. the
 * feed scrolls to top instead of navigating when you tap "Reels" while already on
 * it). `bottomNav` flags the five that fit the mobile bar; Search + Saved live in
 * the mobile top bar instead (see HomeShell).
 */
export const NAV_SECTIONS = [
  { key: 'home', label: 'Home', Icon: Home, route: '/home', bottomNav: true },
  { key: 'reels', label: 'Reels', Icon: Film, route: '/algorithm', bottomNav: true },
  { key: 'community', label: 'Community', Icon: Users, route: '/community', bottomNav: true },
  { key: 'challenges', label: 'Challenges', Icon: Trophy, route: '/challenges', bottomNav: true },
  { key: 'search', label: 'Search', Icon: Search, route: '/search', bottomNav: false },
  { key: 'saved', label: 'Saved', Icon: Bookmark, route: '/saved', bottomNav: false },
  { key: 'profile', label: 'Profile', Icon: UserCircle, route: '/profile', bottomNav: true },
];

export const BOTTOM_NAV_SECTIONS = NAV_SECTIONS.filter((s) => s.bottomNav);
