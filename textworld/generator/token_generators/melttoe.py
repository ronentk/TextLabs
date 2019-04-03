from . import TokenGenerator


class Melttoe(TokenGenerator):

    def __init__(self, **kwargs):
        kwargs['symbol'] = 'melttoe'
        kwargs['vocab'] = {"melt", "arc-melt"}
        super().__init__(**kwargs)
        self.unique = False


    def instantiate(self):
        return self.generate()

    def __str__(self):
        return("Token for generating strings for entity type %s." % (self.symbol()))
