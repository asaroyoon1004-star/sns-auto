import React from 'react';
import {useCurrentFrame} from 'remotion';
import {Body, Scene} from '../components/Frame';
import {Reveal} from '../components/Reveal';
import {series, toMan} from '../data';
import {C, FONT, prog} from '../theme';

const CW = 810;
const CH = 600;
const PAD = {t: 24, b: 64};
const TICKS = [0, 500, 1000]; // 万円

export const ChartScene: React.FC = () => {
  const f = useCurrentFrame();
  const maxMan = 1000;
  const x = (y: number) => (y / 20) * CW;
  const yy = (man: number) => PAD.t + (1 - man / maxMan) * (CH - PAD.t - PAD.b);
  const pts = (k: 'balance' | 'principal') => series.map((s) => [x(s.year), yy(toMan(s[k]))] as const);
  const line = (a: readonly (readonly [number, number])[]) => a.map(([px, py], i) => `${i ? 'L' : 'M'}${px.toFixed(1)},${py.toFixed(1)}`).join(' ');
  const bal = pts('balance');
  const pri = pts('principal');
  const draw = prog(f, 12, 60);
  const last = series[series.length - 1];
  const [ex, ey] = bal[bal.length - 1];
  const gapArea = `${line(bal)} L${pri[pri.length - 1][0]},${pri[pri.length - 1][1]} ${[...pri].reverse().map(([px, py]) => `L${px.toFixed(1)},${py.toFixed(1)}`).join(' ')} Z`;
  return (
    <Scene>
      <Body>
        <Reveal>
          <div style={{fontFamily: FONT.bold, fontSize: 64, color: C.text, marginBottom: 40, lineHeight: 1.3}}>差を生むのは、時間。</div>
        </Reveal>
        <svg width={CW} height={CH} style={{display: 'block', overflow: 'visible'}}>
          {TICKS.map((t) => (
            <g key={t}>
              <line x1={0} x2={CW} y1={yy(t)} y2={yy(t)} stroke={C.rule} strokeWidth={2} />
              {t > 0 && <text x={0} y={yy(t) - 12} fill={C.second} fontSize={30} fontFamily={FONT.num}>
                {t.toLocaleString('en-US')}万円
              </text>}
            </g>
          ))}
          {/* flat tint between principal and balance = what time added */}
          <path d={gapArea} fill={C.gold} opacity={0.12 * prog(f, 60, 12)} />
          <path d={line(pri)} fill="none" stroke={C.second} strokeWidth={4} strokeDasharray="12 10" opacity={draw} />
          <path d={line(bal)} fill="none" stroke={C.gold} strokeWidth={8} strokeLinejoin="round" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - draw} />
          {[0, 10, 20].map((y) => (
            <text key={y} x={x(y)} y={CH - 12} fill={C.second} fontSize={34} fontFamily={FONT.num} textAnchor={y === 0 ? 'start' : y === 20 ? 'end' : 'middle'}>
              {y}年
            </text>
          ))}
          <g opacity={prog(f, 72, 12)}>
            <circle cx={ex} cy={ey} r={12} fill={C.gold} />
            <text x={ex} y={ey - 28} fill={C.gold} fontSize={44} fontFamily={FONT.num} fontWeight={600} textAnchor="end">
              {Math.round(toMan(last.balance))}万円
            </text>
          </g>
        </svg>
        <Reveal at={78} style={{marginTop: 36, display: 'flex', gap: 56, fontFamily: FONT.bold, fontSize: 36, alignItems: 'center'}}>
          <span style={{display: 'flex', alignItems: 'center', gap: 16, color: C.text}}>
            <span style={{width: 40, height: 6, background: C.gold}} />積立残高
          </span>
          <span style={{display: 'flex', alignItems: 'center', gap: 16, color: C.second}}>
            <span style={{width: 40, height: 0, borderTop: `4px dashed ${C.second}`}} />元本
          </span>
        </Reveal>
      </Body>
    </Scene>
  );
};
