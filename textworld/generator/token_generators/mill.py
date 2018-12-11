from . import TokenGenerator


class Mill(TokenGenerator):

    def __init__(self, **kwargs):
        kwargs['symbol'] = 'md'
        kwargs['vocab'] = {"milling device"}
        super().__init__(**kwargs)
        

    def instantiate(self):
        return self.generate(unique=False)

    def __str__(self):
        return("Token for generating strings for entity type %s." % (self.symbol()))
