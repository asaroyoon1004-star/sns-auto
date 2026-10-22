import React from 'react';
import {Body, Scene} from '../components/Frame';
import {CountUp} from '../components/CountUp';
import {Reveal} from '../components/Reveal';
import {FINAL, GAIN, PRINCIPAL, toMan} from '../data';
import {C, FONT} from '../theme';

const Row: React.FC<{at: number; label: string; to: number; color: string; prefix?: string; last?: boolean}> = ({at, label, to, color, prefix, last}) => (
  <Reveal at={at}>
    <div style={{padding: '40px 0', borderTop: `2px solid ${last ? C.gold : C.rule}`}}>
      <div style={{fontFamily: FONT.bold, fontSize: 40, color: C.second, marginBottom: 20}}>{label}</div>
      <CountUp to={Math.round(toMan(to))} at={at + 4} dur={30} prefix={prefix} unit="万円" size={112} unitSize={48} color={color} />
    </div>
  </Reveal>
);

export const BreakdownScene: React.FC = () => (
  <Scene>
    <Body>
      <Row at={0} label="払い込んだ元本" to={PRINCIPAL} color={C.text} />
      <Row at={24} label="運用で増えた分（仮定）" to={GAIN} color={C.green} prefix="+" />
      <Row at={48} label="合計" to={FINAL} color={C.gold} last />
    </Body>
  </Scene>
);
