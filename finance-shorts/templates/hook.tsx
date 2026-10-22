import React from 'react';
import {useCurrentFrame} from 'remotion';
import {Body, Scene} from '../src/components/Frame';
import {Reveal} from '../src/components/Reveal';
import {C, FONT, prog} from '../src/theme';

const G: React.FC<{children: React.ReactNode}> = ({children}) => <span style={{color: C.gold}}>{children}</span>;

export const HookScene: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <Scene>
      <Body style={{paddingTop: 160}}>
        <div style={{height: 3, width: 160 * prog(f, 0, 12), background: C.gold, marginBottom: 56}} />
        <Reveal at={4}>
          <div style={{fontFamily: FONT.bold, fontWeight: 700, fontSize: 96, lineHeight: 1.3, whiteSpace: 'nowrap', color: C.text}}>
            毎月<G>3万円</G>を、
            <br />
            <G>20年</G>続けると。
          </div>
        </Reveal>
        <Reveal at={22}>
          <div style={{fontFamily: FONT.bold, fontSize: 48, color: C.second, marginTop: 64, lineHeight: 1.5}}>
            年3%で積み立てた場合の試算
          </div>
        </Reveal>
      </Body>
    </Scene>
  );
};
