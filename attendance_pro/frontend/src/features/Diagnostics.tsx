import { useEffect, useState } from 'react'
import { Camera, Database, HardDriveDownload, ScanFace, Settings2 } from 'lucide-react'
import { api, type Health } from '../services/api'
import { Eyebrow, Loading, Notice, RouteReveal, Status } from '../components/Primitives'

export function Diagnostics() {
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const load = async () => { setHealth(await api.health()); setError('') }
  useEffect(() => { load().catch(cause => setError(String(cause))) }, [])
  const probe = async () => {
    setBusy(true); setError('')
    try { await api.probeCamera(); await load() }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Camera probe failed') }
    finally { setBusy(false) }
  }
  const checks = health ? [
    { name: 'SQLite database', value: health.database, good: health.database === 'healthy', detail: 'Read-only integrity check of the configured database.', icon: Database },
    { name: 'Face recognition', value: health.face_module ? 'Installed' : 'Missing', good: health.face_module, detail: 'Python face_recognition package.', icon: ScanFace },
    { name: 'OpenCV', value: health.opencv ? 'Installed' : 'Missing', good: health.opencv, detail: 'Local frame acquisition and image decoding.', icon: Camera },
    { name: 'dlib + NumPy', value: health.dlib_numpy.state, good: health.dlib_numpy.state === 'compatible', detail: health.dlib_numpy.message, icon: Settings2 },
    { name: 'Landmark model', value: health.landmark_model ? 'Present' : 'Missing', good: health.landmark_model, detail: 'The local eye landmark predictor used for blink checks.', icon: HardDriveDownload },
  ] : []
  return <RouteReveal><div className="page page--diagnostics"><div className="page-top"><div><Eyebrow>University operations / Settings & diagnostics</Eyebrow><h1>Know the system<br /><em>before the room opens.</em></h1><p>Real checks from the local backend. Run the camera probe before a supervised session.</p></div><div className="page-top__accent"><Settings2 size={31} /><span>Local device health<br />No cloud dependency</span></div></div>
    {error && <Notice tone="bad">{error}</Notice>}{!health ? <Loading /> : <div className="diagnostic-grid"><section className="panel"><div className="section-heading"><div><h2>Software readiness</h2><p>Current host environment</p></div><Status tone={checks.every(row => row.good) ? 'good' : 'warn'}>{checks.every(row => row.good) ? 'Ready' : 'Needs attention'}</Status></div><div className="diagnostic-list">{checks.map(({ name, value, good, detail, icon: Icon }) => <div key={name}><span className="diagnostic-icon"><Icon size={20} /></span><div><strong>{name}</strong><small>{detail}</small></div><Status tone={good ? 'good' : 'bad'}>{value}</Status></div>)}</div></section>
      <div className="management-stack"><section className="panel diagnostic-camera"><Eyebrow>DEVICE / 01</Eyebrow><h2>Local camera</h2><p>The probe acquires the AttendanceOS lease, opens the selected host camera, then releases both handles.</p><div className="camera-state"><Camera size={28} /><div><strong>{health.camera.state}</strong><span>{health.camera.message}</span></div></div><div className="camera-lease"><span>Camera ownership</span><Status tone={health.camera_lease === 'Free' ? 'good' : 'warn'}>{health.camera_lease}</Status></div><button className="button button--ink" disabled={busy || health.camera_lease === 'Held by this API'} onClick={() => void probe()}>{busy ? 'Checking camera…' : 'Probe local camera'}</button></section><section className="panel diagnostic-note"><Eyebrow>ENROLLMENT / 02</Eyebrow><h2>{health.enrolled} active face profile{health.enrolled === 1 ? '' : 's'}</h2><p>Enrollment stores a local image and a 128-value face template. This screen reports a count only and never returns those templates.</p></section></div></div>}
  </div></RouteReveal>
}
