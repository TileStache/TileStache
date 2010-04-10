"""

<stack> 
	<layer src="road-names" /> 
	<layer src="road-inlines" /> 
	<layer src="road-outlines"> 
		<mask src="road-name-halos" /> 
	</layer> 
	<layer color="#ccc"/> 
</stack>
"""

class Stack:

    def __init__(self, layers):
        self.layers = layers

    def render(self):
        pass

class Layer:

    def __init__(self):
        pass

    def render(self):
        pass

class Composite:

    def __init__(self, stackfile):
        self.stackfile = stackfile

    def renderArea(self, width, height, srs, xmin, ymin, xmax, ymax):
        pass
