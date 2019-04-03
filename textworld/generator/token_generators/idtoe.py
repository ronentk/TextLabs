from . import TokenGenerator


class Idtoe(TokenGenerator):

    def __init__(self, **kwargs):
        kwargs['symbol'] = 'idtoe'
        kwargs['vocab'] = {"wash", "quench", "rinse", "evacuate"}
        super().__init__(**kwargs)
        self.unique = False


    def instantiate(self):
        return self.generate()

    def __str__(self):
        return("Token for generating strings for entity type %s." % (self.symbol()))
