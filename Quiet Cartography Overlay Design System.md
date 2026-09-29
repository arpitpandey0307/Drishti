# Quiet Cartography Overlay Design System

## Purpose

This design system defines a reusable visual language for interfaces that place calm, information-dense overlay cards above an interactive map, 3D scene, dashboard, or immersive canvas. Its character is **editorial, tactile, quietly premium, and operational**. The interface should feel designed rather than templated.

The system is optimized for products where the primary visual content remains visible behind the UI. Cards must provide hierarchy and control without overpowering the map or scene.

## Design principles

### Preserve the scene
The underlying map, model, image, or canvas is the primary visual. Overlays should occupy the edges and corners, leaving a clear central field for exploration.

### Use quiet contrast
Prefer warm off-white surfaces, muted ink, sage neutrals, terracotta accents, and translucent borders. Avoid pure white, pure black, saturated gradients, and excessive shadows.

### Make hierarchy editorial
Use a compact uppercase eyebrow, a strong display heading, a short explanatory paragraph, metadata, and one clear action. The card should be scannable in under five seconds.

### Make controls feel physical
Use soft radii, subtle depth, restrained blur, and small active-state changes. Buttons should feel responsive without looking playful or game-like.

### Be honest about precision
If the interface presents approximate or inferred information, say so in a quiet footnote. Trust improves when uncertainty is visible.

## Visual direction

| Element | Default treatment |
|---|---|
| Overall mood | Warm, calm, precise, architectural |
| Primary surface | Warm translucent ivory |
| Primary ink | Deep blue-green charcoal |
| Accent | Burnt terracotta |
| Secondary accent | Muted sage green |
| Radius | 14–20px for cards; 8–12px for controls |
| Border | Thin translucent white or dark neutral line |
| Shadow | Broad, soft, low-opacity shadow with a small contact shadow |
| Blur | 14–20px backdrop blur where supported |
| Motion | 140–220ms, ease-out, transform and opacity only |
| Texture | Use subtle scene lighting or grain; do not add noisy card backgrounds |

## Color tokens

```css
:root {
  --qc-ink: #273133;
  --qc-ink-soft: #6d7772;
  --qc-ink-faint: #89918b;

  --qc-paper: rgba(249, 247, 241, 0.90);
  --qc-paper-solid: #f9f7f1;
  --qc-paper-soft: rgba(247, 244, 236, 0.72);
  --qc-paper-muted: rgba(231, 229, 219, 0.70);

  --qc-terracotta: #c7764d;
  --qc-terracotta-dark: #9a593e;
  --qc-sage: #6f947b;
  --qc-sage-soft: #e8eee4;
  --qc-slate: #324642;
  --qc-slate-dark: #223632;

  --qc-line: rgba(42, 54, 51, 0.13);
  --qc-line-light: rgba(255, 255, 255, 0.62);
  --qc-shadow: rgba(38, 46, 43, 0.14);
  --qc-shadow-contact: rgba(38, 46, 43, 0.08);

  --qc-radius-card: 18px;
  --qc-radius-panel: 14px;
  --qc-radius-control: 9px;
  --qc-radius-pill: 999px;

  --qc-ease-out: cubic-bezier(0.23, 1, 0.32, 1);
  --qc-ease-in-out: cubic-bezier(0.77, 0, 0.175, 1);
  --qc-duration-fast: 140ms;
  --qc-duration-normal: 180ms;
  --qc-duration-slow: 220ms;
}
```

## Typography

Use one functional sans-serif and one editorial serif. The sans-serif handles navigation, labels, metadata, and body copy. The serif appears only for a short emphasized phrase in the main heading.

Recommended default pair:

```html
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;600;700;800&family=Playfair+Display:ital,wght@0,600;1,600&display=swap" rel="stylesheet" />
```

