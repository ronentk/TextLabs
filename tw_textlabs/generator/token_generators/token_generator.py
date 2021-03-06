#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
from typing import Mapping, Set, Optional
from numpy.random import randint, RandomState

DEFAULT_SYMBOL = "DEFAULT"
TEMPLATE_TOKEN = '##'
DYN_TOKEN_MARKER = '~~'
OPT_DYN_TOKEN_MARKER_L = '~{'
OPT_DYN_TOKEN_MARKER_R = '}~'
CHOICE_TOKEN_MARKER = '##'
CHOICE_DELIM = '|'


token_matcher = re.compile('(' + DYN_TOKEN_MARKER + '(.*?)' + DYN_TOKEN_MARKER + ')')
opt_token_matcher = re.compile('(' + OPT_DYN_TOKEN_MARKER_L + '(\d+):(.*?)' + OPT_DYN_TOKEN_MARKER_R + ')')
choice_token_matcher = re.compile('(' + CHOICE_TOKEN_MARKER + '(.*?)' + CHOICE_TOKEN_MARKER + ')')

class DuplicateKeyError(LookupError):
    def __init__(self, msg: str = "Non-unique identifier, already exists."):
        super().__init__(msg)

class TokenGenerator:
    """
    Represents a "dynamic token" which generates variable text. 
    For example, a Temperature TokenGenerator will generate strings representing
    temperatures (e.g. '100 C').
    
    Args:
        symbol: Name of the symbol (which it is indexed by).
        tgstring: The surface text of this token.
        seed: controls randomness of generated tokens.
        vocab: Set of all strings generated by this token generator.
        token_generator_map: global table of symbols in use, for recursive 
        instantiation.
    
    """
    def __init__(self, symbol: str = DEFAULT_SYMBOL, tgstring=None, seed: int = None, vocab: Mapping = {}, token_generator_map: Mapping = {}, unique: bool = True):
        
        # maps between surface name and internal name and vice versa
        self.generated_to_internal = {}
        self.internal_to_generated = {}
        
        self.vocab = vocab
        self.tg_map = token_generator_map
        self.seed = seed if seed else randint(65635)
        self.rng = RandomState(self.seed)
        self.unique = unique
        if not symbol:
            self._symbol = self.symbol()
        else:
            self._symbol = symbol

        if not tgstring:
            self._text = self._symbol
        else:
            self._text = tgstring

    def symbol(self):
        return self._symbol
    
    def next_internal_name(self) -> str:
        return ('%s_%d' % (self._symbol, len(self.internal_to_generated)))
        
    
    def register_internal(self, generated_name: str = None, 
                          internal_name: str = None) -> str:
        """
        Register a new internal name along with its corresponding generated
        surface name (e.g., 'm_0' and 'zinc'). If no internal name is supplied,
        generate new unique one.
        """
        if not internal_name:
            internal_name = self.next_internal_name()
        if internal_name in self.internal_to_generated:
            raise DuplicateKeyError("%s already exists" % (internal_name))
        if internal_name in self.tg_map:
            raise DuplicateKeyError("%s already taken by other token generator" % (self.tg_map[internal_name]))
            
        if not generated_name:
            # default name
            generated_name = internal_name
        self.generated_to_internal.update({generated_name: internal_name})
        self.internal_to_generated.update({internal_name: generated_name})
        

    def generate(self, internal_name: Optional[str] = None) -> str:
        """ 
        Generate entity name from this token generator type. 
        
        Arguments:
            unique: True to generate a unique name that will not be re-used 
            later.
            internal_name: Optionally supply an internal name to be used with 
            the generated surface string.
        """
        if self.vocab:
            generated_name = self.rng.choice(list(self.vocab))
            if self.unique:
                self.vocab.remove(generated_name)
                self.register_internal(generated_name,internal_name)
        else: # default name
            generated_name = self.next_internal_name()
            if self.unique:
                self.register_internal(generated_name=generated_name, internal_name=internal_name)
        return generated_name
                
            
    def get_vocab_words(self) -> Set[str]:
        """ Return all possible generated words """
        return self.vocab        
            

    def instantiate(self) -> str:
        """
        Return string instantiation of the token generator.
        For example an instantiation of 'The ~~m_0~~ and ~~m_1~~ were melted at
        temperature ~~TEMP~~' could be 'The zinc and copper were melted at
        temperature 1200 C'. Notes:
            * All symbols (denoted by ~~ ~~) must be registered and appear in 
            the global tg_map. 
            * The symbols can themselves be comprised of other TokenGenerators,
            which will be called recursively upon instantiation.
        """
        if not self.tg_map:
            return ""
        curr_str = self._text
        
        # Optional tokens enclosed by {x: } will appear with probability x/100
        matched_templates = opt_token_matcher.findall(curr_str)
        for (full_match, prob, sub_string) in matched_templates:
            if self.rng.randint(0,100) < int(prob):
                pass
            else:
                sub_string = ""
            curr_str = curr_str.replace(full_match, sub_string, 1)
            
        # Choice tokens of the form ##x|y|z## will instantiate to one of x,y or
        # z
        matched_templates = choice_token_matcher.findall(curr_str)
        for (full_match, match) in matched_templates:
            sub_string = self.rng.choice(match.split(CHOICE_DELIM))
            curr_str = curr_str.replace(full_match, sub_string, 1)
        
        # Resolve standard tokens
        matched_templates = token_matcher.findall(curr_str)
        for (full_match, match) in matched_templates:
            sub_string = self.tg_map[match].instantiate()
            curr_str = re.sub(full_match, sub_string, curr_str, count=1)
        return curr_str

    def description(self):
        return "General token which can be dynamically instatiated to a generate a string"
