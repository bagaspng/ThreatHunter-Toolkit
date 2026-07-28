import sys
import os

# Menambahkan folder 'src' ke dalam system path agar modul proxyforge terbaca
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from proxyforge.cli.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
