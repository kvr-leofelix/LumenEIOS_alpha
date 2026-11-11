import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { getDefaultDashboardPath } from '../../lib/permissions';
import { ArrowRight } from 'lucide-react';

const steps = [
  ['01', 'Record the gap', 'A teacher or school records lost days, such as an election duty or a weather closure.'],
  ['02', 'See what must stay', 'The time-aware engine shows whether the class is behind and which core topics must stay.'],
  ['03', 'Split the plan', 'A 60/40 plan keeps essential competencies in class and shifts the rest to guided inquiry.'],
];

const roles = [
  ['Management', 'Compares campuses, adds schools, and sets academic rules.'],
  ['School', 'Watches pacing, adds students, and reads school reports.'],
  ['Teacher', 'Plans the year, builds assessments, and grades scans.'],
  ['Student', 'Sees today’s mission, practice, and achievements.'],
  ['Parent', 'Reads progress and a guide for learning at home.'],
];

const featureGroups = [
  ['Network', [
    ['Role workspaces', 'Management, School, Teacher, Student, and Parent each open a workspace built for that job.'],
    ['School directory', 'Management adds schools, compares campuses, and sees student reach across the network.'],
    ['Users and roles', 'Management accounts manage people and switch the demo into any role.'],
    ['Academic configuration', 'Set the rules that classes, calendars, and reports follow.'],
    ['Audit and security', 'Review a log of important actions, including schools and students that were added.'],
  ]],
  ['School', [
    ['Campus dashboard', 'A school sees pacing, staffing, and competency levels for its own campus.'],
    ['Students', 'School accounts add students, assign a class, and keep the roster current.'],
    ['Teacher assignments', 'Schools see which teachers are attached to which classes.'],
    ['Compliance reports', 'Schools export the reports needed to show how learning was protected.'],
  ]],
  ['Teaching', [
    ['Time-aware engine', 'Record lost teaching days and see which core topics must stay in class.'],
    ['180-day curriculum', 'Teachers work from a full-year plan instead of a loose topic list.'],
    ['Class heatmap', 'Teachers see where a class is strong or stuck across the four competencies.'],
    ['AI question studio', 'Build assessments aimed at a competency instead of only a chapter name.'],
    ['Answer sheets', 'Teachers give an assignment. Students upload a sheet, and a demo transcript shows the text and equations.'],
    ['Differentiated homework', 'Assign practice that matches what a student still needs to learn.'],
  ]],
  ['Students and families', [
    ['Learning mission', 'Students see today’s mission, adaptive practice, and achievements.'],
    ['Family progress', 'Parents read competency growth and a home learning guide in plain language.'],
    ['Notifications', 'Each role gets its own alerts. The panel closes when you change role or theme.'],
  ]],
] as const;

export const WelcomePage: React.FC = () => {
  const { currentUser } = useAuth();
  const navigate = useNavigate();
  const dashboardPath = currentUser ? getDefaultDashboardPath(currentUser.role) : '/login';

  return (
    <div className="min-h-screen bg-surface-bg text-content-primary font-sans">
      <header className="sticky top-0 z-20 bg-navy-800">
        <div className="max-w-5xl mx-auto px-6 sm:px-10 py-5 flex items-center justify-between gap-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-teal-500 text-white flex items-center justify-center text-lg font-semibold">
              L
            </div>
            <div>
              <p className="text-base font-semibold leading-none text-white">
                Lumen<span className="text-teal-300">EIOS</span>
              </p>
              <p className="text-sm text-navy-200 mt-1">Adaptive EdTech · NEP 2020</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <Link to="/login" className="text-sm font-medium text-white">
              Sign in
            </Link>
            <button
              type="button"
              onClick={() => navigate(dashboardPath)}
              className="inline-flex items-center gap-2 rounded-lg bg-teal-500 px-4 py-2 text-sm font-semibold text-white"
            >
              {currentUser ? 'Open dashboard' : 'Enter'}
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 sm:px-10">
        <section className="mt-12 sm:mt-16 rounded-3xl bg-white border border-surface-border shadow-card px-8 py-10 sm:px-12 sm:py-14 max-w-4xl">
          <p className="inline-flex rounded-full bg-teal-50 px-3 py-1 text-sm font-semibold text-teal-800">School operating system</p>
          <h1 className="mt-6 text-4xl sm:text-5xl font-semibold tracking-tight text-navy-900 leading-[1.15]">
            Keep students learning when the school calendar breaks.
          </h1>
          <p className="mt-6 text-lg text-content-secondary leading-relaxed max-w-2xl">
            LumenEIOS watches lost teaching days, protects essential competencies, and gives each role a clear next step.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <span className="rounded-lg bg-navy-800 px-3 py-2 text-sm font-semibold text-white">60 / 40 class and home</span>
            <span className="rounded-lg bg-teal-50 px-3 py-2 text-sm font-semibold text-teal-800">Language · Concept · Application · Critical Thinking</span>
          </div>
        </section>

        <section className="mt-14 grid grid-cols-1 md:grid-cols-3 gap-5">
          {steps.map(([n, title, text]) => (
            <article key={n} className="rounded-2xl bg-white border border-surface-border shadow-subtle p-6">
              <p className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-teal-500 text-sm font-semibold text-white">{n}</p>
              <h2 className="mt-5 text-xl font-semibold text-navy-900">{title}</h2>
              <p className="mt-3 text-sm text-content-secondary leading-relaxed">{text}</p>
            </article>
          ))}
        </section>

        <section className="mt-16">
          <h2 className="text-2xl font-semibold text-navy-900">Five workspaces</h2>
          <ul className="mt-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            {roles.map(([label, detail]) => (
              <li key={label} className="rounded-2xl bg-white border border-surface-border p-5">
                <span className="block h-1 w-8 rounded-full bg-teal-500 mb-4" />
                <span className="block text-lg font-semibold text-navy-900">{label}</span>
                <span className="block mt-3 text-sm text-content-secondary leading-relaxed">{detail}</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="mt-16">
          <h2 className="text-2xl font-semibold text-navy-900">Features</h2>
          <div className="mt-6 space-y-6">
            {featureGroups.map(([label, items]) => (
              <div key={label} className="rounded-2xl bg-white border border-surface-border overflow-hidden">
                <h3 className="bg-teal-50 px-6 py-3 text-sm font-semibold text-teal-800">{label}</h3>
                <ul className="grid grid-cols-1 md:grid-cols-2">
                  {items.map(([title, text]) => (
                    <li key={title} className="px-6 py-5 border-t border-surface-border">
                      <p className="text-base font-semibold text-navy-900">{title}</p>
                      <p className="mt-2 text-sm text-content-secondary leading-relaxed">{text}</p>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </section>

        <section className="mt-16 mb-20 flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between rounded-2xl bg-navy-800 px-8 py-8">
          <div>
            <p className="text-xl font-semibold text-white">Open a workspace</p>
            <p className="mt-2 text-sm text-navy-200">Sign in as any role and follow that day’s work.</p>
          </div>
          <div className="flex flex-col gap-3 sm:items-end">
            <button
              type="button"
              onClick={() => navigate(dashboardPath)}
              className="inline-flex items-center gap-2 rounded-lg bg-teal-500 px-5 py-2.5 text-sm font-semibold text-white"
            >
              {currentUser ? `Continue as ${currentUser.name}` : 'Sign in to continue'}
              <ArrowRight className="w-4 h-4" />
            </button>
            {currentUser && (
              <Link to="/login" className="text-sm font-medium text-teal-200">
                Choose a different persona
              </Link>
            )}
          </div>
        </section>
      </main>
    </div>
  );
};
