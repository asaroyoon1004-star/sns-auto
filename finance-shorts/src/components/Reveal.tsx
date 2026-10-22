import React from 'react';
import {useCurrentFrame} from 'remotion';
import {prog} from '../theme';

/** opacity + translateY only, 12 frames (0.4s), ease-out cubic. */
export const Reveal: React.FC<{at?: number; dy?: number; children: React.ReactNode; style?: React.CSSProperties}> = ({
  at = 0,
  dy = 36,
  children,
  style,
}) => {
  const p = prog(useCurrentFrame(), at, 12);
  return <div style={{opacity: p, transform: `translateY(${(1 - p) * dy}px)`, ...style}}>{children}</div>;
};
