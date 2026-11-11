import React, { useState, useMemo, useEffect } from 'react';
import { useData } from '../../context/DataContext';
import { useAuth } from '../../context/AuthContext';
import { Question, CompetencyKey, BloomLevel, SourceDocument } from '../../types';
import { apiClient, AssignmentTarget, ProcessStep } from '../../lib/apiClient';
import { ProcessProgress } from '../../components/common/ProcessProgress';
import { Card, CardHeader, CardBody } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import {
  CheckCircle2,
  Sparkles,
  Trash2,
  UploadCloud,
  FileText,
  RefreshCw,
  Edit3,
  Download,
  Printer,
  AlertTriangle,
  Check,
  FileCheck2,
  AlertCircle,
  Wand2,
} from 'lucide-react';

const BLOOM_LEVELS: BloomLevel[] = [
  'Remember',
  'Understand',
  'Apply',
  'Analyze',
  'Evaluate',
  'Create',
];

const COMPETENCY_GUIDE: Record<CompetencyKey, { name: string; detail: string }> = {
  LU: {
    name: 'Language Understanding',
    detail: 'Interpret terminology, instructions, or the meaning of a passage.',
  },
  CU: {
    name: 'Conceptual Understanding',
    detail: 'Explain a concept, relationship, or why a principle works.',
  },
  AU: {
    name: 'Application',
    detail: 'Use a chapter concept, rule, or method to solve a problem or handle a new situation.',
  },
  CT: {
    name: 'Critical Thinking',
    detail: 'Evaluate evidence, compare explanations, justify a judgment, or identify assumptions.',
  },
};

const BLOOM_DESCRIPTIONS: Record<BloomLevel, string> = {
  Remember: 'Recall foundational facts, terminology, definitions, and standard formulas.',
  Understand: 'Explain core concepts, interpret relationships, and summarize principles in context.',
  Apply: 'Execute procedures, solve quantitative/contextual problems, and apply laws to new situations.',
  Analyze: 'Deconstruct multi-step problems, differentiate assumptions, and compare underlying mechanisms.',
  Evaluate: 'Critique arguments, justify methodological choices, and verify validity against criteria.',
  Create: 'Synthesize novel solutions, design experimental models, or formulate original proofs.',
};

const MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024;

