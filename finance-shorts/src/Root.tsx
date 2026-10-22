import React from 'react';
import {Composition} from 'remotion';
import './fonts';
import {FinanceShort} from './FinanceShort';
import {DURATION, FPS, H, W} from './theme';

export const Root: React.FC = () => (
  <Composition id="FinanceShort" component={FinanceShort} durationInFrames={DURATION} fps={FPS} width={W} height={H} />
);
