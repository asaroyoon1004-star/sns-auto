import React from 'react';
import {Body, Scene} from '../src/components/Frame';
import {CountUp} from '../src/components/CountUp';
import {Reveal} from '../src/components/Reveal';
import {FINAL, PRINCIPAL, toMan} from '../src/data';
import {C, FONT} from '../src/theme';

const PCT = Math.round((FINAL / PRINCIPAL - 1) * 100); // vs. principal, computed

export const HeroNumberScene: React.FC = () => (
  <Scene>
    <Body>
      <Reveal>
        <div style={{fontFamily: FONT.bold, fontSize: 52, color: C.second, marginBottom: 36}}>20年後の積立残高</div>
      </Reveal>
      <div style={{background: C.surface, borderTop: `3px solid ${C.gold}`, padding: '64px 48px 56px', width: 810, boxSizing: 'border-box'}}>
        <CountUp to={Math.round(toMan(FINAL))} at={10} dur={36} unit="万円" size={220} unitSize={80} color={C.gold} />
        <Reveal at={44} dy={16}>
          <div style={{display: 'flex', alignItems: 'baseline', gap: 20, marginTop: 40, borderTop: `2px solid ${C.rule}`, paddingTop: 32}}>
            <span style={{fontFamily: FONT.num, fontWeight: 600, fontSize: 56, color: C.green}}>▲ {PCT}%</span>
            <span style={{fontFamily: FONT.bold, fontSize: 38, color: C.second}}>元本に対して</span>
          </div>
        </Reveal>
      </div>
    </Body>
  </Scene>
);
