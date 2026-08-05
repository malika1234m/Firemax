"""Process-level runtime facts for the platform health console."""
import time

# Set once when the module is first imported at app startup — close enough to
# process start for an uptime readout.
START_TIME = time.time()


def uptime_seconds() -> int:
    return int(time.time() - START_TIME)
