import { Component } from 'react';
import { BRAND } from '../brand.js';
import { DayBreakLogo } from '../shared/components/DayBreakLogo.jsx';

export class GlobalErrorBoundary extends Component {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    console.error(`[${BRAND}] Unhandled interface error`, error, info);
  }

  handleRetry = () => {
    window.location.reload();
  };

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <main className="global-error" role="alert">
        <div className="global-error__card">
          <DayBreakLogo className="global-error__logo" />
          <p className="global-error__eyebrow">{BRAND}</p>
          <h1>We hit an unexpected pause.</h1>
          <p>Your place is safe. Refresh the experience when you’re ready.</p>
          <button type="button" onClick={this.handleRetry}>Try again</button>
        </div>
      </main>
    );
  }
}
