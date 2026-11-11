import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useData } from '../../context/DataContext';
import { KPICard } from '../../components/common/KPICard';
import { Card, CardHeader, CardBody } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { CompetencyBarChart } from '../../components/charts/CompetencyBarChart';
import { getTierBadge } from '../../lib/utils';
import {
  Building2,
  Users,
  GraduationCap,
  BookOpen,
  AlertTriangle,
  CheckCircle2,
  TrendingUp,
  PlusCircle,
  ExternalLink,
  Shield,
  Clock,
  Sparkles,
} from 'lucide-react';

export const AdminDashboard: React.FC = () => {
  const { schools, students, classes, auditLogs } = useData();
  const navigate = useNavigate();

  // Aggregate stats
  const totalSchools = schools.length;
  const totalStudents = schools.reduce((acc, s) => acc + s.studentCount, 0);
  const totalTeachers = schools.reduce((acc, s) => acc + s.teacherCount, 0);
  const activeClasses = schools.reduce((acc, s) => acc + s.classCount, 0);

  const highRiskSchools = schools.filter((s) => s.pacingRisk === 'high');

  // Chart data comparing school performance
  const schoolComparisonData = [
    { name: 'Sunrise Public', LU: 82, CU: 84, AU: 78, CT: 76 },
    { name: 'Green Valley', LU: 78, CU: 80, AU: 74, CT: 71 },
    { name: 'Pragati Govt', LU: 54, CU: 62, AU: 52, CT: 46 },
    { name: 'Vidya Niketan', LU: 75, CU: 76, AU: 70, CT: 68 },
    { name: 'Udaan Learning', LU: 51, CU: 58, AU: 48, CT: 43 },
  ];

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="bg-white p-5 rounded-2xl border border-surface-border shadow-subtle flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-navy-900 tracking-tight">
              Welcome, LEOFELIX
            </h1>
            <Badge variant="teal" size="sm">
              Directorate View
            </Badge>
          </div>
          <p className="text-xs text-content-secondary mt-1">
            Monitoring academic performance, infrastructure tiers, and instructional pacing across 5 partner campuses
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate('/admin/schools')}
            icon={<Building2 className="w-4 h-4" />}
          >
            Schools Directory
          </Button>
          <Button
            variant="teal"
            size="sm"
            onClick={() => navigate('/admin/schools')}
            icon={<PlusCircle className="w-4 h-4" />}
          >
            Onboard Campus
          </Button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          title="Affiliated Schools"
          value={totalSchools}
          subtitle="3 Private • 2 Government"
          icon={<Building2 className="w-5 h-5 text-navy-800" />}
          iconBg="bg-navy-50"
          onClick={() => navigate('/admin/schools')}
        />
        <KPICard
          title="Total Student Reach"
          value={totalStudents.toLocaleString()}
          subtitle="Active NEP Learners"
          icon={<GraduationCap className="w-5 h-5 text-teal-600" />}
          iconBg="bg-teal-50"
        />
        <KPICard
          title="Instructional Faculty"
          value={totalTeachers}
          subtitle="Across all infrastructure tiers"
          icon={<Users className="w-5 h-5 text-blue-600" />}
          iconBg="bg-blue-50"
          onClick={() => navigate('/admin/users')}
        />
        <KPICard
          title="Pacing Intervention Needed"
          value={`${highRiskSchools.length} Schools`}
          subtitle="Pragati & Udaan Gov Campuses"
          icon={<AlertTriangle className="w-5 h-5 text-rose-600" />}
          iconBg="bg-rose-50"
          trend={{ value: 'Urgent', isPositive: false, label: 'Compacting Req.' }}
        />
      </div>

      {/* School Comparison Chart */}
      <Card>
        <CardHeader
          title="Multi-School Competency Benchmark Comparison"
          subtitle="Comparative baseline across Language (LU), Concept (CU), Application (AU), and Critical Thinking (CT)"
          action={
            <Badge variant="teal" size="sm">
              NEP 2020 Metrics
            </Badge>
          }
        />
        <CardBody>
          <CompetencyBarChart data={schoolComparisonData} height={290} />
          <div className="mt-3 p-3 bg-surface-bg rounded-xl border border-surface-border text-xs text-content-secondary leading-relaxed flex items-start gap-2">
            <Sparkles className="w-4 h-4 text-teal-600 shrink-0 mt-0.5" />
            <span>
              <strong>Key Finding:</strong> Government rural campuses (Pragati Govt & Udaan Learning) show solid Concept Understanding (CU: 58-62%) but demonstrate significant Language Understanding gaps (LU: 51-54%) in English-medium textbooks. The Time-Aware Engine recommends vernacular scaffolding for mathematical word problems.
            </span>
          </div>
        </CardBody>
      </Card>

      {/* Campus Directory & Pacing Health */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left (2 cols): Campuses List */}
        <Card className="lg:col-span-2">
          <CardHeader
            title="School Network Directory"
            subtitle="Infrastructure Tiers & Academic Operating Status"
            action={
              <Button
                variant="outline"
                size="sm"
                onClick={() => navigate('/admin/schools')}
                icon={<ExternalLink className="w-3.5 h-3.5" />}
              >
                Manage All
              </Button>
            }
          />
          <CardBody className="p-0">
            <div className="divide-y divide-surface-border">
              {schools.map((school) => {
                const tier = getTierBadge(school.infrastructureTier);
                return (
                  <button
                    key={school.id}
                    type="button"
                    onClick={() => navigate(`/admin/schools?school=${school.id}`)}
                    className="w-full text-left p-4 hover:bg-surface-bg/50 transition-colors flex items-center justify-between gap-3 text-xs"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-navy-900 text-sm">{school.name}</span>
                        <span className={`px-2 py-0.5 rounded text-[11px] font-semibold border ${tier.color}`}>
                          {tier.label}
                        </span>
                      </div>
                      <p className="text-content-secondary text-[11px] mt-0.5">
                        {school.location}, {school.state} • Principal: {school.principalName}
                      </p>
                      <div className="flex items-center gap-3 mt-1.5 text-[11px] text-content-muted">
                        <span>{school.studentCount} Students</span>
                        <span>•</span>
                        <span>{school.teacherCount} Teachers</span>
                        <span>•</span>
                        <span>{school.classCount} Sections</span>
                      </div>
                    </div>

                    <div className="text-right shrink-0">
                      <span
                        className={`inline-block px-2.5 py-1 rounded-full text-[11px] font-semibold ${
                          school.pacingRisk === 'high'
                            ? 'bg-rose-100 text-rose-800'
                            : school.pacingRisk === 'medium'
                            ? 'bg-amber-100 text-amber-800'
                            : 'bg-emerald-100 text-emerald-800'
                        }`}
                      >
                        {school.pacingRisk === 'high'
                          ? 'High Pacing Risk'
                          : school.pacingRisk === 'medium'
                          ? 'Moderate Pacing'
                          : 'On Track'}
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
          </CardBody>
        </Card>

        {/* Right (1 col): Recent Audit Activity */}
        <Card>
          <CardHeader
            title="Recent Platform Activity"
            subtitle="Immutable Audit & Security Trail"
            action={
              <Button
                variant="outline"
                size="sm"
                onClick={() => navigate('/admin/audit-logs')}
                icon={<Clock className="w-3.5 h-3.5" />}
              >
                Full Log
              </Button>
            }
          />
          <CardBody className="p-0">
            <div className="divide-y divide-surface-border max-h-80 overflow-y-auto">
              {auditLogs.slice(0, 5).map((log) => (
                <div key={log.id} className="p-3 text-xs hover:bg-surface-bg/40 transition-colors">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="font-semibold text-navy-900">{log.action}</span>
                    <span className="text-content-muted font-mono">{log.timestamp.substring(11)}</span>
                  </div>
                  <p className="text-content-secondary text-[11px] mt-0.5 line-clamp-2 leading-relaxed">
                    {log.details}
                  </p>
                  <p className="text-[10px] text-teal-700 font-medium mt-1">By: {log.userName}</p>
                </div>
              ))}
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  );
};
