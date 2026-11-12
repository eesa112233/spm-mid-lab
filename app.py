"""FastAPI interactive project management system for the healthcare case study.

Run: python app.py (or RUN_WINDOWS.bat). Data persist in healthcare_pm.sqlite3.
"""
from datetime import date, timedelta
from pathlib import Path
import sqlite3
from urllib.parse import quote
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape

from core import schedule, earned_value, require_text, bounded_int, nonnegative_money, risk_score, revised_baselines, parse_date
from database import connect, initialize, query_all, query_one

ROOT = Path(__file__).parent
app = FastAPI(title='Smart Healthcare Project Manager')
app.mount('/static', StaticFiles(directory=ROOT/'static'), name='static')
ENV = Environment(loader=FileSystemLoader(ROOT/'templates'), autoescape=select_autoescape(['html']))
ENV.filters['money'] = lambda value: 'PKR {:,.0f}'.format(float(value or 0))
ENV.filters['day'] = lambda value: value.strftime('%d %b %Y') if isinstance(value, date) else str(value or '')
initialize()


def full_context(tab, notification='', error=''):
    with connect() as db:
        project = query_one(db, 'SELECT * FROM projects WHERE id=1')
        stakeholders = query_all(db, 'SELECT * FROM stakeholders ORDER BY id')
        team = query_all(db, 'SELECT * FROM team ORDER BY id')
        requirements = query_all(db, 'SELECT * FROM requirements ORDER BY id')
        packages = query_all(db, '''SELECT w.*,r.status AS req_status,r.title AS requirement_title
                                      FROM work_packages w LEFT JOIN requirements r ON r.id=w.requirement_id ORDER BY w.code''')
        changes = query_all(db, 'SELECT * FROM changes ORDER BY id DESC')
        activities = query_all(db, '''SELECT a.*,t.name AS assignee,w.name AS work_package,
                                      w.requirement_id,r.status AS requirement_status
                                      FROM activities a JOIN team t ON a.assignee_id=t.id
                                      JOIN work_packages w ON a.work_package_id=w.id
                                      LEFT JOIN requirements r ON r.id=w.requirement_id ORDER BY a.id''')
        expenses = query_all(db, '''SELECT e.*,a.title AS activity_title FROM expenses e
                                    JOIN activities a ON a.id=e.activity_id ORDER BY e.id DESC''')
        milestones = query_all(db, '''SELECT m.*,t.name AS responsible FROM milestones m
                                       JOIN team t ON m.responsible_id=t.id ORDER BY m.due_date''')
        defects = query_all(db, '''SELECT d.*,t.name AS assignee,a.title AS activity_title
                                   FROM defects d JOIN team t ON d.assignee_id=t.id
                                   LEFT JOIN activities a ON a.id=d.activity_id ORDER BY
                                   CASE d.severity WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 WHEN 'Medium' THEN 3 ELSE 4 END,d.id''')
        inspections = query_all(db, '''SELECT i.*,t.name AS inspector FROM inspections i
                                       JOIN team t ON i.inspector_id=t.id ORDER BY i.id DESC''')
        risks = query_all(db, '''SELECT r.*,t.name AS owner,r.likelihood*r.impact AS score
                                FROM risks r JOIN team t ON r.owner_id=t.id ORDER BY score DESC,r.id''')
    base_schedule = schedule(activities, project['kickoff'], False)
    forecast_schedule = schedule(activities, project['kickoff'], True)
    base_by_id = {t['id']: t for t in base_schedule}
    forecast_by_id = {t['id']: t for t in forecast_schedule}
    today = parse_date(project['as_of_date'])
    total_cost = sum(float(a['planned_cost']) for a in activities)
    ac_by_task = {}
    for x in expenses:
        ac_by_task[x['activity_id']] = ac_by_task.get(x['activity_id'], 0) + x['amount']
    kickoff = parse_date(project['kickoff'])
    boundary = max(parse_date(project['approved_deadline']), *(t['end'] for t in forecast_schedule)) if forecast_schedule else parse_date(project['approved_deadline'])
    width_days = max(1, (boundary-kickoff).days + 3)
    milestone_rows=[]
    for m in milestones:
        mm=dict(m)
        mm['left'] = 100*max(0, (parse_date(m['due_date'])-kickoff).days)/width_days
        milestone_rows.append(mm)
    activity_rows=[]
    for t in activities:
        base=base_by_id[t['id']]
        fore=forecast_by_id[t['id']]
        end=fore['end']
        delayed = (today > base['end'] and t['progress'] < 100) or int(t['delay_days'])>0
        tr=dict(t)
        tr.update(start=base['start'],end=base['end'],forecast_start=fore['start'],forecast_end=end,
                  delayed=delayed, slip=(end-base['end']).days,
                  left=100*max(0,(fore['start']-kickoff).days)/width_days,
                  barwidth=100*max(1,(end-fore['start']).days)/width_days,
                  actual_cost=ac_by_task.get(t['id'],0))
        activity_rows.append(tr)
    evm = earned_value(base_schedule, expenses, project['as_of_date'])
    critical_open = sum(d['severity']=='Critical' and d['status']!='Resolved' for d in defects)
    delayed_count = sum(a['delayed'] for a in activity_rows)
    finish = max((a['forecast_end'] for a in activity_rows), default=kickoff)
    finish_slip = (finish-parse_date(project['approved_deadline'])).days
    base_finish = max((t['end'] for t in base_schedule), default=kickoff)
    actual_cost = sum(e['amount'] for e in expenses)
    progress = round(sum(a['planned_cost']*a['progress']/100 for a in activities)/total_cost*100,1) if total_cost else 0
    warnings=[]
    if total_cost>project['approved_budget']:
        warnings.append('Planned cost exceeds the approved budget.')
    if actual_cost>project['approved_budget']:
        warnings.append('Actual spending exceeds the approved budget.')
    if evm['cpi'] is not None and evm['cpi']<.95:
        warnings.append('Cost performance below threshold: CPI < 0.95.')
    if evm['spi'] is not None and evm['spi']<.95:
        warnings.append('Schedule performance below threshold: SPI < 0.95.')
    if finish_slip>0:
        warnings.append(f'Forecast completion is {finish_slip} calendar day(s) beyond the approved deadline.')
    if critical_open:
        warnings.append(f'{critical_open} unresolved critical defect(s) require attention.')
    # All submitted requirements are shown, but only approved ones are permitted in work packages.
    approved_requirements = [r for r in requirements if r['status']=='Approved']
    valid_packages = [w for w in packages if w['requirement_id'] is None or w['req_status']=='Approved']
    notice=notification
    return locals()


