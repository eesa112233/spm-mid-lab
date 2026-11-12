-- Complete SQLite database schema for CarePM.
PRAGMA foreign_keys=ON;

CREATE TABLE activities (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL, work_package_id INTEGER NOT NULL REFERENCES work_packages(id),
 assignee_id INTEGER NOT NULL REFERENCES team(id), duration_days INTEGER NOT NULL CHECK(duration_days>0),
 start_offset_days INTEGER NOT NULL DEFAULT 0 CHECK(start_offset_days>=0),
 dependency_id INTEGER REFERENCES activities(id), planned_cost REAL NOT NULL CHECK(planned_cost>=0),
 progress INTEGER NOT NULL DEFAULT 0 CHECK(progress BETWEEN 0 AND 100),
 delay_days INTEGER NOT NULL DEFAULT 0 CHECK(delay_days>=0),
 source_change_id INTEGER REFERENCES changes(id));

CREATE TABLE changes (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL, justification TEXT NOT NULL,
 cost_impact REAL NOT NULL CHECK(cost_impact>=0), schedule_impact INTEGER NOT NULL CHECK(schedule_impact>=0),
 priority TEXT NOT NULL DEFAULT 'High', status TEXT NOT NULL DEFAULT 'Pending'
 CHECK(status IN ('Pending','Approved','Rejected')), requested_on TEXT NOT NULL,
 decided_on TEXT, linked_requirement_id INTEGER REFERENCES requirements(id));

CREATE TABLE defects (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL,
 activity_id INTEGER REFERENCES activities(id), severity TEXT NOT NULL CHECK(severity IN ('Critical','High','Medium','Low')),
 assignee_id INTEGER NOT NULL REFERENCES team(id),
 status TEXT NOT NULL CHECK(status IN ('Open','In Progress','Resolved')),
 details TEXT NOT NULL DEFAULT '');

CREATE TABLE expenses (
 id INTEGER PRIMARY KEY, activity_id INTEGER NOT NULL REFERENCES activities(id),
 amount REAL NOT NULL CHECK(amount>=0), date TEXT NOT NULL, description TEXT NOT NULL);

CREATE TABLE inspections (
 id INTEGER PRIMARY KEY, deliverable TEXT NOT NULL, checklist TEXT NOT NULL,
 result TEXT NOT NULL CHECK(result IN ('Pass','Fail','Pending')),
 tested_on TEXT NOT NULL, inspector_id INTEGER NOT NULL REFERENCES team(id), notes TEXT NOT NULL DEFAULT '');

CREATE TABLE milestones (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL, due_date TEXT NOT NULL,
 responsible_id INTEGER NOT NULL REFERENCES team(id), status TEXT NOT NULL CHECK(status IN ('Pending','Done')));

CREATE TABLE projects (
 id INTEGER PRIMARY KEY CHECK(id=1), name TEXT NOT NULL, objectives TEXT NOT NULL,
 scope_in TEXT NOT NULL, scope_out TEXT NOT NULL, baseline_budget REAL NOT NULL CHECK(baseline_budget>=0),
 approved_budget REAL NOT NULL CHECK(approved_budget>=0), kickoff TEXT NOT NULL,
 original_deadline TEXT NOT NULL, approved_deadline TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'Active' CHECK(status IN ('Planned','Active','Closed')),
 plan_scope TEXT NOT NULL, plan_schedule TEXT NOT NULL, plan_cost TEXT NOT NULL,
 plan_quality TEXT NOT NULL, as_of_date TEXT NOT NULL, closure_notes TEXT NOT NULL DEFAULT '',
 closed_at TEXT);

CREATE TABLE requirements (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL, priority TEXT NOT NULL CHECK(priority IN ('High','Medium','Low')),
 status TEXT NOT NULL CHECK(status IN ('Proposed','Approved','Rejected')),
 description TEXT NOT NULL DEFAULT '', source_change_id INTEGER REFERENCES changes(id));

CREATE TABLE risks (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL, likelihood INTEGER NOT NULL CHECK(likelihood BETWEEN 1 AND 5),
 impact INTEGER NOT NULL CHECK(impact BETWEEN 1 AND 5),
 preventive_action TEXT NOT NULL, corrective_action TEXT NOT NULL, owner_id INTEGER NOT NULL REFERENCES team(id));

CREATE TABLE stakeholders (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL, expectation TEXT NOT NULL);

CREATE TABLE team (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, role TEXT NOT NULL);

CREATE TABLE work_packages (
 id INTEGER PRIMARY KEY, parent_id INTEGER REFERENCES work_packages(id),
 requirement_id INTEGER REFERENCES requirements(id), code TEXT NOT NULL UNIQUE,
 name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '');
