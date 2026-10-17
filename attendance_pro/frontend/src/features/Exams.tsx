import { useEffect, useState, type FormEvent } from 'react'
import { ArrowRight, CalendarDays, CheckCircle2, ClipboardList, Play, Square } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api, formatDate, formatStamp, type Exam, type RecordEntry, type RosterEntry, type Student, type Summary } from '../services/api'
import { Empty, Eyebrow, Loading, Notice, RouteReveal, Status } from '../components/Primitives'

const today = () => new Date().toLocaleDateString('en-CA')

export function Exams() {
  const [exams, setExams] = useState<Exam[]>([])
  const [students, setStudents] = useState<Student[]>([])
  const [selected, setSelected] = useState<number | null>(null)
  const [roster, setRoster] = useState<RosterEntry[]>([])
  const [summary, setSummary] = useState<Summary | null>(null)
  const [records, setRecords] = useState<RecordEntry[]>([])
  const [rosterIds, setRosterIds] = useState<string[]>([])
  const [newIds, setNewIds] = useState<string[]>([])
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [examDate, setExamDate] = useState(today)
  const [startTime, setStartTime] = useState('09:00')
  const [endTime, setEndTime] = useState('10:00')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const refresh = async () => { const [nextExams, nextStudents] = await Promise.all([api.exams(), api.students()]); setExams(nextExams); setStudents(nextStudents); setSelected(current => current ?? nextExams[0]?.id ?? null); setLoading(false) }
  useEffect(() => { refresh().catch(cause => { setError(String(cause)); setLoading(false) }) }, [])
  useEffect(() => {
    if (selected === null) return
    Promise.all([api.roster(selected), api.attendance(selected)]).then(([detail, attendance]) => {
      setRoster(detail.participants); setSummary(detail.summary); setRecords(attendance)
      setRosterIds(detail.participants.map(row => row.student_id))
    }).catch(cause => setError(cause instanceof Error ? cause.message : 'Could not load exam'))
  }, [selected, exams])
  const run = async (action: () => Promise<unknown>, success: string) => {
    setBusy(true); setError(''); setMessage('')
    try { await action(); await refresh(); setMessage(success) }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Action failed') }
    finally { setBusy(false) }
  }
  const create = async (event: FormEvent) => {
    event.preventDefault()
    if (!newIds.length) { setError('Assign at least one registered student.'); return }
    setBusy(true); setError(''); setMessage('')
    try {
      const result = await api.createExam({ name: name.trim(), description: description.trim(), exam_date: examDate,
        start_time: startTime, end_time: endTime, student_ids: newIds })
      await refresh(); setSelected(result.exam.id); setName(''); setDescription(''); setNewIds([])
      setMessage(`${result.exam.name} is scheduled with ${newIds.length} participant${newIds.length === 1 ? '' : 's'}. You can start its supervised session now.`)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not create exam') }
    finally { setBusy(false) }
  }
  const chosen = exams.find(row => row.id === selected)
  const active = exams.find(row => row.status === 'active')
  const toggle = (id: string, current: string[], setter: (next: string[]) => void) => setter(current.includes(id) ? current.filter(value => value !== id) : [...current, id])
  return <RouteReveal><div className="page page--exams"><div className="page-top"><div><Eyebrow>University operations / Examinations</Eyebrow><h1>Plan the room.<br /><em>Trust the roster.</em></h1><p>Create a supervised examination, assign students, and review its attendance history.</p></div><div className="page-top__accent"><CalendarDays size={31} /><span>{exams.length} examinations<br />{active ? 'One active session' : 'No active session'}</span></div></div>
    {error && <Notice tone="bad">{error}</Notice>}{message && <Notice tone="good">{message}</Notice>}
    <div className="exam-grid"><section className="panel form-panel exam-create"><Eyebrow>01 / CREATE EXAM</Eyebrow><h2>New examination</h2><p>Set the timetable and initial roster. A newly created scheduled exam may begin immediately for a supervised demo.</p><form onSubmit={create}><label>Exam name<input required maxLength={150} value={name} onChange={event => setName(event.target.value)} placeholder="e.g. Computer Vision · Final" /></label><label>Description<textarea maxLength={1000} rows={3} value={description} onChange={event => setDescription(event.target.value)} placeholder="Course, room, or supervisor notes" /></label><div className="field-pair"><label>Date<input required type="date" value={examDate} onChange={event => setExamDate(event.target.value)} /></label><label>Starts<input required type="time" value={startTime} onChange={event => setStartTime(event.target.value)} /></label></div><label>Ends<input required type="time" value={endTime} onChange={event => setEndTime(event.target.value)} /></label><fieldset className="participant-picker"><legend>Assign students <span>{newIds.length} selected</span></legend>{students.filter(row => row.active).length ? students.filter(row => row.active).map(row => <label key={row.student_id}><input type="checkbox" checked={newIds.includes(row.student_id)} onChange={() => toggle(row.student_id, newIds, setNewIds)} /><span><strong>{row.name}</strong><small>{row.student_id}{!row.enrolled ? ' · face pending' : ''}</small></span></label>) : <p>Register students before creating an exam.</p>}</fieldset><button className="button button--ink" disabled={busy || !students.length}>Create examination <ArrowRight size={17} /></button></form></section>
      <div className="exam-workspace"><section className="panel"><div className="section-heading"><div><h2>Examination ledger</h2><p>Scheduled, active, and previous sessions.</p></div><Status tone={active ? 'live' : 'neutral'}>{active ? 'Live' : 'Standby'}</Status></div>{loading ? <Loading /> : exams.length ? <div className="exam-list">{exams.map(row => <button type="button" className={`exam-row ${selected === row.id ? 'exam-row--selected' : ''}`} key={row.id} onClick={() => setSelected(row.id)}><span className="exam-row__index">{String(row.id).padStart(2, '0')}</span><span className="exam-row__content"><strong>{row.name}</strong><small>{formatDate(row.exam_date)} · {row.start_time}–{row.end_time} · {row.roster_complete ? `${row.assigned} assigned` : 'Roster unknown'}</small></span><Status tone={row.status === 'active' ? 'live' : row.status === 'ended' ? 'neutral' : 'warn'}>{row.status}</Status></button>)}</div> : <Empty title="No examinations yet">Create the first exam using the form beside this ledger.</Empty>}</section>
      <section className="panel exam-detail"><div className="section-heading"><div><h2>{chosen ? chosen.name : 'Exam details'}</h2><p>{chosen ? `${formatDate(chosen.exam_date)} · ${chosen.start_time}–${chosen.end_time}` : 'Select an examination above to inspect its roster and records.'}</p></div>{chosen && <Status tone={chosen.status === 'active' ? 'live' : 'neutral'}>{chosen.status}</Status>}</div>
        {chosen ? <><p className="exam-description">{chosen.description || 'No description added.'}</p><div className="exam-totals"><div><strong>{summary?.assigned ?? '—'}</strong><span>Assigned</span></div><div><strong>{summary?.present ?? records.length}</strong><span>Present</span></div><div><strong>{summary?.rate == null ? '—' : `${summary.rate}%`}</strong><span>Attendance</span></div></div>
          {chosen.status === 'scheduled' && <><div className="section-heading section-heading--small"><div><h2>Edit roster</h2><p>Only scheduled rosters may be changed.</p></div></div><div className="roster-checks">{students.filter(row => row.active).map(row => <label key={row.student_id}><input type="checkbox" checked={rosterIds.includes(row.student_id)} onChange={() => toggle(row.student_id, rosterIds, setRosterIds)} />{row.name}<small>{row.student_id}</small></label>)}</div><button className="button button--quiet" disabled={busy || !rosterIds.length} onClick={() => void run(() => api.setRoster(chosen.id, rosterIds), 'Roster saved.')}>Save roster</button></>}
          <div className="exam-actions">{chosen.status === 'scheduled' && <button className="button button--ink" disabled={busy || !chosen.assigned || !!active || !chosen.roster_complete} onClick={() => void run(() => api.startExam(chosen.id), 'Session started. Open the attendance workstation to connect the host camera.')}><Play size={16} />Start session</button>}{chosen.status === 'active' && <><Link className="button button--ink" to="/attendance">Open workstation <ArrowRight size={16} /></Link><button className="button button--danger" disabled={busy} onClick={() => { if (window.confirm(`Finish ${chosen.name}?`)) void run(() => api.endExam(chosen.id), 'Session finished and camera released.') }}><Square size={15} />Finish session</button></>}</div>
          <div className="section-heading section-heading--small"><div><h2>Assigned roster</h2><p>Presence is confirmed only by a saved attendance record.</p></div></div>{chosen.roster_complete ? roster.length ? <div className="compact-list">{roster.map(row => <div key={row.student_id}><span><strong>{row.name}</strong><small>{row.student_id}</small></span><Status tone={row.status === 'Present' ? 'good' : 'warn'}>{row.status}</Status></div>)}</div> : <Empty title="Roster is empty">Assign at least one student before starting.</Empty> : <Notice tone="warn">This imported exam has an unknown historical roster; attendance rate is unavailable.</Notice>}
          <div className="section-heading section-heading--small"><div><h2>Attendance history</h2><p>{records.length} saved record{records.length === 1 ? '' : 's'}</p></div><ClipboardList size={18} /></div>{records.length ? <div className="compact-list">{records.map(row => <div key={row.student_id}><span><strong>{row.student}</strong><small>{row.student_id} · {formatStamp(row.timestamp)}</small></span><CheckCircle2 size={18} color="#37795e" /></div>)}</div> : <Empty title="No attendance recorded">Confirmations will appear here during the session.</Empty>}</> : <Empty title="Choose an examination">Select a row in the ledger to manage its roster, session, and results.</Empty>}
      </section></div></div></div></RouteReveal>
}
