"""`python -m cadgen.cli.step_inspect` — the same entry every sibling verb
module has via its `if __name__ == "__main__"` guard; step_inspect is a
package, so the shim lives here."""

import sys

from cadgen.cli.step_inspect.cli import main

if __name__ == "__main__":
    sys.exit(main())
