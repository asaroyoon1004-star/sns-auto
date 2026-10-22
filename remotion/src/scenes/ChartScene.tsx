import React from 'react';
import {useCurrentFrame} from 'remotion';
import {Body, Scene} from '../components/Frame';
import {Reveal} from '../components/Reveal';
import {series, toMan} from '../data';
import {C, FONT, prog} from '../theme';

const CW = 810;
const CH = 640;
const PAD = {l: 0, r: 0, t: 24, b: 56};

export const ChartScene: React.FC = () => {
  const f = useCurrentFrame();
  const max = Math.max(...series.map((s) => s.balance)) * 1.05;
  const x = (y: number) => PAD.l + (y / 20) * (CW - PAD.l - PAD.r);
  const yy = (v: number) => PAD.t + (1 - v / max) * (CH - PAD.t - PAD.b);
  const path = (key: 'balance' | 'principal') =>
    series.map((s, i) => `${i ? 'L' : 'M'}${x(s.year).toFixed(1)},${yy(s[key]).toFixed(1)}`).join(' ');
  const draw = prog(f, 12, 60); // slow, eased line draw — never bounces
  const last = series[series.length - 1];
  return (
    <Scene>
      <Body>
        <Reveal>
          <div style={{fontFamily: FONT.bold, fontSize: 56, color: C.text, marginBottom: 36, lineHeight: 1.4}}>
            差を生むのは、時間。
          </div>
        </Reveal>
        <svg width={CW} height={CH} style={{display: 'block'}}>
          {[0, 0.25, 0.5, 0.75, 1].map((t) => (
            <line key={t} x1={0} x2={CW} y1={PAD.t + t * (CH - PAD.t - PAD.b)} y2={PAD.t + t * (CH - PAD.t - PAD.b)} stroke={C.rule} strokeWidth={1} />
          ))}
          <path d={path('principal')} fill="none" stroke={C.second} strokeWidth={4} strokeDasharray="10 10" opacity={draw} />
          <path d={path('balance')} fill="none" stroke={C.gold} strokeWidth={8} strokeLinejoin="round" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - draw} />
          {[0, 10, 20].map((y) => (
            <text key={y} x={Math.min(Math.max(x(y), 24), CW - 36)} y={CH - 12} fill={C.second} fontSize={30} fontFamily={FONT.num} textAnchor="middle">
              {y}年
            </text>
          ))}
        </svg>
        <div style={{display: 'flex', gap: 48, marginTop: 28, fontFamily: FONT.bold, fontSize: 34}}>
          <Reveal at={70}>
            <span style={{color: C.gold}}>━ 積立残高 {Math.round(toMan(last.balance))}万円</span>
          </Reveal>
          <Reveal at={78}>
            <span style={{color: C.second}}>╌ 元本 {Math.round(toMan(last.principal))}万円</span>
          </Reveal>
        </div>
      </Body>
    </Scene>
  );
};
