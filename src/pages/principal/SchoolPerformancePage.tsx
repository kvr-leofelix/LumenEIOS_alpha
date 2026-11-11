import React from 'react';
import { useAuth } from '../../context/AuthContext';
import { SchoolPerformance } from '../../components/school/SchoolPerformance';

export const SchoolPerformancePage: React.FC = () => {
  const { currentUser } = useAuth();
  const schoolId = currentUser?.schoolId || '';

  return (
    <div className="space-y-6">
      <div className="bg-white p-5 rounded-2xl border border-surface-border shadow-subtle">
        <h1 className="text-xl font-bold text-navy-900 tracking-tight">School performance</h1>
        <p className="mt-1 text-sm text-content-secondary">
          Benchmark scores for the school you lead. Click a student’s name to open their monthly performance.
        </p>
      </div>
      <SchoolPerformance schoolId={schoolId} />
    </div>
  );
};
