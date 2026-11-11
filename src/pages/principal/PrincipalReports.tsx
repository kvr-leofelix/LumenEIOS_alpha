import React, { useState } from 'react';
import { useData } from '../../context/DataContext';
import { Card, CardHeader, CardBody } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { FileSpreadsheet, Download, Printer, CheckCircle2 } from 'lucide-react';

export const PrincipalReports: React.FC = () => {
  const { students, schools } = useData();
  const [toast, setToast] = useState<string | null>(null);

  const handleDownload = (reportName: string) => {
    setToast(`Generating printable PDF for "${reportName}"...`);
    setTimeout(() => {
      window.print();
      setToast(null);
    }, 800);
  };

  return (
    <div className="space-y-6">
      {/* Toast Notification */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-50 bg-navy-900 text-white px-4 py-3 rounded-xl shadow-modal border border-teal-500/40 text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-teal-400" />
          <span>{toast}</span>
        </div>
      )}

      {/* Header */}
      <div className="bg-white p-5 rounded-2xl border border-surface-border shadow-subtle flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-navy-900 tracking-tight">Institutional & NEP Governance Reports</h1>
          <p className="text-xs text-content-secondary mt-0.5">
            Export certified competency transcripts, teaching-day loss audits, and student growth summaries
          </p>
        </div>

        <Badge variant="teal" size="sm">
          NEP 2020 Compliant Format
        </Badge>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <Card className="flex flex-col justify-between">
          <CardHeader
            title="School Competency Card"
            subtitle="Campus Q2 Comprehensive Evaluation"
          />
          <CardBody className="space-y-3 text-xs">
            <p className="text-content-secondary leading-relaxed">
              Consolidated 4-dimensional score sheets (LU, CU, AU, CT) across all classes with year-on-year baseline deltas.
            </p>
            <div className="pt-3 border-t border-surface-border">
              <Button
                variant="outline"
                size="sm"
                className="w-full"
                onClick={() => handleDownload('Campus Competency Summary')}
                icon={<Download className="w-3.5 h-3.5" />}
              >
                Export Report PDF
              </Button>
            </div>
          </CardBody>
        </Card>

        <Card className="flex flex-col justify-between">
          <CardHeader
            title="Teaching Days Disruption Audit"
            subtitle="Instructional Calendar Verification"
          />
          <CardBody className="space-y-3 text-xs">
            <p className="text-content-secondary leading-relaxed">
              Official audit log of 16 lost instructional days, citing election, census, and climatic disaster directives.
            </p>
            <div className="pt-3 border-t border-surface-border">
              <Button
                variant="outline"
                size="sm"
                className="w-full"
                onClick={() => handleDownload('Instructional Day Loss Audit')}
                icon={<Download className="w-3.5 h-3.5" />}
              >
                Export Audit PDF
              </Button>
            </div>
          </CardBody>
        </Card>

        <Card className="flex flex-col justify-between">
          <CardHeader
            title="Syllabus Compacting Certificate"
            subtitle="60/40 Strategy Approval Record"
          />
          <CardBody className="space-y-3 text-xs">
            <p className="text-content-secondary leading-relaxed">
              Formal record verifying that 100% of core competencies were protected while 14 supplementary topics were flipped.
            </p>
            <div className="pt-3 border-t border-surface-border">
              <Button
                variant="outline"
                size="sm"
                className="w-full"
                onClick={() => handleDownload('Syllabus Compacting Certification')}
                icon={<Printer className="w-3.5 h-3.5" />}
              >
                Print Certification
              </Button>
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  );
};

