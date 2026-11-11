import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useData } from '../../context/DataContext';
import { Card, CardHeader, CardBody } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { BookOpen, Clock, Sparkles, CheckCircle2 } from 'lucide-react';

export const CurriculumOversight: React.FC = () => {
  const { curriculumDays, lostTeachingDays } = useData();
  const navigate = useNavigate();

  const subjects = [
    { name: 'Mathematics', code: 'MATH-8', completedDays: 104, totalDays: 180, teacher: 'Vikram Sengupta', status: 'Time-Aware Compaction Applied' },
    { name: 'Science & Discovery', code: 'SCI-8', completedDays: 98, totalDays: 180, teacher: 'Vikram Sengupta', status: 'On Track' },
    { name: 'English Communication', code: 'ENG-8', completedDays: 110, totalDays: 180, teacher: 'Anjali Roy', status: 'On Track' },
    { name: 'Social Studies & Civics', code: 'SST-8', completedDays: 92, totalDays: 180, teacher: 'Anjali Roy', status: 'Pacing Warning' },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white p-5 rounded-2xl border border-surface-border shadow-subtle flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-navy-900 tracking-tight">Curriculum Completion & Subject Oversight</h1>
          <p className="text-xs text-content-secondary mt-0.5">
            Monitor syllabus pacing, competency coverage, and time-aware compaction across all disciplines
          </p>
        </div>

        <Button
          variant="teal"
          size="sm"
          onClick={() => navigate('/teacher/time-aware')}
          icon={<Clock className="w-4 h-4" />}
        >
          Time-Aware Pacing Center
        </Button>
      </div>

      {/* Subject Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {subjects.map((sub) => {
          const pct = Math.round((sub.completedDays / sub.totalDays) * 100);
          return (
            <Card key={sub.code}>
              <CardHeader
                title={sub.name}
                subtitle={`Code: ${sub.code} • Lead: ${sub.teacher}`}
                action={
                  <Badge
                    variant={sub.status.includes('Warning') ? 'warning' : 'teal'}
                    size="sm"
                  >
                    {sub.status}
                  </Badge>
                }
              />
              <CardBody className="space-y-4 text-xs">
                <div>
                  <div className="flex justify-between items-center mb-1 font-semibold text-content-secondary">
                    <span>Syllabus Progression</span>
                    <span className="text-navy-900">{sub.completedDays} / {sub.totalDays} Days ({pct}%)</span>
                  </div>
                  <div className="h-3 w-full bg-surface-bg rounded-full overflow-hidden border border-surface-border">
                    <div
                      style={{ width: `${pct}%` }}
                      className={`h-full rounded-full transition-all ${
                        pct > 55 ? 'bg-teal-500' : 'bg-amber-500'
                      }`}
                    />
                  </div>
                </div>

                <div className="p-3 bg-surface-bg rounded-xl border border-surface-border grid grid-cols-2 gap-2">
                  <div>
                    <span className="text-[10px] text-content-muted block uppercase">Protected Core</span>
                    <span className="font-bold text-teal-800">108 Days Protected</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-content-muted block uppercase">Flipped / Supp.</span>
                    <span className="font-bold text-amber-800">72 Days Flexible</span>
                  </div>
                </div>
              </CardBody>
            </Card>
          );
        })}
      </div>
    </div>
  );
};

