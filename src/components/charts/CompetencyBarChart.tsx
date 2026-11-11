import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

interface CompetencyBarChartProps {
  data: Array<{
    name: string;
    LU: number;
    CU: number;
    AU: number;
    CT: number;
  }>;
  height?: number;
}

export const CompetencyBarChart: React.FC<CompetencyBarChartProps> = ({
  data,
  height = 280,
}) => {
  return (
    <div style={{ width: '100%', height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          margin={{ top: 15, right: 15, left: -15, bottom: 5 }}
          barGap={3}
          barSize={14}
        >
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E1E7ED" />
          <XAxis
            dataKey="name"
            tick={{ fill: '#667085', fontSize: 11 }}
            axisLine={{ stroke: '#E1E7ED' }}
            tickLine={false}
          />
          <YAxis
            domain={[0, 100]}
            tick={{ fill: '#667085', fontSize: 11 }}
            axisLine={false}
            tickLine={false}
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
          <Legend
            verticalAlign="top"
            align="right"
            wrapperStyle={{ paddingBottom: '12px', fontSize: '11px' }}
          />
          <Bar dataKey="LU" name="LU (Language)" fill="#3B82F6" radius={[3, 3, 0, 0]} />
          <Bar dataKey="CU" name="CU (Concept)" fill="#10B981" radius={[3, 3, 0, 0]} />
          <Bar dataKey="AU" name="AU (Application)" fill="#F59E0B" radius={[3, 3, 0, 0]} />
          <Bar dataKey="CT" name="CT (Critical Thinking)" fill="#8B5CF6" radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};

