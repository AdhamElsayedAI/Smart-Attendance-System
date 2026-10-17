import { chromium } from 'playwright'
import { mkdir } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'

const output = resolve(fileURLToPath(new URL('../qa-screenshots/', import.meta.url)))
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const failures = []
for (const width of [1920, 1440, 1024, 768, 390]) {
  for (const [route, name] of [['/', 'overview'], ['/students', 'students'], ['/exams', 'exams'],
    ['/attendance', 'live'], ['/analytics', 'analytics'], ['/diagnostics', 'diagnostics'], ['/check-in', 'kiosk']]) {
    const page = await browser.newPage({ viewport: { width, height: 900 }, deviceScaleFactor: 1 })
    const errors = []
    page.on('pageerror', error => errors.push(error.message))
    const response = await page.goto(`http://127.0.0.1:5173${route}`, { waitUntil: 'networkidle' })
    await page.locator('h1').first().waitFor({ timeout: 10000 })
    const state = await page.evaluate(() => ({
      viewport: innerWidth, document: document.documentElement.scrollWidth,
      heading: document.querySelector('h1')?.textContent,
    }))
    if (width === 1440 || width === 390) await page.screenshot({ path: resolve(output, `${name}-${width}.png`), fullPage: true })
    if (response.status() !== 200 || state.document > state.viewport + 1 || errors.length) failures.push({ name, width, status: response.status(), ...state, errors })
    console.log(`${name.padEnd(9)} ${width}: HTTP ${response.status()} · width ${state.document}/${state.viewport} · ${state.heading}`)
    await page.close()
  }
}
await browser.close()
if (failures.length) { console.error(JSON.stringify(failures, null, 2)); process.exitCode = 1 }