export const AssessmentBuilder: React.FC = () => {
  const { currentUser } = useAuth();
  const {
    assessments,
    sourceDocuments,
    addAssessment,
    addSourceDocuments,
    addQuestionsToBank,
    updateBankQuestion,
    deleteBankQuestion,
  } = useData();

  const [toast, setToast] = useState<{ message: string; type?: 'success' | 'warning' } | null>(null);

  const showToast = (message: string, type: 'success' | 'warning' = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4500);
  };

  const [genSubjectId, setGenSubjectId] = useState('');
  const [targetClassId, setTargetClassId] = useState('');
  const [targets, setTargets] = useState<AssignmentTarget[]>();
  const [targetError, setTargetError] = useState('');
  const [isAssigning, setIsAssigning] = useState(false);
  const [studioPdfFile, setStudioPdfFile] = useState<File | null>(null);
  const [studioError, setStudioError] = useState('');
  const [uploadedStudioPdf, setUploadedStudioPdf] = useState<SourceDocument | null>(null);
  const [isUploadingStudioPdf, setIsUploadingStudioPdf] = useState(false);
  const [mcqCount, setMcqCount] = useState<number>(3);
  const [theoryCount, setTheoryCount] = useState<number>(2);
  const [bloomIndex, setBloomIndex] = useState<number>(3); // 'Analyze'
  const [topicHint, setTopicHint] = useState<string>('');
  // Learning-resource links (one per line) used with or instead of the chapter PDF.
  const [studioLinksText, setStudioLinksText] = useState<string>('');
  const studioLinks = Array.from(new Set(studioLinksText.split(/\s+/).map((link) => link.trim()).filter(Boolean)));
  const invalidStudioLink = studioLinks.find((link) => !/^https?:\/\/[^\s/]+\.[^\s]+/i.test(link));
  const hasStudioSource = !!studioPdfFile || !!uploadedStudioPdf || studioLinks.length > 0;
  // Generation & Preview State
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [generationSteps, setGenerationSteps] = useState<ProcessStep[]>([]);
  const [regeneratingId, setRegeneratingId] = useState<string | null>(null);
  const [generatedQuestions, setGeneratedQuestions] = useState<Question[]>([]);

  const targetClass = targets?.find((item) => item.id === targetClassId);
  const subjects = targetClass?.subjects ?? [];
  const targetSubject = subjects.find((item) => item.id === genSubjectId);

  useEffect(() => {
    let active = true;
    setTargets(undefined);
    setTargetError('');
    setGeneratedQuestions([]);
    apiClient.assessments.targets().then((options) => {
      if (!active) return;
      const available = options.filter((item) => item.subjects.length > 0);
      const section = available.find((item) => item.id === 'class-8a') ?? available[0];
      setTargets(available);
      setTargetClassId(section?.id ?? '');
      setGenSubjectId((section?.subjects.find((item) => item.id === 'sub-math') ?? section?.subjects[0])?.id ?? '');
    }).catch((err) => {
      if (active) setTargetError(err instanceof Error ? err.message : 'Could not load classes and subjects.');
    });
    return () => { active = false; };
  }, [currentUser?.id, currentUser?.schoolId]);

  const changeSubject = (subjectId: string) => {
    if (subjectId !== genSubjectId) setGeneratedQuestions([]);
    setGenSubjectId(subjectId);
  };

  const changeClass = (classId: string) => {
    const options = targets?.find((item) => item.id === classId)?.subjects ?? [];
    changeSubject(options.some((item) => item.id === genSubjectId) ? genSubjectId : options[0]?.id ?? '');
    setTargetClassId(classId);
  };

  // Inline Edit Question State
  const [editingQuestionId, setEditingQuestionId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<Partial<Question>>({});

  const currentBloomLevel = BLOOM_LEVELS[bloomIndex] || 'Analyze';

  const chapterPdfs = useMemo(
    () =>
      sourceDocuments.filter(
        (doc) =>
          /^doc-[0-9a-f]{16}$/.test(doc.id) &&
          (doc.mimeType === 'application/pdf' || (doc.fileName || '').toLowerCase().endsWith('.pdf'))
      ),
    [sourceDocuments]
  );

  useEffect(() => {
    if (studioPdfFile || uploadedStudioPdf || chapterPdfs.length === 0) return;
    setUploadedStudioPdf(chapterPdfs[0]);
  }, [studioPdfFile, uploadedStudioPdf, chapterPdfs]);

  const rememberChapterPdf = (file: File) => {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setStudioError('Only a chapter PDF can be used. Choose a .pdf file.');
      return;
    }
    setStudioPdfFile(file);
    setUploadedStudioPdf(null);

    setGeneratedQuestions([]);
    setStudioError('');
  };

  const uploadStudioPdf = async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      throw new Error('Only PDF files are allowed.');
    }
    if (file.size === 0 || file.size > MAX_FILE_SIZE_BYTES) {
      throw new Error(file.size === 0 ? 'The PDF is empty.' : 'The PDF exceeds the 15 MB limit.');
    }

    setIsUploadingStudioPdf(true);
    try {
      const document = await apiClient.documents.uploadStudioPdf(file, genSubjectId);
      addSourceDocuments([document]);
      setUploadedStudioPdf(document);

      setGeneratedQuestions([]);
      setStudioPdfFile(null);
      return document;
    } finally {
      setIsUploadingStudioPdf(false);
    }
  };

  const handleUploadStudioPdf = async () => {
    if (!studioPdfFile) return;
    setStudioError('');
    try {
      await uploadStudioPdf(studioPdfFile);
    } catch (error) {
      setStudioError(error instanceof Error ? error.message : 'PDF upload failed.');
    }
  };

  const handleGenerateQuestions = async () => {
    if (!targetSubject) return;
    if (mcqCount + theoryCount <= 0) {
      showToast('Please specify at least 1 MCQ or 1 Theory question to generate.', 'warning');
      return;
    }

    setIsGenerating(true);
    setGenerationSteps([]);
    const recordStep = (step: ProcessStep) => {
      setGenerationSteps((current) => {
        const index = current.findIndex((item) => item.step === step.step);
        if (index < 0) return [...current, step];
        const next = current.slice();
        next[index] = step;
        return next;
      });
    };
    setStudioError('');
    try {
      let document = uploadedStudioPdf;
      if (studioPdfFile) {
        recordStep({ step: 'upload', label: 'Uploading the chapter PDF', done: 0, total: 1 });
        document = await uploadStudioPdf(studioPdfFile);
        recordStep({ step: 'upload', label: 'Uploaded the chapter PDF', done: 1, total: 1 });
      }
      if (invalidStudioLink) throw new Error(`"${invalidStudioLink}" is not a web link. Use a full https:// address.`);
      if (studioLinks.length > 3) throw new Error('Add at most 3 links.');
      if (!document && studioLinks.length === 0) {
        throw new Error('Choose a chapter PDF or paste a learning-resource link to generate questions.');
      }
      const subjectName = subjects.find((subject) => subject.id === genSubjectId)?.name || 'Subject';
      const response = await apiClient.assessments.generateQuestionsBeta({
        subjectId: genSubjectId,
        subjectName,
        sourceDocumentIds: document ? [document.id] : [],
        sourceUrls: studioLinks,
        mcqCount,
        theoryCount,
        bloomLevel: currentBloomLevel,
        topicHint: topicHint.trim() || undefined,
        saveToBank: true,
      }, recordStep);
      setGeneratedQuestions(response.questions);
      addQuestionsToBank(response.questions);
      showToast(
        `Generated ${response.questions.length} questions from ${response.sourceDocumentsUsed.length} source${response.sourceDocumentsUsed.length === 1 ? '' : 's'} with Qwen ${response.model || '2.5-VL-7B'}.`
      );
    } catch (error) {
      setStudioError(error instanceof Error ? error.message : 'Question generation failed.');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleRegenerateSingle = async (q: Question) => {
    setRegeneratingId(q.id);
    setStudioError('');
    try {
      const result = await apiClient.assessments.generateQuestionsBeta({
        subjectId: q.subjectId || genSubjectId,
        subjectName: subjects.find((subject) => subject.id === (q.subjectId || genSubjectId))?.name || 'Subject',
        sourceDocumentIds: q.sourceDocumentIds ?? [],
        sourceUrls: (q.sourceDocumentNames ?? []).filter((name) => /^https?:\/\//i.test(name)),
        mcqCount: q.type === 'mcq' ? 1 : 0,
        theoryCount: q.type === 'mcq' ? 0 : 1,
        bloomLevel: currentBloomLevel,
        topicHint: `${topicHint.trim() || 'Use the supplied sources'}. Write a different question from: ${q.text}`,
        saveToBank: false,
      });
      const updated: Question = { ...result.questions[0], id: q.id };
      setGeneratedQuestions((prev) => prev.map((item) => (item.id === q.id ? updated : item)));
      updateBankQuestion(q.id, updated);
      showToast(`Regenerated question with fresh ${currentBloomLevel}-level framing!`);
    } catch (error) {
      setStudioError(error instanceof Error ? error.message : 'Question regeneration failed.');
    } finally {
      setRegeneratingId(null);
    }
  };

  const handleStartEditQuestion = (q: Question) => {
    setEditingQuestionId(q.id);
    setEditDraft({
      text: q.text,
      marks: q.marks,
      competency: q.competency,
      bloomLevel: q.bloomLevel,
      correctAnswer: q.correctAnswer || '',
      markingRubric: q.markingRubric || '',
      options: q.options ? [...q.options] : undefined,
    });
  };

  const handleSaveEditQuestion = (id: string) => {
    setGeneratedQuestions((prev) =>
      prev.map((q) => (q.id === id ? { ...q, ...editDraft } : q))
    );
    updateBankQuestion(id, editDraft);
    setEditingQuestionId(null);
    showToast('Saved question edits to Question Bank.');
  };

  const handleDeleteGeneratedQuestion = (id: string) => {
    setGeneratedQuestions((prev) => prev.filter((q) => q.id !== id));
    deleteBankQuestion(id);
    showToast('Removed question from preview and Question Bank.');
  };

  const handleAssignStudioAssignment = async () => {
    if (!targetClass || !targetSubject || !currentUser?.schoolId || generatedQuestions.length === 0 || isAssigning) {
      showToast('Select a class and subject, then generate questions first.', 'warning');
      return;
    }
    const nextCycleNumber =
      Math.max(
        0,
        ...assessments
          .filter((item) => item.classId === targetClassId && item.subjectId === genSubjectId)
          .map((item) => item.cycleNumber)
      ) + 1;
    setIsAssigning(true);
    try {
      await addAssessment({
        schoolId: currentUser.schoolId,
        classId: targetClass.id,
        subjectId: targetSubject.id,
        title: `${targetSubject.name} Assignment`,
        cycleNumber: nextCycleNumber,
        date: new Date().toISOString().slice(0, 10),
        durationMinutes: 45,
        totalMarks: generatedQuestions.reduce((total, question) => total + question.marks, 0),
        questions: generatedQuestions,
        status: 'scheduled',
        competencyFocus: Array.from(new Set(generatedQuestions.map((question) => question.competency))),
      });
      showToast(`Assigned ${targetSubject.name} to ${targetClass.name}. Students can open it in Upload Beta.`);
    } catch (error) {
      showToast(error instanceof Error ? error.message : 'Could not assign the assignment.', 'warning');
    } finally {
      setIsAssigning(false);
    }
  };

  // ============================================================================
  // EXPORT PAPER (PRINTABLE PDF & WORD .DOCX/.DOC)
  // ============================================================================
  const handleExportWordDoc = (questionsToExport: Question[], paperTitle: string) => {
    const subjectObj = subjects.find((s) => s.id === genSubjectId);
    const totalMarks = questionsToExport.reduce((s, q) => s + q.marks, 0);

    const htmlContent = `
      <html xmlns:o="urn:schemas-microsoft-com:office:office"
            xmlns:w="urn:schemas-microsoft-com:office:word"
            xmlns="http://www.w3.org/TR/REC-html40">
      <head>
        <meta charset="utf-8" />
        <title>${paperTitle}</title>
        <style>
          body { font-family: Calibri, Arial, sans-serif; color: #182230; line-height: 1.5; padding: 24px; }
          h1 { color: #142A43; font-size: 20pt; margin-bottom: 4px; }
          .meta { color: #667085; font-size: 10pt; margin-bottom: 18px; border-bottom: 2px solid #142A43; padding-bottom: 10px; }
          .q-box { margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid #E1E7ED; }
          .q-header { font-weight: bold; color: #142A43; font-size: 11pt; }
          .badge { background: #E6F4F1; color: #16A085; padding: 2px 6px; font-size: 9pt; border-radius: 4px; margin-right: 6px; }
          .options { margin-left: 20px; margin-top: 6px; }
          .rubric { background: #F3F6F8; padding: 8px; font-size: 9.5pt; color: #142A43; margin-top: 6px; border-left: 3px solid #16A085; }
        </style>
      </head>
      <body>
        <h1>LumenEIOS — ${paperTitle}</h1>
        <div class="meta">
          <strong>Subject:</strong> ${subjectObj?.name || 'Mathematics'} &nbsp;|&nbsp;
          <strong>Bloom Target:</strong> ${currentBloomLevel} &nbsp;|&nbsp;
          <strong>Total Questions:</strong> ${questionsToExport.length} &nbsp;|&nbsp;
          <strong>Total Marks:</strong> ${totalMarks}
        </div>
        ${questionsToExport
          .map(
            (q, i) => `
          <div class="q-box">
            <div class="q-header">
              Q${i + 1}. [${q.type.toUpperCase()} • ${q.marks} Marks • Competency: ${q.competency} • Bloom: ${q.bloomLevel}]
            </div>
            <p>${q.text}</p>
            ${
              q.options && q.options.length > 0
                ? `<div class="options">${q.options.map((opt) => `<div>${opt}</div>`).join('')}</div>`
                : ''
            }
            <div class="rubric">
              <strong>Official Answer Key:</strong> ${q.correctAnswer || 'See rubric'}<br/>
              <strong>Marking Rubric:</strong> ${q.markingRubric || 'Standard competency rubric applies.'}<br/>
              ${
                q.sourceDocumentNames && q.sourceDocumentNames.length > 0
                  ? `<strong>Grounded Source(s):</strong> ${q.sourceDocumentNames.join(', ')}`
                  : ''
              }
            </div>
          </div>
        `
          )
          .join('')}
      </body>
      </html>
    `;

    const blob = new Blob(['\ufeff', htmlContent], {
      type: 'application/msword;charset=utf-8',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${paperTitle.toLowerCase().replace(/[^a-z0-9]+/g, '_')}.doc`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast(`Exported "${paperTitle}" as Word document (.doc)!`);
  };

  const handlePrintPaperPdf = (questionsToExport: Question[], paperTitle: string) => {
    const subjectObj = subjects.find((s) => s.id === genSubjectId);
    const totalMarks = questionsToExport.reduce((s, q) => s + q.marks, 0);
    const printWin = window.open('', '_blank', 'width=900,height=700');
    if (!printWin) {
      showToast('Pop-up blocked. Please allow pop-ups to print/save as PDF.', 'warning');
      return;
    }
    printWin.document.write(`
      <html>
        <head>
          <title>${paperTitle} — LumenEIOS</title>
          <style>
            body { font-family: Inter, Arial, sans-serif; color: #182230; padding: 32px; line-height: 1.5; }
            h1 { font-size: 20px; color: #142A43; margin: 0 0 4px 0; }
            .sub { font-size: 12px; color: #667085; border-bottom: 2px solid #142A43; padding-bottom: 12px; margin-bottom: 20px; }
            .q-card { margin-bottom: 18px; padding-bottom: 14px; border-bottom: 1px solid #E1E7ED; page-break-inside: avoid; }
            .q-meta { font-size: 11px; font-weight: 700; color: #16A085; margin-bottom: 4px; }
            .q-text { font-size: 13px; font-weight: 600; margin-bottom: 8px; }
            .opts { margin-left: 16px; font-size: 12px; margin-bottom: 8px; }
            .key { background: #F3F6F8; border-left: 3px solid #142A43; padding: 8px 12px; font-size: 11px; }
          </style>
        </head>
        <body>
          <h1>LumenEIOS Adaptive EdTech Ecosystem — ${paperTitle}</h1>
          <div class="sub">
            Subject: <strong>${subjectObj?.name || 'Mathematics'}</strong> &bull;
            Cognitive Target: <strong>${currentBloomLevel}</strong> &bull;
            Items: <strong>${questionsToExport.length}</strong> &bull;
            Max Marks: <strong>${totalMarks}</strong>
          </div>
          ${questionsToExport
            .map(
              (q, i) => `
            <div class="q-card">
              <div class="q-meta">
                QUESTION ${i + 1} &bull; ${q.type.toUpperCase()} &bull; ${q.marks} MARKS &bull; COMPETENCY: ${q.competency} &bull; BLOOM: ${q.bloomLevel}
              </div>
              <div class="q-text">${q.text}</div>
              ${
                q.options && q.options.length > 0
                  ? `<div class="opts">${q.options.map((o) => `<div>${o}</div>`).join('')}</div>`
                  : ''
              }
              <div class="key">
                <div><strong>Answer Key:</strong> ${q.correctAnswer || 'Refer to rubric'}</div>
                <div><strong>Marking Rubric:</strong> ${q.markingRubric || 'Standard NEP 2020 competency rubric'}</div>
              </div>
            </div>
          `
            )
            .join('')}
        </body>
      </html>
    `);
    printWin.document.close();
    printWin.focus();
    setTimeout(() => printWin.print(), 250);
  };

  return (
    <div className="space-y-6">
      {/* Toast Notification */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-50 bg-navy-900 text-white px-4 py-3 rounded-xl shadow-modal border border-teal-500/40 text-xs flex items-center gap-2.5">
          {toast.type === 'warning' ? (
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
          ) : (
            <CheckCircle2 className="w-4 h-4 text-teal-400 shrink-0" />
          )}
          <span>{toast.message}</span>
        </div>
      )}

      {/* Studio header */}
      <div className="bg-white p-5 rounded-2xl border border-surface-border shadow-subtle flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-navy-900 tracking-tight">
              AI Question Studio Beta
            </h1>
            <Badge variant="teal" size="sm">
              NEP 2020 Grounded
            </Badge>
          </div>
          <p className="text-xs text-content-secondary mt-0.5">
            Generate Bloom-calibrated questions from a chapter PDF and assign them to a class.
          </p>
        </div>

      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* LEFT COLUMN: GENERATION CONTROLS (5 COLS) */}
        <div className="lg:col-span-5 space-y-5">
          <Card>
            <CardHeader
              title="1. Sources & Target"
              subtitle="Upload a chapter PDF, paste learning-resource links, or both. Qwen retrieves the most relevant passages to ground the questions."
            />
            <CardBody className="space-y-4 text-xs">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-navy-900 mb-1.5">Target Class</label>
                  <select
                    value={targetClassId}
                    onChange={(e) => changeClass(e.target.value)}
                    disabled={!targets?.length || isGenerating || isUploadingStudioPdf || !!regeneratingId || isAssigning}
                    className="w-full px-3 py-2 bg-white border border-surface-border rounded-xl text-xs font-medium text-navy-900 focus:outline-none focus:border-teal-600"
                  >
                    {!targets?.length && <option value="">{targets || targetError ? 'No classes available' : 'Loading classes…'}</option>}
                    {targets?.map((targetClass) => (
                      <option key={targetClass.id} value={targetClass.id}>
                        {targetClass.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block font-semibold text-navy-900 mb-1.5">Target Subject</label>
                  <select
                    value={genSubjectId}
                    onChange={(e) => changeSubject(e.target.value)}
                    disabled={!subjects.length || isGenerating || isUploadingStudioPdf || !!regeneratingId || isAssigning}
                    className="w-full px-3 py-2 bg-white border border-surface-border rounded-xl text-xs font-medium text-navy-900 focus:outline-none focus:border-teal-600"
                  >
                    {subjects.map((sub) => (
                      <option key={sub.id} value={sub.id}>
                        {sub.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              {targetError && <p role="alert" className="text-rose-700">{targetError}</p>}
              {targets?.length === 0 && <p>No classes with configured subjects are available in your school.</p>}
              <div
                className="space-y-3 rounded-xl border border-dashed border-teal-300 bg-teal-50/40 p-4"
                onDragOver={(event) => event.preventDefault()}
                onDrop={(event) => {
                  event.preventDefault();
                  const file = event.dataTransfer.files?.[0];
                  if (file) rememberChapterPdf(file);
                }}
              >
                <label htmlFor="studio-chapter-pdf" className="block font-semibold text-navy-900">
                  Upload Chapter PDF
                </label>
                <input
                  id="studio-chapter-pdf"
                  type="file"
                  accept=".pdf,application/pdf"
                  disabled={isUploadingStudioPdf || isGenerating}
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) rememberChapterPdf(file);
                  }}
                  className="block w-full text-xs text-content-secondary file:mr-3 file:rounded-lg file:border-0 file:bg-white file:px-3 file:py-2 file:font-semibold file:text-navy-900"
                />
                <div className="flex flex-wrap items-center gap-3">
                  <Button
                    type="button"
                    variant="teal"
                    size="sm"
                    disabled={!targetSubject || !studioPdfFile || isUploadingStudioPdf || isGenerating || isAssigning}
                    onClick={handleUploadStudioPdf}
                    icon={<UploadCloud className="w-3.5 h-3.5" />}
                  >
                    {isUploadingStudioPdf ? 'Uploading PDF...' : 'Upload PDF'}
                  </Button>
                  {uploadedStudioPdf && (
                    <span className="text-[11px] font-medium text-emerald-700">
                      Ready: {uploadedStudioPdf.fileName}
                    </span>
                  )}
                  {studioPdfFile && !isUploadingStudioPdf && (
                    <span>Selected: {studioPdfFile.name}</span>
                  )}
                </div>
                {chapterPdfs.length > 0 && (
                  <div className="space-y-1">
                    <p className="font-semibold text-navy-900">Chapter PDFs already uploaded</p>
                    {chapterPdfs.map((doc) => (
                      <button
                        key={doc.id}
                        type="button"
                        onClick={() => {
                          setUploadedStudioPdf(doc);
                          setStudioPdfFile(null);
                          setStudioError('');
                        }}
                        className={`block w-full truncate rounded-lg border px-2 py-1 text-left ${
                          uploadedStudioPdf?.id === doc.id
                            ? 'border-teal-500 bg-white text-navy-900'
                            : 'border-surface-border bg-white/70 text-content-secondary'
                        }`}
                      >
                        {doc.fileName}
                      </button>
                    ))}
                  </div>
                )}
                <p className="text-[11px] text-content-secondary">
                  Only PDF files (up to 15 MB, 25 pages) are accepted. Qwen uses the chapter as source context.
                  Generate Questions uploads the selected PDF automatically.
                </p>
              </div>

              <div className="space-y-2 rounded-xl border border-surface-border bg-surface-bg/60 p-3">
                <label htmlFor="studio-source-links" className="block font-semibold text-navy-900">
                  Learning-resource links <span className="font-normal text-content-secondary">(optional, up to 3)</span>
                </label>
                <textarea
                  id="studio-source-links"
                  rows={3}
                  value={studioLinksText}
                  disabled={isGenerating}
                  onChange={(e) => {
                    setStudioLinksText(e.target.value);
                    setStudioError('');
                  }}
                  placeholder={'https://en.wikipedia.org/wiki/Photosynthesis\nhttps://byjus.com/biology/photosynthesis/'}
                  className="block w-full rounded-lg border border-surface-border bg-white px-3 py-2 font-mono text-[11px] text-navy-900 focus:border-teal-500 focus:outline-none"
                />
                {studioLinks.length > 0 && !invalidStudioLink && studioLinks.length <= 3 && (
                  <p className="text-[11px] font-medium text-emerald-700">
                    {studioLinks.length} link{studioLinks.length === 1 ? '' : 's'} ready. The server reads each page when you generate.
                  </p>
                )}
                {invalidStudioLink && (
                  <p className="text-[11px] text-rose-700">"{invalidStudioLink}" is not a full web link. Start it with https://.</p>
                )}
                {studioLinks.length > 3 && <p className="text-[11px] text-rose-700">Add at most 3 links.</p>}
                <p className="text-[11px] text-content-secondary">
                  One link per line, for example Wikipedia or BYJU'S. The page text is split into passages and ranked together
                  with the PDF pages by your focus topic; Qwen then writes questions from the best matches. Pages behind a login
                  or built only with JavaScript can't be read.
                </p>
              </div>
            </CardBody>
          </Card>

          {/* GENERATION PARAMETERS CARD */}
          <Card>
            <CardHeader
              title="2. Cognitive & Item Configuration"
              subtitle="Configure MCQ/Theory counts and Bloom's Taxonomy level"
            />
            <CardBody className="space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-navy-900 mb-1">
                    Number of MCQs (2m each)
                  </label>
                  <input
                    type="number"
                    min={0}
                    max={15}
                    value={mcqCount}
                    onChange={(e) => setMcqCount(Math.max(0, Math.min(15, Number(e.target.value))))}
                    className="w-full px-3 py-2 bg-white border border-surface-border rounded-xl text-sm font-bold text-navy-900 focus:outline-none focus:border-teal-600"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-navy-900 mb-1">
                    Theory Questions (5m each)
                  </label>
                  <input
                    type="number"
                    min={0}
                    max={10}
                    value={theoryCount}
                    onChange={(e) =>
                      setTheoryCount(Math.max(0, Math.min(10, Number(e.target.value))))
                    }
                    className="w-full px-3 py-2 bg-white border border-surface-border rounded-xl text-sm font-bold text-navy-900 focus:outline-none focus:border-teal-600"
                  />
                </div>
              </div>

              {/* Bloom's Taxonomy Difficulty Slider */}
              <div className="space-y-2 pt-1">
                <div className="flex items-center justify-between">
                  <label className="font-semibold text-navy-900">
                    Bloom's Taxonomy Cognitive Slider
                  </label>
                  <Badge variant="teal" size="sm">
                    Level {bloomIndex + 1}: {currentBloomLevel}
                  </Badge>
                </div>

                <input
                  type="range"
                  min={0}
                  max={BLOOM_LEVELS.length - 1}
                  step={1}
                  value={bloomIndex}
                  onChange={(e) => setBloomIndex(Number(e.target.value))}
                  className="w-full accent-teal-600 cursor-pointer"
                />

                <div className="grid grid-cols-6 gap-1">
                  {BLOOM_LEVELS.map((lvl, idx) => (
                    <button
                      key={lvl}
                      type="button"
                      onClick={() => setBloomIndex(idx)}
                      className={`py-1 px-1 rounded-lg text-[10px] font-semibold text-center transition-all ${
                        bloomIndex === idx
                          ? 'bg-navy-900 text-white shadow-sm'
                          : 'bg-surface-bg text-content-secondary hover:bg-surface-border/60'
                      }`}
                    >
                      {lvl}
                    </button>
                  ))}
                </div>

                <p className="p-2.5 rounded-xl bg-surface-bg border border-surface-border text-[11px] text-content-secondary">
                  <strong className="text-navy-900">{currentBloomLevel}:</strong>{' '}
                  {BLOOM_DESCRIPTIONS[currentBloomLevel]}
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {(Object.keys(COMPETENCY_GUIDE) as CompetencyKey[]).map((key) => (
                  <p key={key} className="rounded-lg border border-surface-border bg-surface-bg p-2 text-[11px] text-content-secondary">
                    <strong className="text-navy-900">{key}: {COMPETENCY_GUIDE[key].name}.</strong>{' '}
                    {COMPETENCY_GUIDE[key].detail}
                  </p>
                ))}
              </div>

              {/* Optional Topic / Concept Focus */}
              <div>
                <label className="block font-semibold text-navy-900 mb-1">
                  Specific Sub-Topic or Pedagogical Focus (Optional)
                </label>
                <input
                  type="text"
                  value={topicHint}
                  onChange={(e) => setTopicHint(e.target.value)}
                  placeholder="e.g. Mensuration of Cylinders, Algebraic Identities, or Force & Pressure"
                  className="w-full px-3 py-2 bg-white border border-surface-border rounded-xl text-xs text-navy-900 focus:outline-none focus:border-teal-600"
                />
              </div>

              {/* Primary Generate Questions Button */}
              <Button
                type="button"
                variant="teal"
                size="lg"
                className="relative z-10 w-full"
                disabled={!targetSubject || isGenerating || isUploadingStudioPdf || isAssigning || !hasStudioSource || !!invalidStudioLink || studioLinks.length > 3}
                onClick={handleGenerateQuestions}
                icon={<Sparkles className="w-4 h-4" />}
              >
                {isGenerating
                  ? 'Synthesizing Grounded Questions...'
                  : `Generate Questions (${mcqCount} MCQ + ${theoryCount} Theory)`}
              </Button>
              <ProcessProgress steps={generationSteps} />
              {!hasStudioSource && !isGenerating && (
                <p className="rounded-lg bg-amber-50 p-3 text-amber-900">
                  {isUploadingStudioPdf
                    ? 'The PDF is still uploading. Generate Questions turns on when that upload finishes.'
                    : 'Generate Questions is off because there is no source yet. Choose or drop a chapter PDF, or paste a learning-resource link, above.'}
                </p>
              )}
              {studioError && (
                <p role="alert" className="rounded-lg bg-rose-50 p-3 text-rose-800">{studioError}</p>
              )}
            </CardBody>
          </Card>
        </div>

        {/* RIGHT COLUMN: GENERATED QUESTIONS PREVIEW & PAPER ACTIONS (7 COLS) */}
        <div className="lg:col-span-7 space-y-4">
          {/* Top Action Bar */}
          <Card>
            <CardBody className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <h2 className="text-sm font-bold text-navy-900 flex items-center gap-2">
                  <Wand2 className="w-4 h-4 text-teal-600" />
                  Generated Question Paper Preview ({generatedQuestions.length} Items •{' '}
                  {generatedQuestions.reduce((s, q) => s + q.marks, 0)} Marks)
                </h2>
                <p className="text-[11px] text-content-secondary mt-0.5">
                  Review and edit generated questions, export the paper, and assign it to your class.
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={generatedQuestions.length === 0}
                  onClick={() =>
                    handlePrintPaperPdf(
                      generatedQuestions,
                      `${subjects.find((s) => s.id === genSubjectId)?.name || 'Diagnostic'} Assessment Paper`
                    )
                  }
                  icon={<Printer className="w-3.5 h-3.5" />}
                >
                  Export PDF
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={generatedQuestions.length === 0}
                  onClick={() =>
                    handleExportWordDoc(
                      generatedQuestions,
                      `${subjects.find((s) => s.id === genSubjectId)?.name || 'Diagnostic'} Assessment Paper`
                    )
                  }
                  icon={<Download className="w-3.5 h-3.5" />}
                >
                  Export Word (.doc)
                </Button>
              </div>
            </CardBody>
          </Card>

          {/* SKELETON LOADING STATE */}
          {isGenerating ? (
            <div className="space-y-3">
              {[1, 2, 3].map((n) => (
                <Card key={n}>
                  <CardBody className="space-y-3 animate-pulse">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className="h-5 w-16 bg-slate-200 rounded-md" />
                        <div className="h-5 w-24 bg-slate-200 rounded-md" />
                        <div className="h-5 w-32 bg-teal-100 rounded-md" />
                      </div>
                      <div className="h-5 w-14 bg-slate-200 rounded-md" />
                    </div>
                    <div className="h-4 w-11/12 bg-slate-200 rounded" />
                    <div className="h-4 w-3/4 bg-slate-200 rounded" />
                    <div className="grid grid-cols-2 gap-2 pt-2">
                      <div className="h-8 bg-slate-100 rounded-lg" />
                      <div className="h-8 bg-slate-100 rounded-lg" />
                    </div>
                  </CardBody>
                </Card>
              ))}
            </div>
          ) : generatedQuestions.length === 0 ? (
            <Card>
              <CardBody className="py-12 text-center space-y-2">
                <Sparkles className="w-8 h-8 text-teal-600 mx-auto" />
                <h3 className="text-sm font-bold text-navy-900">No Questions in Preview</h3>
                <p className="text-xs text-content-secondary max-w-md mx-auto">
                  Upload a chapter PDF or paste a learning-resource link, adjust the Bloom's Taxonomy level, and click Generate Questions.
                </p>
              </CardBody>
            </Card>
          ) : (
            <div className="space-y-3.5">
              {generatedQuestions.map((q, idx) => {
                const isEditing = editingQuestionId === q.id;
                const isRegeneratingThis = regeneratingId === q.id;

                return (
                  <Card
                    key={q.id}
                    className={`transition-all ${
                      isRegeneratingThis ? 'opacity-60 pointer-events-none' : ''
                    }`}
                  >
                    <CardBody className="space-y-3 text-xs">
                      {/* Question Card Top Header */}
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <span className="px-2 py-0.5 rounded-md bg-navy-900 text-white font-bold text-[11px]">
                            Q{idx + 1}
                          </span>
                          <Badge variant={q.type === 'mcq' ? 'info' : 'teal'} size="sm">
                            {q.type === 'mcq' ? 'MCQ' : 'THEORY / DESCRIPTIVE'}
                          </Badge>
                          <Badge variant="outline" size="sm">
                            {q.competency}: {COMPETENCY_GUIDE[q.competency]?.name || q.competency}
                          </Badge>
                          <Badge variant="outline" size="sm">
                            Bloom: {q.bloomLevel}
                          </Badge>
                          {q.sourceDocumentNames &&
                            q.sourceDocumentNames.map((srcName) => (
                              <span
                                key={srcName}
                                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-teal-50 text-teal-800 border border-teal-200 text-[10px] font-medium max-w-[210px] truncate"
                                title={`Grounded in: ${srcName}`}
                              >
                                <FileText className="w-3 h-3 shrink-0 text-teal-600" />
                                <span className="truncate">{srcName}</span>
                              </span>
                            ))}
                        </div>

                        <div className="flex items-center gap-1.5">
                          <span className="font-bold text-navy-900 px-2 py-0.5 bg-surface-bg rounded-md border border-surface-border">
                            {q.marks} {q.marks === 1 ? 'Mark' : 'Marks'}
                          </span>

                          <button
                            type="button"
                            onClick={() =>
                              isEditing ? handleSaveEditQuestion(q.id) : handleStartEditQuestion(q)
                            }
                            className="p-1.5 rounded-lg border border-surface-border bg-white hover:bg-surface-bg text-navy-800 transition-colors"
                            title={isEditing ? 'Save Changes' : 'Edit Question'}
                          >
                            {isEditing ? (
                              <Check className="w-3.5 h-3.5 text-emerald-600" />
                            ) : (
                              <Edit3 className="w-3.5 h-3.5" />
                            )}
                          </button>

                          <button
                            type="button"
                            onClick={() => handleRegenerateSingle(q)}
                            disabled={isGenerating || regeneratingId !== null || isAssigning}
                            className="p-1.5 rounded-lg border border-surface-border bg-white hover:bg-teal-50 text-teal-700 transition-colors"
                            title="Regenerate Question"
                          >
                            <RefreshCw
                              className={`w-3.5 h-3.5 ${
                                isRegeneratingThis ? 'animate-spin' : ''
                              }`}
                            />
                          </button>

                          <button
                            type="button"
                            onClick={() => handleDeleteGeneratedQuestion(q.id)}
                            className="p-1.5 rounded-lg border border-surface-border bg-white hover:bg-rose-50 text-rose-600 transition-colors"
                            title="Delete Question"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>

                      {/* INLINE EDITOR OR QUESTION DISPLAY */}
                      {isEditing ? (
                        <div className="space-y-2.5 p-3 bg-surface-bg rounded-xl border border-surface-border">
                          <div>
                            <label className="block font-semibold text-navy-900 mb-1">
                              Question Text
                            </label>
                            <textarea
                              rows={3}
                              value={editDraft.text || ''}
                              onChange={(e) =>
                                setEditDraft((d) => ({ ...d, text: e.target.value }))
                              }
                              className="w-full px-3 py-2 bg-white border border-surface-border rounded-lg text-xs"
                            />
                          </div>

                          <div className="grid grid-cols-3 gap-2">
                            <div>
                              <label className="block font-semibold text-navy-900 mb-1">
                                Marks
                              </label>
                              <input
                                type="number"
                                min={1}
                                max={20}
                                value={editDraft.marks || 2}
                                onChange={(e) =>
                                  setEditDraft((d) => ({ ...d, marks: Number(e.target.value) }))
                                }
                                className="w-full px-2.5 py-1.5 bg-white border border-surface-border rounded-lg text-xs"
                              />
                            </div>
                            <div>
                              <label className="block font-semibold text-navy-900 mb-1">
                                Competency
                              </label>
                              <select
                                value={editDraft.competency || 'CU'}
                                onChange={(e) =>
                                  setEditDraft((d) => ({
                                    ...d,
                                    competency: e.target.value as CompetencyKey,
                                  }))
                                }
                                className="w-full px-2.5 py-1.5 bg-white border border-surface-border rounded-lg text-xs"
                              >
                                <option value="LU">LU</option>
                                <option value="CU">CU</option>
                                <option value="AU">AU</option>
                                <option value="CT">CT</option>
                              </select>
                            </div>
                            <div>
                              <label className="block font-semibold text-navy-900 mb-1">
                                Bloom Level
                              </label>
                              <select
                                value={editDraft.bloomLevel || 'Analyze'}
                                onChange={(e) =>
                                  setEditDraft((d) => ({
                                    ...d,
                                    bloomLevel: e.target.value as BloomLevel,
                                  }))
                                }
                                className="w-full px-2.5 py-1.5 bg-white border border-surface-border rounded-lg text-xs"
                              >
                                {BLOOM_LEVELS.map((b) => (
                                  <option key={b} value={b}>
                                    {b}
                                  </option>
                                ))}
                              </select>
                            </div>
                          </div>

                          <div>
                            <label className="block font-semibold text-navy-900 mb-1">
                              Official Answer Key / Model Response
                            </label>
                            <input
                              type="text"
                              value={editDraft.correctAnswer || ''}
                              onChange={(e) =>
                                setEditDraft((d) => ({ ...d, correctAnswer: e.target.value }))
                              }
                              className="w-full px-3 py-1.5 bg-white border border-surface-border rounded-lg text-xs"
                            />
                          </div>

                          <div>
                            <label className="block font-semibold text-navy-900 mb-1">
                              Marking Rubric
                            </label>
                            <input
                              type="text"
                              value={editDraft.markingRubric || ''}
                              onChange={(e) =>
                                setEditDraft((d) => ({ ...d, markingRubric: e.target.value }))
                              }
                              className="w-full px-3 py-1.5 bg-white border border-surface-border rounded-lg text-xs"
                            />
                          </div>

                          <div className="flex justify-end gap-2 pt-1">
                            <Button
                              variant="secondary"
                              size="sm"
                              onClick={() => setEditingQuestionId(null)}
                            >
                              Cancel
                            </Button>
                            <Button
                              variant="teal"
                              size="sm"
                              onClick={() => handleSaveEditQuestion(q.id)}
                            >
                              Save Changes
                            </Button>
                          </div>
                        </div>
                      ) : (
                        <>
                          <p className="text-sm font-medium text-navy-900 leading-relaxed">
                            {q.text}
                          </p>

                          {/* MCQ Options */}
                          {q.options && q.options.length > 0 && (
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1">
                              {q.options.map((opt, oIdx) => {
                                const isCorrect =
                                  q.correctAnswer &&
                                  (opt === q.correctAnswer ||
                                    opt.startsWith(q.correctAnswer.slice(0, 4)));
                                return (
                                  <div
                                    key={oIdx}
                                    className={`p-2.5 rounded-xl border text-xs flex items-start justify-between gap-2 ${
                                      isCorrect
                                        ? 'bg-emerald-50/70 border-emerald-400 text-emerald-950 font-semibold'
                                        : 'bg-surface-bg/60 border-surface-border text-content-secondary'
                                    }`}
                                  >
                                    <span>{opt}</span>
                                    {isCorrect && (
                                      <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          )}

                          {/* Official Answer Key & Rubric Box */}
                          <div className="p-3 rounded-xl bg-teal-50/50 border border-teal-200/70 space-y-1 text-[11px]">
                            {q.correctAnswer && (
                              <div className="text-navy-900">
                                <strong className="text-teal-900">
                                  {q.type === 'mcq' ? 'Recommended answer:' : 'Recommended answer:'}
                                </strong>{' '}
                                {q.correctAnswer}
                              </div>
                            )}
                            {q.markingRubric && (
                              <div className="text-content-secondary">
                                <strong className="text-navy-900">Marking Rubric:</strong>{' '}
                                {q.markingRubric}
                              </div>
                            )}
                          </div>
                        </>
                      )}
                    </CardBody>
                  </Card>
                );
              })}
            </div>
          )}
          <div className="bg-white p-3.5 rounded-2xl border border-surface-border shadow-subtle flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
            <span className="font-medium text-content-secondary">
              Assign to {targetClass?.name || 'target class'} · {targetSubject?.name || 'target subject'}
            </span>
            <Button
              variant="primary"
              size="sm"
              disabled={!targetClass || !targetSubject || isGenerating || !!regeneratingId || generatedQuestions.length === 0}
              loading={isAssigning}
              onClick={handleAssignStudioAssignment}
              icon={<FileCheck2 className="w-3.5 h-3.5" />}
            >
              Assign the Assignment
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};
