from . import TokenGenerator


class LabContainer(TokenGenerator):

    def __init__(self, **kwargs):
        kwargs['symbol'] = 'lc'
        kwargs['vocab'] = {"lab container"}
        super().__init__(**kwargs)
        

    def instantiate(self):
        return self.generate(unique=False)

    def __str__(self):
        return("Token for generating strings for entity type %s." % (self.symbol()))
