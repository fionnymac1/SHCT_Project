"""
Cached wrapper around the course-provided common.Fluid_CP_moist_air module.
Changes no numerical output -- only avoids redundant CoolProp calls.

Root cause (profiled at 278.8s for one simulated day): state() recomputes
three CoolProp reference-state lookups on every call, purely to offset the
returned enthalpy/entropy -- these depend only on `fluid`, never the actual
query, so they're identical every time for a fixed fluid. 93% of runtime was
this redundant recomputation (31,927 calls), not the real property lookups.

The original Fluid_CP_moist_air.py is left untouched on disk; this module
monkey-patches its internal `state` name at import time, so state_moist()'s
own internal calls (which resolve `state` in that module's namespace, not
this one) are cached too, not just calls made through this wrapper directly.
"""
from functools import lru_cache
from common import Fluid_CP_moist_air as _orig

_uncached_state = _orig.state


@lru_cache(maxsize=4096)
def _cached_state(Var, In, fluid, Eh):
    return _uncached_state(Var, In, fluid, Eh)


def state(Var, In, fluid, Eh="CBar"):
    """Same signature/behaviour as Fluid_CP_moist_air.state, memoized on
    (Var, In, fluid, Eh). Returns a copy so callers can't corrupt the cache
    by mutating the Series they get back in place."""
    return _cached_state(tuple(Var), tuple(In), fluid, Eh).copy()


# state_moist() calls the bare name `state` (resolved in Fluid_CP_moist_air's
# own module namespace at call time) -- patch it there so those internal
# calls hit the cache too.
_orig.state = state

state_moist = _orig.state_moist
get_fluid_info = _orig.get_fluid_info
