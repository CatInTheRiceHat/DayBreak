import { useEffect } from 'react';
import { BRAND } from './brand.js';
import { BrowserRouter, Routes, Route, useLocation, Navigate } from 'react-router-dom';
import Lenis from 'lenis';
import { Navbar } from './components/Navbar';
import { FirstRunGate } from './components/FirstRunGate';
import { RebootPage } from './components/RebootPage';
import { ReelsPage } from './components/reels/ReelsPage';
import { AuthProvider } from './lib/AuthProvider';
import { AuthPage } from './components/profile/AuthPage';
import { ForgotPasswordPage } from './components/profile/ForgotPasswordPage';
import { ResetPasswordPage } from './components/profile/ResetPasswordPage';
import { DiagnosticPage } from './components/diagnostic/DiagnosticPage';
import { ProfilePage } from './components/profile/ProfilePage';
import { EditProfileForm } from './components/profile/EditProfileForm';
import { HomePage } from './components/home/HomePage';
import { SearchPage } from './components/home/SearchPage';
import { InboxPage } from './components/home/InboxPage';
import { CommunityPage } from './components/community/CommunityPage';
import { SavedPage } from './components/saved/SavedPage';
import { ChallengesPage } from './components/challenges/ChallengesPage';
import './App.css';
import './auth.css';

function MainPage() {
  return <RebootPage />;
}

// Standalone "app" routes render without the marketing Navbar / Lenis smooth
// scroll / intro overlay (same treatment as the /algorithm feed).
function isAppPath(pathname) {
  return (
    pathname === '/'
    || pathname === '/algorithm'
    || pathname === '/reels'
    || pathname === '/home'
    || pathname === '/community'
    || pathname === '/challenges'
    || pathname === '/saved'
    || pathname === '/search'
    || pathname === '/inbox'
    || pathname === '/login'
    || pathname === '/signup'
    || pathname === '/forgot-password'
    || pathname === '/reset-password'
    || pathname === '/diagnostic'
    || pathname === '/profile'
    || pathname === '/profile/edit'
    || pathname.startsWith('/u/')
  );
}

function AppShell() {
  const { pathname } = useLocation();
  const isAlgorithmExperience = isAppPath(pathname);

  useEffect(() => {
    if (isAlgorithmExperience) return undefined;
    const lenis = new Lenis();
    function raf(time) {
      lenis.raf(time);
      requestAnimationFrame(raf);
    }
    const rafId = requestAnimationFrame(raf);
    return () => {
      cancelAnimationFrame(rafId);
      lenis.destroy();
    };
  }, [isAlgorithmExperience]);

  useEffect(() => {
    if (isAlgorithmExperience || typeof window === 'undefined' || !window.location.hash) {
      return;
    }
    const id = window.location.hash.slice(1);
    const timeout = setTimeout(() => {
      document.getElementById(id)?.scrollIntoView({ behavior: 'auto' });
    }, 100);
    return () => clearTimeout(timeout);
  }, [isAlgorithmExperience]);

  return (
    <>
      <FirstRunGate />
      <div className="min-h-screen overflow-x-hidden">
        {!isAlgorithmExperience && <Navbar />}
        <Routes>
          <Route path="/" element={<ReelsPage />} />
          <Route path="/algorithm" element={<Navigate to="/" replace />} />
          <Route path="/reels" element={<Navigate to="/" replace />} />
          <Route path="/home" element={<Navigate to="/" replace />} />
          <Route path="/community" element={<Navigate to="/" replace />} />
          <Route path="/challenges" element={<ChallengesPage />} />
          <Route path="/saved" element={<SavedPage />} />
          <Route path="/search" element={<Navigate to="/" replace />} />
          <Route path="/inbox" element={<Navigate to="/" replace />} />
          <Route path="/login" element={<AuthPage mode="login" />} />
          <Route path="/signup" element={<AuthPage mode="signup" />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="/diagnostic" element={<DiagnosticPage />} />
          <Route path="/profile" element={<ProfilePage mode="me" />} />
          <Route path="/profile/edit" element={<EditProfileForm />} />
          <Route path="/u/:username" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </>
  );
}

function App() {
  useEffect(() => {
    document.title = `${BRAND} — by Elaine Che`;
  }, []);

  return (
    <BrowserRouter>
      <AuthProvider>
        <AppShell />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
