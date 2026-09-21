"""R2 numerical-preflight execution tooling.

This package contains source-only adapters and evaluators.  Importing it never
imports a historical solver and never creates an execution-output directory.
"""

from .execution_guard import ExecutionAuthorizationError, require_single_execution_authorization

__all__ = ["ExecutionAuthorizationError", "require_single_execution_authorization"]
