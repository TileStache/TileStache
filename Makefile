VERSION=0.1.2
PACKAGE=TileStache-$(VERSION)
TARBALL=$(PACKAGE).tar.gz

all: $(TARBALL)
	#

$(TARBALL): $(PACKAGE)
	tar -czvf $(TARBALL) $(PACKAGE)

$(PACKAGE):
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

clean:
	rm -rf $(PACKAGE) $(TARBALL)