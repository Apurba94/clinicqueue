"""Start the app: python -m clinicqueue [data.db] [--port 8045]"""
import sys

from .fieldkit import main_cli
from .web import create_app

sys.exit(main_cli(create_app, "clinic.db", 8045, sys.argv))
