from . import TokenGenerator


class Press(TokenGenerator):

    def __init__(self, **kwargs):
        kwargs['symbol'] = 'pd'
        kwargs['vocab'] = {"press device"}
        super().__init__(**kwargs)
        

    def instantiate(self):
        return self.generate(unique=False)

    def __str__(self):
        return("Token for generating strings for entity type %s." % (self.symbol()))
