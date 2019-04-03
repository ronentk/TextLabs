from . import TokenGenerator


class Temperature(TokenGenerator):
    def __init__(self, **kwargs):
        kwargs['symbol'] = 'TEMP'
        super().__init__(**kwargs)
        

    def instantiate(self):
        # TODO finish
        return str(self.rng.randint(0,9))

    def description(self):
        return("Token for generating temperature strings.")
