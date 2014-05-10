DOCROOT=tilestache.org:public_html/tilestache/www

live: doc
	rsync -Cr doc/ $(DOCROOT)/doc/
	python setup.py sdist upload

doc:
	mkdir doc

	pydoc -w TileStache
	pydoc -w TileStache.Core
	pydoc -w TileStache.Caches
	pydoc -w TileStache.Memcache
	pydoc -w TileStache.Redis
	pydoc -w TileStache.S3
	pydoc -w TileStache.Config
	pydoc -w TileStache.Vector
	pydoc -w TileStache.Vector.Arc
	pydoc -w TileStache.Geography
	pydoc -w TileStache.Providers
	pydoc -w TileStache.Mapnik
	pydoc -w TileStache.MBTiles
	pydoc -w TileStache.Sandwich
	pydoc -w TileStache.Pixels
	pydoc -w TileStache.Goodies
	pydoc -w TileStache.Goodies.Caches
	pydoc -w TileStache.Goodies.Caches.LimitedDisk
	pydoc -w TileStache.Goodies.Caches.GoogleCloud
	pydoc -w TileStache.Goodies.Providers
	pydoc -w TileStache.Goodies.Providers.Composite
	pydoc -w TileStache.Goodies.Providers.Cascadenik
	pydoc -w TileStache.Goodies.Providers.PostGeoJSON
	pydoc -w TileStache.Goodies.Providers.SolrGeoJSON
	pydoc -w TileStache.Goodies.Providers.MapnikGrid
	pydoc -w TileStache.Goodies.Providers.MirrorOSM
	pydoc -w TileStache.Goodies.Providers.Monkeycache
	pydoc -w TileStache.Goodies.Providers.UtfGridComposite
	pydoc -w TileStache.Goodies.Providers.UtfGridCompositeOverlap
	pydoc -w TileStache.Goodies.Providers.TileDataOSM
	pydoc -w TileStache.Goodies.Providers.Grid
	pydoc -w TileStache.Goodies.Providers.GDAL
	pydoc -w TileStache.Goodies.AreaServer
	pydoc -w TileStache.Goodies.StatusServer
	pydoc -w TileStache.Goodies.Proj4Projection
	pydoc -w TileStache.Goodies.ExternalConfigServer
	pydoc -w TileStache.Goodies.VecTiles
	pydoc -w TileStache.Goodies.VecTiles.server
	pydoc -w TileStache.Goodies.VecTiles.client
	pydoc -w TileStache.Goodies.VecTiles.geojson
	pydoc -w TileStache.Goodies.VecTiles.topojson
	pydoc -w TileStache.Goodies.VecTiles.mvt
	pydoc -w TileStache.Goodies.VecTiles.wkb
	pydoc -w TileStache.Goodies.VecTiles.ops

	pydoc -w scripts/tilestache-*.py

	mv TileStache.html doc/
	mv TileStache.*.html doc/
	mv tilestache-*.html doc/
	
	perl -pi -e 's#<br><a href="file:/[^"]+">[^<]+</a>##' doc/*.html

	cp API.html doc/index.html
	perl -pi -e 's#http://tilestache.org/doc/##' doc/index.html
	perl -pi -e 's#\bN\.N\.N\b#$(TileStache/VERSION)#' doc/index.html

clean:
	find TileStache -name '*.pyc' -delete
	rm -rf doc
