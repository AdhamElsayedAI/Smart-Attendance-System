import assert from 'node:assert/strict'
import { chromium } from 'playwright'

const browser = await chromium.launch({ channel: 'chrome', headless: true })
try {
  const desktop = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  await desktop.goto('http://127.0.0.1:5173/', { waitUntil: 'networkidle' })
  const students = await desktop.evaluate(async () => (await (await fetch('/api/overview')).json()).metrics.students)
  assert.equal(await desktop.locator('.metric-band strong').first().textContent(), String(students))
  await desktop.getByRole('link', { name: /Prepare a live session/i }).click()
  await desktop.getByRole('heading', { name: /Attendance workstation/i }).waitFor()
  assert.match(await desktop.locator('.session-strip').textContent(), /Standby/)
  await desktop.getByRole('link', { name: /Open student display/i }).click()
  await desktop.getByRole('heading', { name: /Waiting for the session/i }).waitFor()
  assert.equal(await desktop.locator('.kiosk__camera').count(), 1)
  await desktop.close()

  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce' })
  await mobile.goto('http://127.0.0.1:5173/', { waitUntil: 'networkidle' })
  await mobile.getByRole('button', { name: 'Open navigation' }).click()
  await mobile.getByRole('link', { name: /Live attendance/i }).click()
  await mobile.getByRole('heading', { name: /Attendance workstation/i }).waitFor()
  assert.equal(await mobile.evaluate(() => matchMedia('(prefers-reduced-motion: reduce)').matches), true)
  assert.equal(await mobile.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
  await mobile.close()
  console.log('Navigation, real API data, kiosk route, mobile menu, and reduced motion: PASS')
} finally { await browser.close() }
