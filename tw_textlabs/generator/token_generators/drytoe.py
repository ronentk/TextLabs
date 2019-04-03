from . import TokenGenerator


class Drytoe(TokenGenerator):

    def __init__(self, **kwargs):
        kwargs['symbol'] = 'drytoe'
        kwargs['vocab'] = {"dry", "dry out", "heat"}
        super().__init__(**kwargs)
        self.unique = False


    def instantiate(self):
        return self.generate()

    def __str__(self):
        return("Token for generating strings for entity type %s." % (self.symbol()))
