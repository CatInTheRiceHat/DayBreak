# DayBreak design system

DayBreak’s visual system is warm, thoughtful, and research-informed. It uses color to clarify hierarchy and state, not to decorate every element. Prefer calm surfaces, moderate rounding, restrained depth, clear language, and generous whitespace.

The public CSS contract lives in `algorithm/website/src/index.css`. The legacy `about` frontend carries the same token contract in `about/src/index.css`. Reusable React primitives live in `algorithm/website/src/components/ui` and are exported from its `index.jsx`.

## Official palette

| Name | Value | CSS token | Primary role |
| --- | --- | --- | --- |
| Midnight Horizon | `#233A57` | `--db-color-midnight-horizon` | Text, structure, dark backgrounds |
| Twilight Violet | `#6D597A` | `--db-color-twilight-violet` | Secondary actions and navigation |
| Horizon Rose | `#CE6969` | `--db-color-horizon-rose` | Meaningful emphasis and selected-state family |
| Sunrise Coral | `#E6866C` | `--db-color-sunrise-coral` | Primary actions and momentum |
| Morning Light | `#FFDFAB` | `--db-color-morning-light` | Warm highlights and background family |

Use the exact brand tokens for identity and illustration. Use semantic tokens for interface work so contrast and themes remain centralized.

## Semantic tokens

| Purpose | CSS token | Tailwind key | Guidance |
| --- | --- | --- | --- |
| Background | `--db-color-background` | `background` | Default page canvas |
| Background subtle | `--db-color-background-subtle` | `background-subtle` | Quiet grouped regions |
| Surface | `--db-color-surface` | `surface` | Cards and controls |
| Surface elevated | `--db-color-surface-elevated` | `surface-elevated` | Dialogs and floating surfaces |
| Primary text | `--db-color-text-primary` | `text-primary` or `foreground` | Headings and body copy |
| Secondary text | `--db-color-text-secondary` | `text-secondary` | Supporting copy |
| Muted text | `--db-color-text-muted` | `text-muted` | Metadata; not long body copy |
| Border | `--db-color-border` | `border` | Default separators |
| Strong border | `--db-color-border-strong` | `border-strong` | Inputs and emphasized boundaries |
| Primary action | `--db-color-action-primary` | `primary` | One strongest action per region |
| Primary action hover | `--db-color-action-primary-hover` | `primary-hover` | Hover only |
| Secondary action | `--db-color-action-secondary` | `secondary` | Secondary controls and links |
| Selected state | `--db-color-selected` | `selected` | Checked, saved, or meaningful state |
| Focus ring | `--db-color-focus-ring` | `ring` | Keyboard focus only |
| Success | `--db-color-success` | `success` | Confirmed positive outcome |
| Warning | `--db-color-warning` | `warning` | Caution or recoverable issue |
| Error | `--db-color-error` | `error` | Validation or failed action |
| Overlay | `--db-color-overlay` | `overlay` | Modal backdrop |

Supporting “on color” tokens (`--db-color-on-primary`, `--db-color-on-secondary`, `--db-color-on-selected`, and `--db-color-on-status`) provide accessible foregrounds. Do not assume white works on the official coral or rose: it does not meet WCAG AA for normal text. Sunrise Coral with the designated deep action ink reaches 5.53:1. The selected semantic is a darker rose-family value so white state labels reach 5.40:1.

Use Tailwind opacity modifiers normally, for example `bg-surface/80`, `text-text-secondary`, and `border-border/60`. Compatibility keys such as `primary`, `foreground`, `card`, and `muted` remain available while older components migrate.

## Typography

Montserrat is the default sans-serif. It is already loaded by both frontends and needs no new dependency. Abril Fatface is reserved for short editorial display and page titles. Story Script may be used sparingly for one-to-four-word decorative annotations, never for controls, research instructions, or long copy.

| Role | Class | Guidance |
| --- | --- | --- |
| Display | `.db-type-display` | Short hero statement; Abril Fatface |
| Page title | `.db-type-page-title` | Route title; Abril Fatface |
| Section heading | `.db-type-section-heading` | Major content division |
| Card heading | `.db-type-card-heading` | Concise card title |
| Body | `.db-type-body` | Default reading copy, max 72 characters |
| Small body | `.db-type-small-body` | Supporting copy, not critical instructions |
| Label | `.db-type-label` | Form and UI labels |
| Caption | `.db-type-caption` | Metadata and captions |
| Button | `.db-type-button` | Action labels |
| Research annotation | `.db-type-research` | Provenance or methodological annotation |

