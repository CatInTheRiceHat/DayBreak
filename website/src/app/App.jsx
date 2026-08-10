import { useEffect } from 'react';
import { BRAND } from '../brand.js';
import {
  BrowserRouter,
  Navigate,
  Outlet,
  Route,
  Routes,
  useLocation,
} from 'react-router-dom';
import Lenis from 'lenis';
import { Navbar } from '../features/marketing/Navbar';
import { GlobalErrorBoundary } from './GlobalErrorBoundary';
import { FirstRunGate } from '../features/onboarding/FirstRunGate';
import { ReelsPage } from '../features/reels/ReelsPage';
import { AuthProvider } from '../lib/AuthProvider';
import { AuthPage } from '../features/profile/AuthPage';
import { ForgotPasswordPage } from '../features/profile/ForgotPasswordPage';
import { ResetPasswordPage } from '../features/profile/ResetPasswordPage';
import { DiagnosticPage } from '../features/diagnostic/DiagnosticPage';
import { ProfilePage } from '../features/profile/ProfilePage';
import { EditProfileForm } from '../features/profile/EditProfileForm';
import { SavedPage } from '../features/saved/SavedPage';
import { ChallengesPage } from '../features/challenges/ChallengesPage';
import { IntentionalBreakRouteGuard } from '../features/research/IntentionalBreakRouteGuard.jsx';
import { ResearchPage } from '../features/research/ResearchPage';
import '../styles/marketing.css';
import '../styles/auth.css';
import '../styles/app-shell.css';

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
    || pathname === '/study'
    || pathname.startsWith('/u/')
  );
}

function ProductShell() {
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
        <Outlet />
      </div>
    </>
  );
}

function StudyShell() {
  return (
    <div className="min-h-screen overflow-x-hidden">
      <ResearchPage />
    </div>
  );
}

function AppShell() {
  return (
    <Routes>
      <Route path="/study" element={<StudyShell />} />
      <Route element={<IntentionalBreakRouteGuard />}>
        <Route element={<ProductShell />}>
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
        </Route>
      </Route>
    </Routes>
  );
}

function App() {
  useEffect(() => {
    document.title = `${BRAND} — A brighter way to scroll`;
  }, []);

  return (
    <GlobalErrorBoundary>
      <BrowserRouter>
        <AuthProvider>
          <AppShell />
        </AuthProvider>
      </BrowserRouter>
    </GlobalErrorBoundary>
  );
}

export default App;
