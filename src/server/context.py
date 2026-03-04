from contextvars import ContextVar

current_user_id: ContextVar[str | None] = ContextVar("current_user_id", default=None)
current_role: ContextVar[str | None] = ContextVar("current_role", default=None)
