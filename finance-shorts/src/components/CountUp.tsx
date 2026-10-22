import React from 'react';
import {useCurrentFrame} from 'remotion';
import {FONT, prog} from '../theme';

/** Smooth ease-out count-up (no overshoot). 24 frames by default so it reads as a calm roll, not a flash. */
export const CountUp: React.FC<{
  to: number;
  at?: number;
  dur?: number;
  prefix?: string;
  unit?: string;
  size: number;
  unitSize?: number;
  color: string;
}> = ({to, at = 0, dur = 24, prefix = '', unit = '', size, unitSize, color}) => {
  const v = Math.round(to * prog(useCurrentFrame(), at, dur));
  return (
    <div style={{display: 'flex', alignItems: 'baseline', whiteSpace: 'nowrap', color}}>
      <span style={{fontFamily: FONT.num, fontWeight: 600, fontSize: size, fontVariantNumeric: 'tabular-nums', lineHeight: 1}}>
        {prefix}
        {v.toLocaleString('en-US')}
      </span>
      {unit && (
        <span style={{fontFamily: FONT.bold, fontWeight: 700, fontSize: unitSize ?? size * 0.4, marginLeft: 14}}>{unit}</span>
      )}
    </div>
  );
};
