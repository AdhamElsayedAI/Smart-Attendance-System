# AttendanceOS React experience

The seven routes are `/` Overview, `/students`, `/exams`, `/attendance`, `/analytics`, `/diagnostics`, and `/check-in`. The first six share an administrative rail. Check-in has a separate, student-facing frame with no admin navigation or controls. It uses the same backend session state, and its recorded animation requires a saved API outcome.

Warm paper, deep ink, teal, restrained copper, and sage build an academic visual identity. Overview uses an editorial feature and compact readiness ledger. Students pairs the directory with registration and enrollment forms. Exams pairs a setup desk with history, roster, session controls, and results. Live attendance prioritizes the camera and verification sequence. Analytics gives real denominators, filters, a comparison chart, a record table, and CSV. Diagnostics reports concrete environment and camera checks. These screens have distinct composition rather than repeating a generic dashboard grid.

Motion is limited to navigation entry, backend stage transitions, bars based on real records, and brief hover/focus feedback. `prefers-reduced-motion` disables CSS motion, and React `useReducedMotion` suppresses state animation. Labels, validation feedback, keyboard focus, status text, and 44px actions are present. Browser QA checks 1920, 1440, 1024, 768, and 390px; on small screens analytics rows become stacked cards.

Screenshots generated from the isolated QA database are under the Git-ignored `qa-screenshots/` folder. The browser state script intercepts status solely to check kiosk rendering; it does not establish live biometric operation. The camera feed belongs to the host FastAPI process, not the browser device.
