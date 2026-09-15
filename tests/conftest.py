import os
from forecaster.config import load_config, DEFAULT_CONFIG_PATH
import pytest

os.environ["FORECASTER_CONFIG"] = str(DEFAULT_CONFIG_PATH)
