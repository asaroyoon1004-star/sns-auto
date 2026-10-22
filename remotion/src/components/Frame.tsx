import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {C, DURATION, FONT, H, MARGIN, W} from '../theme';

/** Persistent chrome: marker + label, progress rule. Lives at the top, inside the safe area. */
export const Chrome: React.FC<{label: string; index: number; total: number; globalFrame: number}> = ({
  label,
  index,
  total,
  globalFrame,
}) => {
  const pct = Math.min(1, globalFrame / DURATION);
  return (
    <div style={{position: 'absolute', left: MARGIN, right: MARGIN, top: 120, fontFamily: FONT.bold}}>
      <div style={{display: 'flex', alignItems: 'center', justifyContent: 'space-between'}}>
        <div style={{display: 'flex', alignItems: 'center', gap: 16}}>
          <div style={{width: 10, height: 40, background: C.gold}} />
          <div style={{color: C.gold, fontFamily: FONT.serif, fontSize: 38, letterSpacing: 6}}>{label}</div>
        </div>
        <div style={{color: C.second, fontSize: 36, fontFamily: FONT.num}}>
          {String(index).padStart(2, '0')} / {String(total).padStart(2, '0')}
        </div>
      </div>
      <div style={{marginTop: 20, height: 2, background: C.rule, position: 'relative'}}>
        <div style={{position: 'absolute', left: 0, top: 0, height: 2, width: `${pct * 100}%`, background: C.gold}} />
      </div>
    </div>
  );
};

/** Scene wrapper: 12-frame opacity-only exit so cuts read as a calm dissolve, not a jump. */
export const Scene: React.FC<{children: React.ReactNode}> = ({children}) => {
  const f = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const out = interpolate(f, [durationInFrames - 12, durationInFrames], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  return (
    <AbsoluteFill style={{background: C.bg, width: W, height: H, opacity: out}}>
      {children}
    </AbsoluteFill>
  );
};

/** Bloomberg-style data footer: states the assumptions on every frame. Sits just above the platform UI zone. */
export const Footer: React.FC = () => (
  <div style={{position: 'absolute', left: MARGIN, width: 810, top: 1920 - 380 - 150, fontFamily: FONT.bold}}>
    <div style={{height: 2, background: C.rule, marginBottom: 24}} />
    <div style={{display: 'flex', gap: 28, alignItems: 'baseline'}}>
      <span style={{fontFamily: FONT.serif, fontStyle: 'normal', fontSize: 28, letterSpacing: 4, color: C.gold}}>ASSUMPTION</span>
      <span style={{fontSize: 30, color: C.second}}>毎月3万円・年3.0%・月次複利・20年</span>
    </div>
  </div>
);

/** Content region inside margin + platform keep-out zones. */
export const Body: React.FC<{children: React.ReactNode; style?: React.CSSProperties}> = ({children, style}) => (
  <div
    style={{
      position: 'absolute',
      left: MARGIN,
      top: 300,
      width: 810, // 75% max text width
      height: 1920 - 300 - 380 - 170, // leaves room for the assumption footer
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'flex-start',
      paddingTop: 80,
      ...style,
    }}
  >
    {children}
  </div>
);

export const useGlobalFrame = (offset: number) => useCurrentFrame() + offset;
