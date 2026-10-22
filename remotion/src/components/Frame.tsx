import React from 'react';
import {AbsoluteFill, useCurrentFrame} from 'remotion';
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
          <div style={{width: 10, height: 36, background: C.gold}} />
          <div style={{color: C.gold, fontSize: 36, letterSpacing: 4}}>{label}</div>
        </div>
        <div style={{color: C.second, fontSize: 32, fontFamily: FONT.num}}>
          {String(index).padStart(2, '0')} / {String(total).padStart(2, '0')}
        </div>
      </div>
      <div style={{marginTop: 20, height: 2, background: C.rule, position: 'relative'}}>
        <div style={{position: 'absolute', left: 0, top: 0, height: 2, width: `${pct * 100}%`, background: C.gold}} />
      </div>
    </div>
  );
};

export const Scene: React.FC<{children: React.ReactNode}> = ({children}) => (
  <AbsoluteFill style={{background: C.bg, width: W, height: H}}>{children}</AbsoluteFill>
);

/** Content region inside margin + platform keep-out zones. */
export const Body: React.FC<{children: React.ReactNode; style?: React.CSSProperties}> = ({children, style}) => (
  <div
    style={{
      position: 'absolute',
      left: MARGIN,
      top: 300,
      width: 810, // 75% max text width
      height: 1920 - 300 - 380,
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'center',
      ...style,
    }}
  >
    {children}
  </div>
);

export const useGlobalFrame = (offset: number) => useCurrentFrame() + offset;
