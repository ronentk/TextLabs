from . import TokenGenerator


class Material(TokenGenerator):

    def __init__(self, **kwargs):
        kwargs['symbol'] = 'm'
        kwargs['vocab'] = {"Mn","Fe", "Ni", "Ge"}
        super().__init__(**kwargs)
        

    def instantiate(self):
        return self.generate(unique=False)

    def __str__(self):
        return("Token for generating strings for entity type %s." % (self.symbol()))
