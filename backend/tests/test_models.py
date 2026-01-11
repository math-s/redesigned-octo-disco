from app.models import ActionType, GoalStatus


def test_action_type_from_any():
    assert ActionType.from_any("bjj") == ActionType.BJJ
    assert ActionType.from_any("pilates") == ActionType.PILATES
    assert ActionType.from_any(" READ ") == ActionType.READ
    assert ActionType.from_any("save") == ActionType.SAVE
    assert ActionType.from_any("") is None
    assert ActionType.from_any(None) is None
    assert ActionType.from_any("nope") is None


def test_goal_status_from_any():
    assert GoalStatus.from_any("TODO") == GoalStatus.TODO
    assert GoalStatus.from_any(" doing ") == GoalStatus.DOING
    assert GoalStatus.from_any("done") == GoalStatus.DONE
    assert GoalStatus.from_any("") is None
    assert GoalStatus.from_any(None) is None
    assert GoalStatus.from_any("nope") is None

