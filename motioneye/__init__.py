VERSION = "0.43.1b49"

# Ensure UI extensions (additional sections/configs) are registered at import time
# Importing here guarantees sections are available even if server imports change
from motioneye.controls import wifictl  # noqa: F401
from motioneye.controls import ledctl   # noqa: F401
from motioneye import config as _config

# Rebuild additional config cache after registering controls
_config.invalidate()
