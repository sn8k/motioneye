VERSION = "0.43.1b48"

# Ensure UI extensions (additional sections/configs) are registered at import time
# Importing here guarantees sections are available even if server imports change
from motioneye.controls import wifictl  # noqa: F401
from motioneye.controls import ledctl   # noqa: F401
