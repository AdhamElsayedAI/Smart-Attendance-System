import { useState } from 'react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import { ArrowUpRight, BarChart3, CalendarDays, ChartNoAxesCombined, Menu, MonitorPlay, ScanFace, Settings2, UsersRound, X } from 'lucide-react'

export function AppShell() {
  const [open, setOpen] = useState(false)
  return <div className="shell">
    <a className="skip-link" href="#content">Skip to content</a>
    <header className="mobile-header"><Link className="brand brand--mobile" to="/" onClick={() => setOpen(false)}><span className="brand__mark">A<span>·</span></span><span>Attendance<span className="brand__os">OS</span></span></Link>
      <button className="icon-button" aria-label={open ? 'Close navigation' : 'Open navigation'} aria-expanded={open} onClick={() => setOpen(!open)}>{open ? <X /> : <Menu />}</button>
    </header>
    {open && <button className="mobile-scrim" aria-label="Close navigation" onClick={() => setOpen(false)} />}
    <aside className={`sidebar ${open ? 'sidebar--open' : ''}`}>
      <Link className="brand" to="/" onClick={() => setOpen(false)}><span className="brand__mark">A<span>·</span></span><span>Attendance<span className="brand__os">OS</span><small>University edition</small></span></Link>
      <div className="sidebar__line" />
      <nav aria-label="Primary navigation">
        <div className="nav-label">Operations</div>
        <NavLink end to="/" onClick={() => setOpen(false)} className={({ isActive }) => `nav-link ${isActive ? 'nav-link--active' : ''}`}><ChartNoAxesCombined size={19} /><span>Overview</span><span className="nav-link__marker" /></NavLink>
        <NavLink to="/students" onClick={() => setOpen(false)} className={({ isActive }) => `nav-link ${isActive ? 'nav-link--active' : ''}`}><UsersRound size={19} /><span>Students</span><span className="nav-link__marker" /></NavLink>
        <NavLink to="/exams" onClick={() => setOpen(false)} className={({ isActive }) => `nav-link ${isActive ? 'nav-link--active' : ''}`}><CalendarDays size={19} /><span>Examinations</span><span className="nav-link__marker" /></NavLink>
        <NavLink to="/attendance" onClick={() => setOpen(false)} className={({ isActive }) => `nav-link ${isActive ? 'nav-link--active' : ''}`}><MonitorPlay size={19} /><span>Live attendance</span><span className="nav-link__marker" /></NavLink>
        <NavLink to="/analytics" onClick={() => setOpen(false)} className={({ isActive }) => `nav-link ${isActive ? 'nav-link--active' : ''}`}><BarChart3 size={19} /><span>Analytics</span><span className="nav-link__marker" /></NavLink>
        <NavLink to="/diagnostics" onClick={() => setOpen(false)} className={({ isActive }) => `nav-link ${isActive ? 'nav-link--active' : ''}`}><Settings2 size={19} /><span>Diagnostics</span><span className="nav-link__marker" /></NavLink>
        <div className="nav-label nav-label--space">Student experience</div>
        <NavLink to="/check-in" onClick={() => setOpen(false)} className={({ isActive }) => `nav-link ${isActive ? 'nav-link--active' : ''}`}><ScanFace size={19} /><span>Check-in display</span><ArrowUpRight className="nav-external" size={15} /></NavLink>
      </nav>
      <div className="sidebar__bottom"><span className="sidebar__pulse" />Local supervised system<span className="sidebar__version">Prototype V1 · loopback</span></div>
    </aside>
    <main id="content" className="main"><Outlet /></main>
  </div>
}
