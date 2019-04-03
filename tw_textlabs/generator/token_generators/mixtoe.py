from . import TokenGenerator


class Mixtoe(TokenGenerator):

    def __init__(self, **kwargs):
        kwargs['symbol'] = 'mixtoe'
        kwargs['vocab'] = {"mix", "add", "stir"}
        super().__init__(**kwargs)
        self.unique = False


    def instantiate(self):
        return self.generate()

    def __str__(self):
        return("Token for generating strings for entity type %s." % (self.symbol()))
