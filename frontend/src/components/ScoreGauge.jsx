import { useMemo } from 'react';
import { getGradeColor } from '../utils/helpers';

export default function ScoreGauge({ score, grade, size = 180, strokeWidth = 10 }) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;

  const { offset, color } = useMemo(() => {
    const pct = Math.min(100, Math.max(0, score)) / 100;
    return {
      offset: circumference * (1 - pct),
      color: getGradeColor(grade),
    };
  }, [score, grade, circumference]);

  return (
    <div className="score-gauge" style={{ width: size, height: size }}>
      <svg width={size} height={size}>
        <circle
          className="gauge-bg"
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={strokeWidth}
        />
        <circle
          className="gauge-fill"
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={strokeWidth}
          stroke={color}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ filter: `drop-shadow(0 0 8px ${color}40)` }}
        />
      </svg>
      <div className="score-value">
        <span className="score-number" style={{ color }}>{Math.round(score)}</span>
        <span className="score-label">out of 100</span>
      </div>
    </div>
  );
}
