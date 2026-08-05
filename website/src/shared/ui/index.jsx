import {
  createContext,
  createElement,
  cloneElement,
  forwardRef,
  useContext,
  useEffect,
  useId,
  isValidElement,
  useMemo,
  useRef,
  useState,
} from 'react';

function cx(...values) {
  return values.filter(Boolean).join(' ');
}

export const Spinner = forwardRef(function Spinner(
  { className, label = 'Loading', size = 'md', ...props },
  ref,
) {
  return (
    <span
      ref={ref}
      className={cx('db-spinner', `db-spinner--${size}`, className)}
      role="status"
      aria-label={label}
      {...props}
    />
  );
});

export const Button = forwardRef(function Button(
  {
    as: Component = 'button',
    children,
    className,
    disabled = false,
    leftIcon,
    loading = false,
    loadingLabel = 'Loading',
    rightIcon,
    size = 'md',
    type,
    variant = 'primary',
    ...props
  },
  ref,
) {
  const isButton = Component === 'button';
  return (
    <Component
      ref={ref}
      className={cx('db-button', `db-button--${variant}`, `db-button--${size}`, className)}
      disabled={isButton ? disabled || loading : undefined}
      aria-disabled={!isButton && (disabled || loading) ? true : undefined}
      aria-busy={loading || undefined}
      type={isButton ? type || 'button' : undefined}
      {...props}
    >
      {loading ? <Spinner size="sm" label={loadingLabel} /> : leftIcon}
      <span className="db-button__label">{children}</span>
      {!loading && rightIcon}
    </Component>
  );
});

export const IconButton = forwardRef(function IconButton(
  {
    children,
    className,
    disabled = false,
    label,
    loading = false,
    size = 'md',
    type = 'button',
    variant = 'ghost',
    ...props
  },
  ref,
) {
  const accessibleLabel = props['aria-label'] || label;
  return (
    <button
      ref={ref}
      className={cx('db-icon-button', `db-icon-button--${variant}`, `db-icon-button--${size}`, className)}
      type={type}
      aria-label={accessibleLabel}
      aria-busy={loading || undefined}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? <Spinner size="sm" label={`${accessibleLabel || 'Action'} in progress`} /> : children}
    </button>
  );
});

export const Card = forwardRef(function Card(
  { as: Component = 'div', className, elevated = false, selected = false, ...props },
  ref,
) {
  return createElement(Component, {
    ...props,
    ref,
    className: cx('db-card', elevated && 'db-card--elevated', selected && 'is-selected', className),
    'data-selected': selected || undefined,
  });
});

export function CardHeader({ className, ...props }) {
  return <div className={cx('db-card__header', className)} {...props} />;
}

export function CardTitle({ as: Component = 'h3', className, ...props }) {
  return createElement(Component, { ...props, className: cx('db-card__title', className) });
}

export function CardDescription({ className, ...props }) {
  return <p className={cx('db-card__description', className)} {...props} />;
}

export function CardContent({ className, ...props }) {
  return <div className={cx('db-card__content', className)} {...props} />;
}

export function CardFooter({ className, ...props }) {
  return <div className={cx('db-card__footer', className)} {...props} />;
}

function FieldFrame({ children, className, error, errorId, hint, hintId, id, label, required }) {
  return (
    <div className={cx('db-field', error && 'db-field--error', className)}>
      {label && (
        <label className="db-field__label" htmlFor={id}>
          {label}
          {required && <span className="db-field__required" aria-hidden="true"> *</span>}
        </label>
      )}
      {children}
      {hint && !error && <span className="db-field__hint" id={hintId}>{hint}</span>}
      {error && <span className="db-field__error" id={errorId}>{error}</span>}
    </div>
  );
}

function fieldA11y({ describedBy, error, errorId, hint, hintId }) {
  return {
    'aria-describedby': describedBy || (error ? errorId : hint ? hintId : undefined),
    'aria-invalid': error ? true : undefined,
  };
}

