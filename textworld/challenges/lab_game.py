# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT license.


import numpy as np

from typing import Optional
import textworld
from textworld.utils import uniquify
from textworld.generator import LabGameMaker
from textworld.generator.data import KnowledgeBase
from textworld.generator.surface_generator import SurfaceGenerator
from textworld.challenges.utils import get_seeds_for_game_generation

from textworld.utils import encode_seeds
from textworld.generator.lab_game import LabGameOptions
from textworld.generator.sketch_generator import SketchGenerationOptions, WinConditionType
from textworld.generator.process_graph import MATERIAL_STATES

from textworld.utils import quest_gen_logger

# Maximum number of search steps to add with each difficulty increase 
# (e.g., easy = 700, medium = 1400...)
MAX_SEARCH_STEPS_PER_MODE = 700


def make_game_from_level(level: int, lab_game_options: Optional[LabGameOptions] = None
    ) -> textworld.Game:
    """ Make a Lab Challenge of the desired difficulty level.

    Arguments:
        level: Difficulty level (see notes).
        lab_game_options: Options for customizing the game generation.

    Returns:
        game: Generated game.

    Notes:
        Difficulty levels are defined as follows:

        * Level  1 to 10: mode easy, nb. devices and materials =  1,
        start material state always powder. Max. quest length ranging
          from 5 to 10 as the difficulty increases;
        * Level 11 to 20: mode medium, nb. devices and materials 
          between 2 and 3, start material states variable.
          Quest length ranging from 10 to 15 as the difficulty 
          increases;
        * Level 21 to 30: mode hard, nb. devices 3 and nb. 
          materials = 4 , quest length ranging from 15 to 22 as the difficulty
          increases;

        where the different modes correspond to:

        * Easy: Nb. materials/devices 2/1. Material start states 
          always powder. Each device must be used exactly once.
        * Medium: Nb. materials/devices 2-3/2-3 (variable). 
          Material start states variable. Each device must be used 
          at least 1-2 times, and at most 3 times.
        * Hard: Nb. materials/devices 4/3 (variable). 
          Material start states more variable than Medium level. Each
          device must be used at least 1-3 times, and at most 3 times.
    """
    if not lab_game_options:
        lab_game_options = LabGameOptions()

    if level >= 21:
        mode = "hard"
        max_quest_lengths = np.round(np.linspace(15, 22, 10))
        lab_game_options.max_quest_length = int(max_quest_lengths[level - 21])
    elif level >= 11:
        mode = "medium"
        max_quest_lengths = np.round(np.linspace(10, 15, 10))
        lab_game_options.max_quest_length = int(max_quest_lengths[level - 11])
    elif level >= 1:
        mode = "easy"
        max_quest_lengths = np.round(np.linspace(5, 10, 10))
        lab_game_options.max_quest_length = int(max_quest_lengths[level - 1])
    
    modes = ["easy", "medium", "hard"]
    mode_idx = modes.index(mode)
    lab_game_options.surface_gen_options.set_difficulty_mode(mode)
    # Set max search steps according to difficulty if not otherwise specified
    if lab_game_options.default_sketch_opts:
        lab_game_options.max_steps = ((mode_idx + 1) * 
    MAX_SEARCH_STEPS_PER_MODE)
        

    return make_game(mode, lab_game_options)

