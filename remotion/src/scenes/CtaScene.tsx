import React from 'react';
import {Body, Scene} from '../components/Frame';
import {Reveal} from '../components/Reveal';
import {C, FONT} from '../theme';

export const CtaScene: React.FC = () => (
  <Scene>
    <Body>
      <Reveal>
        <div style={{fontFamily: FONT.bold, fontSize: 84, lineHeight: 1.35, color: C.text}}>
          毎日1分で、
          <br />
          お金の基礎を。
        </div>
      </Reveal>
      <Reveal at={14}>
        <div style={{marginTop: 56, display: 'inline-block', alignSelf: 'flex-start', border: `3px solid ${C.gold}`, padding: '24px 48px', fontFamily: FONT.bold, fontSize: 48, color: C.gold}}>
          フォローして続きを見る
        </div>
      </Reveal>
      <Reveal at={30}>
        <div style={{marginTop: 64, fontFamily: FONT.bold, fontSize: 30, lineHeight: 1.7, color: C.second}}>
          年3%は仮定の試算で、将来の成果を保証するものではありません。投資には元本割れの可能性があります。
        </div>
      </Reveal>
    </Body>
  </Scene>
);
