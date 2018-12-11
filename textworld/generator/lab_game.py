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

from textworld import g_rng
from textworld.utils import encode_seeds, uniquify
from textworld.generator.data import KnowledgeBase
from textworld.generator.game import GameOptions
from textworld.generator.chaining import ChainingOptions
from textworld.generator.surface_generator import SurfaceGenerationOptions
from textworld.generator.sketch_generator import SketchGenerationOptions

from textworld.generator.process_graph import MATERIAL_STATES

class UnderspecifiedQuestError(NameError):
    def __init__(self):
        msg = "Either the list of actions or the win_condition  he quest must have "
        super().__init__(msg)

class InvalidLabConfigError(ValueError):
    def __init__(self, message):
        # Call the base class constructor with the parameters it needs
        super().__init__(message)



@dataclass
class LabConfig:
    """
    Represents the initial state of the lab and device avaiability and usage
    targets for quest generation.
    Arguments:
        devices: available devices for this quest.
    	min_uses_per_device: Generated quest must include at least this number 
        of uses per device. Must be specified for each device in 'devices'.
        max_uses_per_device: Generated quest may include at most this number of
        uses per device. Must be specified for each device in 'devices'.
    	lab_container_available: - flag indicating whether a lab_container is
        available. Currently we only support one such instance.
    	material_states: Starting states of each of the materials. Must be in
        ['powder', 'liquid', 'solid']",
    """
    devices: List[str]
    min_uses_per_device: Mapping[str, int]
    max_uses_per_device: Mapping[str, int]
    lab_container_available: bool
    material_states: List[str]

    def validiate(self):
        """ Validate input fields """
        device_types = uniquify(KnowledgeBase.default().types.descendants('sa'))
        if not set(device_types).issuperset(set(self.devices)):
            raise InvalidLabConfigError("Using undefined devices! Must be in %s" % (device_types))
        if not MATERIAL_STATES.issuperset(set(self.material_states)):
            raise InvalidLabConfigError("Using undefined material states!")
        if not set(self.devices) <= self.min_uses_per_device.keys():
            raise InvalidLabConfigError("Min. uses per device not defined for all devices.")
        if not set(self.devices) <= self.max_uses_per_device.keys():
            raise InvalidLabConfigError("Max. uses per device not defined for all devices.")
        


def load_lab_config(path: Path) -> LabConfig:
    """
    Load json file containing lab config and return LabConfig instance.
    """
    with path.open() as f:
        raw_data = json.load(f)
    
    lab_config = LabConfig(**raw_data)
    lab_config.validiate()
    return lab_config

    
class LabGameOptions(GameOptions):
    """
    Options for customizing the game generation.

    Attributes:
        seed:
            Sets specified seed for the random number generator controlling
            random elements of quest/text generation.
        lab_config_path:
            Path to file containing initial lab configuration.
        max_quest_length:
            Maximum number of actions comprising the minimal winning 
        policy.
        surface_gen_options:
            Options controlling generation of surface text.
        sketch_gen_options:
            Options controlling quest generation.
    """

    def __init__(self, seed: Optional[int] = None,
                 max_quest_length: Optional[int] = None,
                 lab_config_path: Optional[Path] = None,
                surface_gen_options: Optional[Union[Mapping, SurfaceGenerationOptions]] = None,
                sketch_gen_options: Optional[SketchGenerationOptions] = None
                ):
        super(LabGameOptions, self).__init__()
        self.chaining = ChainingOptions() # use defaults
        self.surface_gen_options = SurfaceGenerationOptions() \
        if not surface_gen_options else surface_gen_options
        self.sketch_gen_options = SketchGenerationOptions() \
        if not sketch_gen_options else sketch_gen_options
        if max_quest_length:
            self.sketch_gen_options.max_depth = max_quest_length
        if seed:
            self._seeds = seed
        self._lab_config = None


    @property
    def max_quest_length(self) -> int:
        return self.sketch_gen_options.max_depth

    @max_quest_length.setter
    def max_quest_length(self, value: int) -> None:
        self.sketch_gen_options.max_depth = value

    @property
    def lab_config(self) -> LabConfig:
        return self._lab_config
    
    @lab_config.setter
    def lab_config(self, lab_config: LabConfig) -> None:
        self._lab_config = lab_config
    
    
    def load_lab_config(self, lab_config_path: Path) -> None:
        """
        Loads a configuration file defining initial game state. This should be a
        JSON file, see LabConfig for required fields.
        """
        self.lab_config = load_lab_config(lab_config_path)
    
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
        uuid = uuid.format(specs=encode_seeds((self.sketch_gen_options.max_depth,
                                               self.sketch_gen_options.max_steps)),
                           surface=self.surface_gen_options.uuid,
                           seeds=encode_seeds([self.seeds[k] for k in sorted(self._seeds)]))
        return uuid
