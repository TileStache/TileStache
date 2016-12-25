Installation
============
TileStache can be run from the download directory as is. For example the scripts:

    tilestache-render.py tilestache-seed.py tilestache-server.py

Can all be run locally like:

    ./scripts/tilestache-server.py

Install of TileStache and requirements via pip
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

::

    # The following 2 lines may or may not be necessary depending on your system:
    export CPLUS_INCLUDE_PATH=/usr/include/gdal
    export C_INCLUDE_PATH=/usr/include/gdal

    pip install -r requirements.txt
    pip install -r requirements-dev.txt
    pip install -e .
