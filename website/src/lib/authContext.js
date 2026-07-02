import { createContext, useContext } from 'react';

/**
 * Auth context + hook, kept in their own (non-component) module so the provider
 * file can export only its component (keeps React Fast Refresh happy).
 */
export const AuthContext = createContext(null);

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
}
