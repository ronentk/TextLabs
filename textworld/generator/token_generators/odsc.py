from . import TokenGenerator


class Odsc(TokenGenerator):

    def __init__(self, **kwargs):
        kwargs['symbol'] = 'odsc'
        kwargs['vocab'] = {"opdesc1", "opdesc2", "opdesc3", "opdesc4",
        "opdesc5", "opdesc6", "opdesc7", "opdesc8",
        "opdesc9", "opdesc10", "opdesc11", "opdesc12"}
        super().__init__(**kwargs)
        self.unique = True

    def instantiate(self):
        return self.generate(unique=False)

    def __str__(self):
        return("Token for generating strings for entity type %s." % (self.symbol()))
