import React, { useState } from 'react';
import { useData } from '../../context/DataContext';
import { Card, CardHeader, CardBody } from '../../components/common/Card';
import { Badge } from '../../components/common/Badge';
import { SearchInput } from '../../components/common/SearchInput';
import { ShieldCheck, Filter, Clock } from 'lucide-react';

export const AuditLogs: React.FC = () => {
  const { auditLogs } = useData();
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('all');

  const filteredLogs = auditLogs.filter((log) => {
    const matchesSearch =
      log.action.toLowerCase().includes(search.toLowerCase()) ||
      log.details.toLowerCase().includes(search.toLowerCase()) ||
      log.userName.toLowerCase().includes(search.toLowerCase());
    const matchesCat = categoryFilter === 'all' || log.category === categoryFilter;
    return matchesSearch && matchesCat;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white p-5 rounded-2xl border border-surface-border shadow-subtle flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-navy-900 tracking-tight">Security & Pedagogical Audit Trail</h1>
          <p className="text-xs text-content-secondary mt-0.5">
            Immutable log of syllabus compression approvals, lost days recorded, and baseline recalibrations
          </p>
        </div>

        <Badge variant="teal" size="sm">
          {auditLogs.length} Events Logged
        </Badge>
      </div>

      {/* Filters */}
      <Card>
        <CardBody className="p-4 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 text-xs">
          <SearchInput
            value={search}
            onChange={setSearch}
            placeholder="Search action or operator..."
            className="sm:w-72"
          />

          <div className="flex items-center gap-2">
            <span className="font-semibold text-content-secondary">Category:</span>
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="px-3 py-1.5 bg-surface-bg border border-surface-border rounded-lg text-xs"
            >
              <option value="all">All Categories</option>
              <option value="curriculum">Curriculum & Time-Aware</option>
              <option value="assessment">Assessments & Scans</option>
              <option value="system">System & Campuses</option>
            </select>
          </div>
        </CardBody>
      </Card>

      {/* Logs Table */}
      <Card>
        <CardBody className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-surface-bg/80 text-content-secondary border-b border-surface-border">
                <tr>
                  <th className="py-3 px-4">Timestamp</th>
                  <th className="py-3 px-4">Action Event</th>
                  <th className="py-3 px-3">Category</th>
                  <th className="py-3 px-4">Operator / Teacher</th>
                  <th className="py-3 px-4">Technical Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-border bg-white">
                {filteredLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-surface-bg/40 transition-colors">
                    <td className="py-3 px-4 font-mono text-content-muted whitespace-nowrap">
                      {log.timestamp}
                    </td>
                    <td className="py-3 px-4 font-bold text-navy-900">{log.action}</td>
                    <td className="py-3 px-3">
                      <span className="px-2 py-0.5 rounded text-[11px] font-semibold uppercase tracking-wider bg-surface-bg border border-surface-border text-navy-800">
                        {log.category}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-teal-700 font-semibold">{log.userName}</td>
                    <td className="py-3 px-4 text-content-secondary leading-relaxed">{log.details}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardBody>
      </Card>
    </div>
  );
};

