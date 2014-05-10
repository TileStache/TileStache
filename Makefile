VERSION:=$(shell cat TileStache/VERSION)
DOCROOT=tilestache.org:public_html/tilestache/www

live: doc
	rsync -Cr doc/ $(DOCROOT)/doc/
	python setup.py sdist upload

doc:
	mkdir doc

	python -m pydoc -w TileStache
	python -m pydoc -w TileStache.Core
	python -m pydoc -w TileStache.Caches
	python -m pydoc -w TileStache.Memcache
	python -m pydoc -w TileStache.Redis
	python -m pydoc -w TileStache.S3
	python -m pydoc -w TileStache.Config
	python -m pydoc -w TileStache.Vector
	python -m pydoc -w TileStache.Vector.Arc
	python -m pydoc -w TileStache.Geography
	python -m pydoc -w TileStache.Providers
	python -m pydoc -w TileStache.Mapnik
	python -m pydoc -w TileStache.MBTiles
	python -m pydoc -w TileStache.Sandwich
	python -m pydoc -w TileStache.Pixels
	python -m pydoc -w TileStache.Goodies
	python -m pydoc -w TileStache.Goodies.Caches
	python -m pydoc -w TileStache.Goodies.Caches.LimitedDisk
	python -m pydoc -w TileStache.Goodies.Caches.GoogleCloud
	python -m pydoc -w TileStache.Goodies.Providers
	python -m pydoc -w TileStache.Goodies.Providers.Composite
	python -m pydoc -w TileStache.Goodies.Providers.Cascadenik
	python -m pydoc -w TileStache.Goodies.Providers.PostGeoJSON
	python -m pydoc -w TileStache.Goodies.Providers.SolrGeoJSON
	python -m pydoc -w TileStache.Goodies.Providers.MapnikGrid
	python -m pydoc -w TileStache.Goodies.Providers.MirrorOSM
	python -m pydoc -w TileStache.Goodies.Providers.Monkeycache
	python -m pydoc -w TileStache.Goodies.Providers.UtfGridComposite
	python -m pydoc -w TileStache.Goodies.Providers.UtfGridCompositeOverlap
	python -m pydoc -w TileStache.Goodies.Providers.TileDataOSM
	python -m pydoc -w TileStache.Goodies.Providers.Grid
	python -m pydoc -w TileStache.Goodies.Providers.GDAL
	python -m pydoc -w TileStache.Goodies.AreaServer
	python -m pydoc -w TileStache.Goodies.StatusServer
	python -m pydoc -w TileStache.Goodies.Proj4Projection
	python -m pydoc -w TileStache.Goodies.ExternalConfigServer
	python -m pydoc -w TileStache.Goodies.VecTiles
	python -m pydoc -w TileStache.Goodies.VecTiles.server
	python -m pydoc -w TileStache.Goodies.VecTiles.client
	python -m pydoc -w TileStache.Goodies.VecTiles.geojson
	python -m pydoc -w TileStache.Goodies.VecTiles.topojson
	python -m pydoc -w TileStache.Goodies.VecTiles.mvt
	python -m pydoc -w TileStache.Goodies.VecTiles.wkb
	python -m pydoc -w TileStache.Goodies.VecTiles.ops

	python -m pydoc -w scripts/tilestache-*.py

	mv TileStache.html doc/
	mv TileStache.*.html doc/
	mv tilestache-*.html doc/
	
	perl -pi -e 's#<br><a href="file:/[^"]+">[^<]+</a>##' doc/*.html

	cp API.html doc/index.html
	perl -pi -e 's#http://tilestache.org/doc/##' doc/index.html
	perl -pi -e 's#\bN\.N\.N\b#$(VERSION)#' doc/index.html

clean:
	find TileStache -name '*.pyc' -delete
	rm -rf doc