| Role | Font | Size | Weight | Letter spacing |
|---|---|---:|---:|---:|
| Card heading | Manrope | 22–28px | 800 | −0.055em to −0.065em |
| Editorial emphasis | Playfair Display Italic | Inherit | 600 | −0.03em |
| Body copy | Manrope | 10–12px | 400–500 | Normal |
| Eyebrow | DM Mono | 8–10px | 500 | 0.11–0.16em |
| Metadata | DM Mono | 8–10px | 400–500 | 0.01–0.05em |
| Button label | Manrope | 10–11px | 800 | Normal |
| List title | Manrope | 11–12px | 800 | −0.02em |
| List secondary text | DM Mono | 9px | 400 | Normal |

Do not use uppercase for long paragraphs. Use uppercase only for short labels, categories, status text, and utility metadata.

## Surface recipe

The main overlay surface combines a warm translucent fill, a light edge, soft depth, and background blur.

```css
.qc-glass-panel {
  background: var(--qc-paper);
  border: 1px solid var(--qc-line-light);
  border-radius: var(--qc-radius-card);
  box-shadow:
    0 18px 60px var(--qc-shadow),
    0 2px 4px var(--qc-shadow-contact);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
}
```

When backdrop blur is unavailable, use `var(--qc-paper-solid)` rather than a highly transparent fallback. Text contrast must remain reliable over every possible scene background.

## Overlay card anatomy

A standard detail card has six layers, in this order:

1. **Context label.** A small uppercase category such as `LEARNING`, `SPORTS`, or `ACCESS`.
2. **Index or status.** A compact right-aligned value such as `09 / 18` or `LIVE`.
3. **Title.** One or two lines using strong sans-serif typography.
4. **Description.** One short paragraph that explains why the selected place matters.
5. **Metadata tags.** Two or three compact facts.
6. **Primary action.** One full-width action with a dark slate surface.

### Detail-card HTML structure

```html
<aside class="qc-detail-card qc-glass-panel" aria-live="polite">
  <div class="qc-detail-topline">
    <span class="qc-place-type">Learning</span>
    <span class="qc-place-index">09 / 18</span>
  </div>

  <h2>Central Library</h2>
  <p>
    The central learning anchor with a connected network of departmental libraries.
  </p>

  <div class="qc-detail-tags">
    <span>≈1.90 lakh books</span>
    <span>11,822+ titles</span>
    <span>RFID & multimedia</span>
  </div>

  <button class="qc-primary-action">
    <span aria-hidden="true">↗</span>
    Focus on map
    <span aria-hidden="true">↗</span>
  </button>
</aside>
```

### Detail-card CSS

```css
.qc-detail-card {
  width: min(285px, calc(100vw - 32px));
  padding: 20px 21px 18px;
}

.qc-detail-topline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.qc-place-type,
.qc-place-index {
  font-family: "DM Mono", monospace;
  font-size: 9px;
}

.qc-place-type {
  color: var(--qc-terracotta-dark);
  letter-spacing: 0.11em;
  text-transform: uppercase;
}

.qc-place-index {
  color: var(--qc-ink-faint);
}

.qc-detail-card h2 {
  margin: 0 0 7px;
  color: var(--qc-ink);
  font-size: 22px;
  line-height: 1.08;
  letter-spacing: -0.055em;
  font-weight: 800;
}

.qc-detail-card p {
  margin: 0;
  color: var(--qc-ink-soft);
  font-size: 10px;
  line-height: 1.55;
}

.qc-detail-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin: 13px 0 17px;
}

.qc-detail-tags span {
  padding: 5px 7px;
  border-radius: 5px;
  background: var(--qc-paper-muted);
  color: #66736c;
  font-size: 9px;
  font-weight: 700;
}
```

## Primary action

The primary action is dark, compact, and full width. It should use one clear verb. Suitable verbs include **Focus**, **Open**, **Route**, **Explore**, and **View details**.

