from uuid import uuid4

from domain.role.assignment import UserRoleAssignment
from domain.role.events import RoleAssigned, RoleRevoked


def test_create_emits_role_assigned() -> None:
    user_id = uuid4()
    role_id = uuid4()

    assignment = UserRoleAssignment.create(user_id=user_id, role_id=role_id)

    events = assignment.pull_events()
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, RoleAssigned)
    assert event.payload() == {
        "user_id": str(user_id),
        "role_id": str(role_id),
    }


def test_revoke_emits_role_revoked() -> None:
    user_id = uuid4()
    role_id = uuid4()
    assignment = UserRoleAssignment.create(user_id=user_id, role_id=role_id)
    assignment.pull_events()

    assignment.revoke()

    events = assignment.pull_events()
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, RoleRevoked)
    assert event.payload() == {
        "user_id": str(user_id),
        "role_id": str(role_id),
    }
