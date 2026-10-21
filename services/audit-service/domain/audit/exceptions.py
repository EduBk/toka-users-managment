"""Errors raised while building audit entries."""


class InvalidEventType(ValueError):
    pass


class InvalidActorId(ValueError):
    pass


class InvalidEventPayload(ValueError):
    pass


class InvalidAuditEntry(ValueError):
    pass
