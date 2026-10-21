"""List users with offset pagination, caching each page."""

from application.dto import ListUsersQuery, UserPage
from application.ports.unit_of_work import UnitOfWorkFactory
from application.ports.user_cache import UserCache


class ListUsers:
    def __init__(
        self, unit_of_work: UnitOfWorkFactory, cache: UserCache
    ) -> None:
        self._unit_of_work = unit_of_work
        self._cache = cache

    async def execute(self, query: ListUsersQuery) -> UserPage:
        cached = await self._cache.get_page(
            page=query.page, page_size=query.page_size
        )
        if cached is not None:
            return cached

        async with self._unit_of_work() as uow:
            items, total = await uow.users.list(
                page=query.page, page_size=query.page_size
            )
        page = UserPage(
            items=items,
            total=total,
            page=query.page,
            page_size=query.page_size,
        )
        await self._cache.set_page(page)
        return page
