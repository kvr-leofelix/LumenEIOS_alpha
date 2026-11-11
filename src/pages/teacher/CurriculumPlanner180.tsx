import React, { useState } from 'react';
import { useData } from '../../context/DataContext';
import { CurriculumDay, VARKModality, BloomLevel } from '../../types';
import { Card, CardHeader, CardBody } from '../../components/common/Card';
import { Badge } from '../../components/common/Badge';
import { Button } from '../../components/common/Button';
import { Modal } from '../../components/common/Modal';
import { SearchInput } from '../../components/common/SearchInput';
import {
  Calendar,
  Layers,
  Filter,
  CheckCircle2,
  Clock,
  Sparkles,
  BookOpen,
  ArrowRight,
  Eye,
} from 'lucide-react';

export const CurriculumPlanner180: React.FC = () => {
  const { curriculumDays } = useData();

  const [selectedDay, setSelectedDay] = useState<CurriculumDay | null>(null);
  const [filterQuery, setFilterQuery] = useState('');
  const [filterClassif, setFilterClassif] = useState<'all' | 'core' | 'supplementary'>('all');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [filterModality, setFilterModality] = useState<string>('all');

  const filteredDays = curriculumDays.filter((d) => {
    const matchesQuery =
      d.topic.toLowerCase().includes(filterQuery.toLowerCase()) ||
      d.objective.toLowerCase().includes(filterQuery.toLowerCase()) ||
      `Day ${d.dayNumber}`.toLowerCase().includes(filterQuery.toLowerCase());

    const matchesClassif = filterClassif === 'all' || d.classification === filterClassif;
    const matchesStatus = filterStatus === 'all' || d.status === filterStatus;
    const matchesMod = filterModality === 'all' || d.varkModality === filterModality;

    return matchesQuery && matchesClassif && matchesStatus && matchesMod;
  });

  const completedCount = curriculumDays.filter((d) => d.status === 'completed').length;
  const compressedCount = curriculumDays.filter(
    (d) => d.status === 'compressed_to_homework' || d.status === 'integrated'
  ).length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white p-5 rounded-2xl border border-surface-border shadow-subtle flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-navy-900 tracking-tight">
              180-Day Daily Micro-Curriculum
            </h1>
            <Badge variant="teal" size="sm">
              NEP 2020 VARK & Bloom's Taxonomy
            </Badge>
          </div>
          <p className="text-xs text-content-secondary mt-1">
            Grade 8 Mathematics • Micro-sequenced daily lessons with granular pedagogical outcomes
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs">
          <span className="font-semibold text-teal-800 bg-teal-50 px-3 py-1.5 rounded-lg border border-teal-200">
            Day 104 in Progress (72 Days Remaining)
          </span>
        </div>
      </div>

      {/* Progress & Classification Counters */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
        <div className="p-4 bg-white rounded-xl border border-surface-border">
          <span className="text-content-secondary uppercase font-semibold text-[11px]">Taught Lessons</span>
          <p className="text-2xl font-bold text-navy-900 mt-1">{completedCount} Days</p>
          <span className="text-emerald-700 font-medium">Completed contact hours</span>
        </div>
        <div className="p-4 bg-white rounded-xl border border-surface-border">
          <span className="text-content-secondary uppercase font-semibold text-[11px]">Protected Core</span>
          <p className="text-2xl font-bold text-teal-700 mt-1">
            {curriculumDays.filter((d) => d.classification === 'core').length} Lessons
          </p>
          <span className="text-teal-600 font-medium">60% Essential Syllabi</span>
        </div>
        <div className="p-4 bg-white rounded-xl border border-surface-border">
          <span className="text-content-secondary uppercase font-semibold text-[11px]">Supplementary / Flipped</span>
          <p className="text-2xl font-bold text-amber-700 mt-1">
            {curriculumDays.filter((d) => d.classification === 'supplementary').length} Lessons
          </p>
          <span className="text-amber-600 font-medium">40% Extension & Guided</span>
        </div>
        <div className="p-4 bg-white rounded-xl border border-surface-border">
          <span className="text-content-secondary uppercase font-semibold text-[11px]">Compacted / Integrated</span>
          <p className="text-2xl font-bold text-indigo-700 mt-1">{compressedCount} Lessons</p>
          <span className="text-indigo-600 font-medium">Flipped homework units</span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <Card>
        <CardBody className="p-4 flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3 text-xs">
          <SearchInput
            value={filterQuery}
            onChange={setFilterQuery}
            placeholder="Search topic, chapter, or objective..."
            className="md:w-72"
          />

          <div className="flex flex-wrap items-center gap-2">
            <select
              value={filterClassif}
              onChange={(e) => setFilterClassif(e.target.value as any)}
              className="px-2.5 py-1.5 bg-surface-bg border border-surface-border rounded-lg"
            >
              <option value="all">All Classifications</option>
              <option value="core">Core Only (60%)</option>
              <option value="supplementary">Supplementary Only (40%)</option>
            </select>

            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="px-2.5 py-1.5 bg-surface-bg border border-surface-border rounded-lg"
            >
              <option value="all">All Statuses</option>
              <option value="completed">Completed</option>
              <option value="in-progress">In Progress (Today)</option>
              <option value="pending">Pending</option>
              <option value="compressed_to_homework">Compressed to Homework</option>
              <option value="integrated">Cross-Curricular Integrated</option>
            </select>

            <select
              value={filterModality}
              onChange={(e) => setFilterModality(e.target.value)}
              className="px-2.5 py-1.5 bg-surface-bg border border-surface-border rounded-lg"
            >
              <option value="all">All VARK Modalities</option>
              <option value="Visual">Visual</option>
              <option value="Auditory">Auditory</option>
              <option value="Reading/Writing">Reading/Writing</option>
              <option value="Kinesthetic">Kinesthetic</option>
            </select>
          </div>
        </CardBody>
      </Card>

      {/* 180 Days List Grid */}
      <div className="space-y-3">
        {filteredDays.slice(0, 30).map((day) => {
          const isToday = day.dayNumber === 104;
          return (
            <div
              key={day.id}
              onClick={() => setSelectedDay(day)}
              className={`p-4 rounded-xl border transition-all cursor-pointer flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs ${
                isToday
                  ? 'bg-teal-50/50 border-2 border-teal-500 shadow-sm'
                  : day.status === 'completed'
                  ? 'bg-white border-surface-border opacity-85'
                  : day.status === 'compressed_to_homework'
                  ? 'bg-amber-50/30 border-amber-200'
                  : 'bg-white border-surface-border hover:border-teal-300 hover:shadow-subtle'
              }`}
            >
              <div className="flex items-start gap-3">
                <div
                  className={`w-12 h-12 rounded-xl flex flex-col items-center justify-center font-bold shrink-0 ${
                    isToday
                      ? 'bg-teal-500 text-white'
                      : day.status === 'completed'
                      ? 'bg-navy-800 text-white'
                      : 'bg-surface-bg text-content-secondary border border-surface-border'
                  }`}
                >
                  <span className="text-[10px] uppercase font-normal">Day</span>
                  <span className="text-sm font-black">{day.dayNumber}</span>
                </div>

                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-bold text-navy-900 text-sm">{day.topic}</span>
                    <Badge
                      variant={day.classification === 'core' ? 'teal' : 'warning'}
                      size="sm"
                    >
                      {day.classification === 'core' ? 'Core Concept (Protected)' : 'Supplementary'}
                    </Badge>
                    <Badge variant="outline" size="sm">
                      {day.varkModality}
                    </Badge>
                    <Badge variant="info" size="sm">
                      Bloom: {day.bloomLevel}
                    </Badge>
                  </div>
                  <p className="text-content-secondary text-[11px] mt-1 line-clamp-1 leading-relaxed">
                    Objective: {day.objective}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3 shrink-0 self-end sm:self-auto">
                <span
                  className={`text-[11px] font-semibold px-2 py-0.5 rounded capitalize ${
                    day.status === 'completed'
                      ? 'text-emerald-700 bg-emerald-50'
                      : day.status === 'in-progress'
                      ? 'text-teal-800 bg-teal-100 font-bold'
                      : day.status === 'compressed_to_homework'
                      ? 'text-amber-800 bg-amber-100'
                      : 'text-content-muted'
                  }`}
                >
                  {day.status.replace('_', ' ')}
                </span>
                <Eye className="w-4 h-4 text-content-muted" />
              </div>
            </div>
          );
        })}
      </div>

      {/* Lesson Plan Detail Modal */}
      {selectedDay && (
        <Modal
          isOpen={!!selectedDay}
          onClose={() => setSelectedDay(null)}
          title={`Day ${selectedDay.dayNumber} Lesson Plan: ${selectedDay.topic}`}
          subtitle={`Classification: ${selectedDay.classification.toUpperCase()} • Modality: ${selectedDay.varkModality}`}
          maxWidth="2xl"
          footer={
            <Button variant="secondary" size="sm" onClick={() => setSelectedDay(null)}>
              Close Lesson Detail
            </Button>
          }
        >
          <div className="space-y-4 text-xs">
            <div className="flex flex-wrap gap-2">
              <Badge variant="teal">VARK: {selectedDay.varkModality}</Badge>
              <Badge variant="info">Bloom's: {selectedDay.bloomLevel}</Badge>
              <Badge variant={selectedDay.classification === 'core' ? 'success' : 'warning'}>
                {selectedDay.classification === 'core' ? 'Protected Core (NEP 2020)' : 'Supplementary'}
              </Badge>
              <Badge variant="outline">Duration: {selectedDay.estimatedDurationMins} Mins</Badge>
            </div>

            <div className="p-3 bg-surface-bg rounded-xl border border-surface-border space-y-1">
              <span className="font-bold text-navy-900 block">Specific Learning Objective</span>
              <p className="text-content-secondary leading-relaxed">{selectedDay.objective}</p>
            </div>

            <div className="p-3 bg-surface-bg rounded-xl border border-surface-border space-y-1">
              <span className="font-bold text-navy-900 block">Teaching Process & Activity</span>
              <p className="text-content-secondary leading-relaxed">{selectedDay.teachingProcess}</p>
            </div>

            <div className="p-3 bg-teal-50 border border-teal-200 rounded-xl space-y-1">
              <span className="font-bold text-teal-900 block">Measurable Competency Outcome</span>
              <p className="text-teal-800 leading-relaxed">{selectedDay.measurableOutcome}</p>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};

