"""Infrastructure layer: adapters that implement the application ports
(SQLAlchemy, Alembic, Redis, RabbitMQ, HTTP clients).

It may import ``application/`` and ``domain/``; it must never import ``api/``.
"""
