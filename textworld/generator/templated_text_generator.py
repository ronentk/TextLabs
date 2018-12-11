
import re
from textworld.generator.token_generators import TokenGenerator, grab_all
from textworld.generator.token_generators.token_generator import DYN_TOKEN_MARKER
from numpy.random import RandomState, randint

# Turn text into template which will be dynamically instantiated by 
# TemplatedTextGenerator, if a token generator with symbol s is registered.
def templatize_text(s):
    return DYN_TOKEN_MARKER + s + DYN_TOKEN_MARKER

def templatize_text_list(s_list):
    return [templatize_text(s) for s in s_list]

class TemplatedTextGenerator(object):
    """
    Helper class for random text generation using templates.
    Arguments:
        seed: sets specified seed for the random number generator used for 
        text generation. 
    """
    def __init__(self, seed: int = None):
        self.template_matcher = re.compile(DYN_TOKEN_MARKER + '(.*?)' + DYN_TOKEN_MARKER)
        self.token_generators_dict = {}
        self.seed = seed if seed else randint(65635)
        self.rng = RandomState(self.seed)
        # Collect all predefined token generators
        for token in grab_all(seed=self.seed,
                              token_generator_map=self.token_generators_dict):
            self.register_token_generator(token)
    
    def register_token_generators(self, tg_list):
        for symbol, tg_string in tg_list:
            self.register_token_generator(TokenGenerator(symbol=symbol,
                                                     tgstring=tg_string,
                                                     seed=self.seed,
                                                     token_generator_map=self.token_generators_dict))
            
    def register_token_generator(self, tg):
        """ Register a token generator after verifying it's valid. """
        if tg.symbol() in self.token_generators_dict:
            raise KeyError("%s already in tokens dictionary!" % (tg.symbol()))
        try: 
            self.verify_tg(tg)
        except KeyError as e:
            print(e)
            return
            
        self.token_generators_dict[tg.symbol()] = tg
        
    def instantiate_tg(self, tg):
        """ Recursively instantiate a TokenGenerator with text. """
        try:
            self.verify_tg(tg)
        except KeyError as e:
            print(e)
            return ""
            
        return tg.instantiate()
    
    def generate_entity(self, entity_type: str, internal_name: str = None) -> str:
        """ 
        Generate a unique name for an entity of given type.
        
        Arguments:
            entity_type: Type of entity to create name for. This will be the
            "printed name" in the Inform7 code.
            internal_name: internal name by which the entity is indexed (should
            match the internal TextWorld name).
        """
        if entity_type in self.token_generators_dict:
            entity_name = self.token_generators_dict[entity_type].generate(unique=True,
                                                        internal_name=internal_name)
            if not internal_name: # take default generated by token generator
                internal_name = self.token_generators_dict[entity_type].generated_to_internal[entity_name]
            self.register_token_generator(TokenGenerator(symbol=internal_name,
                                    tgstring=entity_name,
                                    seed=self.seed,
                                    token_generator_map=self.token_generators_dict))
        else:
            raise KeyError("Unknown entity type: %s" % (entity_type))
        return entity_name
    
    def instantiate_template_text(self, template_text):
        """
        Instantiate all templates recursively in a given template text, using
        the currently registered token generators to produce the tokens.
        """
        tg = TokenGenerator(symbol="NAN", tgstring=template_text,
                            seed=self.seed,
                            token_generator_map=self.token_generators_dict)
        return self.instantiate_tg(tg)
        
    def verify_tg(self, tg):
        # TODO not verifying circular references
        matched_templates = self.template_matcher.findall(tg._text)
        bad_symbols = [k for k in matched_templates if k not in self.token_generators_dict]
        if len(bad_symbols) > 0:
            raise KeyError("Error verifying template text '%s'. Symbols %s not in dynamic tokens dictionary!" % (tg._text, bad_symbols))

    