export const Input = forwardRef(function Input(
  { className, error, hint, id: suppliedId, label, required, ...props },
  ref,
) {
  const generatedId = useId();
  const id = suppliedId || `db-input-${generatedId}`;
  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;
  return (
    <FieldFrame error={error} errorId={errorId} hint={hint} hintId={hintId} id={id} label={label} required={required}>
      <input
        ref={ref}
        id={id}
        className={cx('db-control', className)}
        required={required}
        {...props}
        {...fieldA11y({ describedBy: props['aria-describedby'], error, errorId, hint, hintId })}
      />
    </FieldFrame>
  );
});

export const Textarea = forwardRef(function Textarea(
  { className, error, hint, id: suppliedId, label, required, rows = 4, ...props },
  ref,
) {
  const generatedId = useId();
  const id = suppliedId || `db-textarea-${generatedId}`;
  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;
  return (
    <FieldFrame error={error} errorId={errorId} hint={hint} hintId={hintId} id={id} label={label} required={required}>
      <textarea
        ref={ref}
        id={id}
        className={cx('db-control', 'db-textarea', className)}
        required={required}
        rows={rows}
        {...props}
        {...fieldA11y({ describedBy: props['aria-describedby'], error, errorId, hint, hintId })}
      />
    </FieldFrame>
  );
});

export const Select = forwardRef(function Select(
  { children, className, error, hint, id: suppliedId, label, placeholder, required, ...props },
  ref,
) {
  const generatedId = useId();
  const id = suppliedId || `db-select-${generatedId}`;
  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;
  return (
    <FieldFrame error={error} errorId={errorId} hint={hint} hintId={hintId} id={id} label={label} required={required}>
      <span className="db-select-wrap">
        <select
          ref={ref}
          id={id}
          className={cx('db-control', 'db-select', className)}
          required={required}
          {...props}
          {...fieldA11y({ describedBy: props['aria-describedby'], error, errorId, hint, hintId })}
        >
          {placeholder && <option value="">{placeholder}</option>}
          {children}
        </select>
      </span>
    </FieldFrame>
  );
});

const Choice = forwardRef(function Choice(
  { className, description, error, inputClassName, label, type, ...props },
  ref,
) {
  const generatedId = useId();
  const id = props.id || `db-${type}-${generatedId}`;
  const descriptionId = `${id}-description`;
  const errorId = `${id}-error`;
  return (
    <label className={cx('db-choice', error && 'db-choice--error', className)} htmlFor={id}>
      <input
        ref={ref}
        className={cx('db-choice__input', inputClassName)}
        id={id}
        type={type}
        {...props}
        aria-describedby={props['aria-describedby'] || (error ? errorId : description ? descriptionId : undefined)}
        aria-invalid={error ? true : undefined}
      />
      <span className="db-choice__copy">
        <span className="db-choice__label">{label}</span>
        {description && <span className="db-choice__description" id={descriptionId}>{description}</span>}
        {error && <span className="db-choice__error" id={errorId}>{error}</span>}
      </span>
    </label>
  );
});

export const Checkbox = forwardRef(function Checkbox(props, ref) {
  return <Choice {...props} inputClassName="db-checkbox" type="checkbox" ref={ref} />;
});

export const Radio = forwardRef(function Radio(props, ref) {
  return <Choice {...props} inputClassName="db-radio" type="radio" ref={ref} />;
});

export const Switch = forwardRef(function Switch(
  { className, description, label, ...props },
  ref,
) {
  const generatedId = useId();
  const id = props.id || `db-switch-${generatedId}`;
  return (
    <label className={cx('db-switch', className)} htmlFor={id}>
      <span className="db-switch__copy">
        <span className="db-switch__label">{label}</span>
        {description && <span className="db-switch__description">{description}</span>}
      </span>
      <input ref={ref} className="db-switch__input" id={id} type="checkbox" role="switch" {...props} />
      <span className="db-switch__track" aria-hidden="true"><span className="db-switch__thumb" /></span>
    </label>
  );
});