```css
.qc-primary-action {
  display: flex;
  align-items: center;
  gap: 7px;
  width: 100%;
  padding: 10px 11px;
  border: 0;
  border-radius: var(--qc-radius-control);
  background: var(--qc-slate);
  color: #f7f3e9;
  font-size: 10px;
  font-weight: 800;
  cursor: pointer;
  transition:
    transform var(--qc-duration-fast) var(--qc-ease-out),
    background var(--qc-duration-fast) var(--qc-ease-out);
}

.qc-primary-action span:last-child {
  margin-left: auto;
}

.qc-primary-action:hover {
  background: var(--qc-slate-dark);
  transform: translateY(-1px);
}

.qc-primary-action:active {
  transform: scale(0.98);
}
```

## Directory card

A directory card is taller than a detail card and is usually anchored to the left edge. It contains a title, search field, horizontal category pills, result count, scrollable rows, and a quiet explanatory footnote.

```css
.qc-directory-card {
  width: 324px;
  max-height: calc(100vh - 154px);
  padding: 25px 17px 15px;
  overflow: hidden;
}

.qc-directory-card h1 {
  margin: 9px 0 19px;
  color: var(--qc-ink);
  font-size: 28px;
  line-height: 1.05;
  letter-spacing: -0.065em;
  font-weight: 800;
}

.qc-directory-card h1 em {
  color: #b76443;
  font-family: "Playfair Display", serif;
  font-style: italic;
  font-weight: 600;
  letter-spacing: -0.03em;
}
```

### Search field

The search field should appear slightly inset from the card surface. Use a muted warm fill instead of a white input.

```css
.qc-search-field {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0 1px 12px;
  padding: 11px 12px;
  border: 1px solid rgba(62, 75, 68, 0.08);
  border-radius: 11px;
  background: var(--qc-paper-muted);
  color: #7a8580;
}

.qc-search-field input {
  min-width: 0;
  flex: 1;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--qc-ink);
  font-size: 12px;
}
```

### Category pills

Category pills are filters, not primary navigation. Keep them compact and horizontally scrollable on narrow screens.

```css
.qc-category-pill {
  flex: 0 0 auto;
  padding: 6px 9px;
  border: 0;
  border-radius: var(--qc-radius-pill);
  background: rgba(226, 228, 218, 0.65);
  color: #758078;
  font-size: 10px;
  font-weight: 700;
  transition:
    background var(--qc-duration-fast) ease,
    color var(--qc-duration-fast) ease;
}

.qc-category-pill[aria-selected="true"] {
  background: #31423e;
  color: #f6f4e9;
}
```

### Directory row

A directory row uses a tinted icon container, a two-line text block, and a trailing arrow that appears on hover or selection.

```css
.qc-directory-row {
  display: flex;
  align-items: center;
  gap: 11px;
  width: 100%;
  padding: 9px 8px;
  border-radius: 11px;
  background: transparent;
  color: var(--qc-ink);
  text-align: left;
  cursor: pointer;
  transition:
    background var(--qc-duration-fast) ease,
    transform var(--qc-duration-fast) var(--qc-ease-out);
}

.qc-directory-row:hover {
  background: rgba(233, 230, 219, 0.92);
  transform: translateX(2px);
}

.qc-directory-row[aria-current="true"] {
  background: #eef0e7;
  box-shadow: inset 3px 0 var(--qc-terracotta);
}

.qc-directory-row .qc-row-arrow {
  margin-left: auto;
  color: #acb1a9;
  opacity: 0;
  transition: opacity var(--qc-duration-fast) ease;
}

.qc-directory-row:hover .qc-row-arrow,
.qc-directory-row[aria-current="true"] .qc-row-arrow {
  opacity: 1;
}
```

## Floating controls

Controls should be compact and secondary. Place them away from the primary detail card. Use one selected mode and a small group of icon-only camera controls.

```css
.qc-control-group {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 5px;
  border-radius: 13px;
}

.qc-control-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 30px;
  padding: 8px 9px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: #718078;
  font-size: 10px;
  font-weight: 800;
  transition: background var(--qc-duration-fast) ease, color var(--qc-duration-fast) ease;
}

.qc-control-button[aria-pressed="true"],
.qc-control-button:hover {
  background: #e8e9df;
  color: #344842;
}

.qc-icon-button {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: 8px;
  background: transparent;
  color: #718078;
}
```

