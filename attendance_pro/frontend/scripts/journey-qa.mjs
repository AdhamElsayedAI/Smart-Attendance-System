// Browser journey against .qa-api.db only. A direct database write below simulates
// persistence for reporting checks; it is NOT a biometric verification test.
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright'

const root = resolve(fileURLToPath(new URL('../../', import.meta.url)))
const dbPath = resolve(root, '.qa-api.db')
const python = process.env.ATTENDANCE_QA_PYTHON || resolve(root, '.venv-app311/Scripts/python.exe')
const suffix = Date.now().toString(36)
const studentId = `QA-${suffix}`
const guardId = `QA-guard-${suffix}`
const browser = await chromium.launch({ channel: 'chrome', headless: true })
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, acceptDownloads: true })
  execFileSync(python, ['-c', 'import sys; from attendance.db import Database; Database(sys.argv[1]).add_student(sys.argv[2], "QA guard")', dbPath, guardId], { cwd: root })
  await page.goto('http://127.0.0.1:5173/students', { waitUntil: 'networkidle' })
  const guard = await page.evaluate(async id =>
    (await (await fetch(`/api/students?search=${encodeURIComponent(id)}`)).json()).some(row => row.student_id === id), guardId)
  assert.ok(guard, 'Browser API is not connected to .qa-api.db; stop before writing')
  await page.getByLabel('University ID').fill(studentId)
  await page.getByLabel('Full name').fill('Browser Student')
  await page.getByRole('button', { name: /Register student/i }).click()
  await page.getByText(`${studentId}`, { exact: true }).first().waitFor()
  await page.getByLabel('Search students').fill(studentId)
  assert.equal(await page.locator('.student-row').count(), 1)
  await page.getByLabel('University ID').fill(studentId)
  await page.getByLabel('Full name').fill('Duplicate')
  await page.getByRole('button', { name: /Register student/i }).click()
  await page.getByRole('alert').getByText(/already registered/i).waitFor()
  await page.locator('#face-photo').setInputFiles({ name: 'invalid.jpg', mimeType: 'image/jpeg', buffer: Buffer.from('not-an-image') })
  await page.getByRole('button', { name: /Enroll face/i }).click()
  await page.getByRole('alert').getByText(/Unreadable image/i).waitFor()

  await page.getByRole('link', { name: 'Examinations' }).click()
  await page.getByLabel('Exam name').fill(`Browser Practical ${suffix}`)
  await page.getByLabel('Description').fill('Isolated browser QA room')
  await page.getByRole('checkbox', { name: new RegExp(studentId) }).first().check()
  await page.getByRole('button', { name: /Create examination/i }).click()
  await page.getByText(/scheduled with 1 participant/i).waitFor()
  const examId = await page.locator('.exam-row--selected').evaluate(row => Number(row.querySelector('.exam-row__index')?.textContent))
  assert.ok(examId > 0)
  await page.getByRole('button', { name: /Start session/i }).click()
  await page.getByText(/Session started/i).waitFor()

  await page.getByRole('link', { name: 'Live attendance' }).click()
  await page.locator('.session-strip').getByText(/Session active/i).waitFor()
  await page.getByRole('button', { name: /Resume camera/i }).click()
  await page.waitForTimeout(1200)
  const cameraState = await page.evaluate(async () => (await (await fetch('/api/session/status')).json()).camera)
  if (cameraState === 'connected') await page.getByRole('button', { name: /Pause camera/i }).click()
  else assert.ok(await page.getByRole('alert').count() > 0, 'Camera failure should be visible to the supervisor')

  // Isolated service-level persistence simulation; no fake biometric claim.
  execFileSync(python, ['-c', 'import sys; from attendance.db import Database; assert Database(sys.argv[1]).record_attendance(int(sys.argv[2]), sys.argv[3])', dbPath, String(examId), studentId], { cwd: root })
  await page.locator('.live-activity').getByText('Browser Student').waitFor({ timeout: 10000 })
  page.once('dialog', dialog => dialog.accept())
  await page.getByRole('button', { name: /End session/i }).click()
  await page.getByRole('link', { name: 'Analytics' }).click()
  await page.getByRole('row').filter({ has: page.getByRole('cell', { name: studentId, exact: true }) }).getByRole('cell', { name: 'Browser Student' }).waitFor()
  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: /Export CSV/i }).click()
  const download = await downloadPromise
  assert.match(download.suggestedFilename(), /attendance-.*\.csv/)
  const text = await (await import('node:fs/promises')).readFile(await download.path(), 'utf8')
  assert.match(text, /Browser Student/)
  assert.match(text, new RegExp(studentId))
  await page.getByLabel('Examination').selectOption(String(examId))
  await page.getByRole('row').filter({ has: page.getByRole('cell', { name: studentId, exact: true }) }).getByRole('cell', { name: 'Browser Student' }).waitFor()
  await page.close()
  console.log(`Browser student → exam → session → simulated persistence → analytics → CSV: PASS (exam ${examId})`)
} finally { await browser.close() }