export const Badge = forwardRef(function Badge(
  { as: Component = 'span', className, variant = 'neutral', ...props },
  ref,
) {
  return createElement(Component, {
    ...props,
    ref,
    className: cx('db-badge', `db-badge--${variant}`, className),
  });
});

export const Alert = forwardRef(function Alert(
  { actions, children, className, icon, live, title, variant = 'info', ...props },
  ref,
) {
  const role = props.role || (variant === 'error' ? 'alert' : 'status');
  return (
    <div
      ref={ref}
      className={cx('db-alert', `db-alert--${variant}`, className)}
      role={role}
      aria-live={live || (role === 'alert' ? 'assertive' : 'polite')}
      {...props}
    >
      {icon && <span className="db-alert__icon" aria-hidden="true">{icon}</span>}
      <div className="db-alert__body">
        {title && <div className="db-alert__title">{title}</div>}
        <div className="db-alert__content">{children}</div>
        {actions && <div className="db-alert__actions">{actions}</div>}
      </div>
    </div>
  );
});

export function Dialog({
  children,
  className,
  description,
  dismissLabel = 'Close dialog',
  onOpenChange,
  open,
  title,
  ...props
}) {
  const dialogRef = useRef(null);
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  function requestClose() {
    onOpenChange?.(false);
  }

  return (
    <dialog
      ref={dialogRef}
      className={cx('db-dialog', className)}
      aria-labelledby={title ? titleId : undefined}
      aria-describedby={description ? descriptionId : undefined}
      onCancel={(event) => {
        event.preventDefault();
        requestClose();
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) requestClose();
      }}
      {...props}
    >
      <div className="db-dialog__panel">
        <div className="db-dialog__header">
          <div>
            {title && <h2 className="db-dialog__title" id={titleId}>{title}</h2>}
            {description && <p className="db-dialog__description" id={descriptionId}>{description}</p>}
          </div>
          <IconButton label={dismissLabel} size="sm" onClick={requestClose}>
            <span aria-hidden="true">×</span>
          </IconButton>
        </div>
        <div className="db-dialog__content">{children}</div>
      </div>
    </dialog>
  );
}

export function DialogFooter({ className, ...props }) {
  return <div className={cx('db-dialog__footer', className)} {...props} />;
}

export function Tooltip({ children, className, content, side = 'top' }) {
  const id = useId();
  if (!content) return children;
  const trigger = isValidElement(children)
    ? cloneElement(children, {
      'aria-describedby': [children.props['aria-describedby'], id].filter(Boolean).join(' '),
    })
    : children;
  return (
    <span className={cx('db-tooltip', className)}>
      {trigger}
      <span className={cx('db-tooltip__content', `db-tooltip__content--${side}`)} id={id} role="tooltip">
        {content}
      </span>
    </span>
  );
}

const TabsContext = createContext(null);

export function Tabs({
  children,
  className,
  defaultValue,
  onValueChange,
  orientation = 'horizontal',
  value: controlledValue,
}) {
  const [uncontrolledValue, setUncontrolledValue] = useState(defaultValue);
  const value = controlledValue ?? uncontrolledValue;
  const baseId = useId();
  const context = useMemo(() => ({
    baseId,
    orientation,
    setValue(nextValue) {
      if (controlledValue === undefined) setUncontrolledValue(nextValue);
      onValueChange?.(nextValue);
    },
    value,
  }), [baseId, controlledValue, onValueChange, orientation, value]);

  return (
    <TabsContext.Provider value={context}>
      <div className={cx('db-tabs', className)}>{children}</div>
    </TabsContext.Provider>
  );
}

function useTabs() {
  const context = useContext(TabsContext);
  if (!context) throw new Error('Tabs components must be rendered inside <Tabs>.');
  return context;
}