## Placement and responsive behavior

Use a two-card desktop composition. The directory lives near the upper-left edge. The detail card lives near the upper-right edge. Camera controls sit near the lower-right edge. Stats or status live near the lower-left or lower-center edge.

```css
.qc-directory-card {
  position: absolute;
  top: 96px;
  left: 28px;
  z-index: 3;
}

.qc-detail-card {
  position: absolute;
  top: 25px;
  right: 28px;
  z-index: 3;
}

.qc-control-group {
  position: absolute;
  right: 28px;
  bottom: 88px;
  z-index: 3;
}
```

At widths below 640px, the directory becomes a full-width drawer, the detail card moves above the bottom controls, and the top bar spans the available width. Keep the canvas visible behind the cards.

```css
@media (max-width: 640px) {
  .qc-directory-card {
    top: 82px;
    right: 16px;
    left: 16px;
    width: auto;
    max-height: calc(100vh - 145px);
  }

  .qc-detail-card {
    right: 16px;
    bottom: 134px;
    left: 16px;
    width: auto;
  }

  .qc-control-group {
    right: 16px;
    bottom: 84px;
  }

  .qc-control-button span {
    display: none;
  }
}
```

## Motion

Motion must explain state changes. Use transform and opacity only. Do not animate layout properties such as width, height, margin, or padding.

| Interaction | Recommended motion |
|---|---|
| Button press | `scale(0.98)` over 140ms |
| Row hover | `translateX(2px)` over 140ms |
| Card open | `translateY(8px)` to `translateY(0)` with opacity, 180–220ms |
| Card close | Reverse the opening motion, 140–180ms |
| Selection highlight | Background and border-color transition, 140ms |
| Filter change | Keep instant; do not animate keyboard-driven filtering |

Respect reduced motion:

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

## Icons

Use a consistent outline icon set such as Lucide. Use 15–18px icons inside controls and 17–20px icons inside directory rows. Icons should support the label rather than replace it unless the control is universally recognizable, such as zoom in, zoom out, close, reset, or compass.

## Content rules

Card copy should be short and concrete. Use one idea per sentence. A good detail description is usually 12–20 words. Metadata tags should contain facts, not promotional language. Avoid wrapping a card title across more than two lines.

Recommended card content model:

```ts
type OverlayPlace = {
  name: string;
  category: string;
  description: string;
  index?: string;
  tags: string[];
  actionLabel: string;
};
```

## Accessibility

Every icon-only button must have an accessible name. Every selected filter must expose `aria-selected="true"` or `aria-pressed="true"`. The selected directory row should expose `aria-current="true"`. Use `aria-live="polite"` on detail content that changes after selection. Maintain visible focus rings.

```css
:where(button, input, [tabindex]):focus-visible {
  outline: 2px solid var(--qc-terracotta);
  outline-offset: 2px;
}
```

Do not use translucent text over an unpredictable scene background without a solid or translucent card surface behind it. Check keyboard order, mobile touch target size, and contrast against both light and dark map regions.

## Implementation checklist

Before shipping an interface using this system, confirm that the layout leaves the primary scene visible, every card has a clear hierarchy, the main action is visually distinct, the selected state is visible without relying on color alone, cards remain readable over changing backgrounds, mobile cards do not block all scene context, and reduced-motion preferences are respected.

## Reference implementation

The visual system was derived from the KIET 3D Campus Map interface. Its design language combines warm ivory glass panels, deep blue-green ink, terracotta accents, sage neutrals, Manrope for functional text, Playfair Display for editorial emphasis, and DM Mono for compact map metadata.

## References

[1]: https://fonts.google.com/specimen/Manrope "Manrope typeface"
[2]: https://fonts.google.com/specimen/Playfair+Display "Playfair Display typeface"
[3]: https://fonts.google.com/specimen/DM+Mono "DM Mono typeface"
