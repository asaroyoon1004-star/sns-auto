import React from 'react';
import {useCurrentFrame} from 'remotion';
import {Body, Scene} from '../components/Frame';
import {Reveal} from '../components/Reveal';
import {C, FONT, prog} from '../theme';

export const HookScene: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <Scene>
      <Body>
        <div style={{height: 3, width: 160 * prog(f, 0, 12), background: C.gold, marginBottom: 48}} />
        <Reveal at={4}>
          <div style={{fontFamily: FONT.bold, fontWeight: 700, fontSize: 104, lineHeight: 1.3, color: C.text}}>
            毎月3万円を、
            <br />
            20年続けると。
          </div>
        </Reveal>
        <Reveal at={22}>
          <div style={{fontFamily: FONT.bold, fontSize: 44, color: C.second, marginTop: 56, lineHeight: 1.5}}>
            年3%で積み立てた場合の試算
          </div>
        </Reveal>
      </Body>
    </Scene>
  );
};
