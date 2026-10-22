// Simulation: monthly contribution compounded monthly. Assumption, not a forecast.
export const MONTHLY = 30000;
export const YEARS = 20;
export const RATE = 0.03;

export const balanceAt = (months: number) => {
  const r = RATE / 12;
  return MONTHLY * ((Math.pow(1 + r, months) - 1) / r);
};

export const PRINCIPAL = MONTHLY * 12 * YEARS; // 7,200,000
export const FINAL = balanceAt(YEARS * 12); // ~9.85M
export const GAIN = FINAL - PRINCIPAL;
export const toMan = (yen: number) => yen / 10000;

/** yearly series for the chart */
export const series = Array.from({length: YEARS + 1}, (_, y) => ({
  year: y,
  balance: y === 0 ? 0 : balanceAt(y * 12),
  principal: MONTHLY * 12 * y,
}));