@app.get('/', response_class=HTMLResponse)
async def home(tab: str = 'dashboard', notice: str = '', error: str = ''):
    permitted={'dashboard','initiation','scope','schedule','cost','quality','report'}
    if tab not in permitted:
        tab='dashboard'
    template=ENV.get_template('page.html')
    return HTMLResponse(template.render(**full_context(tab,notice,error)))


def fail(msg):
    return HTMLResponse(f'''<!doctype html><html><head><meta charset="utf-8"><style>
        body{{font-family:Arial;background:#f5f7fa;padding:40px;color:#243047}}
        section{{max-width:650px;margin:60px auto;background:#fff;padding:36px;border-radius:15px}}
        a{{color:#0873b9}}</style></head><body><section><h2>Input could not be saved</h2>
        <p>{__import__('html').escape(str(msg))}</p><a href="/">Return to the application</a></section></body></html>''',status_code=400)


def route_to(tab, msg):
    return RedirectResponse('/?tab='+quote(tab)+'&notice='+quote(msg), status_code=303)


def val(form, key, label):
    return require_text(form.get(key),label)


def choice(form, key, options):
    x=val(form,key,key.replace('_',' ').title())
    if x not in options:
        raise ValueError(f'Invalid {key}: {x}')
    return x


def ident(form,key,label=None):
    return bounded_int(form.get(key),label or key,1,1_000_000)


def ensure_exists(db,table,pk):
    if table not in ('team','activities','requirements','work_packages','milestones','changes','defects','inspections','risks','stakeholders'):
        raise ValueError('Unknown table')
    if not db.execute(f'SELECT 1 FROM {table} WHERE id=?',(pk,)).fetchone():
        raise ValueError(f'{table[:-1]} record {pk} does not exist.')


