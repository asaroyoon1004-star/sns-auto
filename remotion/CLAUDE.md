# FINANCE SHORTS DESIGN SYSTEM (Remotion)

Think Bloomberg Terminal. Luxury before excitement.
Brand: Bloomberg × Wall Street Journal × Apple Keynote.

## Output
- 1080×1920 (9:16), 30fps, 750 frames (25s). All constants live in `src/theme.ts`.

## Color (only these)
Background #05070A / Surface #101419 / Text #F8FAFC / Secondary #8A94A6 / Gold #C8A96A / Green #4ADE80 / Red #EF4444.
Green = gain, Red = cost/loss, Gold = neutral emphasis.

## Typography
IBM Plex Sans (JP build) Bold for headlines, SemiBold for numbers. Libre Baskerville only for Latin editorial labels.
Fonts are bundled in `public/fonts` (OFL). No other fonts.

## Motion
- Duration 0.35–0.45s (11–14 frames). Only opacity / translateY / scale.
- Never bounce / overshoot / elastic / spring with overshoot. Use `ease()` from `src/theme.ts` (ease-out cubic).
- Numbers count up smoothly with the same easing. Charts never bounce. Camera movement minimal.

## Layout
- Margin 64px. 12-column grid. Max text width 75% of the frame (810px).
- Safe area: also keep clear of the Shorts/TikTok UI — top 220px, bottom 380px, right 120px for text.

## Forbidden
Neon gradients, glassmorphism, emoji, huge drop shadows, TikTok-style flashy effects.

## Structure
One React component per scene in `src/scenes/`. Shared pieces in `src/components/`. `src/FinanceShort.tsx` only sequences scenes.

## Content rules
Figures are labelled as assumptions/simulations. No investment advice, no guarantees of returns.
