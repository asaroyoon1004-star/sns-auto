import React from 'react';
import {Body, Scene} from '../components/Frame';
import {CountUp} from '../components/CountUp';
import {Reveal} from '../components/Reveal';
import {FINAL, toMan} from '../data';
import {C, FONT} from '../theme';

export const HeroNumberScene: React.FC = () => (
  <Scene>
    <Body>
      <Reveal>
        <div style={{fontFamily: FONT.bold, fontSize: 48, color: C.second, marginBottom: 40}}>20年後の積立残高</div>
      </Reveal>
      <div style={{background: C.surface, borderLeft: `6px solid ${C.gold}`, padding: '56px 48px'}}>
        <CountUp to={Math.round(toMan(FINAL))} at={10} dur={36} unit="万円" size={200} unitSize={72} color={C.gold} />
      </div>
      <Reveal at={40}>
        <div style={{fontFamily: FONT.bold, fontSize: 40, color: C.second, marginTop: 40, lineHeight: 1.6}}>
          毎月3万円・年3%・月次複利の仮定
        </div>
      </Reveal>
    </Body>
  </Scene>
);
