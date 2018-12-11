from . import TokenGenerator


class Mixture(TokenGenerator):

    def __init__(self, **kwargs):
        kwargs['symbol'] = 'mx'
        kwargs['vocab'] = {"mixture"}
        super().__init__(**kwargs)
        

    def instantiate(self):
        return self.generate(unique=False)

    def __str__(self):
        return("Token for generating strings for entity type %s." % (self.symbol()))
