# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT license.


import copy
import json

from typing import List, Dict, Optional, Mapping, Union
try:
    from typing import Collection
except ImportError:
    # Collection is new in Python 3.6 -- fall back on Iterable for 3.5
    from typing import Iterable as Collection
    
from pathlib import Path
from dataclasses import dataclass
from numpy.random import RandomState

from tw_textlabs import g_rng
from tw_textlabs.utils import encode_seeds, uniquify
from tw_textlabs.generator.data import KnowledgeBase
from tw_textlabs.generator.game import GameOptions
from tw_textlabs.generator.chaining import ChainingOptions
from tw_textlabs.generator.surface_generator import SurfaceGenerationOptions
from tw_textlabs.generator.quest_generator import QuestGenerationOptions

from tw_textlabs.generator.process_graph import MATERIAL_STATES

class UnderspecifiedQuestError(NameError):
    def __init__(self):
        msg = "Either the list of actions or the win_condition  he quest must have "
        super().__init__(msg)

class InvalidLabConfigError(ValueError):
    def __init__(self, message):
        # Call the base class constructor with the parameters it needs
        super().__init__(message)



    
class LabGameOptions(GameOptions):
    """
    Options for customizing the game generation.

    Attributes:
        seed:
            Sets specified seed for the random number generator controlling
            random elements of quest/text generation.
        max_quest_length:
            Maximum number of actions comprising the minimal winning 
        policy.
        preset_ops:
            True to preset all operation types, false to allow them to be dynamically defined.
        surface_gen_options:
            Options controlling generation of surface text.
        quest_gen_options:
            Options controlling quest generation.
    """

    def __init__(self, seed: Optional[int] = None,
                 max_quest_length: Optional[int] = None,
                 preset_ops: Optional[bool] = False,
                surface_gen_options: Optional[Union[Mapping, SurfaceGenerationOptions]] = None,
                quest_gen_options: Optional[QuestGenerationOptions] = None
                ):
        super(LabGameOptions, self).__init__()
        self.chaining = ChainingOptions() # use defaults
        self.surface_gen_options = SurfaceGenerationOptions() \
        if not surface_gen_options else surface_gen_options
        if not quest_gen_options:
            self.quest_gen_options = QuestGenerationOptions()
            self._default_sketch_opts = True
        else:
            self.quest_gen_options = quest_gen_options
            self._default_sketch_opts = False
        if max_quest_length:
            self.quest_gen_options.max_depth = max_quest_length
        if seed:
            self._seeds = seed
        self._lab_config = None

        self.preset_ops = preset_ops


    @property
    def default_sketch_opts(self) -> bool:
        return self._default_sketch_opts
    
    @property
    def preset_ops(self) -> bool:
        return self.quest_gen_options.preset_ops

    @preset_ops.setter
    def preset_ops(self, value: bool) -> None:
        self.quest_gen_options.preset_ops = value
        self.surface_gen_options.preset_ops = value

    @property
    def quest_reward(self) -> int:
        return self.quest_gen_options.quest_reward

    @quest_reward.setter
    def quest_reward(self, value: int) -> None:
        self.quest_gen_options.quest_reward = value
        
    @property
    def max_quest_length(self) -> int:
        return self.quest_gen_options.max_depth

    @max_quest_length.setter
    def max_quest_length(self, value: int) -> None:
        self.quest_gen_options.max_depth = value
        
    @property
    def max_search_steps(self) -> int:
        return self.quest_gen_options.max_steps

    @max_search_steps.setter
    def max_search_steps(self, value: int) -> None:
        self.quest_gen_options.max_steps = value
    
    
    @property
    def seeds(self):
        return self._seeds

    @seeds.setter
    def seeds(self, value: Union[int, Mapping[str, int]]) -> None:
        keys = ['map', 'objects', 'quest', 'surface']

        def _key_missing(seeds):
            return not set(seeds.keys()).issuperset(keys)

        seeds = value
        if type(value) is int:
            rng = RandomState(value)
            seeds = {}
        elif _key_missing(value):
            rng = g_rng.next()

        # Check if we need to generate missing seeds.
        self._seeds = {}
        for key in keys:
            if key in seeds:
                self._seeds[key] = seeds[key]
            else:
                self._seeds[key] = rng.randint(65635)

        self.quest_gen_options.quest_rng = self.rngs['quest']
        self.surface_gen_options.seed = self._seeds['surface'] 

    @property
    def rngs(self) -> Dict[str, RandomState]:
        rngs = {}
        for key, seed in self._seeds.items():
            rngs[key] = RandomState(seed)

        return rngs

    def copy(self) -> "LabGameOptions":
        return copy.copy(self)

    @property
    def uuid(self) -> str:
        # TODO: incomplete, finish this
        uuid = "tw-game-{specs}-{surface}-{seeds}"
        uuid = uuid.format(specs=encode_seeds((self.quest_gen_options.max_depth,
                                               self.quest_gen_options.max_steps)),
                           surface=self.surface_gen_options.uuid,
                           seeds=encode_seeds([self.seeds[k] for k in sorted(self._seeds)]))
        return uuid
