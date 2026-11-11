import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { useData } from '../../context/DataContext';
import { User, Role } from '../../types';
import { Card, CardHeader, CardBody } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { SearchInput } from '../../components/common/SearchInput';
import { Users, Shield, BookOpen, GraduationCap, School, CheckCircle2, Code } from 'lucide-react';

export const UsersManagement: React.FC = () => {
  const { availableUsers, loginAsRole } = useAuth();
  const { schools } = useData();

  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState<string>('all');
  const [toast, setToast] = useState<string | null>(null);

  const filteredUsers = availableUsers.filter((u) => {
    const matchesSearch =
      u.name.toLowerCase().includes(search.toLowerCase()) ||
      u.email.toLowerCase().includes(search.toLowerCase()) ||
      (u.designation && u.designation.toLowerCase().includes(search.toLowerCase()));
    const matchesRole = roleFilter === 'all' || u.role === roleFilter;
    return matchesSearch && matchesRole;
  });

  const getRoleIcon = (role: Role) => {
    switch (role) {
      case 'developer':
        return <Code className="w-4 h-4 text-teal-700" />;
      case 'admin':
        return <Shield className="w-4 h-4 text-indigo-600" />;
      case 'principal':
        return <School className="w-4 h-4 text-teal-600" />;
      case 'teacher':
        return <BookOpen className="w-4 h-4 text-emerald-600" />;
      case 'student':
        return <GraduationCap className="w-4 h-4 text-sky-600" />;
      case 'parent':
        return <Users className="w-4 h-4 text-amber-600" />;
    }
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
          <h1 className="text-xl font-bold text-navy-900 tracking-tight">User Directory & Role Permissions</h1>
          <p className="text-xs text-content-secondary mt-0.5">
            Manage authenticated demo personas, campus assignments, and role access controls
          </p>
        </div>

        <Badge variant="teal" size="sm">
          5 Demo Personas Configured
        </Badge>
      </div>

      {/* Filters */}
      <Card>
        <CardBody className="p-4 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 text-xs">
          <SearchInput
            value={search}
            onChange={setSearch}
            placeholder="Search user name or email..."
            className="sm:w-72"
          />

          <div className="flex items-center gap-2">
            <span className="font-semibold text-content-secondary">Role:</span>
            <select
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              className="px-3 py-1.5 bg-surface-bg border border-surface-border rounded-lg text-xs"
            >
              <option value="all">All Roles</option>
              <option value="admin">Admin</option>
              <option value="principal">Principal</option>
              <option value="teacher">Teacher</option>
              <option value="student">Student</option>
              <option value="parent">Parent</option>
            </select>
          </div>
        </CardBody>
      </Card>

      {/* Users Table */}
      <Card>
        <CardBody className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-surface-bg/80 text-content-secondary border-b border-surface-border">
                <tr>
                  <th className="py-3 px-4">User Name & Email</th>
                  <th className="py-3 px-4">Designation</th>
                  <th className="py-3 px-3">Role</th>
                  <th className="py-3 px-4">Campus Association</th>
                  <th className="py-3 px-4 text-right">Instant Switch</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-border bg-white">
                {filteredUsers.map((user) => {
                  const userSchool = schools.find((s) => s.id === user.schoolId);
                  return (
                    <tr key={user.id} className="hover:bg-surface-bg/40 transition-colors">
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-full bg-navy-800 text-white flex items-center justify-center font-bold text-xs shrink-0">
                            {user.name.charAt(0)}
                          </div>
                          <div>
                            <span className="font-bold text-navy-900 block">{user.name}</span>
                            <span className="text-content-muted font-mono text-[11px]">{user.email}</span>
                          </div>
                        </div>
                      </td>
                      <td className="py-3 px-4 text-content-secondary">
                        {user.designation || 'Staff Member'}
                      </td>
                      <td className="py-3 px-3">
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold border bg-surface-bg border-surface-border text-navy-900 capitalize">
                          {getRoleIcon(user.role)}
                          <span>{user.role}</span>
                        </span>
                      </td>
                      <td className="py-3 px-4 text-content-primary">
                        {userSchool ? userSchool.name : 'Statewide Platform Access'}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <button
                          onClick={() => {
                            loginAsRole(user.role);
                            setToast(`Switched active context to ${user.name} (${user.role})`);
                          }}
                          className="px-3 py-1 bg-navy-800 hover:bg-navy-900 text-white rounded-lg text-xs font-semibold transition-colors"
                        >
                          Login As
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </CardBody>
      </Card>
    </div>
  );
};

