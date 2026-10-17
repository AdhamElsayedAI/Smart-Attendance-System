import { useEffect, useState, type FormEvent } from 'react'
import { Camera, CheckCircle2, Search, UserPlus, UsersRound } from 'lucide-react'
import { api, type Student } from '../services/api'
import { Empty, Eyebrow, Loading, Notice, RouteReveal, Status } from '../components/Primitives'

export function Students() {
  const [students, setStudents] = useState<Student[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState('all')
  const [studentId, setStudentId] = useState('')
  const [name, setName] = useState('')
  const [enrollmentId, setEnrollmentId] = useState('')
  const [photo, setPhoto] = useState<File | null>(null)
  const refresh = async () => { setStudents(await api.students()); setLoading(false) }
  useEffect(() => { refresh().catch(cause => { setError(String(cause)); setLoading(false) }) }, [])
  const register = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setError(''); setMessage('')
    try {
      const created = await api.createStudent(studentId.trim(), name.trim())
      await refresh(); setEnrollmentId(created.student_id); setStudentId(''); setName('')
      setMessage(`${created.name} is registered. Add one clear face photo to complete enrollment.`)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Registration failed') }
    finally { setBusy(false) }
  }
  const enroll = async (event: FormEvent) => {
    event.preventDefault(); if (!photo || !enrollmentId) return
    setBusy(true); setError(''); setMessage('')
    try {
      await api.enroll(enrollmentId, photo); await refresh(); setPhoto(null)
      const input = document.getElementById('face-photo') as HTMLInputElement | null
      if (input) input.value = ''
      setMessage(`Face enrollment completed for ${enrollmentId}.`)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Enrollment failed') }
    finally { setBusy(false) }
  }
  const visible = students.filter(row => `${row.name} ${row.student_id}`.toLowerCase().includes(query.toLowerCase()) &&
    (filter === 'all' || (filter === 'enrolled' ? !!row.enrolled : !row.enrolled)))
  const enrolledCount = students.filter(row => row.active && row.enrolled).length
  return <RouteReveal><div className="page page--students">
    <div className="page-top"><div><Eyebrow>University operations / Students</Eyebrow><h1>People behind <em>the record.</em></h1><p>Register students, prepare a single face profile, and keep the directory ready for exam rosters.</p></div><div className="page-top__accent"><UsersRound size={31} /><span>{students.length} registered<br />{enrolledCount} face enrolled</span></div></div>
    {error && <Notice tone="bad">{error}</Notice>}{message && <Notice tone="good">{message}</Notice>}
    <div className="management-grid"><section className="panel directory-panel"><div className="section-heading"><div><h2>Student directory</h2><p>Search by name or university ID.</p></div><Status tone="good">{enrolledCount} ready</Status></div>
      <div className="directory-tools"><label className="search-field"><Search size={18} /><span className="sr-only">Search students</span><input aria-label="Search students" placeholder="Search students or IDs" value={query} onChange={event => setQuery(event.target.value)} /></label><select aria-label="Filter enrollment" value={filter} onChange={event => setFilter(event.target.value)}><option value="all">All students</option><option value="enrolled">Face enrolled</option><option value="pending">Awaiting enrollment</option></select></div>
      {loading ? <Loading /> : visible.length ? <div className="student-list">{visible.map(row => <button type="button" className={`student-row ${enrollmentId === row.student_id ? 'student-row--selected' : ''}`} key={row.student_id} onClick={() => { setEnrollmentId(row.student_id); setPhoto(null) }}><span className="student-avatar">{row.name.slice(0, 1).toUpperCase()}</span><span className="student-row__main"><strong>{row.name}</strong><small>{row.student_id}</small></span><Status tone={row.enrolled ? 'good' : 'warn'}>{row.enrolled ? 'Enrolled' : 'Needs photo'}</Status></button>)}</div> : <Empty title="No matching students">Register a student or change the search and filter.</Empty>}
    </section><div className="management-stack"><section className="panel form-panel"><span className="form-panel__icon"><UserPlus size={21} /></span><Eyebrow>01 / REGISTER</Eyebrow><h2>Add a student</h2><p>Use their stable university identifier. Duplicate IDs are rejected.</p><form onSubmit={register}><label>University ID<input required maxLength={64} value={studentId} onChange={event => setStudentId(event.target.value)} placeholder="e.g. UNI-2026-001" /></label><label>Full name<input required maxLength={150} value={name} onChange={event => setName(event.target.value)} placeholder="Student's full name" /></label><button className="button button--ink" disabled={busy}>{busy ? 'Working…' : 'Register student'} <UserPlus size={17} /></button></form></section>
      <section className="panel form-panel form-panel--warm"><span className="form-panel__icon"><Camera size={21} /></span><Eyebrow>02 / FACE ENROLLMENT</Eyebrow><h2>Prepare a face profile</h2><p>Choose a registered student and one consented JPG, PNG, or BMP photo showing exactly one face.</p><form onSubmit={enroll}><label>Student<select required value={enrollmentId} onChange={event => setEnrollmentId(event.target.value)}><option value="">Select a student</option>{students.filter(row => row.active).map(row => <option value={row.student_id} key={row.student_id}>{row.name} · {row.student_id}{row.enrolled ? ' · enrolled' : ''}</option>)}</select></label><label>Face photo<input id="face-photo" type="file" accept="image/jpeg,image/png,image/bmp" required onChange={event => setPhoto(event.target.files?.[0] || null)} /></label><button className="button button--ink" disabled={busy || !enrollmentId || !photo}>{busy ? 'Processing…' : 'Enroll face'} <CheckCircle2 size={17} /></button></form><small className="form-footnote">Photos and biometric templates stay on the local host. The browser receives enrollment status only.</small></section></div></div>
  </div></RouteReveal>
}
