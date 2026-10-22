import React from 'react';
import {Sequence, useCurrentFrame} from 'remotion';
import {Chrome} from './components/Frame';
import {BreakdownScene} from './scenes/BreakdownScene';
import {ChartScene} from './scenes/ChartScene';
import {CtaScene} from './scenes/CtaScene';
import {HeroNumberScene} from './scenes/HeroNumberScene';
import {HookScene} from './scenes/HookScene';
import {C, FPS} from './theme';

// [component, label, seconds] — sums to 25s.
const SCENES = [
  {C: HookScene, label: 'SIMULATION', sec: 3},
  {C: HeroNumberScene, label: 'RESULT', sec: 6},
  {C: ChartScene, label: 'GROWTH', sec: 7},
  {C: BreakdownScene, label: 'BREAKDOWN', sec: 5},
  {C: CtaScene, label: 'FOLLOW', sec: 4},
];

export const FinanceShort: React.FC = () => {
  const frame = useCurrentFrame();
  let start = 0;
  let active = 0;
  const seqs = SCENES.map((s, i) => {
    const from = start;
    const dur = s.sec * FPS;
    start += dur;
    if (frame >= from) active = i;
    return (
      <Sequence key={s.label} from={from} durationInFrames={dur}>
        <s.C />
      </Sequence>
    );
  });
  return (
    <div style={{background: C.bg, width: '100%', height: '100%'}}>
      {seqs}
      <Chrome label={SCENES[active].label} index={active + 1} total={SCENES.length} globalFrame={frame} />
    </div>
  );
};
