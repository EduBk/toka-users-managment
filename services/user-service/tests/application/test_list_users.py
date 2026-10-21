from application.dto import CreateUserCommand, ListUsersQuery
from application.use_cases.create_user import CreateUser
from application.use_cases.list_users import ListUsers
from tests.application.fakes import FakeUnitOfWork, FakeUserCache


async def _seed(uow: FakeUnitOfWork, count: int) -> None:
    use_case = CreateUser(lambda: uow, FakeUserCache())
    for index in range(count):
        await use_case.execute(
            CreateUserCommand(
                email=f"user{index}@example.com",
                name=f"User {index}",
                profile={},
                correlation_id="req-1234",
            )
        )


async def test_list_users_returns_a_page_and_the_total() -> None:
    uow = FakeUnitOfWork()
    await _seed(uow, 3)

    first_page = await ListUsers(lambda: uow, FakeUserCache()).execute(
        ListUsersQuery(page=1, page_size=2)
    )
    second_page = await ListUsers(lambda: uow, FakeUserCache()).execute(
        ListUsersQuery(page=2, page_size=2)
    )

    assert first_page.total == 3
    assert first_page.page == 1
    assert first_page.page_size == 2
    assert len(first_page.items) == 2
    assert len(second_page.items) == 1
    assert {user.id for user in first_page.items}.isdisjoint(
        {user.id for user in second_page.items}
    )


async def test_list_users_returns_an_empty_page_when_there_are_no_users() -> None:
    uow = FakeUnitOfWork()

    result = await ListUsers(lambda: uow, FakeUserCache()).execute(
        ListUsersQuery(page=1, page_size=20)
    )

    assert result.items == []
    assert result.total == 0


async def test_list_users_serves_the_second_read_from_cache() -> None:
    uow = FakeUnitOfWork()
    await _seed(uow, 3)
    cache = FakeUserCache()
    use_case = ListUsers(lambda: uow, cache)

    first = await use_case.execute(ListUsersQuery(page=1, page_size=20))
    uow.users.users.clear()
    second = await use_case.execute(ListUsersQuery(page=1, page_size=20))

    assert second.total == first.total == 3
    assert [user.id for user in second.items] == [
        user.id for user in first.items
    ]
    assert cache.writes == 1
