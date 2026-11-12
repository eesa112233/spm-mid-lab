"""Integration cases run against a temporary isolated SQLite database."""
from datetime import date
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import database
from core import schedule, earned_value, risk_score, revised_baselines, bounded_int
from app import app, full_context


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(database,'DB_PATH',tmp_path/'isolated.sqlite3')
    database.initialize()
    return TestClient(app)


def count(table):
    with database.connect() as db:
        return db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]


def project():
    with database.connect() as db:
        return dict(db.execute('SELECT * FROM projects WHERE id=1').fetchone())


def test_TC01_all_seven_gui_views_render(client):
    for tab in ['dashboard','initiation','scope','schedule','cost','quality','report']:
        response=client.get('/',params={'tab':tab})
        assert response.status_code==200
        assert '<main class="main">' in response.text


def test_TC02_seed_project_charter_and_team(client):
    p=project()
    assert p['baseline_budget']==5000000
    assert p['approved_budget']==5000000
    assert p['original_deadline']=='2026-11-23'
    assert len([*database.connect().execute('SELECT id FROM team')])==7
    assert count('stakeholders')>=4


def test_TC03_baseline_schedule_16_weeks_and_delay_propagates(client):
    c=full_context('schedule')
    assert c['base_finish']==date(2026,11,23)
    assert c['finish']==date(2026,11,28)
    assert c['finish_slip']==5
    assert all(x['slip']==5 for x in c['activity_rows'][4:])


def test_TC04_evm_programmatic_values(client):
    c=full_context('cost')
    assert c['evm']['pv']==4100000
    assert c['evm']['ev']==3760000
    assert c['evm']['ac']==3930000
    assert c['evm']['cpi']==.957
    assert c['evm']['spi']==.917
    assert c['total_cost']==5000000


def test_TC05_pending_change_does_not_modify_baseline(client):
    p=project()
    assert p['approved_budget']==5000000
    assert p['approved_deadline']=='2026-11-23'
    assert count('requirements')==6
    assert count('activities')==8
    assert count('changes')==1


def test_TC06_approve_ai_mobile_change_integrates_all_modules(client):
    result=client.post('/action/change_decide',data={'change_id':1,'decision':'Approved'},follow_redirects=False)
    assert result.status_code==303
    p=project()
    assert p['approved_budget']==5800000
    assert p['approved_deadline']=='2026-12-14'
    assert count('requirements')==7
    assert count('activities')==9
    assert count('work_packages')==14
    c=full_context('dashboard')
    assert c['total_cost']==5800000
    assert c['finish']==date(2026,12,19) # observed 5-day delay still propagates
    with database.connect() as db:
        r=db.execute('SELECT status,linked_requirement_id FROM changes WHERE id=1').fetchone()
        assert r['status']=='Approved' and r['linked_requirement_id']
        assert db.execute('SELECT COUNT(*) FROM activities WHERE source_change_id=1').fetchone()[0]==1
        assert db.execute("SELECT due_date FROM milestones WHERE title LIKE '%release sign-off%'").fetchone()[0]=='2026-12-14'


def test_TC07_double_change_approval_is_blocked(client):
    client.post('/action/change_decide',data={'change_id':1,'decision':'Approved'})
    repeat=client.post('/action/change_decide',data={'change_id':1,'decision':'Approved'})
    assert repeat.status_code==400
    assert count('activities')==9
    assert project()['approved_budget']==5800000


def test_TC08_rejected_change_preserves_budget_schedule_scope(client):
    r=client.post('/action/change_decide',data={'change_id':1,'decision':'Rejected'})
    assert r.status_code==200
    assert project()['approved_budget']==5000000
    assert project()['approved_deadline']=='2026-11-23'
    assert count('activities')==8
    assert count('requirements')==6


def test_TC09_unapproved_requirements_cannot_join_wbs(client):
    resp=client.post('/action/requirement',data={'mode':'add','title':'Unapproved prototype','priority':'High','status':'Proposed','description':'Not authorized'})
    assert resp.status_code==200
    assert count('requirements')==7
    resp=client.post('/action/work_package',data={'requirement_id':7,'code':'7','name':'Unapproved scope'})
    assert resp.status_code==400
    assert count('work_packages')==12


def test_TC10_negative_expense_rejected(client):
    previous=count('expenses')
    resp=client.post('/action/expense',data={'activity_id':2,'amount':-5,'date':'2026-10-26','description':'Invalid cost'})
    assert resp.status_code==400
    assert count('expenses')==previous


