"""Expected errors raised while executing user use cases."""


class UserNotFound(Exception):
    """No user exists with the requested id."""
