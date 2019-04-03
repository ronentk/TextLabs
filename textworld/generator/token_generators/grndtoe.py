from . import TokenGenerator


class Grndtoe(TokenGenerator):

    def __init__(self, **kwargs):
        kwargs['symbol'] = 'grndtoe'
        kwargs['vocab'] = {"grind", "mill", "finely grind"}
        super().__init__(**kwargs)
        self.unique = False


    def instantiate(self):
        return self.generate()

    def __str__(self):
        return("Token for generating strings for entity type %s." % (self.symbol()))
