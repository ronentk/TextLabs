from . import TokenGenerator


class Furnace(TokenGenerator):

    def __init__(self, **kwargs):
        kwargs['symbol'] = 'fd'
        kwargs['vocab'] = {"furnace device"}
        super().__init__(**kwargs)
        

    def instantiate(self):
        return self.generate(unique=False)

    def __str__(self):
        return("Token for generating strings for entity type %s." % (self.symbol()))
