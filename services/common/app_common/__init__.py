"""Technical helpers shared by every service.

This package holds infrastructure concerns only (configuration, logging, error
schema, health probe and app factory). It must never contain business rules,
which belong to each service's ``domain/`` layer.
"""

__version__ = "0.1.0"
