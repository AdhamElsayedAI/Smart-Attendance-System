# Supervised graduation demonstration

Use a consented volunteer and a physical webcam on the host computer. The isolated demo database is empty until you create records. Never use real student records for a public presentation.

## Start

1. Install the Python and npm dependencies in the [repository README](../README.md). Verify the native stack in a Python 3.11 environment; this machine's NumPy 2/dlib combination cannot perform face recognition.
2. From `attendance_pro`, run `.\run-local.ps1 -Python .\.venv-app311\Scripts\python.exe`. Its default `.demo-data` folder is separate from operational SQLite and photos. The script starts FastAPI on `127.0.0.1:8000` and Vite on `127.0.0.1:5173`. Open the latter URL.
3. Open **Diagnostics**. Confirm database, recognition, OpenCV, dlib + NumPy, and landmark model. Click **Probe local camera**; it should report Available and then release the device. If the probe fails, resolve device permission or `CAMERA_INDEX` before presenting live recognition.

## Presentation sequence

1. **Overview:** explain that totals and readiness come from the demo database. An empty upcoming exam state links to Exams.
2. **Students:** register the consented volunteer with a stable demo ID. Upload one clear JPG/PNG/BMP face photo. Confirm **Enrolled**. A second registration with the same ID produces a conflict, with no duplicate row.
3. **Examinations:** create a named exam dated today, with a valid time interval and a short room description. Assign the volunteer. Review the selected roster. Click **Start session**; an eligible newly created exam starts immediately regardless of the clock time within its displayed interval.
4. **Live attendance:** click **Resume camera**. The host camera feed and backend stage should move through face detection, identity match, blink required, and verified. Only one face should be visible. Ask the volunteer to hold still, close and reopen both eyes naturally, and wait for **Attendance recorded**. The present count and recent confirmation should update even if the kiosk browser is closed.
5. **Student check-in:** open `/check-in` on the same host, ideally fullscreen. It has no admin controls and shows only the current exam and matched student state. It displays success only after a saved backend outcome.
6. Ask the same volunteer to retry. Show the duplicate attendance feedback; the roster and Analytics retain one row for that student/exam.
7. **Analytics:** select the exam. Confirm assigned, present, absent, percentage, and record table. Download CSV and inspect the saved row.
8. Return to Live attendance. Pause the camera to release the device, then **End session**. Diagnostics should show the camera lease free. An ended exam cannot be restarted; create a new exam for another run.

## Recovery and evidence

- **Camera unavailable:** close other camera applications, check Windows permission, set `CAMERA_INDEX`, and probe again. No attendance should appear from a failed start.
- **dlib + NumPy unavailable:** use the owner's verified Python 3.11 environment or rebuild a compatible isolated environment; do not reinstall native dependencies in the preserved working environment during the presentation.
- **No face match:** improve lighting, show one face, and inspect enrollment status/photo. Recognition accuracy is not measured.
- **Recognized but not recorded:** check roster membership, active exam status, blink feedback, and duplicate status. A successful frontend animation alone cannot create a record.
- **Browser refresh/disconnect:** reopen the local URL. The backend camera worker and event pump continue until paused or ended.
- **Logs:** the optional launcher writes API output to the ignored `.local-run` folder. Preserve the demo database if you want to replay its reporting screen; otherwise remove `.demo-data` manually after closing both services.

Owner-side hardware verification is still pending until a real face and webcam complete this sequence in a compatible environment. A simulated API event or manually inserted QA row is not a hardware pass.
