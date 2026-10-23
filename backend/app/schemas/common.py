from typing import Annotated

from pydantic import StringConstraints

# Whitespace is stripped before length checks, so "   " is rejected as empty.
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
