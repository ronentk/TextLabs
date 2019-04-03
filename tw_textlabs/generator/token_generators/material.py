from . import TokenGenerator


class Material(TokenGenerator):

    def __init__(self, **kwargs):
        kwargs['symbol'] = 'm'
        kwargs['vocab'] = {"mn","fe", "ni", "ge", "na", "mg"}
        super().__init__(**kwargs)
        self.unique = True
        

    def instantiate(self):
        return self.generate(unique=True)

    def __str__(self):
        return("Token for generating strings for entity type %s." % (self.symbol()))
