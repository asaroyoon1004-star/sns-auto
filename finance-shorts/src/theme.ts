import {Easing, interpolate} from 'remotion';

export const W = 1080;
export const H = 1920;
export const FPS = 30;
export const DURATION = 25 * FPS; // 750

export const C = {
  bg: '#05070A',
  surface: '#101419',
  text: '#F8FAFC',
  second: '#8A94A6',
  gold: '#C8A96A',
  green: '#4ADE80',
  red: '#EF4444',
  rule: 'rgba(138,148,166,0.28)',
} as const;

export const MARGIN = 64;
export const COL_W = (W - MARGIN * 2) / 12; // 12-column grid
export const MAX_TEXT_W = Math.round(W * 0.75); // 810
// Platform UI keep-out zones for text.
export const SAFE = {top: 220, bottom: 380, right: 120};

export const FONT = {
  bold: 'IBM Plex Sans JP',
  num: 'IBM Plex Sans JP Semi',
  serif: 'Libre Baskerville',
};

// ease-out cubic: no overshoot by construction.
export const ease = Easing.out(Easing.cubic);

/** 0→1 over `dur` frames starting at `start`, eased, clamped (never overshoots). */
export const prog = (frame: number, start: number, dur = 12) =>
  interpolate(frame, [start, start + dur], [0, 1], {
    easing: ease,
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

export const yen = (n: number) => Math.round(n).toLocaleString('en-US');
