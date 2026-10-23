import pytest
from backend.teams import team_for, annotate


@pytest.mark.parametrize('name,team', [('가상연구원','AI'),('Example Developer','AI'),('가상 개발자','AI'),('가상팀원가','SW'),('가상팀원나','SW'),('가상팀원다','SW'),('가상팀원라','SW'),('가상팀원마','SW'),('가상팀원마2','unassigned'),('', 'unassigned'),(None,'unassigned')])
def test_roster_exact_match(name,team):
    assert team_for(name) == team


def test_meetings_are_not_assigned_by_attendee_name():
    event = {'kind': 'meeting', 'person': '가상연구원'}
    assert 'team' not in annotate(event)


def test_annotation_does_not_mutate_source_or_identity():
    original = {'id':'keep-id','kind':'leave','person':'가상팀원가'}
    result = annotate(original)
    assert result['team'] == 'SW'
    assert result['id'] == 'keep-id'
    assert 'team' not in original


@pytest.mark.parametrize('source_type,leave_type', [('pdf','연차'),('ecount','반차')])
def test_unspecified_half_day_has_provisional_display_only(source_type, leave_type):
    original = dict(id='stable', kind='leave', person='가상팀원다', amount=0.5,
                    leaveType=leave_type, title=f'가상팀원다 · {leave_type}', sourceType=source_type)
    result = annotate(original)
    assert result['displayLeaveType'] == '오전반차'
    assert result['timeSlotNote'] == '시간대 미명시 · 오전으로 임시 표시'
    assert all(result[key] == value for key, value in original.items())
    assert 'displayLeaveType' not in original


@pytest.mark.parametrize('leave_type,amount', [('오전반차',0.5),('오후반차',0.5),('연차',1)])
def test_confirmed_slots_and_full_days_are_not_assumed(leave_type, amount):
    result = annotate(dict(kind='leave', person='가상팀원다', leaveType=leave_type, amount=amount))
    assert 'timeSlotNote' not in result
    assert 'displayLeaveType' not in result
