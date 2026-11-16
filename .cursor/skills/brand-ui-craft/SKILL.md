---
name: brand-ui-craft
description: >-
  Applies Yassir Benhaddouche's light editorial engineering-console brand system
  (Lavender Mist canvas, Electric Violet, CI Gate PASS/BLOCKED chips, Plus Jakarta
  Sans + JetBrains Mono). Use when building or restyling the RAG evaluation UI,
  frontend, canvas, or any visual surface in this project.
---

# Brand UI Craft — Yassir Benhaddouche

Light editorial engineering console. Not a dark neon dashboard. Not a generic SaaS template.

Micro-label everywhere it earns its keep: `BUILD • SOLVE • EVALUATE`

## Tokens

| Role | Value | Notes |
| --- | --- | --- |
| Canvas | `#F7F5FC` | Lavender Mist page background |
| Surface | `#FFFFFF` | Cards, panels, popovers |
| Subtle | `#F0ECF9` | Nested wells, table header, chip tracks |
| Hairline | `#E4E0F0` | `1px solid` borders only |
| Ink | `#121118` | Charcoal primary text |
| Secondary | `#524E63` | Labels, captions, helper copy |
| Electric Violet | `#7C3AED` | Links, focus, active controls |
| Violet hover | `#6D28D9` | Hover / pressed |
| Violet soft | `#EDE9FE` | Selected rows, focus rings (soft) |
| PASS ink | `#059669` | CI Gate pass |
| PASS wash | `#ECFDF5` | CI Gate pass chip |
| BLOCKED ink | `#E11D48` | CI Gate blocked |
| BLOCKED wash | `#FFF1F2` | CI Gate blocked chip |

```css
:root {
  --canvas: #f7f5fc;
  --surface: #ffffff;
  --subtle: #f0ecf9;
  --hairline: #e4e0f0;
  --ink: #121118;
  --secondary: #524e63;
  --violet: #7c3aed;
  --violet-hover: #6d28d9;
  --violet-soft: #ede9fe;
  --pass: #059669;
  --pass-wash: #ecfdf5;
  --blocked: #e11d48;
  --blocked-wash: #fff1f2;
  --font-sans: "Plus Jakarta Sans", "Segoe UI", sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, monospace;
}
```

## Type

- UI + editorial: `Plus Jakarta Sans` (400/500/600/700).
- Scores, IDs, chunk keys, run indices: `JetBrains Mono` with `font-variant-numeric: tabular-nums`.
- Display titles: tracking slightly tight, sentence case. No all-caps hero blobs except the micro-label.
- Micro-label: 11px, letter-spacing `0.18em`, `BUILD • SOLVE • EVALUATE`, Electric Violet or Secondary.

Google Fonts:

```
https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap
```

## Layout

- Page sits on Lavender Mist. Content is a white surface with hairline border and a quiet shadow (`0 1px 0 rgba(18,17,24,0.04), 0 12px 32px rgba(124,58,237,0.06)`).
- Radius 12–16px on cards; 999px on CI chips.
- Generous whitespace. Hairline dividers, not heavy rules.
- Numbers align in columns (tabular-nums). Threshold vs observed score is a pair, never a blended average.

## CI Gate chips

```html
<span class="gate-chip pass">PASS</span>
<span class="gate-chip blocked">BLOCKED</span>
```

```css
.gate-chip {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.08em;
  padding: 2px 10px;
  border-radius: 999px;
}
.gate-chip.pass { color: var(--pass); background: var(--pass-wash); }
.gate-chip.blocked { color: var(--blocked); background: var(--blocked-wash); }
```

Never encode pass/fail with color alone: always keep the word PASS or BLOCKED.

## Hand-drawn underline

Use a 1.5px Electric Violet SVG stroke under section titles (not CSS `text-decoration`). Slight wobble, not a perfect line:

```svg
<svg width="120" height="8" viewBox="0 0 120 8" fill="none" aria-hidden="true">
  <path d="M1.5 5.2 C 22 1.8, 48 6.4, 72 4.1 S 108 2.2, 118.5 5.6"
        stroke="#7C3AED" stroke-width="1.5" stroke-linecap="round"/>
</svg>
```

Sit it 2px below the baseline, opacity 0.85, width ≈ 40–70% of the title.

## Do / Don't

**Do**

- Light canvas, white surfaces, violet as punctuation.
- Show four metrics separately. Gate on pass *rate* (e.g. 4/5), never a single blended score.
- Treat DeepEval `reason` strings as first-class copy: readable, editorial, mono for IDs inside them.

**Don't**

- Dark mode neon gradients, glassmorphism, purple-on-black “AI” chrome.
- Generic Inter/system-only templates, Bootstrap defaults, or rainbow metric gauges.
- Drop shadows larger than a whisper. No 3D cards. No stock illustration packs.
