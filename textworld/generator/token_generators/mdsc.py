from . import TokenGenerator


class Mdsc(TokenGenerator):

    def __init__(self, **kwargs):
        kwargs['symbol'] = 'mdsc'
        kwargs['vocab'] = {"matdesc1", "matdesc2", "matdesc3", "matdesc4",
        "matdesc5", "matdesc6", "matdesc7", "matdesc8",
        "matdesc9", "matdesc10", "matdesc11", "matdesc12"}
        super().__init__(**kwargs)
        self.unique = True

    def instantiate(self):
        return self.generate(unique=False)

    def __str__(self):
        return("Token for generating strings for entity type %s." % (self.symbol()))
