import mapnik
import PIL.Image

class Mapnik:

    def __init__(self, layer):
        self.layer = layer

    def renderEnvelope(self, width, height, srs, xmin, ymin, xmax, ymax):
        
        m = mapnik.Map(width, height, srs)
        
        m.background = mapnik.Color('black')
        
        s = mapnik.Style()
        r = mapnik.Rule()
        r.symbols.append(mapnik.PolygonSymbolizer(mapnik.Color('white')))
        s.rules.append(r)

        m.append_style('coastline', s)
        l = mapnik.Layer('coastline', m.srs)
        l.datasource = mapnik.PostGIS(dbname='planet_osm', host='localhost', user='osm', table='coastline')
        l.styles.append('coastline')
        m.layers.append(l)

        m.zoom_to_box(mapnik.Envelope(xmin, ymin, xmax, ymax))
        
        i = mapnik.Image(width, height)
        mapnik.render(m, i)
        
        img = PIL.Image.fromstring('RGBA', (width, height), i.tostring())
        
        return img
