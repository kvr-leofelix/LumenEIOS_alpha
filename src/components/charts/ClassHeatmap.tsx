import React, { useState } from 'react';
import { Student, CompetencyKey } from '../../types';
import { cn, getCompetencyColor } from '../../lib/utils';
import { SearchInput } from '../common/SearchInput';
import { Badge } from '../common/Badge';
import { ArrowUpDown, AlertCircle } from 'lucide-react';

interface ClassHeatmapProps {
  students: Student[];
  onSelectStudent?: (student: Student) => void;
  onTriggerRemediation?: (student: Student) => void;
}

export const ClassHeatmap: React.FC<ClassHeatmapProps> = ({
  students,
  onSelectStudent,
  onTriggerRemediation,
}) => {
  const [filterQuery, setFilterQuery] = useState('');
  const [sortKey, setSortKey] = useState<'name' | 'rollNo' | CompetencyKey | 'overall'>('rollNo');
  const [sortAsc, setSortAsc] = useState(true);

  const filtered = students.filter(
    (s) =>
      s.name.toLowerCase().includes(filterQuery.toLowerCase()) ||
      s.rollNo.toString().includes(filterQuery) ||
      (s.supportArea && s.supportArea.toLowerCase().includes(filterQuery.toLowerCase()))
  );

  const sorted = [...filtered].sort((a, b) => {
    let diff = 0;
    if (sortKey === 'name') {
      diff = a.name.localeCompare(b.name);
    } else if (sortKey === 'rollNo') {
      diff = a.rollNo - b.rollNo;
    } else if (sortKey === 'overall') {
      diff = a.competencies.overall - b.competencies.overall;
    } else {
      diff = a.competencies[sortKey] - b.competencies[sortKey];
    }
    return sortAsc ? diff : -diff;
  });

  const handleSort = (key: typeof sortKey) => {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(true);
    }
  };

  const renderCell = (score: number, key: CompetencyKey) => {
    const col = getCompetencyColor(score);
    return (
      <div
        className={cn(
          'w-14 h-8 rounded-md flex items-center justify-center font-semibold text-xs border transition-transform hover:scale-105',
          col.bg,
          col.text,
          col.border
        )}
        title={`${key}: ${score}%`}
      >
        {score}%
      </div>
    );
  };

  return (
    <div className="space-y-3.5">
      {/* Controls */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <SearchInput
          value={filterQuery}
          onChange={setFilterQuery}
          placeholder="Filter student by name, roll no or gap..."
          className="max-w-xs"
        />

        {/* Legend */}
        <div className="flex items-center gap-2 text-xs">
          <span className="text-content-secondary font-medium">Mastery:</span>
          <span className="inline-flex items-center gap-1 text-rose-700 bg-rose-50 px-2 py-0.5 rounded border border-rose-200">
            &lt;50% Gap
          </span>
          <span className="inline-flex items-center gap-1 text-amber-700 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
            50-64% Emerging
          </span>
          <span className="inline-flex items-center gap-1 text-blue-700 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
            65-79% Proficient
          </span>
          <span className="inline-flex items-center gap-1 text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
            80%+ Mastery
          </span>
        </div>
      </div>

      {/* Heatmap Table */}
      <div className="overflow-x-auto border border-surface-border rounded-xl">
        <table className="w-full text-left text-xs">
          <thead className="bg-surface-bg/80 text-content-secondary border-b border-surface-border select-none">
            <tr>
              <th
                onClick={() => handleSort('rollNo')}
                className="py-3 px-3 cursor-pointer hover:text-content-primary"
              >
                <div className="flex items-center gap-1">
                  <span>Roll</span>
                  <ArrowUpDown className="w-3 h-3" />
                </div>
              </th>
              <th
                onClick={() => handleSort('name')}
                className="py-3 px-4 cursor-pointer hover:text-content-primary"
              >
                <div className="flex items-center gap-1">
                  <span>Student Name</span>
                  <ArrowUpDown className="w-3 h-3" />
                </div>
              </th>
              <th className="py-3 px-3">VARK Modality</th>
              <th
                onClick={() => handleSort('LU')}
                className="py-3 px-2 text-center cursor-pointer hover:text-content-primary"
              >
                <div className="flex items-center justify-center gap-1">
                  <span>LU (Language)</span>
                  <ArrowUpDown className="w-3 h-3" />
                </div>
              </th>
              <th
                onClick={() => handleSort('CU')}
                className="py-3 px-2 text-center cursor-pointer hover:text-content-primary"
              >
                <div className="flex items-center justify-center gap-1">
                  <span>CU (Concept)</span>
                  <ArrowUpDown className="w-3 h-3" />
                </div>
              </th>
              <th
                onClick={() => handleSort('AU')}
                className="py-3 px-2 text-center cursor-pointer hover:text-content-primary"
              >
                <div className="flex items-center justify-center gap-1">
                  <span>AU (Apply)</span>
                  <ArrowUpDown className="w-3 h-3" />
                </div>
              </th>
              <th
                onClick={() => handleSort('CT')}
                className="py-3 px-2 text-center cursor-pointer hover:text-content-primary"
              >
                <div className="flex items-center justify-center gap-1">
                  <span>CT (Critical)</span>
                  <ArrowUpDown className="w-3 h-3" />
                </div>
              </th>
              <th
                onClick={() => handleSort('overall')}
                className="py-3 px-3 text-center cursor-pointer hover:text-content-primary"
              >
                <div className="flex items-center justify-center gap-1">
                  <span>Baseline</span>
                  <ArrowUpDown className="w-3 h-3" />
                </div>
              </th>
              <th className="py-3 px-3 text-right">Adaptive Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-border bg-white">
            {sorted.map((student) => (
              <tr
                key={student.id}
                className="hover:bg-surface-bg/40 transition-colors cursor-pointer"
                onClick={() => onSelectStudent && onSelectStudent(student)}
              >
                <td className="py-2.5 px-3 font-mono text-content-muted">#{student.rollNo}</td>
                <td className="py-2.5 px-4">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-content-primary">{student.name}</span>
                    {student.needsSupport && (
                      <span title={student.supportArea || 'Intervention needed'}>
                        <AlertCircle className="w-3.5 h-3.5 text-rose-500" />
                      </span>
                    )}
                  </div>
                  {student.supportArea && (
                    <p className="text-[10px] text-content-muted truncate max-w-[200px]">
                      {student.supportArea}
                    </p>
                  )}
                </td>
                <td className="py-2.5 px-3">
                  <Badge variant="outline" size="sm">
                    {student.learningModality}
                  </Badge>
                </td>
                <td className="py-2.5 px-2 text-center">
                  <div className="flex justify-center">{renderCell(student.competencies.LU, 'LU')}</div>
                </td>
                <td className="py-2.5 px-2 text-center">
                  <div className="flex justify-center">{renderCell(student.competencies.CU, 'CU')}</div>
                </td>
                <td className="py-2.5 px-2 text-center">
                  <div className="flex justify-center">{renderCell(student.competencies.AU, 'AU')}</div>
                </td>
                <td className="py-2.5 px-2 text-center">
                  <div className="flex justify-center">{renderCell(student.competencies.CT, 'CT')}</div>
                </td>
                <td className="py-2.5 px-3 text-center font-bold text-navy-800">
                  {student.competencies.overall}%
                </td>
                <td className="py-2.5 px-3 text-right">
                  {onTriggerRemediation && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onTriggerRemediation(student);
                      }}
                      className="px-2.5 py-1 text-[11px] font-medium text-teal-700 bg-teal-50 hover:bg-teal-100 border border-teal-200 rounded-lg transition-colors"
                    >
                      Differentiate
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

