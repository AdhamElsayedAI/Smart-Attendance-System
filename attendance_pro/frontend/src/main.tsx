import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AppShell } from './layouts/AppShell'
import { Overview } from './features/Overview'
import { LiveAttendance } from './features/LiveAttendance'
import { Kiosk } from './features/Kiosk'
import { Students } from './features/Students'
import { Exams } from './features/Exams'
import { Analytics } from './features/Analytics'
import { Diagnostics } from './features/Diagnostics'
import './styles/app.css'
import './styles/management.css'

ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><BrowserRouter><Routes>
  <Route element={<AppShell />}><Route index element={<Overview />} /><Route path="students" element={<Students />} /><Route path="exams" element={<Exams />} /><Route path="attendance" element={<LiveAttendance />} /><Route path="analytics" element={<Analytics />} /><Route path="diagnostics" element={<Diagnostics />} /></Route>
  <Route path="check-in" element={<Kiosk />} />
  <Route path="*" element={<div className="not-found"><h1>That page is not here.</h1><a href="/">Return to overview</a></div>} />
</Routes></BrowserRouter></React.StrictMode>)
