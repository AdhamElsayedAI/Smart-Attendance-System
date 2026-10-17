export type Exam = {
  id: number; name: string; exam_date: string; start_time: string; end_time: string;
  description: string; status: 'scheduled' | 'active' | 'ended'; assigned: number; roster_complete: number;
}
export type Student = { student_id: string; name: string; active: number; enrolled: number }
export type RosterEntry = { student_id: string; name: string; status: 'Present' | 'Absent'; timestamp: string | null }
export type RecordEntry = {
  exam_id: number; exam: string; student_id: string; student: string;
  timestamp: string; verification_method: string;
}
export type Summary = { assigned: number; present: number; absent: number; rate: number | null }
export type Analytics = { exams: { exam: Exam; summary: Summary | null; records: number }[]; records: RecordEntry[] }
export type Health = { database: string; face_module: boolean; opencv: boolean;
  dlib_numpy: { state: string; message: string }; landmark_model: boolean; enrolled: number;
  camera_lease: string; camera: { state: string; message: string } }
export type Overview = {
  active: Exam | null; featured: Exam | null;
  metrics: { students: number; enrolled: number; exams: number; upcoming: number; events: number };
  recent: RecordEntry[];
  distribution: { exam_id: number; name: string; date: string; count: number }[];
  readiness: Health;
  attention: { unenrolled: number; landmark_missing: boolean };
  featured_summary: Summary | null;
}
export type Session = {
  exam: Exam | null; camera: 'paused' | 'connected' | 'disconnected';
  stage: 'Waiting' | 'Face detected' | 'Identity matched' | 'Blink required' | 'Verified' | 'Recorded';
  identity: string | null; feedback: string; face_count: number;
  outcome: { kind: 'recorded' | 'rejected' | 'error'; message: string } | null;
  progress: Summary | null; error?: string | null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, { ...init, headers: { Accept: 'application/json', ...init?.headers } })
  if (!response.ok) {
    let detail = `Request failed (${response.status})`
    try { detail = (await response.json()).detail || detail } catch { /* use HTTP status */ }
    throw new Error(detail)
  }
  return response.json() as Promise<T>
}

export const api = {
  overview: (signal?: AbortSignal) => request<Overview>('/overview', { signal }),
  health: (signal?: AbortSignal) => request<Health>('/health', { signal }),
  probeCamera: () => request<{ state: string; message: string }>('/diagnostics/camera', { method: 'POST' }),
  students: (search = '', signal?: AbortSignal) => request<Student[]>(`/students?search=${encodeURIComponent(search)}`, { signal }),
  createStudent: (student_id: string, name: string) => request<Student>('/students', { method: 'POST',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ student_id, name }) }),
  enroll: (studentId: string, file: File) => request<{ student_id: string; enrolled: boolean }>(
    `/students/${encodeURIComponent(studentId)}/enrollment?filename=${encodeURIComponent(file.name)}`,
    { method: 'POST', headers: { 'Content-Type': file.type }, body: file }),
  exams: (signal?: AbortSignal) => request<Exam[]>('/exams', { signal }),
  createExam: (payload: { name: string; exam_date: string; start_time: string; end_time: string;
    description: string; student_ids: string[] }) => request<{ exam: Exam }>('/exams', { method: 'POST',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),
  roster: (id: number) => request<{ exam: Exam; summary: Summary | null; participants: RosterEntry[] }>(`/exams/${id}/roster`),
  setRoster: (id: number, student_ids: string[]) => request<{ exam: Exam; participants: RosterEntry[] }>(`/exams/${id}/roster`,
    { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ student_ids }) }),
  analytics: (examId?: number, examDate?: string, signal?: AbortSignal) => request<Analytics>(
    `/analytics?${new URLSearchParams({ ...(examId ? { exam_id: String(examId) } : {}), ...(examDate ? { exam_date: examDate } : {}) })}`, { signal }),
  attendance: (examId: number, signal?: AbortSignal) => request<RecordEntry[]>(`/exams/${examId}/attendance`, { signal }),
  status: (signal?: AbortSignal) => request<Session>('/session/status', { signal }),
  startExam: (id: number) => request<{ exam: Exam }>(`/exams/${id}/start`, { method: 'POST' }),
  endExam: (id: number) => request<{ exam: Exam }>(`/exams/${id}/end`, { method: 'POST' }),
  startCamera: () => request<{ camera: string }>('/session/camera/start', { method: 'POST' }),
  pauseCamera: () => request<{ camera: string }>('/session/camera/pause', { method: 'POST' }),
}

export function formatDate(value: string): string {
  return new Intl.DateTimeFormat('en', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(`${value}T12:00:00`))
}

export function formatStamp(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat('en', {
    day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
  }).format(date)
}
