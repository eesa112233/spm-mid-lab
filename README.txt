SMART HEALTHCARE PROJECT MANAGEMENT SYSTEM (CarePM)
CSE-494 | Mid-term Case Study | Working implementation

QUICK START (WINDOWS)
1. Install Python 3.10 or newer, with Python added to PATH.
2. Extract this entire folder without rearranging files.
3. Double-click RUN_WINDOWS.bat. It installs the Python requirements and starts the application.
4. Open http://127.0.0.1:8765 if a browser tab does not open automatically.
5. Stop the server using Ctrl+C in the launcher terminal.

QUICK START (MAC / LINUX)
Run: bash RUN_MAC_LINUX.sh

SUBMITTED COMPONENTS
- app.py + core.py + database.py: functional application, validation and scheduling/EVM.
- templates/page.html + static/style.css: interactive browser-based GUI.
- healthcare_pm.sqlite3: persistent populated SQLite database.
- schema.sql + sample_data.sql: database schema and sample INSERT records.
- screenshots/: snapshots of each implemented module, before and after change approval.
- Healthcare_System_Demonstration.mp4: short GUI walkthrough demonstrating baseline changes.
- tests/test_application.py: automated integration/validation test cases.
- test_cases_expected_actual.csv + test_results.xml + TEST_SUMMARY.txt: test evidence.

MODULES
1. Project Initiation & Integration: charter, objectives, stakeholders, integrated plans, milestones, closure.
2. Scope & WBS: requirements lifecycle, hierarchical WBS, cost/schedule change approval gate.
3. Schedule & Resources: calendar-day earliest-start dates, task dependencies, delays, Gantt/milestones.
4. Cost & EVM: activity cost estimates, expenditures, PV, EV, AC, CPI, SPI, threshold alerts.
5. Quality & Risk: critical defects, test/inspection checklists, risk matrix and PDPC action plan.
6. Reporting: integrated progress, changes, delayed work, budget and critical-defect summary.

CASE STUDY WALKTHROUGH
1. Review the Overview page showing PKR 5m and original 16-week deadline.
2. Open Scope & WBS. The sample AI-diagnosis + mobile app request is PENDING.
3. Select Approve on change CR-1 and confirm.
4. Reopen Scope & WBS: approved requirement + WBS package appear.
5. See new dependent activity on Schedule; approved deadline is 2026-12-14.
6. See Cost & EVM and Dashboard: approved cost is now PKR 5,800,000.
7. Use Quality & Risk to review unresolved appointment and patient-record critical bugs.
8. Open Project Report to see the integrated status.

SAMPLE DATA NOTES
This database contains fictional demonstration dates and job-role labels. Its original 16-week
project runs 2026-08-03 to 2026-11-23. The sample scenario change is pending at launch,
so approving it can be demonstrated. Approval adds PKR 800,000 and 21 calendar days.
The UI permits entering additional data; the SQLite file keeps changes across restarts.
If you want to reset the demonstration, restore a fresh copy of healthcare_pm.sqlite3.

EVM NOTES
PV = sum(planned activity cost × fraction of scheduled duration elapsed at report date).
EV = sum(planned activity cost × percent complete).
AC = sum(persisted expense amounts).
CPI = EV/AC; SPI = EV/PV; zero denominators are represented as N/A.
Activity durations and approved changes are expressed in calendar days.
Warning thresholds are CPI < 0.95 and SPI < 0.95, plus deadline/budget checks.

TESTS
Once requirements are installed, run:
    python -m pytest -q tests/test_application.py
Test functions create fresh, isolated temporary SQLite databases.

This is a local Python application launched from a .bat file, not a standalone .exe.