def approved_package(db, wp):
    row=query_one(db,'''SELECT w.*,r.status AS req_status FROM work_packages w
                        LEFT JOIN requirements r ON r.id=w.requirement_id WHERE w.id=?''',(wp,))
    if not row or row['req_status']!='Approved':
        raise ValueError('Activities can only be assigned to work packages with approved requirements.')


@app.post('/action/{kind}')
async def mutate(kind: str, request: Request):
    form=await request.form()
    tab={'project':'initiation','plan':'initiation','stakeholder':'initiation','milestone':'initiation',
         'closure':'initiation','requirement':'scope','work_package':'scope','change':'scope',
         'change_decide':'scope','activity':'schedule','progress':'schedule','expense':'cost',
         'defect':'quality','inspection':'quality','risk':'quality','as_of':'cost'}.get(kind,'dashboard')
    try:
        with connect() as db:
            project=query_one(db,'SELECT * FROM projects WHERE id=1')
            if project['status']=='Closed' and kind != 'closure':
                raise ValueError('The project is closed. Reopen it before editing project records.')
            if kind=='project':
                name=val(form,'name','Project name');obj=val(form,'objectives','Objectives')
                in_scope=val(form,'scope_in','In-scope boundaries');out_scope=val(form,'scope_out','Out-of-scope boundaries')
                status=choice(form,'status',('Planned','Active'))
                kickoff=val(form,'kickoff','Kickoff date');deadline=val(form,'original_deadline','Baseline deadline')
                if parse_date(deadline)<=parse_date(kickoff):raise ValueError('Deadline must follow kickoff date.')
                # Baseline schedule, original budget and approved change records are immutable in charter editing.
                db.execute('''UPDATE projects SET name=?,objectives=?,scope_in=?,scope_out=?,status=? WHERE id=1''',
                           (name,obj,in_scope,out_scope,status))
                msg='Project charter updated.'
            elif kind=='plan':
                db.execute('''UPDATE projects SET plan_scope=?,plan_schedule=?,plan_cost=?,plan_quality=? WHERE id=1''',
                           tuple(val(form,k,k.replace('_',' ')) for k in ('plan_scope','plan_schedule','plan_cost','plan_quality')))
                msg='Project management plan updated.'
            elif kind=='stakeholder':
                db.execute('INSERT INTO stakeholders(name,role,expectation) VALUES (?,?,?)',
                           (val(form,'name','Name'),val(form,'role','Role'),val(form,'expectation','Expectation')))
                msg='Stakeholder added.'
            elif kind=='milestone':
                owner=ident(form,'responsible_id','Responsible team member');ensure_exists(db,'team',owner)
                due=val(form,'due_date','Due date');parse_date(due)
                db.execute('INSERT INTO milestones(title,due_date,responsible_id,status) VALUES (?,?,?,?)',
                           (val(form,'title','Title'),due,owner,choice(form,'status',('Pending','Done'))))
                msg='Milestone recorded.'
            elif kind=='closure':
                status=choice(form,'status',('Active','Closed'))
                notes=str(form.get('closure_notes','')).strip()
                if status=='Closed' and not notes:raise ValueError('Closure records require closure notes.')
                db.execute('UPDATE projects SET status=?,closure_notes=?,closed_at=? WHERE id=1',
                           (status,notes,date.today().isoformat() if status=='Closed' else None))
                msg='Project closure record saved.'
            elif kind=='requirement':
                mode=choice(form,'mode',('add','update'))
                title=val(form,'title','Requirement title');priority=choice(form,'priority',('High','Medium','Low'))
                status=choice(form,'status',('Proposed','Approved','Rejected'))
                desc=str(form.get('description','')).strip()
                if mode=='add':
                    # Newly proposed requirements cannot be self-approved; change control authorizes scope additions.
                    if status=='Approved':raise ValueError('New scope must be approved through a change request.')
                    db.execute('INSERT INTO requirements(title,priority,status,description) VALUES (?,?,?,?)',
                               (title,priority,status,desc))
                else:
                    id_=ident(form,'record_id','Requirement');ensure_exists(db,'requirements',id_)
                    current=query_one(db,'SELECT * FROM requirements WHERE id=?',(id_,))
                    if current['status']=='Approved' and status!='Approved':
                        raise ValueError('Approved requirements cannot be revoked while in scope.')
                    if current['status']!='Approved' and status=='Approved':
                        raise ValueError('Proposed requirements must be approved by a change request.')
                    db.execute('UPDATE requirements SET title=?,priority=?,status=?,description=? WHERE id=?',
                               (title,priority,status,desc,id_))
                msg='Requirement saved (approval gate enforced).'
            elif kind=='work_package':
                requirement_id=ident(form,'requirement_id','Requirement')
                req=query_one(db,'SELECT * FROM requirements WHERE id=?',(requirement_id,))
                if not req or req['status']!='Approved':raise ValueError('Only approved requirements may enter the WBS.')
                parent_raw=str(form.get('parent_id','')).strip()
                parent=int(parent_raw) if parent_raw else None
                if parent:ensure_exists(db,'work_packages',parent)
                code=val(form,'code','WBS code')
                if parent:
                    parent_code=db.execute('SELECT code FROM work_packages WHERE id=?',(parent,)).fetchone()[0]
                    if not code.startswith(parent_code+'.'):
                        raise ValueError('Child WBS code must begin with its parent code and a dot.')
                db.execute('''INSERT INTO work_packages(parent_id,requirement_id,code,name,description)
                               VALUES (?,?,?,?,?)''',(parent,requirement_id,code,val(form,'name','WBS name'),
                               str(form.get('description','')).strip()))
                msg='Approved-scope WBS work package created.'
            elif kind=='change':
                cost=nonnegative_money(form.get('cost_impact'),'Cost impact')
                duration=bounded_int(form.get('schedule_impact'),'Schedule impact days',0,365)
                if cost==0 and duration==0:raise ValueError('Change must have cost or schedule impact.')
                db.execute('''INSERT INTO changes(title,justification,cost_impact,schedule_impact,priority,status,requested_on)
                              VALUES (?,?,?,?,?,'Pending',?)''',
                           (val(form,'title','Change title'),val(form,'justification','Justification'),cost,duration,
                            choice(form,'priority',('High','Medium','Low')),date.today().isoformat()))
                msg='Change submitted for review; no baseline impact until approval.'
            elif kind=='change_decide':
                cid=ident(form,'change_id','Change request')
                decision=choice(form,'decision',('Approved','Rejected'))
                change=query_one(db,'SELECT * FROM changes WHERE id=?',(cid,))
                if not change:raise ValueError('Change request does not exist.')
                if change['status']!='Pending':raise ValueError('Change was already decided; double approval is blocked.')
                if decision=='Rejected':
                    db.execute('UPDATE changes SET status=?,decided_on=? WHERE id=?',
                               ('Rejected',date.today().isoformat(),cid))
                    msg='Change rejected: approved scope, budget and schedule remain unchanged.'
                else:
                    budget,deadline=revised_baselines(project['approved_budget'],project['approved_deadline'],
                                                       change['cost_impact'],change['schedule_impact'])
                    if change['cost_impact'] > 0 or change['schedule_impact']>0:
                        db.execute('''INSERT INTO requirements(title,priority,status,description,source_change_id)
                                     VALUES (?,?,'Approved',?,?)''',
                                   (change['title'],change['priority'],change['justification'],cid))
                        requirement_id=db.execute('SELECT last_insert_rowid()').fetchone()[0]
                        root=query_one(db,"SELECT id,code FROM work_packages WHERE code='5'")
                        if not root:
                            # Approved change adds the change-management WBS parent, tied to the new approved requirement.
                            db.execute('''INSERT INTO work_packages(parent_id,requirement_id,code,name,description)
                                          VALUES (NULL,?,?,?,?)''',
                                       (requirement_id,'5','Approved Change Deliverables','Approved project scope changes'))
                            root_id=db.execute('SELECT last_insert_rowid()').fetchone()[0]
                        else:
                            root_id=root['id']
                        code=f'5.{cid}'
                        db.execute('''INSERT INTO work_packages(parent_id,requirement_id,code,name,description)
                                      VALUES (?,?,?,?,?)''',
                                   (root_id,requirement_id,code,change['title'],change['justification']))
                        wp_id=db.execute('SELECT last_insert_rowid()').fetchone()[0]
                        prev=query_one(db,'SELECT id FROM activities ORDER BY id DESC LIMIT 1')
                        # Zero-day changes create a parallel 1-day work item without extending
                        # the finish-to-start critical path; approved deadline stays unchanged.
                        new_days=max(1,change['schedule_impact'])
                        predecessor = prev['id'] if prev and change['schedule_impact'] else None
                        db.execute('''INSERT INTO activities(title,work_package_id,assignee_id,duration_days,
                                     start_offset_days,dependency_id,planned_cost,progress,delay_days,source_change_id)
                                     VALUES (?,?,1,?,0,?,?,0,0,?)''',
                                   (change['title'],wp_id,new_days,predecessor,change['cost_impact'],cid))
                        db.execute('UPDATE changes SET status=?,decided_on=?,linked_requirement_id=? WHERE id=?',
                                   ('Approved',date.today().isoformat(),requirement_id,cid))
                        # Shift release sign-off when the authorized deadline is extended.
                        if change['schedule_impact']:
                            late_miles=query_all(db,"SELECT id,due_date FROM milestones WHERE status='Pending' AND title LIKE '%release sign-off%'")
                            for milestone in late_miles:
                                shifted=parse_date(milestone['due_date'])+timedelta(days=change['schedule_impact'])
                                db.execute('UPDATE milestones SET due_date=? WHERE id=?',(shifted.isoformat(),milestone['id']))
                    db.execute('UPDATE projects SET approved_budget=?,approved_deadline=? WHERE id=1',
                               (budget,deadline))
                    msg=f'Change approved: +PKR {change["cost_impact"]:,.0f}; +{change["schedule_impact"]} calendar days. WBS and task added.'
            elif kind=='activity':
                wp=ident(form,'work_package_id','Work package');approved_package(db,wp)
                owner=ident(form,'assignee_id','Assignee');ensure_exists(db,'team',owner)
                dur=bounded_int(form.get('duration_days'),'Duration days',1,365)
                offset=bounded_int(form.get('start_offset_days'),'Start offset days',0,1000)
                cost=nonnegative_money(form.get('planned_cost'),'Activity cost')
                dep_raw=str(form.get('dependency_id','')).strip()
                dep=int(dep_raw) if dep_raw else None
                if dep:ensure_exists(db,'activities',dep)
                if str(form.get('task_id','')).strip():
                    task_id=ident(form,'task_id','Task');ensure_exists(db,'activities',task_id)
                    if task_id==dep:raise ValueError('A task cannot depend on itself.')
                    # Change-controlled tasks must retain their approved costs and durations.
                    rec=query_one(db,'SELECT * FROM activities WHERE id=?',(task_id,))
                    if rec['source_change_id'] is not None and (rec['planned_cost']!=cost or rec['duration_days']!=dur):
                        raise ValueError('Approved change cost/duration must match the approved request.')
                    db.execute('''UPDATE activities SET title=?,work_package_id=?,assignee_id=?,duration_days=?,
                                  start_offset_days=?,dependency_id=?,planned_cost=? WHERE id=?''',
                               (val(form,'title','Title'),wp,owner,dur,offset,dep,cost,task_id))
                else:
                    db.execute('''INSERT INTO activities(title,work_package_id,assignee_id,duration_days,
                                  start_offset_days,dependency_id,planned_cost,progress,delay_days)
                                  VALUES (?,?,?,?,?,?,?,0,0)''',
                               (val(form,'title','Title'),wp,owner,dur,offset,dep,cost))
                # Validate dependency graph before committing; transaction rolls back on failure.
                tasks=query_all(db,'SELECT * FROM activities ORDER BY id')
                schedule(tasks,project['kickoff'],False)
                msg='Activity and dependency schedule saved.'
            elif kind=='progress':
                task_id=ident(form,'task_id','Task');ensure_exists(db,'activities',task_id)
                progress=bounded_int(form.get('progress'),'Progress',0,100)
                delay=bounded_int(form.get('delay_days'),'Delay days',0,365)
                db.execute('UPDATE activities SET progress=?,delay_days=? WHERE id=?',(progress,delay,task_id))
                msg='Progress and delay saved; successor forecast recalculated.'
            elif kind=='expense':
                aid=ident(form,'activity_id','Activity');ensure_exists(db,'activities',aid)
                amount=nonnegative_money(form.get('amount'),'Expenditure')
                if amount==0:raise ValueError('Expenditure must exceed zero.')
                spent=val(form,'date','Expense date');parse_date(spent)
                db.execute('INSERT INTO expenses(activity_id,amount,date,description) VALUES (?,?,?,?)',
                           (aid,amount,spent,val(form,'description','Description')))
                msg='Actual project expenditure recorded.'
            elif kind=='as_of':
                d=val(form,'as_of_date','As-of date');parse_date(d)
                db.execute('UPDATE projects SET as_of_date=? WHERE id=1',(d,))
                msg='EVM reporting date updated.'
            elif kind=='defect':
                assignee=ident(form,'assignee_id','Assignee');ensure_exists(db,'team',assignee)
                raw=str(form.get('activity_id','')).strip()
                activity=int(raw) if raw else None
                if activity:ensure_exists(db,'activities',activity)
                fields=(val(form,'title','Defect title'),activity,
                        choice(form,'severity',('Critical','High','Medium','Low')),assignee,
                        choice(form,'status',('Open','In Progress','Resolved')),
                        str(form.get('details','')).strip())
                if str(form.get('record_id','')).strip():
                    did=ident(form,'record_id','Defect');ensure_exists(db,'defects',did)
                    db.execute('''UPDATE defects SET title=?,activity_id=?,severity=?,assignee_id=?,status=?,details=? WHERE id=?''',
                               fields+(did,))
                else:
                    db.execute('''INSERT INTO defects(title,activity_id,severity,assignee_id,status,details)
                                  VALUES (?,?,?,?,?,?)''',fields)
                msg='Defect recorded.'
            elif kind=='inspection':
                inspector=ident(form,'inspector_id','Inspector');ensure_exists(db,'team',inspector)
                day=val(form,'tested_on','Inspection date');parse_date(day)
                db.execute('''INSERT INTO inspections(deliverable,checklist,result,tested_on,inspector_id,notes)
                               VALUES (?,?,?,?,?,?)''',
                           (val(form,'deliverable','Deliverable'),val(form,'checklist','Checklist'),
                            choice(form,'result',('Pass','Fail','Pending')),day,inspector,
                            str(form.get('notes','')).strip()))
                msg='Quality inspection/test result recorded.'
            elif kind=='risk':
                owner=ident(form,'owner_id','Risk owner');ensure_exists(db,'team',owner)
                likelihood=bounded_int(form.get('likelihood'),'Likelihood',1,5)
                impact=bounded_int(form.get('impact'),'Impact',1,5)
                db.execute('''INSERT INTO risks(title,likelihood,impact,preventive_action,corrective_action,owner_id)
                               VALUES (?,?,?,?,?,?)''',
                           (val(form,'title','Risk title'),likelihood,impact,
                            val(form,'preventive_action','Preventive action'),
                            val(form,'corrective_action','Corrective action'),owner))
                msg=f'Risk scored {risk_score(likelihood,impact)}/25 and added to PDPC.'
            else:
                raise ValueError('Unknown action requested.')
        return route_to(tab,msg)
    except (ValueError, sqlite3.IntegrityError, OverflowError) as ex:
        return fail(ex)


@app.get('/health',response_class=PlainTextResponse)
def health():
    return 'ok'


if __name__=='__main__':
    import uvicorn, webbrowser, threading
    threading.Timer(1.5,lambda:webbrowser.open('http://127.0.0.1:8765')).start()
    uvicorn.run(app,host='127.0.0.1',port=8765)
