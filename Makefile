VERSION=0.1.10
PACKAGE=TileStache-$(VERSION)
TARBALL=$(PACKAGE).tar.gz
DOCROOT=tilestache.org:public_html/tilestache/www

all: $(TARBALL)
	#

live: $(TARBALL) doc
	scp $(TARBALL) $(DOCROOT)/download/
	rsync -Cr doc/ $(DOCROOT)/doc/
	python setup.py register

$(TARBALL): doc
	mkdir $(PACKAGE)
	ln setup.py $(PACKAGE)/
	ln README $(PACKAGE)/
	ln tilestache.cfg $(PACKAGE)/
	ln tilestache.cgi $(PACKAGE)/

	mkdir $(PACKAGE)/TileStache
	ln TileStache/*.py $(PACKAGE)/TileStache/

	mkdir $(PACKAGE)/TileStache/Goodies
	ln TileStache/Goodies/*.py $(PACKAGE)/TileStache/Goodies/

	mkdir $(PACKAGE)/TileStache/Goodies/Providers
	ln TileStache/Goodies/Providers/*.py $(PACKAGE)/TileStache/Goodies/Providers/
	ln TileStache/Goodies/Providers/*.ttf $(PACKAGE)/TileStache/Goodies/Providers/

	mkdir $(PACKAGE)/scripts
	ln scripts/*.py $(PACKAGE)/scripts/

	mkdir $(PACKAGE)/examples
	ln examples/*.py $(PACKAGE)/examples/

	mkdir $(PACKAGE)/doc
	ln doc/*.html $(PACKAGE)/doc/

	tar -czf $(TARBALL) $(PACKAGE)
	rm -rf $(PACKAGE)

doc:
	mkdir doc

	pydoc -w TileStache
	pydoc -w TileStache.Core
	pydoc -w TileStache.Caches
	pydoc -w TileStache.Config
	pydoc -w TileStache.Geography
	pydoc -w TileStache.Providers
	pydoc -w TileStache.Goodies
	pydoc -w TileStache.Goodies.Providers
	pydoc -w TileStache.Goodies.Providers.Composite
	pydoc -w TileStache.Goodies.Providers.Grid
	
	pydoc -w scripts/tilestache-*.py

	mv TileStache.html doc/
	mv TileStache.*.html doc/
	mv tilestache-*.html doc/

clean:
	rm -rf $(TARBALL) doc
