import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, CalendarDays, CircleCheck, Fingerprint, GraduationCap, Radio, ShieldAlert, UsersRound } from 'lucide-react'
import { motion, useReducedMotion } from 'framer-motion'
import { api, formatDate, formatStamp, type Overview as OverviewData } from '../services/api'
import { Empty, Eyebrow, Loading, Notice, RouteReveal, SectionHeading, Status, TextLink } from '../components/Primitives'

export function Overview() {
  const [data, setData] = useState<OverviewData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const reduced = useReducedMotion()
  useEffect(() => {
    const controller = new AbortController()
    api.overview(controller.signal).then(setData).catch(cause => {
      if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : 'Could not load overview')
    })
    return () => controller.abort()
  }, [])
  if (error) return <div className="page"><Notice tone="bad">Unable to reach the local API: {error}. Start the FastAPI process and reload.</Notice></div>
  if (!data) return <div className="page"><Loading /></div>
  const exam = data.featured
  const distribution = data.distribution.filter(row => row.count > 0).slice(0, 5)
  const max = Math.max(1, ...distribution.map(row => row.count))
  const coverage = data.metrics.students ? Math.round(100 * data.metrics.enrolled / data.metrics.students) : 0
  const blocked = data.readiness.database !== 'healthy' || !data.readiness.face_module ||
    !data.readiness.opencv || data.readiness.dlib_numpy.state !== 'compatible' ||
    !data.readiness.landmark_model || !data.metrics.enrolled
  const readinessLabel = blocked ? 'Setup needed' : data.readiness.camera.state === 'Not tested' ? 'Camera not tested' :
    data.readiness.camera.state === 'Unavailable' ? 'Camera unavailable' : 'Ready'
  return <RouteReveal><div className="page page--overview">
    <div className="page-top"><div><Eyebrow>University operations / Overview</Eyebrow><h1>Good to have everything<br /><em>in view.</em></h1><p>A calm command center for exam readiness, enrollment, and verified attendance.</p></div><span className="page-top__date">{new Intl.DateTimeFormat('en', { weekday: 'long', day: 'numeric', month: 'long' }).format(new Date())}</span></div>
    <div className="overview-hero">
      <section className="featured" aria-labelledby="featured-heading"><div className="featured__top"><span className="featured__label"><span className="signal-dot" />{data.active ? 'SESSION IN PROGRESS' : exam ? 'NEXT ON THE SCHEDULE' : 'EXAM DESK'}</span><span className="featured__index">01 / 03</span></div>
        {exam ? <><div className="featured__content"><span className="featured__overline">{data.active ? 'Currently taking attendance' : 'Upcoming examination'}</span><h2 id="featured-heading">{exam.name}</h2><div className="featured__meta"><span><CalendarDays size={17} />{formatDate(exam.exam_date)}</span><span>{exam.start_time} — {exam.end_time}</span><span><UsersRound size={17} />{exam.roster_complete ? exam.assigned : 'Unknown'} assigned</span></div></div>
          <div className="featured__foot"><div>{data.featured_summary ? <><strong>{data.featured_summary.present}<span> / {data.featured_summary.assigned}</span></strong><small>students recorded</small></> : <><strong>—</strong><small>Historical roster unknown</small></>}</div><Link className="button button--ivory" to="/attendance">Open workstation <ArrowRight size={18} /></Link></div></> : <><div className="featured__content"><span className="featured__overline">Ready for a new session</span><h2 id="featured-heading">No upcoming exam is scheduled.</h2><p>Create an examination and assign its roster in the Exams workspace.</p></div><div className="featured__foot"><span>Local prototype</span><TextLink to="/exams">Create examination</TextLink></div></>}
      </section>
      <section className="readiness" aria-labelledby="readiness-heading"><div className="readiness__heading"><span className="readiness__symbol"><Fingerprint size={27} strokeWidth={1.6} /></span><Status tone={blocked || data.readiness.camera.state === 'Unavailable' ? 'warn' : readinessLabel === 'Ready' ? 'good' : 'neutral'}>{readinessLabel}</Status></div><Eyebrow>System readiness</Eyebrow><h2 id="readiness-heading">A prepared campus starts here.</h2><p>Check the essentials before the next supervised session.</p><div className="readiness__list"><div><span><CircleCheck size={16} />Face profiles</span><strong>{data.metrics.enrolled} enrolled · {coverage}%</strong></div><div><span><GraduationCap size={16} />Vision stack</span><strong>{data.readiness.dlib_numpy.state === 'compatible' && data.readiness.face_module && data.readiness.opencv ? 'Compatible' : 'Check setup'}</strong></div><div><span><ShieldAlert size={16} />Landmark model</span><strong>{data.readiness.landmark_model ? 'In place' : 'Needs setup'}</strong></div><div><span><Radio size={16} />Local camera</span><strong>{data.readiness.camera.state}</strong></div></div>{data.attention.unenrolled > 0 && <div className="readiness__note">{data.attention.unenrolled} active {data.attention.unenrolled === 1 ? 'student is' : 'students are'} awaiting face enrollment.</div>}</section>
    </div>
    <div className="metric-band" aria-label="Operational totals"><div className="metric-band__intro"><Eyebrow>Live ledger</Eyebrow><span>At a glance</span></div><div><span>Students</span><strong>{data.metrics.students}</strong></div><div><span>Face profiles</span><strong>{data.metrics.enrolled}</strong></div><div><span>All exams</span><strong>{data.metrics.exams}</strong></div><div><span>Upcoming</span><strong>{data.metrics.upcoming}</strong></div><div><span>Recorded events</span><strong>{data.metrics.events}</strong></div></div>
    <div className="overview-lower"><section className="panel distribution"><SectionHeading title="Attendance across exams" detail="Recorded events · historical rosters may be incomplete" />{distribution.length ? <div className="distribution__list">{distribution.map(row => <div className="distribution__row" key={row.exam_id}><div className="distribution__label"><strong>{row.name}</strong><span>{formatDate(row.date)}</span></div><div className="distribution__bar" aria-label={`${row.count} recorded events`}><motion.span initial={reduced ? false : { width: 0 }} animate={{ width: `${row.count / max * 100}%` }} transition={{ duration: .55, ease: 'easeOut' }} /></div><strong className="distribution__number">{row.count}</strong></div>)}</div> : <Empty title="No attendance to chart">Verified attendance will appear here when a session records its first student.</Empty>}</section>
      <section className="panel activity"><SectionHeading title="Recent confirmations" detail="Latest attendance saved to the local record" action={<Radio size={19} className="activity__icon" aria-hidden="true" />} />{data.recent.length ? <div className="activity__list">{data.recent.map((row, index) => <div className="activity__row" key={`${row.exam_id}-${row.student_id}-${index}`}><span className="activity__avatar" aria-hidden="true">{row.student.slice(0, 1).toUpperCase()}</span><div><strong>{row.student}</strong><small>{row.exam} · {formatStamp(row.timestamp)}</small></div><span className="activity__check" title={row.verification_method === 'blink' ? 'Blink verified' : 'Imported legacy record'}>{row.verification_method === 'blink' ? <CircleCheck size={18} /> : 'Legacy'}</span></div>)}</div> : <Empty title="A quiet record so far">Recent verified students will appear here after check-in.</Empty>}</section></div>
    <div className="page-footnote"><span>All figures are read from the local attendance database.</span><Link to="/attendance">Prepare a live session <ArrowRight size={15} /></Link></div>
  </div></RouteReveal>
}