def test_TC11_spending_changes_actual_cost_and_cpi(client):
    r=client.post('/action/expense',data={'activity_id':6,'amount':70000,'date':'2026-10-26','description':'Additional API testing'})
    assert r.status_code==200
    evm=full_context('cost')['evm']
    assert evm['ac']==4000000
    assert evm['cpi']==.94
    assert any('Cost performance below threshold' in w for w in full_context('dashboard')['warnings'])


def test_TC12_update_progress_updates_earned_value(client):
    before=full_context('cost')['evm']['ev']
    resp=client.post('/action/progress',data={'task_id':6,'progress':80,'delay_days':0})
    assert resp.status_code==200
    assert full_context('cost')['evm']['ev']==before+170000


def test_TC13_dependency_cycle_detected_and_rolled_back(client):
    # T1 <- T8 while the chain T8 -> ... -> T1 already exists.
    data={'task_id':1,'title':'Requirements & charter','work_package_id':2,'assignee_id':1,
          'duration_days':14,'start_offset_days':0,'dependency_id':8,'planned_cost':300000}
    resp=client.post('/action/activity',data=data)
    assert resp.status_code==400
    with database.connect() as db:
        assert db.execute('SELECT dependency_id FROM activities WHERE id=1').fetchone()[0] is None


def test_TC14_quality_defect_resolution_updates_dashboard(client):
    data={'record_id':1,'title':'Double-booking when doctors change slots','activity_id':5,'severity':'Critical',
          'assignee_id':2,'status':'Resolved','details':'Fixed and retested'}
    result=client.post('/action/defect',data=data)
    assert result.status_code==200
    assert full_context('dashboard')['critical_open']==1


def test_TC15_risk_matrix_scores_sorted_and_pdpc_present(client):
    assert risk_score(4,5)==20
    c=full_context('quality')
    assert c['risks'][0]['score']>=c['risks'][-1]['score']
    assert all(r['preventive_action'] and r['corrective_action'] for r in c['risks'])


def test_TC16_project_closure_persist_and_block_edit(client):
    assert client.post('/action/closure',data={'status':'Closed','closure_notes':'Acceptance complete'}).status_code==200
    assert project()['status']=='Closed' and project()['closed_at'] is not None
    assert client.post('/action/expense',data={'activity_id':1,'amount':100,'date':'2026-10-26','description':'Locked'}).status_code==400
    assert client.post('/action/closure',data={'status':'Active','closure_notes':'Reopened'}).status_code==200
    assert project()['status']=='Active'


def test_TC17_add_quality_inspection_and_milestone(client):
    n=count('inspections')
    r=client.post('/action/inspection',data={'deliverable':'Video consultation','checklist':'Audio/video and access checks',
          'result':'Pass','tested_on':'2026-10-26','inspector_id':7,'notes':'Verified'})
    assert r.status_code==200 and count('inspections')==n+1
    m=count('milestones')
    r=client.post('/action/milestone',data={'title':'Stakeholder demo','due_date':'2026-11-01','responsible_id':1,'status':'Pending'})
    assert r.status_code==200 and count('milestones')==m+1


def test_TC18_missing_dependency_and_invalid_risk_bounds(client):
    tasks=[{'id':1,'duration_days':3,'dependency_id':9,'start_offset_days':0}]
    with pytest.raises(ValueError,match='Missing dependency'):
        schedule(tasks,'2026-01-01')
    with pytest.raises(ValueError,match='between 1 and 5'):
        risk_score(0,5)


def test_TC19_approved_cost_only_change_does_not_extend_schedule(client):
    r=client.post('/action/change',data={'title':'Additional audit licenses','justification':'Compliance requirement',
                   'cost_impact':'100000','schedule_impact':'0','priority':'High'})
    assert r.status_code==200
    assert client.post('/action/change_decide',data={'change_id':2,'decision':'Approved'}).status_code==200
    assert project()['approved_budget']==5100000
    assert project()['approved_deadline']=='2026-11-23'
    assert full_context('schedule')['finish']==date(2026,11,28)


def test_TC20_invalid_new_activity_wbs_gate(client):
    before=count('activities')
    r=client.post('/action/activity',data={'title':'Attempt','work_package_id':99,'assignee_id':1,'duration_days':4,
                'start_offset_days':0,'dependency_id':'','planned_cost':100})
    assert r.status_code==400 and count('activities')==before
