#!/bin/bash -e

if [ -f ~/.bootstrap_complete ]; then
    exit 0
fi

set -x

whoami
sudo apt-get -q update
sudo apt-get -q install python-software-properties
sudo add-apt-repository ppa:mapnik/nightly-2.3 -y
sudo apt-get -q update
sudo apt-get -q install libmapnik-dev mapnik-utils python-mapnik virtualenvwrapper python-dev -y
sudo apt-get -q install gdal-bin libgdal-dev -y

# needed to build gdal bindings separately
sudo apt-get install build-essential -y

# create a python virtualenv
virtualenv -q ~/.virtualenvs/tilestache
source ~/.virtualenvs/tilestache/bin/activate

# make sure it gets activated the next time we log in
echo "source ~/.virtualenvs/tilestache/bin/activate" >> ~/.bashrc

# add system mapnik to virtualenv
ln -s /usr/lib/pymodules/python2.7/mapnik ~/.virtualenvs/tilestache/lib/python2.7/site-packages/mapnik

# for tests
sudo apt-get -q install postgresql-9.3-postgis-2.1 memcached -y
~/.virtualenvs/tilestache/bin/pip install nose coverage python-memcached psycopg2 werkzeug
~/.virtualenvs/tilestache/bin/pip install pil --allow-external pil --allow-unverified pil

# install basic TileStache requirements
cd /srv/tilestache/
~/.virtualenvs/tilestache/bin/pip install -r requirements.txt --allow-external ModestMaps --allow-unverified ModestMaps

# workaround for gdal bindings
~/.virtualenvs/tilestache/bin/pip install --no-install GDAL
cd ~/.virtualenvs/tilestache/build/GDAL
~/.virtualenvs/tilestache/bin/python setup.py build_ext --include-dirs=/usr/include/gdal/
~/.virtualenvs/tilestache/bin/pip install --no-download GDAL

# allow any user to connect as postgres to this test data. DO NOT USE IN PRODUCTION
sudo sed -i '1i local  test_tilestache  postgres                     trust' /etc/postgresql/9.3/main/pg_hba.conf

sudo /etc/init.d/postgresql restart

# add some test data
sudo -u postgres psql -c "drop database if exists test_tilestache"
sudo -u postgres psql -c "create database test_tilestache"
sudo -u postgres psql -c "create extension postgis" -d test_tilestache
sudo -u postgres ogr2ogr -nlt MULTIPOLYGON -f "PostgreSQL" PG:"user=postgres dbname=test_tilestache" ./examples/sample_data/world_merc.shp

set +x
echo "
****************************************************************
* Warning: your postgres security settings (pg_hba.conf)
* are not setup for production (i.e. have been set insecurely).
****************************************************************"

# we did it. let's mark the script as complete
touch ~/.bootstrap_complete