export function TabsList({ className, label = 'Sections', ...props }) {
  const { orientation } = useTabs();
  return (
    <div
      className={cx('db-tabs__list', className)}
      role="tablist"
      aria-label={props['aria-label'] || label}
      aria-orientation={orientation}
      {...props}
    />
  );
}

export function TabsTrigger({ className, disabled, value, ...props }) {
  const { baseId, orientation, setValue, value: selectedValue } = useTabs();
  const selected = selectedValue === value;
  function handleKeyDown(event) {
    const horizontal = orientation === 'horizontal';
    const previousKey = horizontal ? 'ArrowLeft' : 'ArrowUp';
    const nextKey = horizontal ? 'ArrowRight' : 'ArrowDown';
    if (![previousKey, nextKey, 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const tabs = [...event.currentTarget.parentElement.querySelectorAll('[role="tab"]:not(:disabled)')];
    const index = tabs.indexOf(event.currentTarget);
    const target = event.key === 'Home'
      ? tabs[0]
      : event.key === 'End'
        ? tabs.at(-1)
        : tabs[(index + (event.key === nextKey ? 1 : -1) + tabs.length) % tabs.length];
    target?.focus();
    target?.click();
  }
  return (
    <button
      className={cx('db-tabs__trigger', className)}
      id={`${baseId}-tab-${value}`}
      type="button"
      role="tab"
      aria-controls={`${baseId}-panel-${value}`}
      aria-selected={selected}
      disabled={disabled}
      tabIndex={selected ? 0 : -1}
      onClick={() => setValue(value)}
      onKeyDown={handleKeyDown}
      {...props}
    />
  );
}

export function TabsContent({ children, className, value, ...props }) {
  const { baseId, value: selectedValue } = useTabs();
  const selected = selectedValue === value;
  return (
    <div
      className={cx('db-tabs__content', className)}
      id={`${baseId}-panel-${value}`}
      role="tabpanel"
      aria-labelledby={`${baseId}-tab-${value}`}
      hidden={!selected}
      tabIndex={0}
      {...props}
    >
      {children}
    </div>
  );
}

export function Progress({
  className,
  label = 'Progress',
  max = 100,
  showValue = false,
  value,
  valueLabel,
}) {
  const indeterminate = value === undefined || value === null;
  const safeValue = indeterminate ? 0 : Math.min(Math.max(value, 0), max);
  const percentage = max > 0 ? (safeValue / max) * 100 : 0;
  return (
    <div className={cx('db-progress', indeterminate && 'db-progress--indeterminate', className)}>
      <div className="db-progress__meta">
        <span>{label}</span>
        {showValue && !indeterminate && <span>{valueLabel || `${Math.round(percentage)}%`}</span>}
      </div>
      <div
        className="db-progress__track"
        role="progressbar"
        aria-label={label}
        aria-valuemin={indeterminate ? undefined : 0}
        aria-valuemax={indeterminate ? undefined : max}
        aria-valuenow={indeterminate ? undefined : safeValue}
        aria-valuetext={valueLabel}
      >
        <span className="db-progress__bar" style={{ '--db-progress-value': `${percentage}%` }} />
      </div>
    </div>
  );
}

export function Skeleton({ className, height, style, width, ...props }) {
  return (
    <span
      className={cx('db-skeleton', className)}
      aria-hidden="true"
      {...props}
      style={{ height, width, ...style }}
    />
  );
}

export function EmptyState({
  action,
  className,
  description,
  icon,
  title,
  titleAs = 'h2',
  ...props
}) {
  return (
    <div className={cx('db-empty-state', className)} {...props}>
      {icon && <div className="db-empty-state__icon" aria-hidden="true">{icon}</div>}
      {createElement(titleAs, { className: 'db-empty-state__title' }, title)}
      {description && <p className="db-empty-state__description">{description}</p>}
      {action && <div className="db-empty-state__action">{action}</div>}
    </div>
  );
}
