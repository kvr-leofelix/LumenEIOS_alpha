import React, { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useData } from '../../context/DataContext';
import { School, InfrastructureTier } from '../../types';
import { Card, CardHeader, CardBody } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Modal } from '../../components/common/Modal';
import { SearchInput } from '../../components/common/SearchInput';
import { getTierBadge } from '../../lib/utils';
import { SchoolPerformance } from '../../components/school/SchoolPerformance';
import { PlusCircle, Edit2, CheckCircle2 } from 'lucide-react';

export const SchoolsManagement: React.FC = () => {
  const { schools, addSchool, updateSchool } = useData();
  const [searchParams, setSearchParams] = useSearchParams();

  const [search, setSearch] = useState('');
  const [tierFilter, setTierFilter] = useState<string>('all');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingSchool, setEditingSchool] = useState<School | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  // Form State
  const [name, setName] = useState('');
  const [location, setLocation] = useState('');
  const [state, setState] = useState('Karnataka');
  const [tier, setTier] = useState<InfrastructureTier>('standard');
  const [principalName, setPrincipalName] = useState('');
  const [studentCount, setStudentCount] = useState(500);
  const [teacherCount, setTeacherCount] = useState(25);
  const [description, setDescription] = useState('');

  const filteredSchools = schools.filter((s) => {
    const matchesSearch =
      s.name.toLowerCase().includes(search.toLowerCase()) ||
      s.location.toLowerCase().includes(search.toLowerCase()) ||
      s.state.toLowerCase().includes(search.toLowerCase());
    const matchesTier = tierFilter === 'all' || s.infrastructureTier === tierFilter;
    return matchesSearch && matchesTier;
  });

  const selectedSchool = schools.find((s) => s.id === searchParams.get('school')) || null;

  const openSchool = (schoolId: string) => {
    setSearchParams({ school: schoolId });
  };

  const handleOpenCreate = () => {
    setEditingSchool(null);
    setName('');
    setLocation('');
    setState('Karnataka');
    setTier('standard');
    setPrincipalName('');
    setStudentCount(500);
    setTeacherCount(25);
    setDescription('');
    setIsModalOpen(true);
  };

  const handleOpenEdit = (s: School) => {
    setEditingSchool(s);
    setName(s.name);
    setLocation(s.location);
    setState(s.state);
    setTier(s.infrastructureTier);
    setPrincipalName(s.principalName);
    setStudentCount(s.studentCount);
    setTeacherCount(s.teacherCount);
    setDescription(s.description);
    setIsModalOpen(true);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    if (editingSchool) {
      updateSchool(editingSchool.id, {
        name,
        location,
        state,
        infrastructureTier: tier,
        principalName,
        studentCount: Number(studentCount),
        teacherCount: Number(teacherCount),
        description,
      });
      setToast(`Updated ${name} successfully!`);
    } else {
      addSchool({
        name,
        location,
        state,
        infrastructureTier: tier,
        principalName: principalName || 'Principal Assigned',
        studentCount: Number(studentCount),
        teacherCount: Number(teacherCount),
        description,
      });
      setToast(`Onboarded ${name} to platform!`);
    }

    setIsModalOpen(false);
    setTimeout(() => setToast(null), 4000);
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
          <h1 className="text-xl font-bold text-navy-900 tracking-tight">Affiliated Schools Directory</h1>
          <p className="text-xs text-content-secondary mt-0.5">
            Choose a school to see its teachers, students, and benchmark scores
          </p>
        </div>

        <Button
          variant="teal"
          size="md"
          onClick={handleOpenCreate}
          icon={<PlusCircle className="w-4 h-4" />}
        >
          Add New Campus
        </Button>
      </div>

      {selectedSchool ? (
        <SchoolPerformance schoolId={selectedSchool.id} onBack={() => setSearchParams({})} />
      ) : (
      <>
      {/* Filters */}
      <Card>
        <CardBody className="p-4 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 text-xs">
          <SearchInput
            value={search}
            onChange={setSearch}
            placeholder="Search school name, city, or state..."
            className="sm:w-72"
          />

          <div className="flex items-center gap-2">
            <span className="font-semibold text-content-secondary">Tier:</span>
            <select
              value={tierFilter}
              onChange={(e) => setTierFilter(e.target.value)}
              className="px-3 py-1.5 bg-surface-bg border border-surface-border rounded-lg text-xs"
            >
              <option value="all">All Infrastructure Tiers</option>
              <option value="high-tech">High-Tech Private</option>
              <option value="standard">Standard Blended</option>
              <option value="low-tech">Low-Tech / Rural Gov</option>
            </select>
          </div>
        </CardBody>
      </Card>

      {/* School Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {filteredSchools.map((s) => {
          const tierInfo = getTierBadge(s.infrastructureTier);
          return (
            <Card
              key={s.id}
              hoverable
              role="button"
              tabIndex={0}
              onClick={() => openSchool(s.id)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault();
                  openSchool(s.id);
                }
              }}
              className="flex flex-col justify-between"
            >
              <CardHeader
                title={s.name}
                subtitle={`${s.location}, ${s.state}`}
                action={
                  <span className={`px-2 py-0.5 rounded text-[11px] font-semibold border ${tierInfo.color}`}>
                    {tierInfo.label}
                  </span>
                }
              />
              <CardBody className="space-y-3 text-xs">
                <p className="text-content-secondary line-clamp-2 leading-relaxed">
                  {s.description}
                </p>

                <div className="p-3 bg-surface-bg rounded-xl border border-surface-border grid grid-cols-3 gap-2 text-center">
                  <div>
                    <span className="text-[10px] text-content-muted block uppercase">Students</span>
                    <span className="font-bold text-navy-900">{s.studentCount}</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-content-muted block uppercase">Faculty</span>
                    <span className="font-bold text-teal-700">{s.teacherCount}</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-content-muted block uppercase">Pacing</span>
                    <span
                      className={`font-bold capitalize ${
                        s.pacingRisk === 'high'
                          ? 'text-rose-600'
                          : s.pacingRisk === 'medium'
                          ? 'text-amber-600'
                          : 'text-emerald-600'
                      }`}
                    >
                      {s.pacingRisk}
                    </span>
                  </div>
                </div>

                <div className="pt-2 border-t border-surface-border flex items-center justify-between text-[11px]">
                  <span className="text-content-secondary">
                    Principal: <strong className="text-navy-900">{s.principalName}</strong>
                  </span>
                  <div className="flex items-center gap-1.5">
                    <button
                      onClick={(event) => {
                        event.stopPropagation();
                        handleOpenEdit(s);
                      }}
                      className="p-1.5 text-content-secondary hover:text-navy-900 hover:bg-surface-bg rounded-lg transition-colors"
                      title="Edit school"
                    >
                      <Edit2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              </CardBody>
            </Card>
          );
        })}
      </div>
      </>
      )}

      {/* Create / Edit Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title={editingSchool ? `Edit ${editingSchool.name}` : 'Onboard New Campus'}
        subtitle="Configure infrastructure specifications and academic enrollment"
        maxWidth="lg"
        footer={
          <div className="flex items-center justify-end gap-2.5 w-full">
            <Button variant="secondary" size="md" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="teal" size="md" onClick={handleSubmit}>
              {editingSchool ? 'Save Changes' : 'Onboard Campus'}
            </Button>
          </div>
        }
      >
        <form onSubmit={handleSubmit} className="space-y-4 text-xs">
          <div>
            <label className="block font-semibold text-content-primary mb-1">School Name</label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Kendriya Vidyalaya No. 1"
              className="w-full px-3 py-2 bg-white border border-surface-border rounded-lg"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-content-primary mb-1">City / District</label>
              <input
                type="text"
                required
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="e.g. Sanganer, Jaipur"
                className="w-full px-3 py-2 bg-white border border-surface-border rounded-lg"
              />
            </div>
            <div>
              <label className="block font-semibold text-content-primary mb-1">State</label>
              <input
                type="text"
                required
                value={state}
                onChange={(e) => setState(e.target.value)}
                placeholder="e.g. Rajasthan"
                className="w-full px-3 py-2 bg-white border border-surface-border rounded-lg"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-content-primary mb-1">Infrastructure Tier</label>
              <select
                value={tier}
                onChange={(e) => setTier(e.target.value as any)}
                className="w-full px-3 py-2 bg-white border border-surface-border rounded-lg"
              >
                <option value="high-tech">High-Tech (Digital smart boards, 1:1 tablets)</option>
                <option value="standard">Standard (Computer labs, blended projectors)</option>
                <option value="low-tech">Low-Tech (Physical worksheets, mobile OCR)</option>
              </select>
            </div>
            <div>
              <label className="block font-semibold text-content-primary mb-1">Principal in Charge</label>
              <input
                type="text"
                value={principalName}
                onChange={(e) => setPrincipalName(e.target.value)}
                placeholder="e.g. Dr. Sunita Deshmukh"
                className="w-full px-3 py-2 bg-white border border-surface-border rounded-lg"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-content-primary mb-1">Student Enrollment</label>
              <input
                type="number"
                value={studentCount}
                onChange={(e) => setStudentCount(Number(e.target.value))}
                className="w-full px-3 py-2 bg-white border border-surface-border rounded-lg"
              />
            </div>
            <div>
              <label className="block font-semibold text-content-primary mb-1">Teaching Staff</label>
              <input
                type="number"
                value={teacherCount}
                onChange={(e) => setTeacherCount(Number(e.target.value))}
                className="w-full px-3 py-2 bg-white border border-surface-border rounded-lg"
              />
            </div>
          </div>

          <div>
            <label className="block font-semibold text-content-primary mb-1">Infrastructure Notes</label>
            <textarea
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g. Campus has 3 computer laboratories and dedicated tinkering hubs..."
              className="w-full px-3 py-2 bg-white border border-surface-border rounded-lg"
            />
          </div>
        </form>
      </Modal>
    </div>
  );
};

