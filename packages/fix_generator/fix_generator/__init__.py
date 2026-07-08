"""Fix_Generator subsystem — turns an Issue into at most one SuggestedFix.

A pure transformation that never writes to the database. Depends only on
Core_Package.
"""

from fix_generator.generator import FixGenerator

__all__ = ["FixGenerator"]
