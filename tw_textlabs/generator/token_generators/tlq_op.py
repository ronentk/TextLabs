from . import TokenGenerator


class TlqOp(TokenGenerator):

    def __init__(self, **kwargs):
        kwargs['symbol'] = 'tlq_op'
        kwargs['vocab'] = {"op1", "op2", "op3",
        "op4","op5", "op6", "op7", "op8"}
        super().__init__(**kwargs)
        self.unique = True

    def instantiate(self):
        return self.generate()

    def __str__(self):
        return("Token for generating strings for entity type %s." % (self.symbol()))