def make_game(mode: str, lab_game_options: LabGameOptions
    ) -> textworld.Game:
    """ Make a TextLab game.

    Arguments:
        mode: Difficulty mode, where the different modes correspond to:

        * Easy: Nb. materials/devices 2/1. Material start states 
          always powder. Each device must be used exactly once.
        * Medium: Nb. materials/devices 2-3/2-3 (variable). 
          Material start states variable. Each device must be used 
          at least 1-2 times, and at most 3 times.
        * Hard: Nb. materials/devices 4/3 (variable). 
          Material start states more variable than Medium level. Each
          device must be used at least 1-3 times, and at most 3 times.

        lab_game_options: Options for customizing the game generation.

    Returns:
        Generated game.
    """
    
    max_quest_length = lab_game_options.sketch_gen_options.max_depth
    surface_gen_options = lab_game_options.surface_gen_options
    max_search_steps = lab_game_options.max_search_steps
    # Deal with any missing random seeds.
    seeds = get_seeds_for_game_generation(lab_game_options.seeds)

    metadata = {}  # Collect infos for reproducibility.
    metadata["orig_seed"] = lab_game_options.seeds
    metadata["desc"] = "Lab-Game"
    metadata["mode"] = mode
    metadata["seeds"] = seeds
    metadata["world_size"] = 1 # Single room always 
    metadata["max_quest_length"] = max_quest_length
    metadata["surface_gen_options"] = surface_gen_options.serialize()

    rng_objects = np.random.RandomState(seeds['objects'])
    rng_quest = np.random.RandomState(seeds['quest'])
    
    quest_gen_logger.debug('Seeds are %s' % (str(seeds)))
    sg = SurfaceGenerator(seed=seeds['surface'],
                                         surface_gen_options=surface_gen_options)
    
    modes = ["easy", "medium", "hard"]
    mode_idx = modes.index(mode)

    # get all defined device types
    device_types = uniquify(KnowledgeBase.default().types.descendants('sa'))
    
    if mode == "easy":
        n_devices = 1
        n_materials = 2
        material_states = ["powder"]
        min_uses_per_device = {device_type: 1 for device_type \
                               in device_types}
        max_uses_per_device = {device_type: 1 for device_type \
                               in device_types}
    elif mode == "medium":
        n_devices =  rng_objects.choice([2, 3])
        n_materials = rng_objects.choice([2, 3])
        min_uses_per_device = {device_type: rng_objects.choice([1, 2]) for device_type \
                               in device_types}
        max_uses_per_device = {device_type: 3 for device_type \
                               in device_types}
        material_states = rng_objects.choice(list(MATERIAL_STATES), n_materials, replace=True)
    elif mode == "hard":
        n_devices = 3
        n_materials = 4
        material_states = list(MATERIAL_STATES)
        min_uses_per_device = {device_type: rng_objects.choice([1, 3]) for device_type \
                               in device_types}
        max_uses_per_device = {device_type: 3 for device_type \
                               in device_types}

    quest_gen_logger.debug("min_uses_per_device: %s" % (min_uses_per_device))
    M = LabGameMaker(surface_generator=sg)

    # Create the lab room.
    lab = M.new_room("lab")

    M.set_player(lab)
    
    # - Describe the room.
    lab.desc = "The lab is a magical place where you'll learn materials synthesis"
    
    # Used so that Inform7 will be able to reference names of any of the
    # devices (needed for the single argument hack), but we only want 
    # the player to be able to interact with the chosen ones.
    limbo = M.new_room("Limbo")
    limbo.desc = "Storeroom for unused devices."
    
    

    # Add materials to the world.
    for i in range(n_materials):
        mat_state = rng_objects.choice(material_states)
        mat = M.new_lab_entity('m')
        mat.add_property(mat_state)
        lab.add(mat)
    
    # Add lab_container to the world.
    lab_container = M.new_lab_container()
    lab.add(lab_container)
        
    # Add devices to the world.
    chosen_devices = rng_objects.choice(device_types, min(n_devices, len(device_types)), replace=False)
    for device_type in device_types:
        device = M.new_lab_entity(device_type)
        if device_type in chosen_devices:
            lab.add(device)
        else:
            limbo.add(device)
    
    # Set quest generation options.
    quest_gen_options = SketchGenerationOptions(max_depth=max_quest_length,
                            max_steps=max_search_steps,
                            win_condition=WinConditionType.ALL,
                            quest_rng=rng_quest,
                            min_uses_per_device=min_uses_per_device,
                            max_uses_per_device=max_uses_per_device
                            )
    
    # Generate quest and corresponding surface (set in quest description)
    quest = M.generate_quest_surface_pair(quest_gen_options)
    game = M.build()
    game.metadata = metadata
    mode_choice = modes.index(mode)

    # TODO add uuid based on rest of settings
    uuid = "tw-lab_game-{specs}-{surface_gen}-{seeds}"
    uuid = uuid.format(specs=encode_seeds((mode_choice, quest_gen_options.max_depth)), 
                        surface_gen=surface_gen_options.uuid,
                       seeds=encode_seeds([seeds[k] for k in sorted(seeds)]))
    game.metadata["uuid"] = uuid
    return game

