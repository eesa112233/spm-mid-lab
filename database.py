"""SQLite schema and realistic hospital-project sample data."""
import sqlite3
from datetime import date, timedelta
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / 'healthcare_pm.sqlite3'

SCHEMA = '''
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS projects (
 id INTEGER PRIMARY KEY CHECK(id=1), name TEXT NOT NULL, objectives TEXT NOT NULL,
 scope_in TEXT NOT NULL, scope_out TEXT NOT NULL, baseline_budget REAL NOT NULL CHECK(baseline_budget>=0),
 approved_budget REAL NOT NULL CHECK(approved_budget>=0), kickoff TEXT NOT NULL,
 original_deadline TEXT NOT NULL, approved_deadline TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'Active' CHECK(status IN ('Planned','Active','Closed')),
 plan_scope TEXT NOT NULL, plan_schedule TEXT NOT NULL, plan_cost TEXT NOT NULL,
 plan_quality TEXT NOT NULL, as_of_date TEXT NOT NULL, closure_notes TEXT NOT NULL DEFAULT '',
 closed_at TEXT);
CREATE TABLE IF NOT EXISTS stakeholders (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL, expectation TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS team (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, role TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS requirements (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL, priority TEXT NOT NULL CHECK(priority IN ('High','Medium','Low')),
 status TEXT NOT NULL CHECK(status IN ('Proposed','Approved','Rejected')),
 description TEXT NOT NULL DEFAULT '', source_change_id INTEGER REFERENCES changes(id));
CREATE TABLE IF NOT EXISTS work_packages (
 id INTEGER PRIMARY KEY, parent_id INTEGER REFERENCES work_packages(id),
 requirement_id INTEGER REFERENCES requirements(id), code TEXT NOT NULL UNIQUE,
 name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS activities (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL, work_package_id INTEGER NOT NULL REFERENCES work_packages(id),
 assignee_id INTEGER NOT NULL REFERENCES team(id), duration_days INTEGER NOT NULL CHECK(duration_days>0),
 start_offset_days INTEGER NOT NULL DEFAULT 0 CHECK(start_offset_days>=0),
 dependency_id INTEGER REFERENCES activities(id), planned_cost REAL NOT NULL CHECK(planned_cost>=0),
 progress INTEGER NOT NULL DEFAULT 0 CHECK(progress BETWEEN 0 AND 100),
 delay_days INTEGER NOT NULL DEFAULT 0 CHECK(delay_days>=0),
 source_change_id INTEGER REFERENCES changes(id));
CREATE TABLE IF NOT EXISTS changes (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL, justification TEXT NOT NULL,
 cost_impact REAL NOT NULL CHECK(cost_impact>=0), schedule_impact INTEGER NOT NULL CHECK(schedule_impact>=0),
 priority TEXT NOT NULL DEFAULT 'High', status TEXT NOT NULL DEFAULT 'Pending'
 CHECK(status IN ('Pending','Approved','Rejected')), requested_on TEXT NOT NULL,
 decided_on TEXT, linked_requirement_id INTEGER REFERENCES requirements(id));
CREATE TABLE IF NOT EXISTS expenses (
 id INTEGER PRIMARY KEY, activity_id INTEGER NOT NULL REFERENCES activities(id),
 amount REAL NOT NULL CHECK(amount>=0), date TEXT NOT NULL, description TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS milestones (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL, due_date TEXT NOT NULL,
 responsible_id INTEGER NOT NULL REFERENCES team(id), status TEXT NOT NULL CHECK(status IN ('Pending','Done')));
CREATE TABLE IF NOT EXISTS defects (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL,
 activity_id INTEGER REFERENCES activities(id), severity TEXT NOT NULL CHECK(severity IN ('Critical','High','Medium','Low')),
 assignee_id INTEGER NOT NULL REFERENCES team(id),
 status TEXT NOT NULL CHECK(status IN ('Open','In Progress','Resolved')),
 details TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS inspections (
 id INTEGER PRIMARY KEY, deliverable TEXT NOT NULL, checklist TEXT NOT NULL,
 result TEXT NOT NULL CHECK(result IN ('Pass','Fail','Pending')),
 tested_on TEXT NOT NULL, inspector_id INTEGER NOT NULL REFERENCES team(id), notes TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS risks (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL, likelihood INTEGER NOT NULL CHECK(likelihood BETWEEN 1 AND 5),
 impact INTEGER NOT NULL CHECK(impact BETWEEN 1 AND 5),
 preventive_action TEXT NOT NULL, corrective_action TEXT NOT NULL, owner_id INTEGER NOT NULL REFERENCES team(id));
'''


