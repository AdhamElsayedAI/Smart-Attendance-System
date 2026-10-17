import type { ReactNode } from 'react'
import { AlertCircle, ArrowUpRight, Check, CircleHelp, LoaderCircle } from 'lucide-react'
import { motion, useReducedMotion } from 'framer-motion'
import { Link } from 'react-router-dom'

export function Eyebrow({ children }: { children: ReactNode }) { return <span className="eyebrow">{children}</span> }

export function Status({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'good' | 'warn' | 'bad' | 'live' }) {
  return <span className={`status status--${tone}`}><span className="status__dot" aria-hidden="true" />{children}</span>
}

export function SectionHeading({ title, detail, action }: { title: string; detail?: string; action?: ReactNode }) {
  return <div className="section-heading"><div><h2>{title}</h2>{detail && <p>{detail}</p>}</div>{action}</div>
}

export function Notice({ tone = 'neutral', children }: { tone?: 'neutral' | 'good' | 'warn' | 'bad'; children: ReactNode }) {
  const Icon = tone === 'good' ? Check : tone === 'bad' ? AlertCircle : CircleHelp
  return <div className={`notice notice--${tone}`} role={tone === 'bad' ? 'alert' : 'status'}><Icon size={18} aria-hidden="true" /><div>{children}</div></div>
}

export function Empty({ title, children }: { title: string; children: ReactNode }) {
  return <div className="empty"><span className="empty__mark" aria-hidden="true">↗</span><strong>{title}</strong><p>{children}</p></div>
}

export function RouteReveal({ children }: { children: ReactNode }) {
  const reduced = useReducedMotion()
  return <motion.div initial={reduced ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
    transition={{ duration: .34, ease: [.22, 1, .36, 1] }}>{children}</motion.div>
}

export function Loading({ label = 'Loading current records' }: { label?: string }) {
  return <div className="loading" role="status"><LoaderCircle size={19} className="spin" aria-hidden="true" />{label}</div>
}

export function TextLink({ children, to }: { children: ReactNode; to: string }) {
  return <Link className="text-link" to={to}>{children}<ArrowUpRight size={15} aria-hidden="true" /></Link>
}
