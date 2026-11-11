/**
 * LumenEIOS Production API Client
 * Facilitates typed asynchronous communication with the FastAPI backend.
 * Provides resilient fallback handling for local offline demonstration environments.
 */

import type { Role, Student, User } from '../types';

const API_BASE_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000/api/v1';

type AccountDetails = {
  name: string;
  email: string;
  password: string;
  phone?: string;
  address?: string;
  date_of_birth?: string;
};

type ApiUser = Pick<User, 'id' | 'name' | 'email'> & {
  role: Role;
  school_id: string | null;
  avatar?: string;
  designation?: string;
  demo_root?: boolean;
};

export type SubscriptionRow = {
  id: string;
  kind: 'base' | 'seats';
  status: string;
  quantity: number;
  paypal_subscription_id: string | null;
};

export type StartSubscriptionResult = {
  subscriptions: SubscriptionRow[];
  approve_links: string[];
};

export class ApiError extends Error {
  constructor(public status: number, message: string, public data?: any) {
    super(message);
    this.name = 'ApiError';
  }
}

export type ProcessStep = {
  step: string;
  label: string;
  done: number;
  total: number;
};

export type AssignmentTarget = { id: string; name: string; subjects: { id: string; name: string }[] };

export type UploadAssignment = {
  id: string;
  title: string;
  date: string;
  class_name: string;
  subject_name: string;
  total_marks: number;
  uploaded: boolean;
  questions: { id: string | null; text: string; type: string; options: string[] | null; marks: number; competency: string | null }[];
};

function authHeaders(options: RequestInit = {}): Record<string, string> {
  const token = localStorage.getItem('lumeneios_token');
  const currentSchoolId = localStorage.getItem('lumeneios_current_school') || 'school-1';
  const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData;
  const headers: Record<string, string> = {
    ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
    'X-School-Id': currentSchoolId,
    ...(options.headers as Record<string, string>),
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return headers;
}

function errorMessage(errorBody: any, fallback: string) {
  const detail = errorBody?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => (typeof item === 'string' ? item : item?.msg || 'Request failed')).join(' ');
  }
  return fallback;
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  try {
    const response = await fetch(url, { ...options, headers: authHeaders(options) });

    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({ detail: response.statusText }));
      throw new ApiError(response.status, errorMessage(errorBody, 'API request failed') || 'API request failed', errorBody);
    }

    return await response.json();
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    throw new ApiError(0, err.message || 'Network connection to LumenEIOS backend failed');
  }
}

