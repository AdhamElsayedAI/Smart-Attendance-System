import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, Camera, CameraOff, CheckCircle2, CirclePause, CirclePlay, MonitorPlay, ScanFace, Square } from 'lucide-react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { api, formatDate, formatStamp, type Exam, type RecordEntry, type Session } from '../services/api'
import { Empty, Eyebrow, Loading, Notice, RouteReveal, SectionHeading, Status } from '../components/Primitives'
import { useCameraFrame, useLiveSession } from '../hooks/useLiveSession'

const stages = ['Waiting', 'Face detected', 'Identity matched', 'Blink required', 'Verified', 'Recorded'] as const
const guidance: Record<string, string> = {
  Waiting: 'Invite one student to stand in front of the host camera.',
  'Face detected': 'Keep one face in frame while the system checks identity.',
  'Identity matched': 'Hold still while recognition stabilizes.',
  'Blink required': 'Close and reopen your eyes once to complete verification.',
  Verified: 'Verification passed. Saving the attendance record.',
  Recorded: 'Attendance is recorded. The next student may step forward.',
}

function Verification({ session }: { session: Session }) {
  const reduced = useReducedMotion()
  const index = stages.indexOf(session.stage)
  return <section className="verification"><div className="verification__top"><span className="verification__number">02 / VERIFICATION</span><ScanFace size={22} aria-hidden="true" /></div><Eyebrow>Live identity check</Eyebrow><AnimatePresence mode="wait"><motion.div key={session.stage} initial={reduced ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={reduced ? undefined : { opacity: 0, y: -7 }} transition={{ duration: .22 }}><h2>{session.stage}</h2><p>{session.stage === 'Face detected' || session.stage === 'Blink required' ? session.feedback : guidance[session.stage] || session.feedback}</p></motion.div></AnimatePresence><div className="verification__track" aria-label={`Verification stage: ${session.stage}`}>{stages.map((stage, step) => <div className={`verification__step ${step <= index ? 'verification__step--done' : ''}`} key={stage}><span />{stage}</div>)}</div><div className="identity"><small>Current match</small><strong>{session.identity || 'Awaiting student'}</strong><span>{session.identity ? 'Matched against local enrolled profiles' : 'Identity appears after a stable face match'}</span></div></section>
}

export function LiveAttendance() {
  const { session, error: statusError, refresh } = useLiveSession()
  const [exams, setExams] = useState<Exam[]>([])
  const [selected, setSelected] = useState<number | null>(null)
  const [records, setRecords] = useState<RecordEntry[]>([])
  const [actionError, setActionError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const cameraOn = session?.camera === 'connected'
  const frame = useCameraFrame(cameraOn)
  useEffect(() => {
    api.exams().then(setExams).catch(cause => setActionError(cause instanceof Error ? cause.message : 'Could not load exams'))
  }, [])
  useEffect(() => {
    if (!session?.exam) { setRecords([]); return }
    const examId = session.exam.id
    let active = true
    let timer: number
    const poll = async () => {
      try { const next = await api.attendance(examId); if (active) setRecords(next) }
      catch { /* the status request reports connectivity errors */ }
      if (active) timer = window.setTimeout(poll, 2500)
    }
    void poll()
    return () => { active = false; window.clearTimeout(timer) }
  }, [session?.exam?.id])
  const run = async (action: () => Promise<unknown>) => {
    setBusy(true); setActionError(null)
    try { await action(); await refresh(); setExams(await api.exams()) }
    catch (cause) { setActionError(cause instanceof Error ? cause.message : 'Action failed') }
    finally { setBusy(false) }
  }
  if (!session) return <div className="page"><Loading label="Connecting to local attendance service" />{statusError && <Notice tone="bad">{statusError}</Notice>}</div>
  const active = session.exam
  const scheduled = exams.filter(exam => exam.status === 'scheduled')
  const chosen = scheduled.find(exam => exam.id === selected) || scheduled[0]
  const summary = session.progress
  return <RouteReveal><div className="page page--live">
    <div className="page-top page-top--compact"><div><Eyebrow>University operations / Live attendance</Eyebrow><h1>Attendance <em>workstation.</em></h1><p>A supervised, host-camera session. Only verified, assigned students are recorded.</p></div><Link className="kiosk-link" to="/check-in">Open student display <ArrowRight size={17} /></Link></div>
    {(actionError || statusError) && <Notice tone="bad">{actionError || statusError}</Notice>}
    {session.error && <Notice tone="bad">Camera disconnected: {session.error}. Pause and retry after checking the device.</Notice>}
    {session.outcome && <Notice tone={session.outcome.kind === 'recorded' ? 'good' : session.outcome.kind === 'error' ? 'bad' : 'warn'}>{session.outcome.message}</Notice>}
    <div className="session-strip"><div className="session-strip__name"><span className="session-strip__icon"><MonitorPlay size={23} /></span><div><small>Current examination</small><strong>{active?.name || 'No active session'}</strong><span>{active ? `${formatDate(active.exam_date)} · ${active.start_time}–${active.end_time} · ${active.assigned} assigned` : 'Choose a scheduled exam to begin.'}</span></div></div><div className="session-strip__state"><Status tone={active ? 'live' : 'neutral'}>{active ? 'Session active' : 'Standby'}</Status></div></div>
    {!active && <div className="session-setup"><div><Eyebrow>Start a session</Eyebrow><h2>Choose the examination to supervise.</h2><p>The roster is used to accept or reject each verified student.</p></div>{scheduled.length ? <div className="session-setup__form"><label htmlFor="exam-select">Scheduled exam</label><select id="exam-select" value={chosen?.id || ''} onChange={event => setSelected(Number(event.target.value))}>{scheduled.map(exam => <option value={exam.id} key={exam.id}>{exam.name} · {formatDate(exam.exam_date)}</option>)}</select><button className="button button--ink" disabled={busy || !chosen?.assigned} onClick={() => chosen && void run(() => api.startExam(chosen.id))}>Start exam session <ArrowRight size={17} /></button></div> : <Empty title="No scheduled exam available"><Link to="/exams">Create an examination</Link> and assign participants first.</Empty>}</div>}
    {active && <><div className="controls"><div className="controls__label"><Eyebrow>01 / SESSION CONTROL</Eyebrow><p>The webcam is attached to the computer running the local API.</p></div><div className="controls__actions"><button className="button button--ink" disabled={busy || cameraOn} onClick={() => void run(api.startCamera)}><CirclePlay size={18} />{cameraOn ? 'Camera running' : 'Resume camera'}</button><button className="button button--quiet" disabled={busy || !cameraOn} onClick={() => void run(api.pauseCamera)}><CirclePause size={18} />Pause camera</button><button className="button button--danger" disabled={busy} onClick={() => { if (window.confirm(`End ${active.name}? Attendance will stop for this exam.`)) void run(() => api.endExam(active.id)) }}><Square size={16} />End session</button></div></div>
      <div className="workstation"><section className="viewport" aria-label="Host camera feed"><div className="viewport__top"><span><span className={`signal-dot ${cameraOn ? 'signal-dot--live' : ''}`} />HOST CAMERA / 01</span><Status tone={cameraOn ? 'good' : 'warn'}>{cameraOn ? 'Connected' : 'Paused'}</Status></div><div className="viewport__image">{frame && cameraOn ? <img src={frame} alt="Live feed from the local host webcam" /> : <div className="viewport__empty">{cameraOn ? <Camera size={38} strokeWidth={1.2} /> : <CameraOff size={38} strokeWidth={1.2} />}<strong>{cameraOn ? 'Connecting to camera feed' : 'Camera is paused'}</strong><span>{cameraOn ? 'Waiting for the first local frame.' : 'Resume the camera when a student is ready to check in.'}</span></div>}</div><div className="viewport__bottom"><span>ONE STUDENT IN FRAME</span><span>{session.face_count > 1 ? 'MULTIPLE FACES · HOLD' : session.face_count === 1 ? 'FACE DETECTED' : 'WAITING FOR FACE'}</span></div></section><Verification session={session} /></div>
      <div className="live-lower"><section className="panel live-progress"><SectionHeading title="Session progress" detail="Recorded attendance against the assigned roster" /><div className="live-progress__numbers"><strong>{summary?.present || 0}<span> / {summary?.assigned || active.assigned}</span></strong><Status tone="good">Confirmed</Status></div><div className="live-progress__bar" role="progressbar" aria-valuenow={summary?.present || 0} aria-valuemin={0} aria-valuemax={summary?.assigned || active.assigned}><span style={{ width: `${summary?.assigned ? summary.present / summary.assigned * 100 : 0}%` }} /></div><p>{summary?.absent ?? active.assigned} still awaiting attendance.</p></section><section className="panel live-activity"><SectionHeading title="Latest confirmations" detail="This examination only" action={<CheckCircle2 size={19} />} />{records.length ? records.slice(0, 4).map(row => <div className="live-activity__row" key={row.student_id}><span className="live-activity__check"><CheckCircle2 size={18} /></span><div><strong>{row.student}</strong><small>{formatStamp(row.timestamp)}</small></div><Status tone="good">Recorded</Status></div>) : <Empty title="Awaiting the first student">A confirmation appears only after the backend saves attendance.</Empty>}</section></div>
    </>}
  </div></RouteReveal>
}
