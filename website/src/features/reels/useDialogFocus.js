import { useEffect, useRef } from 'react';

const FOCUSABLE = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

/**
 * Keeps keyboard focus inside an open presentation dialog and restores focus
 * to the control that launched it when the dialog unmounts.
 */
export function useDialogFocus(open = true) {
  const dialogRef = useRef(null);

  useEffect(() => {
    if (!open || typeof document === 'undefined') return undefined;

    const previouslyFocused = document.activeElement;
    const dialog = dialogRef.current;
    if (!dialog) return undefined;

    const focusableItems = () => [...dialog.querySelectorAll(FOCUSABLE)]
      .filter((element) => element.getAttribute('aria-hidden') !== 'true');

    const frame = window.requestAnimationFrame(() => {
      const preferred = dialog.querySelector('[data-dialog-initial-focus]');
      const first = preferred || focusableItems()[0] || dialog;
      first.focus({ preventScroll: true });
    });

    const keepFocusInside = (event) => {
      if (event.key !== 'Tab') return;
      const items = focusableItems();
      if (!items.length) {
        event.preventDefault();
        dialog.focus({ preventScroll: true });
        return;
      }

      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && (document.activeElement === first || !dialog.contains(document.activeElement))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    dialog.addEventListener('keydown', keepFocusInside);
    return () => {
      window.cancelAnimationFrame(frame);
      dialog.removeEventListener('keydown', keepFocusInside);
      if (previouslyFocused instanceof HTMLElement && document.contains(previouslyFocused)) {
        previouslyFocused.focus({ preventScroll: true });
      }
    };
  }, [open]);

  return dialogRef;
}
