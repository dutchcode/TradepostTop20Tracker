import sys
import os
from pathlib import Path

def add_vendor_to_path():
    vendor_dir = Path(__file__).resolve().parent.parent.parent / 'vendor'
    if vendor_dir.exists() and str(vendor_dir) not in sys.path:
        sys.path.insert(0, str(vendor_dir))