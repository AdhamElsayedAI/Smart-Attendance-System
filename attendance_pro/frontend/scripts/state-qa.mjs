// Visual state contract only: intercepted API responses, no database mutation.
import assert from 'node:assert/strict'
import { chromium } from 'playwright'

const browser = await chromium.launch({ channel: 'chrome', headless: true })
try {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce' })
  let state = { exam: null, camera: 'paused', stage: 'Waiting', identity: null,
    feedback: 'Start the host camera when ready.', face_count: 0, outcome: null, progress: null, error: null }
  await page.route('**/api/session/status', route => route.fulfill({ json: state }))
  await page.route('**/api/session/frame', route => route.fulfill({ status: 404 }))
  await page.goto('http://127.0.0.1:5173/check-in', { waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: 'Waiting for the session.' }).waitFor()
  const exam = { id: 87, name: 'State QA', exam_date: '2026-10-17', start_time: '09:00', end_time: '10:00', status: 'active', assigned: 1, roster_complete: 1, description: '' }
  state = { ...state, exam, camera: 'connected', feedback: 'Show one face' }
  await page.getByRole('heading', { name: 'Step into view when invited.' }).waitFor()
  state = { ...state, stage: 'Face detected', face_count: 1, feedback: 'Face unknown or landmarks unavailable' }
  await page.getByRole('heading', { name: 'Face detected. Hold still.' }).waitFor()
  state = { ...state, stage: 'Identity matched', identity: 'State Student', feedback: 'Hold still' }
  await page.getByRole('heading', { name: 'Hold still for a moment.' }).waitFor()
  state = { ...state, stage: 'Blink required', feedback: 'Eyes closed — reopen to complete blink' }
  await page.getByRole('heading', { name: 'Close and reopen your eyes once.' }).waitFor()
  state = { ...state, stage: 'Verified', feedback: 'Blink verified' }
  await page.getByRole('heading', { name: 'Saving your attendance.' }).waitFor()
  state = { ...state, stage: 'Recorded', outcome: { kind: 'recorded', message: 'Attendance recorded for State Student.' } }
  await page.getByRole('heading', { name: 'You are checked in.' }).waitFor()
  state = { ...state, stage: 'Verified', outcome: { kind: 'rejected', message: 'Attendance was already recorded.' } }
  await page.getByRole('heading', { name: 'Please ask the supervisor for help.' }).waitFor()
  assert.equal(await page.locator('nav').count(), 0)
  assert.equal(await page.evaluate(() => matchMedia('(prefers-reduced-motion: reduce)').matches), true)
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
  await page.close()
  console.log('Kiosk waiting → face → identity → blink → verified → recorded/rejected, reduced motion: PASS (intercepted states)')
} finally { await browser.close() }