def connect():
    db = sqlite3.connect(str(DB_PATH), timeout=15)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA busy_timeout=10000')
    return db


def initialize():
    with connect() as db:
        db.executescript(SCHEMA)
        if db.execute('SELECT COUNT(*) FROM projects').fetchone()[0]:
            return
        kickoff = date(2026, 8, 3)
        deadline = kickoff + timedelta(weeks=16)
        as_of = date(2026, 10, 26)
        db.execute('''INSERT INTO projects VALUES (1,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
            'Smart Healthcare Project Management System',
            'Deliver a healthcare management solution for five hospitals covering appointments, laboratory reports, doctor schedules, online consultations, and billing.',
            'Patient appointments; laboratory reports; doctor schedules; online consultations; hospital billing; patient records.',
            'AI-based preliminary diagnosis and mobile app unless approved through change control.',
            5000000,5000000,kickoff.isoformat(),deadline.isoformat(),deadline.isoformat(),'Active',
            'Deliver approved hospital modules; manage requirements through acceptance and approval.',
            '16 calendar weeks; baseline activities organized using finish-to-start dependencies.',
            'Baseline ceiling PKR 5,000,000; activity estimates and verified actual expenditures.',
            'Track critical appointment and patient-record defects; inspect module deliverables and record test outcomes.',
            as_of.isoformat(),'',None))
        team = [
            ('Project Manager', 'Project Manager'),
            ('Backend Developer 1', 'Backend Developer'),
            ('Backend Developer 2', 'Backend Developer'),
            ('Frontend Developer 1', 'Frontend Developer'),
            ('Frontend Developer 2', 'Frontend Developer'),
            ('Database Developer', 'Database Developer'),
            ('QA Engineer', 'Quality Assurance Engineer'),
        ]
        db.executemany('INSERT INTO team(name,role) VALUES (?,?)',team)
        db.executemany('INSERT INTO stakeholders(name,role,expectation) VALUES (?,?,?)',[
            ('Five-hospital Management Board','Sponsor','Delivery in 16 weeks within PKR 5m approved baseline'),
            ('Hospital Administration','Operational stakeholder','Reliable appointments, doctor schedules, and billing'),
            ('Doctors and Lab Staff','End user','Accurate lab reports and consultation records'),
            ('Patients','End user','Accessible booking and online consultations')])
        req_titles = [
            ('Patient registration and medical records','High'),('Doctor availability and schedules','High'),
            ('Patient appointment scheduling','High'),('Laboratory reports','High'),
            ('Online consultations','Medium'),('Hospital billing','High')]
        db.executemany('INSERT INTO requirements(title,priority,status,description) VALUES (?,?,"Approved",?)',
                       [(title,pr,'Approved baseline requirement') for title,pr in req_titles])
        packages = [
            (None,1,'1','Initiation & Architecture','Project foundation'),
            (1,1,'1.1','Requirements & Design','Specification and overall architecture'),
            (None,2,'2','Core Platform','Core records and doctor schedules'),
            (3,1,'2.1','Patient & Database','Patient records and database'),
            (3,2,'2.2','Doctor Schedules','Doctor availability'),
            (None,3,'3','Healthcare Workflows','Patient-facing functions'),
            (6,3,'3.1','Appointments','Scheduling'),
            (6,4,'3.2','Lab Reports','Reports'),
            (6,5,'3.3','Consultations','Remote care'),
            (None,6,'4','Billing & Validation','Billing and quality'),
            (10,6,'4.1','Billing Integration','Financial operations'),
            (10,3,'4.2','Testing & Delivery','Regression and release')]
        for parent,req,code,name,desc in packages:
            db.execute('INSERT INTO work_packages(parent_id,requirement_id,code,name,description) VALUES (?,?,?,?,?)',
                       (parent,req,code,name,desc))
        activity_data = [
            ('Requirements & charter',2,1,14,None,300000,100,0),
            ('Architecture and UI design',2,4,14,1,500000,100,0),
            ('Database & patient records',4,6,14,2,700000,100,0),
            ('Doctor schedules / core APIs',5,2,14,3,900000,100,0),
            ('Appointment scheduling',7,3,14,4,850000,100,5),
            ('Lab reports & consultations',8,5,14,5,850000,60,0),
            ('Billing and integration',11,2,14,6,550000,0,0),
            ('System QA and deployment',12,7,14,7,350000,0,0),
        ]
        for title,pkg,owner,duration,dep,cost,progress,delay in activity_data:
            db.execute('''INSERT INTO activities(title,work_package_id,assignee_id,duration_days,start_offset_days,
                dependency_id,planned_cost,progress,delay_days) VALUES (?,?,?,?,0,?,?,?,?)''',
                       (title,pkg,owner,duration,dep,cost,progress,delay))
        # Pending, unapproved change: must have no effect on scope, schedule or budget.
        db.execute('''INSERT INTO changes(title,justification,cost_impact,schedule_impact,priority,status,requested_on)
                   VALUES (?,?,?,?,?,?,?)''',(
            'AI-based preliminary diagnosis + mobile app',
            'Hospital management requires AI assisted preliminary diagnosis and mobile accessibility.',
            800000,21,'High','Pending','2026-10-26'))
        for name,deadline_offset,owner,status in [
            ('Charter approved',14,1,'Done'),('Core platform ready',56,2,'Done'),
            ('Integrated healthcare functions',98,1,'Pending'),('QA and release sign-off',112,7,'Pending')]:
            db.execute('INSERT INTO milestones(title,due_date,responsible_id,status) VALUES (?,?,?,?)',
                       (name,(kickoff+timedelta(days=deadline_offset)).isoformat(),owner,status))
        for activity_id,amount,desc in [
            (1,320000,'Analysis and requirements'),(2,515000,'Design delivery'),
            (3,735000,'Database and record implementation'),(4,940000,'Doctor schedules'),
            (5,910000,'Appointment module and rework'),(6,510000,'Lab and consultation partial delivery')]:
            db.execute('INSERT INTO expenses(activity_id,amount,date,description) VALUES (?,?,?,?)',
                       (activity_id,amount,'2026-10-26',desc))
        db.executemany('''INSERT INTO defects(title,activity_id,severity,assignee_id,status,details)
                         VALUES (?,?,?,?,?,?)''',[
            ('Double-booking when doctors change slots',5,'Critical',2,'Open','Reproduce simultaneous bookings; verify locking.'),
            ('Patient record is overwritten on concurrent updates',3,'Critical',6,'In Progress','Protect patient history and test isolation.'),
            ('Billing summary rounding issue',7,'Medium',2,'Open','Compare invoice subtotals and totals.')])
        db.executemany('''INSERT INTO inspections(deliverable,checklist,result,tested_on,inspector_id,notes)
                          VALUES (?,?,?,?,?,?)''',[
            ('Patient records','Create/update/history integrity','Fail','2026-10-26',7,'Concurrent update defect open'),
            ('Appointment scheduling','No double booking; cancellation; reschedule','Fail','2026-10-26',7,'Double-booking defect open'),
            ('Doctor schedules','Availability and conflict checking','Pass','2026-10-23',7,'Acceptance checks passed'),
            ('Billing integration','Invoice totals and receipts','Pending','2026-10-26',7,'Awaiting full integration')])
        db.executemany('''INSERT INTO risks(title,likelihood,impact,preventive_action,corrective_action,owner_id)
                          VALUES (?,?,?,?,?,?)''',[
            ('Critical appointment defects block acceptance',4,5,'Run concurrent-booking regression suites','Hotfix and rerun regression before release',7),
            ('Patient data corruption during concurrent edits',3,5,'Add transactions and audit history','Restore backup; patch concurrent write handling',6),
            ('Unapproved AI/mobile expansion exceeds budget',4,4,'Require signed change-control decision','Defer work until revised budget and deadline approved',1),
            ('Integration delay impacts release',3,4,'Review dependent tasks and critical path daily','Reassign available developers and rebaseline only after approval',1)])


def query_all(db, sql, args=()):
    return [dict(r) for r in db.execute(sql,args).fetchall()]


def query_one(db, sql, args=()):
    row = db.execute(sql,args).fetchone()
    return dict(row) if row else None
