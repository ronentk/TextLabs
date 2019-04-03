from . import TokenGenerator


class Mixture(TokenGenerator):

    def __init__(self, **kwargs):
        kwargs['symbol'] = 'mx'
        kwargs['vocab'] = {"mixture1", "mixture2", "mixture3", "mixture4",
        "mixture5", "mixture6", "mixture7", "mixture8",
        "mixture9", "mixture10", "mixture11", "mixture12"}
        super().__init__(**kwargs)
        self.unique = True


    def instantiate(self):
        return self.generate(unique=False)

    def __str__(self):
        return("Token for generating strings for entity type %s." % (self.symbol()))
