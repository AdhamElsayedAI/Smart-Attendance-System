import { useEffect, useState } from 'react'
import { BarChart3, Download, Filter } from 'lucide-react'
import { api, formatDate, formatStamp, type Analytics as AnalyticsData, type Exam } from '../services/api'
import { Empty, Eyebrow, Loading, Notice, RouteReveal, Status } from '../components/Primitives'

function csvCell(value: string | number) {
  const string = String(value)
  const safe = /^[\s]*[=+\-@]/.test(string) ? `'${string}` : string
  return `"${safe.replaceAll('"', '""')}"`
}

export function Analytics() {
  const [exams, setExams] = useState<Exam[]>([])
  const [data, setData] = useState<AnalyticsData | null>(null)
  const [examId, setExamId] = useState('')
  const [examDate, setExamDate] = useState('')
  const [error, setError] = useState('')
  useEffect(() => { api.exams().then(setExams).catch(cause => setError(String(cause))) }, [])
  useEffect(() => {
    const controller = new AbortController()
    api.analytics(examId ? Number(examId) : undefined, examDate || undefined, controller.signal)
      .then(next => { setData(next); setError('') }).catch(cause => { if (!controller.signal.aborted) setError(String(cause)) })
    return () => controller.abort()
  }, [examId, examDate])
  const known = data?.exams.filter(row => row.summary !== null) || []
  const assigned = known.reduce((sum, row) => sum + (row.summary?.assigned || 0), 0)
  const present = known.reduce((sum, row) => sum + (row.summary?.present || 0), 0)
  const unknown = data?.exams.filter(row => row.summary === null).length || 0
  const exportCsv = () => {
    if (!data) return
    const columns = ['Exam ID', 'Exam', 'Student ID', 'Student', 'Timestamp', 'Verification method']
    const rows = data.records.map(row => [row.exam_id, row.exam, row.student_id, row.student, row.timestamp, row.verification_method])
    const content = [columns, ...rows].map(row => row.map(csvCell).join(',')).join('\r\n')
    const url = URL.createObjectURL(new Blob(['\ufeff', content], { type: 'text/csv;charset=utf-8' }))
    const link = document.createElement('a'); link.href = url; link.download = `attendance-${examId || 'all'}-${examDate || 'all-dates'}.csv`; link.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  return <RouteReveal><div className="page page--analytics"><div className="page-top"><div><Eyebrow>University records / Analytics</Eyebrow><h1>Every confirmation<br /><em>has a context.</em></h1><p>Inspect attendance by examination and export the exact records shown below.</p></div><div className="page-top__accent"><BarChart3 size={31} /><span>Exam-scoped figures<br />Live local database</span></div></div>
    {error && <Notice tone="bad">{error}</Notice>}
    <section className="panel report-filters"><div><Filter size={18} /><strong>Filter the ledger</strong></div><label>Examination<select value={examId} onChange={event => setExamId(event.target.value)}><option value="">All examinations</option>{exams.map(row => <option value={row.id} key={row.id}>{row.name} · {formatDate(row.exam_date)}</option>)}</select></label><label>Exam date<input type="date" value={examDate} onChange={event => setExamDate(event.target.value)} /></label><button className="button button--quiet" onClick={() => { setExamId(''); setExamDate('') }}>Clear filters</button></section>
    {!data ? <Loading /> : <><div className="report-metrics"><div><span>Assigned · known rosters</span><strong>{assigned || (known.length ? '0' : '—')}</strong></div><div><span>Present · known rosters</span><strong>{known.length ? present : '—'}</strong></div><div><span>Absent · known rosters</span><strong>{known.length ? assigned - present : '—'}</strong></div><div><span>Attendance rate</span><strong>{assigned ? `${Math.round(present / assigned * 1000) / 10}%` : '—'}</strong></div><div><span>Saved records</span><strong>{data.records.length}</strong></div></div>
      {unknown > 0 && <Notice tone="warn">{unknown} historical exam{unknown === 1 ? ' has' : 's have'} an unknown roster. Its records are shown, but excluded from assigned, absent, and percentage figures.</Notice>}
      <div className="analytics-grid"><section className="panel"><div className="section-heading"><div><h2>Attendance by examination</h2><p>Present out of assigned for known rosters; record count for unknown rosters.</p></div><BarChart3 size={19} /></div>{data.exams.length ? <div className="chart-list">{data.exams.map(({ exam, summary, records }) => <div className="chart-row" key={exam.id}><div><strong>{exam.name}</strong><small>{formatDate(exam.exam_date)} · {exam.status}</small></div><div className="chart-track" role="img" aria-label={summary?.rate == null ? `${records} records, roster unknown` : `${summary.present} of ${summary.assigned} assigned students present`}><span style={{ width: `${summary?.rate ?? (records ? 100 : 0)}%` }} /></div><strong>{summary ? `${summary.present}/${summary.assigned}` : `${records} records`}</strong></div>)}</div> : <Empty title="No matching examinations">Change the filters or create an exam to populate this report.</Empty>}</section>
        <section className="panel report-context"><Eyebrow>DATA NOTE</Eyebrow><h2>Numbers with a denominator.</h2><p>A percentage is shown only when a roster is known and at least one student is assigned. Imported historical records can have an unknown roster.</p><div><Status tone="good">Known roster</Status><span>{known.length} exam{known.length === 1 ? '' : 's'}</span></div><div><Status tone="warn">Unknown roster</Status><span>{unknown} exam{unknown === 1 ? '' : 's'}</span></div></section></div>
      <section className="panel report-records"><div className="section-heading"><div><h2>Attendance records</h2><p>Each row is saved in SQLite; no generated confirmations.</p></div><button className="button button--ink" onClick={exportCsv} disabled={!data.records.length}><Download size={17} />Export CSV</button></div>{data.records.length ? <div className="table-wrap"><table><thead><tr><th>Student</th><th>University ID</th><th>Examination</th><th>Recorded</th><th>Method</th></tr></thead><tbody>{data.records.map(row => <tr key={`${row.exam_id}-${row.student_id}`}><td data-label="Student">{row.student}</td><td data-label="University ID">{row.student_id}</td><td data-label="Examination">{row.exam}</td><td data-label="Recorded">{formatStamp(row.timestamp)}</td><td data-label="Method">{row.verification_method === 'blink' ? 'Blink verified' : 'Imported legacy'}</td></tr>)}</tbody></table></div> : <Empty title="No records for this selection">Attendance appears after verification and database confirmation.</Empty>}</section>
    </>}
  </div></RouteReveal>
}