async function postEventStream<T>(
  endpoint: string,
  options: RequestInit,
  onProgress: (step: ProcessStep) => void,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${endpoint}`, { ...options, headers: authHeaders(options) });
  } catch (err: any) {
    throw new ApiError(0, err.message || 'Network connection to LumenEIOS backend failed');
  }
  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({ detail: response.statusText }));
    throw new ApiError(response.status, errorMessage(errorBody, 'API request failed') || 'API request failed', errorBody);
  }
  if (!response.body) throw new ApiError(0, 'The server did not report progress.');

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let result: T | undefined;
  let failed: ApiError | undefined;
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split('\n\n');
    buffer = chunks.pop() ?? '';
    for (const chunk of chunks) {
      const line = chunk.split('\n').find((item) => item.startsWith('data: '));
      if (!line) continue;
      const event = JSON.parse(line.slice(6));
      if (event.kind === 'progress') onProgress(event);
      else if (event.kind === 'complete') result = event.result as T;
      else if (event.kind === 'error') failed = new ApiError(event.status || 500, event.message || 'The process failed.');
    }
  }
  if (failed) throw failed;
  if (result === undefined) throw new ApiError(0, 'The server closed the progress stream before finishing.');
  return result;
}

function mapQuestionOut(q: any) {
  return {
    id: q.id,
    assessmentId: q.assessment_id || q.assessmentId,
    subjectId: q.subject_id || q.subjectId,
    text: q.text,
    type: q.type,
    options: q.options || undefined,
    correctAnswer: q.correct_answer ?? q.correctAnswer,
    markingRubric: q.marking_rubric ?? q.markingRubric,
    marks: q.marks,
    competency: q.competency,
    bloomLevel: q.bloom_level || q.bloomLevel,
    sourceDocumentIds: q.source_document_ids || q.sourceDocumentIds || [],
    sourceDocumentNames: q.source_document_names || q.sourceDocumentNames || [],
    isAiGenerated: q.is_ai_generated ?? q.isAiGenerated ?? false,
  };
}

function mapSourceDocOut(d: any) {
  return {
    id: d.id,
    schoolId: d.school_id || d.schoolId || 'school-1',
    subjectId: d.subject_id || d.subjectId,
    uploadedBy: d.uploaded_by || d.uploadedBy || 'user-teacher-1',
    fileName: d.file_name || d.fileName,
    mimeType: d.mime_type || d.mimeType,
    fileSize: d.file_size ?? d.fileSize ?? 0,
    pageCount: d.page_count ?? d.pageCount ?? 1,
    docType: d.doc_type || d.docType || 'source_material',
    status: d.status || 'ready',
    extractedTextPreview: d.extracted_text_preview || d.extractedTextPreview || '',
    createdAt: d.created_at || d.createdAt,
  };
}

function mapBatchItemOut(it: any) {
  return {
    id: it.id,
    batchId: it.batch_id || it.batchId,
    documentId: it.document_id ?? it.documentId ?? null,
    fileName: it.file_name || it.fileName,
    fileSize: it.file_size ?? it.fileSize ?? 0,
    mimeType: it.mime_type || it.mimeType || 'application/pdf',
    pageCount: it.page_count ?? it.pageCount ?? 1,
    pageRange: it.page_range ?? it.pageRange ?? null,
    status: it.status,
    stageProgress: it.stage_progress ?? it.stageProgress ?? 0,
    errorMessage: it.error_message ?? it.errorMessage ?? null,
    retryCount: it.retry_count ?? it.retryCount ?? 0,
    studentId: it.student_id ?? it.studentId ?? null,
    studentName: it.student_name ?? it.studentName ?? null,
    studentConfidence: it.student_confidence ?? it.studentConfidence ?? 0,
    ocrConfidence: it.ocr_confidence ?? it.ocrConfidence ?? 0,
    extractedText: it.extracted_text ?? it.extractedText ?? null,
    questionEvaluations: it.question_evaluations || it.questionEvaluations || [],
    marksObtained: it.marks_obtained ?? it.marksObtained ?? 0,
    maxMarks: it.max_marks ?? it.maxMarks ?? 25,
    percentage: it.percentage ?? 0,
    grade: it.grade || 'C',
    competencyScores: it.competency_scores || it.competencyScores || {},
    requiresReview: it.requires_review ?? it.requiresReview ?? false,
    reviewReasons: it.review_reasons || it.reviewReasons || [],
    teacherApproved: it.teacher_approved ?? it.teacherApproved ?? false,
    approvedById: it.approved_by_id ?? it.approvedById ?? null,
    approvedAt: it.approved_at ?? it.approvedAt ?? null,
  };
}

function mapBatchOut(b: any) {
  return {
    id: b.id,
    schoolId: b.school_id || b.schoolId || 'school-1',
    classId: b.class_id || b.classId,
    className: b.class_name ?? b.className ?? null,
    subjectId: b.subject_id || b.subjectId,
    subjectName: b.subject_name ?? b.subjectName ?? null,
    assessmentId: b.assessment_id || b.assessmentId,
    assessmentTitle: b.assessment_title ?? b.assessmentTitle ?? null,
    createdById: b.created_by_id || b.createdById || 'user-teacher-1',
    uploadMode: b.upload_mode || b.uploadMode || 'bulk',
    status: b.status,
    totalFiles: b.total_files ?? b.totalFiles ?? 0,
    validFiles: b.valid_files ?? b.validFiles ?? 0,
    invalidOrDuplicateFiles: b.invalid_or_duplicate_files ?? b.invalidOrDuplicateFiles ?? 0,
    completedFiles: b.completed_files ?? b.completedFiles ?? 0,
    reviewRequiredFiles: b.review_required_files ?? b.reviewRequiredFiles ?? 0,
    failedFiles: b.failed_files ?? b.failedFiles ?? 0,
    splitMultiPdf: b.split_multi_pdf ?? b.splitMultiPdf ?? false,
    concurrencyLimit: b.concurrency_limit ?? b.concurrencyLimit ?? 4,
    createdAt: b.created_at ?? b.createdAt ?? null,
    completedAt: b.completed_at ?? b.completedAt ?? null,
    items: Array.isArray(b.items) ? b.items.map(mapBatchItemOut) : [],
  };
}

export type AssistantTurn = { role: 'user' | 'assistant'; content: string };
export type AssistantReply = {
  answer: string;
  links: { label: string; path: string }[];
  model_available: boolean;
  citations: { document_id: string; name: string; page: number }[];
};

export const apiClient = {
  assistant: {
    chat: (message: string, history: AssistantTurn[], signal: AbortSignal, searchLibrary = false) =>
      request<AssistantReply>('/assistant/chat', {
        method: 'POST', body: JSON.stringify({ message, history, search_library: searchLibrary }), signal,
      }),
    document: async (id: string) => {
      const response = await fetch(`${API_BASE_URL}/documents/${encodeURIComponent(id)}/download`, {
        headers: authHeaders(),
      });
      if (!response.ok) throw new ApiError(response.status, 'Could not open the source PDF.');
      return response.blob();
    },
  },
  // Authentication
  auth: {
    async login(email: string, password: string) {
      const res = await request<{ access_token: string; user: ApiUser }>('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      });
      if (res.access_token) {
        localStorage.setItem('lumeneios_token', res.access_token);
      }
      return res;
    },
    async me() {
      return request<ApiUser>('/auth/me');
    },
    async switchDemoRole(role: Role) {
      const response = await request<{ access_token: string; user: ApiUser }>('/auth/demo-root/role', {
        method: 'POST',
        body: JSON.stringify({ role }),
      });
      localStorage.setItem('lumeneios_token', response.access_token);
      return response.user;
    },
    async switchSchool(schoolId: string) {
      const res = await request<{ access_token: string; user: ApiUser }>('/auth/switch-school', {
        method: 'POST',
        body: JSON.stringify({ school_id: schoolId }),
      });
      if (res.access_token) {
        localStorage.setItem('lumeneios_token', res.access_token);
      }
      return res;
    },
    async logout() {
      localStorage.removeItem('lumeneios_token');
      try {
        await request('/auth/logout', { method: 'POST' });
      } catch {
        // Ignore logout network errors
      }
    },
  },

  onboarding: {
    classes(schoolId: string) {
      return request<Array<{ id: string; name: string }>>(`/schools/${encodeURIComponent(schoolId)}/classes`);
    },
    addStudent(details: AccountDetails & { class_id: string; roll_no: number; gender: string }) {
      return request<ApiUser>('/onboarding/students', { method: 'POST', body: JSON.stringify(details) });
    },
    addTeacher(details: AccountDetails & { designation?: string }) {
      return request<ApiUser>('/onboarding/teachers', { method: 'POST', body: JSON.stringify(details) });
    },
    addSchool(details: {
      name: string; location: string; state: string; infrastructure_tier: string;
      academic_year: string; official_working_days: number; principal: AccountDetails;
    }) {
      return request<{ id: string; name: string }>('/onboarding/schools', {
        method: 'POST', body: JSON.stringify(details),
      });
    },
  },

  student: {
    async profile(): Promise<Student & { subjectNames: string[]; parentNames: string[] }> {
      const student = await request<any>('/classes/students/me');
      return {
        id: student.id,
        schoolId: student.school_id,
        classId: student.class_id,
        className: student.class_name,
        name: student.name,
        rollNo: student.roll_no,
        gender: student.gender,
        attendancePct: student.attendance_pct,
        competencies: student.competencies,
        baselineCompetencies: student.baseline_competencies,
        learningModality: student.learning_modality,
        parentId: student.parent_id,
        homeworkCompletionRate: student.homework_completion_rate,
        needsSupport: student.needs_support,
        supportArea: student.support_area,
        subjectNames: student.subject_names,
        parentNames: student.parent_names,
      };
    },
  },

  // Schools
  schools: {
    async getAll() {
      return request<any[]>('/schools');
    },
    async getById(id: string) {
      return request<any>(`/schools/${id}`);
    },
  },

  teachers: {
    async create(teacher: { name: string; email: string; designation: string; schoolId: string }) {
      return request<any>('/teachers', {
        method: 'POST',
        body: JSON.stringify({
          name: teacher.name,
          email: teacher.email,
          designation: teacher.designation,
          school_id: teacher.schoolId,
        }),
        signal: AbortSignal.timeout(4000),
      });
    },
  },

  classes: {
    async create(schoolId: string, name: string) {
      return request<any>('/classes', {
        method: 'POST',
        body: JSON.stringify({ school_id: schoolId, name }),
      });
    },
  },

  // Documents & Bulk Source Upload
  documents: {
    async list(subjectId?: string, docType: string = 'source_material') {
      const params = new URLSearchParams();
      if (subjectId) params.append('subject_id', subjectId);
      if (docType) params.append('doc_type', docType);
      const docs = await request<any[]>(`/documents?${params.toString()}`);
      return docs.map(mapSourceDocOut);
    },
    async bulkUpload(files: File[], subjectId?: string, docType: string = 'source_material') {
      const formData = new FormData();
      files.forEach((f) => formData.append('files', f));
      if (subjectId) formData.append('subject_id', subjectId);
      formData.append('doc_type', docType);
      const res = await request<any>('/documents/bulk-upload', {
        method: 'POST',
        body: formData,
      });
      return {
        totalSelected: res.total_selected,
        uploadedCount: res.uploaded_count,
        duplicateCount: res.duplicate_count,
        failedCount: res.failed_count,
        items: (res.items || []).map((it: any) => ({
          fileName: it.file_name,
          fileSize: it.file_size,
          mimeType: it.mime_type,
          status: it.status,
          documentId: it.document_id,
          pageCount: it.page_count,
          errorMessage: it.error_message,
          extractedTextPreview: it.extracted_text_preview,
        })),
      };
    },
    async uploadStudioPdf(file: File, subjectId: string) {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('subject_id', subjectId);
      const document = await request<any>('/documents/studio-pdf-upload', {
        method: 'POST',
        body: formData,
      });
      return mapSourceDocOut(document);
    },
    async delete(documentId: string) {
      return request<any>(`/documents/${documentId}`, {
        method: 'DELETE',
      });
    },
  },

  // Academic Calendar & Disruptions
  calendar: {
    async getSchoolCalendar(schoolId: string) {
      return request<any>(`/schools/${schoolId}/calendar`);
    },
    async recordDisruption(schoolId: string, data: { date: string; reason: string; days_lost: number; notes?: string }) {
      return request<any>(`/schools/${schoolId}/disruptions`, {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },
    async deleteDisruption(disruptionId: string) {
      return request<any>(`/disruptions/${disruptionId}`, {
        method: 'DELETE',
      });
    },
  },

  // Time-Aware Pedagogical Engine
  timeAware: {
    async calculatePacing(classId: string, data: { total_official_days: number; current_day: number }) {
      return request<any>(`/classes/${classId}/time-aware/calculate`, {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },
    async previewCompression(classId: string, data: { total_official_days: number; current_day: number }) {
      return request<any>(`/classes/${classId}/time-aware/compression-preview`, {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },
    async approveProposal(proposalId: string, action: 'approve' | 'reject' = 'approve') {
      return request<any>(`/curriculum-proposals/${proposalId}/approve`, {
        method: 'POST',
        body: JSON.stringify({ action }),
      });
    },
  },

  // Assessments & AI Question Generation
  assessments: {
    async getAll() {
      return request<any[]>('/assessments');
    },
    targets() {
      return request<AssignmentTarget[]>('/assessments/targets');
    },
    uploadAssignments() {
      return request<UploadAssignment[]>('/assessments/upload-assignments');
    },
    async create(classId: string, data: any) {
      return request<{ id: string; school_id: string }>(`/classes/${encodeURIComponent(classId)}/assessments`, {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },
    async getSubmissions(assessmentId: string) {
      return request<any[]>(`/assessments/${assessmentId}/submissions`);
    },
    async submitGrade(assessmentId: string, data: any) {
      return request<any>(`/assessments/${assessmentId}/submissions`, {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },
    async getQuestionBank(subjectId?: string, bloomLevel?: string) {
      const params = new URLSearchParams();
      if (subjectId) params.append('subject_id', subjectId);
      if (bloomLevel) params.append('bloom_level', bloomLevel);
      const list = await request<any[]>(`/assessments/question-bank?${params.toString()}`);
      return list.map(mapQuestionOut);
    },
    async generateQuestionsBeta(data: {
      subjectId: string;
      subjectName: string;
      sourceDocumentIds: string[];
      sourceUrls?: string[];
      mcqCount: number;
      theoryCount: number;
      bloomLevel: string;
      topicHint?: string;
      saveToBank?: boolean;
    }, onProgress?: (step: ProcessStep) => void) {
      const body = JSON.stringify({
        subject_id: data.subjectId,
        subject_name: data.subjectName,
        source_document_ids: data.sourceDocumentIds,
        source_urls: data.sourceUrls ?? [],
        mcq_count: data.mcqCount,
        theory_count: data.theoryCount,
        bloom_level: data.bloomLevel,
        focus_topic: data.topicHint || undefined,
        save_to_bank: data.saveToBank ?? true,
      });
      const res = onProgress
        ? await postEventStream<any>('/assessments/generate-questions-beta/stream', { method: 'POST', body }, onProgress)
        : await request<any>('/assessments/generate-questions-beta', { method: 'POST', body });
      return {
        subjectId: res.subject_id,
        bloomLevel: res.bloom_level,
        sourceDocumentsUsed: res.source_documents_used || [],
        model: res.model,
        generatedCount: res.generated_count,
        questions: (res.questions || []).map(mapQuestionOut),
      };
    },
    async updateQuestion(questionId: string, data: Partial<{
      text: string;
      type: string;
      options: string[];
      correctAnswer: string;
      markingRubric: string;
      marks: number;
      competency: string;
      bloomLevel: string;
    }>) {
      const res = await request<any>(`/assessments/questions/${questionId}`, {
        method: 'PUT',
        body: JSON.stringify({
          text: data.text,
          type: data.type,
          options: data.options,
          correct_answer: data.correctAnswer,
          marking_rubric: data.markingRubric,
          marks: data.marks,
          competency: data.competency,
          bloom_level: data.bloomLevel,
        }),
      });
      return mapQuestionOut(res);
    },
    async deleteQuestion(questionId: string) {
      return request<any>(`/assessments/questions/${questionId}`, {
        method: 'DELETE',
      });
    },
  },

  // OCR, Optical Verification & Auto-Grade Batch Engine
  ocr: {
    history() {
      return request<Array<{
        id: string; file_name: string; extracted_text: string; pages_processed: number; created_at: string;
        assignment_title: string | null;
      }>>('/ocr/history');
    },
    async extractPreview(
      files: File[],
      waitBeforeEachImage: boolean,
      onProgress?: (step: ProcessStep) => void,
      assessmentId?: string,
    ) {
      const formData = new FormData();
      formData.append('wait_before_each_image', String(waitBeforeEachImage));
      if (assessmentId) formData.append('assessment_id', assessmentId);
      files.forEach((file) => formData.append('files', file));

      const response = onProgress
        ? await postEventStream<{
            provider: string;
            model_version: string;
            results: { file_name: string; extracted_text: string; pages_processed: number }[];
          }>('/ocr/extract-preview/stream', { method: 'POST', body: formData }, onProgress)
        : await request<{
            provider: string;
            model_version: string;
            results: { file_name: string; extracted_text: string; pages_processed: number }[];
          }>('/ocr/extract-preview', { method: 'POST', body: formData });

      return {
        provider: response.provider,
        modelVersion: response.model_version,
        results: response.results.map((result) => ({
          fileName: result.file_name,
          extractedText: result.extracted_text,
          pagesProcessed: result.pages_processed,
        })),
      };
    },
    async processDocument(documentId: string, provider: string = 'simulated') {
      return request<any>('/ocr/process', {
        method: 'POST',
        body: JSON.stringify({ document_id: documentId, provider }),
      });
    },
    async verifyHumanReview(data: {
      document_id: string;
      student_id: string;
      assessment_id: string;
      verified_items: any[];
      teacher_notes?: string;
    }) {
      return request<any>('/ocr/review/verify', {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },
    async createBatch(params: {
      classId: string;
      subjectId: string;
      assessmentId: string;
      uploadMode: 'single' | 'bulk';
      splitMultiPdf?: boolean;
      concurrencyLimit?: number;
      files: File[];
    }) {
      const formData = new FormData();
      formData.append('class_id', params.classId);
      formData.append('subject_id', params.subjectId);
      formData.append('assessment_id', params.assessmentId);
      formData.append('upload_mode', params.uploadMode);
      formData.append('split_multi_pdf', String(Boolean(params.splitMultiPdf)));
      formData.append('concurrency_limit', String(params.concurrencyLimit || 4));
      params.files.forEach((f) => formData.append('files', f));

      const res = await request<any>('/ocr/batches', {
        method: 'POST',
        body: formData,
      });
      return mapBatchOut(res);
    },
    async listBatches(assessmentId?: string, classId?: string) {
      const params = new URLSearchParams();
      if (assessmentId) params.append('assessment_id', assessmentId);
      if (classId) params.append('class_id', classId);
      const list = await request<any[]>(`/ocr/batches?${params.toString()}`);
      return list.map(mapBatchOut);
    },
    async getBatch(batchId: string) {
      const res = await request<any>(`/ocr/batches/${batchId}`);
      return mapBatchOut(res);
    },
    async startBatch(batchId: string, waitForCompletion: boolean = false) {
      const res = await request<any>(`/ocr/batches/${batchId}/start?wait_for_completion=${waitForCompletion}`, {
        method: 'POST',
      });
      return mapBatchOut(res);
    },
    async cancelBatch(batchId: string) {
      const res = await request<any>(`/ocr/batches/${batchId}/cancel`, {
        method: 'POST',
      });
      return mapBatchOut(res);
    },
    async removeBatchItem(batchId: string, itemId: string) {
      const res = await request<any>(`/ocr/batches/${batchId}/items/${itemId}`, {
        method: 'DELETE',
      });
      return mapBatchOut(res);
    },
    async retryBatchItem(batchId: string, itemId: string, waitForCompletion: boolean = false) {
      const res = await request<any>(`/ocr/batches/${batchId}/items/${itemId}/retry?wait_for_completion=${waitForCompletion}`, {
        method: 'POST',
      });
      return mapBatchOut(res);
    },
    async updateBatchItem(
      batchId: string,
      itemId: string,
      data: {
        studentId?: string;
        marksObtained?: number;
        questionEvaluations?: any[];
        clearReviewFlag?: boolean;
      }
    ) {
      const res = await request<any>(`/ocr/batches/${batchId}/items/${itemId}`, {
        method: 'PUT',
        body: JSON.stringify({
          student_id: data.studentId,
          marks_obtained: data.marksObtained,
          question_evaluations: data.questionEvaluations,
          clear_review_flag: data.clearReviewFlag ?? true,
        }),
      });
      return mapBatchItemOut(res);
    },
    async approveBatchItem(batchId: string, itemId: string) {
      const res = await request<any>(`/ocr/batches/${batchId}/items/${itemId}/approve`, {
        method: 'POST',
      });
      return mapBatchOut(res);
    },
    async approveAllBatchItems(batchId: string) {
      const res = await request<any>(`/ocr/batches/${batchId}/approve-all`, {
        method: 'POST',
      });
      return mapBatchOut(res);
    },
  },

  // Notifications & Audit
  notifications: {
    async getAll() {
      return request<any[]>('/notifications');
    },
  },
  audit: {
    async getEvents(category?: string, search?: string) {
      const params = new URLSearchParams();
      if (category) params.append('category', category);
      if (search) params.append('search', search);
      return request<any[]>(`/audit/events?${params.toString()}`);
    },
  },

  // PayPal subscriptions for the principal's school
  subscriptions: {
    async status() {
      return request<SubscriptionRow[]>('/subscriptions/status');
    },
    async start(teacherCount: number) {
      return request<StartSubscriptionResult>('/subscriptions/start', {
        method: 'POST',
        body: JSON.stringify({ teacher_count: teacherCount }),
      });
    },
    async changeSeats(teacherCount: number) {
      return request<SubscriptionRow>('/subscriptions/seats', {
        method: 'POST',
        body: JSON.stringify({ teacher_count: teacherCount }),
      });
    },
  },

  // Health
  health: {
    async check() {
      try {
        // /health sits at the server root, outside /api/v1.
        const res = await fetch(`${API_BASE_URL.replace(/\/api\/v1\/?$/, '')}/health`);
        return res.ok;
      } catch {
        return false;
      }
    },
  },
};
