import { Check, Eye, ScanFace } from 'lucide-react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { formatDate } from '../services/api'
import { useCameraFrame, useLiveSession } from '../hooks/useLiveSession'
import { Loading, Notice, Status } from '../components/Primitives'

export function Kiosk() {
  const { session, error } = useLiveSession()
  const reduced = useReducedMotion()
  const frame = useCameraFrame(session?.camera === 'connected')
  if (!session) return <div className="kiosk kiosk--loading"><Loading label="Connecting to supervised check-in" />{error && <Notice tone="bad">{error}</Notice>}</div>
  const recorded = session.outcome?.kind === 'recorded' && session.stage === 'Recorded'
  const blocked = session.outcome?.kind === 'error' || session.outcome?.kind === 'rejected'
  const instruction = recorded ? 'You are checked in.' : blocked ? 'Please ask the supervisor for help.' :
    !session.exam ? 'Waiting for the session.' :
    session.camera === 'disconnected' ? 'Camera needs attention.' :
    session.camera !== 'connected' ? 'Waiting for the camera.' :
    session.stage === 'Blink required' ? 'Close and reopen your eyes once.' :
    session.stage === 'Identity matched' ? 'Hold still for a moment.' :
    session.stage === 'Face detected' ? 'Face detected. Hold still.' :
    session.stage === 'Verified' ? 'Saving your attendance.' : 'Step into view when invited.'
  return <div className="kiosk"><a className="skip-link" href="#kiosk-content">Skip to check-in status</a><header className="kiosk__header"><div className="kiosk__brand"><span className="brand__mark">A<span>·</span></span><span>Attendance<span className="brand__os">OS</span><small>STUDENT CHECK-IN</small></span></div><div className="kiosk__header-right"><Status tone={session.camera === 'connected' ? 'good' : 'warn'}>{session.camera === 'connected' ? 'Camera ready' : 'Camera paused'}</Status></div></header>
    <main id="kiosk-content" className="kiosk__main"><div className="kiosk__intro"><span className="kiosk__eyebrow">SUPERVISED CHECK-IN / LOCAL CAMERA</span><p>{session.exam ? `${session.exam.name} · ${formatDate(session.exam.exam_date)}` : 'No examination is active'}</p></div><div className="kiosk__grid"><div className="kiosk__copy"><div className={`kiosk__symbol ${recorded ? 'kiosk__symbol--good' : ''}`}>{recorded ? <Check size={34} /> : session.stage === 'Blink required' ? <Eye size={34} /> : <ScanFace size={34} />}</div><AnimatePresence mode="wait"><motion.div key={instruction} initial={reduced ? false : { opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={reduced ? undefined : { opacity: 0, y: -10 }} transition={{ duration: .26 }}><h1>{instruction}</h1><p>{recorded ? session.outcome?.message : blocked ? session.outcome?.message : !session.exam ? 'The supervisor will open an exam before check-in begins.' : session.camera !== 'connected' ? 'The supervisor will enable the host camera when ready.' : session.stage === 'Blink required' ? 'A natural close and reopen completes the identity check.' : session.feedback}</p></motion.div></AnimatePresence><div className="kiosk__progress" aria-label={`Current stage: ${session.stage}`}><span className={session.stage !== 'Waiting' ? 'is-active' : ''} /><span className={['Identity matched', 'Blink required', 'Verified', 'Recorded'].includes(session.stage) ? 'is-active' : ''} /><span className={['Verified', 'Recorded'].includes(session.stage) ? 'is-active' : ''} /><span className={recorded ? 'is-active' : ''} /></div><div className="kiosk__identity">{session.identity ? <>Recognized as <strong>{session.identity}</strong></> : 'Your name appears here after recognition.'}</div></div><div className="kiosk__camera"><div className="kiosk__camera-top"><span>CAMERA / HOST DEVICE</span><span>{session.face_count > 1 ? 'ONE FACE AT A TIME' : session.camera === 'connected' ? 'LIVE' : 'STANDBY'}</span></div>{frame && session.camera === 'connected' ? <img src={frame} alt="Local host camera view for supervised check-in" /> : <div className="kiosk__camera-empty"><ScanFace size={48} strokeWidth={1} /><span>{session.camera === 'connected' ? 'Connecting to camera' : 'Waiting for the supervisor to enable the camera'}</span></div>}<div className="kiosk__camera-foot">Face the camera · Keep a comfortable distance · Wait for instruction</div></div></div>{error && <Notice tone="bad">Connection to the local attendance service was lost: {error}</Notice>}</main><footer className="kiosk__footer">Attendance is saved only after a recognized face completes the blink check and the exam assignment is confirmed.<span>University edition · supervised local prototype</span></footer></div>
}
