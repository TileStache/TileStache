VERSION=0.1.3
PACKAGE=TileStache-$(VERSION)
TARBALL=$(PACKAGE).tar.gz

all: $(TARBALL)
	#

$(TARBALL): $(PACKAGE)
	tar -czvf $(TARBALL) $(PACKAGE)

$(PACKAGE): doc
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

	mkdir $(PACKAGE)/examples
	ln examples/*.py $(PACKAGE)/examples/

	mkdir $(PACKAGE)/doc
	ln doc/*.html $(PACKAGE)/doc/

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

	mv TileStache.html doc/
	mv TileStache.*.html doc/

clean:
	rm -rf $(PACKAGE) $(TARBALL) doc
