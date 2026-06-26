"""
Cached wrapper around the course-provided common.Fluid_CP_moist_air module.
Changes NO numerical output -- only avoids redundant CoolProp calls.

Root cause (found by profiling one simulate_season() call -- 289 timesteps,
278.8s total): Fluid_CP_moist_air.state() recomputes three CoolProp
reference-state lookups (h0, s0, u0 at the fixed triple point T0/p0) on
EVERY call, purely to offset the returned enthalpy/entropy to that
reference. These three values depend only on `fluid`, never on the actual
query, so for any fixed fluid they are the same every time. state_moist()
compounds this: it ALSO recomputes two more such reference calls (h_a0,
h_w0) on every call of its own, on top of calling state() repeatedly inside.
Result: 31,927 calls to state() for one simulated day, consuming 258 of the
278.8 total seconds (93%) -- almost entirely this redundant recomputation,
not the "real" property lookups simulate_season actually needs.

The original Fluid_CP_moist_air.py is left untouched on disk. This module
monkey-patches its internal `state` name at import time, so state_moist()'s
OWN internal calls (which resolve the bare name `state` in that module's
global namespace, not this one -- this is where most of the 31,927 calls
actually originate) are cached too, not just calls made through this
wrapper's re-exported `state`.
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