Use sentence case. Preserve a 16px body size and roughly 65–75 characters per line. Create hierarchy with size, spacing, placement, and restrained weight before introducing another typeface.

## Foundations

- Spacing follows a 4px rhythm through `--db-space-1` to `--db-space-24`. Page gutters use `--db-page-gutter`; section rhythm uses `--db-section-space`.
- Containers are `42rem` narrow, `72rem` default, and `90rem` wide. Use `.db-page-container` with the `--narrow` or `--wide` modifier.
- Radii range from 8px to 24px. Use pill rounding for compact actions and state chips only; cards use 16px by default.
- Shadows are deliberately restrained (`--db-shadow-sm`, `--db-shadow-md`, `--db-shadow-lg`). A border should usually do the work before elevation is added.
- Interactive transitions are 120ms, 220ms, or 420ms using the shared standard easing. Avoid decorative looping motion.
- Minimum interactive size is `--db-touch-target` (44px). Compact visual controls may be smaller only when their clickable wrapper remains 44px.
- Responsive checkpoints are 320px, 375px, 768px, 1024px, and 1440px. Tailwind adds `compact`, `phone`, and `canvas`; its established `md` and `lg` remain 768px and 1024px.
- Dark semantics are available under `[data-theme="dark"]` or `.dark`; feature components should not redefine brand colors for dark mode.

## Shared components

Import primitives from the shared barrel:

```jsx
import {
  Alert,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Checkbox,
  Dialog,
  DialogFooter,
  EmptyState,
  IconButton,
  Input,
  Progress,
  Radio,
  Select,
  Skeleton,
  Spinner,
  Switch,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  Textarea,
  Tooltip,
} from '@/components/ui';
```

Component conventions:

- `Button` variants are `primary`, `secondary`, `soft`, `ghost`, and `danger`; sizes are `sm`, `md`, and `lg`. `loading` retains the label and exposes `aria-busy`.
- `IconButton` requires `label` or `aria-label`. Pair unfamiliar icon-only actions with `Tooltip`.
- `Input`, `Textarea`, and `Select` accept `label`, `hint`, `error`, and `required`; IDs and ARIA error associations are generated when omitted. Visible labels are the default.
- `Checkbox`, `Radio`, and `Switch` include their visible label in the touch target. Use `description` for short supporting context.
- `Card` accepts `elevated` and `selected`; selected meaning must also appear in text, an icon, or an accessible state attribute.
- `Alert` variants are `info`, `success`, `warning`, and `error`. Error alerts announce assertively; other variants are polite status messages.
- `Dialog` is controlled with `open` and `onOpenChange`. It uses the native modal dialog for focus containment, Escape behavior, and focus return.
- `Tabs` may be controlled or use `defaultValue`; triggers support arrow keys, Home, and End.
- `Progress` becomes indeterminate when `value` is omitted. Use an explicit label that names the process.
- `Skeleton` is decorative and hidden from assistive technology. `Spinner` provides a status label. Loading regions should preserve their eventual layout.
- `EmptyState` is for a genuinely empty result, not for errors; provide a useful next action when one exists.

The primitives pass native props and refs through whenever practical. Prefer extending them through `className` and semantic tokens instead of copying their styles into route CSS.

## Accessibility expectations

- Normal text meets WCAG AA (4.5:1); large text and meaningful boundaries meet at least 3:1. Do not use coral, rose, or Morning Light as body text.
- Every interactive element has a visible `:focus-visible` indicator. Never remove the shared outline without replacing it with an equally visible treatment.
- Controls have visible labels. Placeholder text is an example, not a label. Errors must identify the field and explain recovery.
- Do not rely on color alone for selected, success, warning, or error state. Add text, icons, checked state, or ARIA state.
- Dialogs require a useful title. Icon-only actions require accessible names. Tooltips supplement names; they do not replace them.
- Honor `prefers-reduced-motion`. The global fallback removes animation and smooth scrolling, and primitives include static loading/modal behavior.
- Verify keyboard order, zoom to 200%, 320px layout, long labels, and touch targets before merging route work.

## Guidance for future pages

Start with the semantic background, one content container, the typography hierarchy, and shared primitives. Use one primary action per decision area. Let content and whitespace carry the page; avoid heavy shadows, glassmorphism, neon effects, excessive gradients, and repeated decorative cards.

Only user-facing branding changes to DayBreak. Internal package names, component identifiers, API routes, storage keys, database objects, analytics events, and research events containing `Chrysalis` may remain unchanged for compatibility. Do not rename them as visual cleanup.
