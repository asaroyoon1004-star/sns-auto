import React from 'react';
import {useCurrentFrame} from 'remotion';
import {Body, Scene} from '../components/Frame';
import {CountUp} from '../components/CountUp';
import {Reveal} from '../components/Reveal';
import {FINAL, GAIN, PRINCIPAL, toMan} from '../data';
import {C, FONT, prog} from '../theme';

const Row: React.FC<{at: number; label: string; to: number; color: string; prefix?: string; last?: boolean}> = ({at, label, to, color, prefix, last}) => (
  <Reveal at={at}>
    <div style={{padding: '36px 0', borderTop: `2px solid ${last ? C.gold : C.rule}`}}>
      <div style={{fontFamily: FONT.bold, fontSize: 42, color: C.second, marginBottom: 20}}>{label}</div>
      <CountUp to={Math.round(toMan(to))} at={at + 4} dur={30} prefix={prefix} unit="万円" size={120} unitSize={52} color={color} />
    </div>
  </Reveal>
);

/** Flat share bar: principal vs. gain, sized from the real numbers. */
const ShareBar: React.FC = () => {
  const p = prog(useCurrentFrame(), 72, 24);
  const wP = (PRINCIPAL / FINAL) * 810 * p;
  const wG = (GAIN / FINAL) * 810 * p;
  return (
    <div style={{display: 'flex', height: 20, width: 810, marginTop: 8}}>
      <div style={{width: wP, background: C.second}} />
      <div style={{width: wG, background: C.green}} />
    </div>
  );
};

export const BreakdownScene: React.FC = () => (
  <Scene>
    <Body style={{paddingTop: 40}}>
      <Row at={0} label="払い込んだ元本" to={PRINCIPAL} color={C.text} />
      <Row at={24} label="運用で増えた分（仮定）" to={GAIN} color={C.green} prefix="+" />
      <Row at={48} label="合計" to={FINAL} color={C.gold} last />
      <ShareBar />
    </Body>
  </Scene>
);
