import React from 'react';
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import { CompetencyScores } from '../../types';

interface CompetencyRadarChartProps {
  current: CompetencyScores;
  baseline?: CompetencyScores;
  benchmarkName?: string;
  height?: number;
}

export const CompetencyRadarChart: React.FC<CompetencyRadarChartProps> = ({
  current,
  baseline,
  benchmarkName = 'Baseline',
  height = 260,
}) => {
  const data = [
    {
      subject: 'Language (LU)',
      full: 'Language Understanding',
      Current: current.LU,
      ...(baseline ? { [benchmarkName]: baseline.LU } : {}),
    },
    {
      subject: 'Concept (CU)',
      full: 'Concept Understanding',
      Current: current.CU,
      ...(baseline ? { [benchmarkName]: baseline.CU } : {}),
    },
    {
      subject: 'Application (AU)',
      full: 'Application Understanding',
      Current: current.AU,
      ...(baseline ? { [benchmarkName]: baseline.AU } : {}),
    },
    {
      subject: 'Critical (CT)',
      full: 'Critical Thinking',
      Current: current.CT,
      ...(baseline ? { [benchmarkName]: baseline.CT } : {}),
    },
  ];

  return (
    <div style={{ width: '100%', height }}>
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart cx="50%" cy="50%" outerRadius="75%" data={data}>
          <PolarGrid stroke="#E1E7ED" />
          <PolarAngleAxis
            dataKey="subject"
            tick={{ fill: '#142A43', fontSize: 12, fontWeight: 500 }}
          />
          <PolarRadiusAxis angle={30} domain={[0, 100]} stroke="#CBD5E1" tick={{ fontSize: 10 }} />
          {baseline && (
            <Radar
              name={benchmarkName}
              dataKey={benchmarkName}
              stroke="#94A3B8"
              fill="#94A3B8"
              fillOpacity={0.2}
              strokeDasharray="4 4"
            />
          )}
          <Radar
            name="Current Mastery"
            dataKey="Current"
            stroke="#16A085"
            fill="#16A085"
            fillOpacity={0.45}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#FFFFFF',
              borderRadius: '8px',
              border: '1px solid #E1E7ED',
              boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)',
              fontSize: '12px',
            }}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
};

