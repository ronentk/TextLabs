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
from textworld.generator.sketch_generator import SketchGenerationOptions, WinConditionType, init_usage_map
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

        * Level  1 to 10: mode easy, nb. operations ranging from 1 to 2, 
        nb. materials ranging from 2 to 3 as the difficulty increases.
        Max number of descriptors per entity is 1;
        * Level  11 to 20: mode medium, nb. operations ranging from 3 to 5, 
        nb. materials ranging from 3 to 4 as the difficulty increases.
        Max number of descriptors per entity is 2;
        * Level  11 to 20: mode hard, nb. operations ranging from 4 to 6, 
        nb. materials ranging from 5 to 8 as the difficulty increases.
        Max number of descriptors per entity is 3;

    """
    if not lab_game_options:
        lab_game_options = LabGameOptions()

    lab_game_options.quest_reward = 1
    
    if level >= 21:
        mode = "hard"
        max_quest_lengths = np.round(np.linspace(60, 90, 10))
        nb_materials_scale = np.round(np.linspace(4, 6, 10))
        nb_ops_scale = np.round(np.linspace(5, 8, 10))
        lab_game_options.preset_ops = True
        lab_game_options.max_quest_length = int(max_quest_lengths[level - 21])
        lab_game_options.sketch_gen_options.nb_materials = int(nb_materials_scale[level - 21])
        lab_game_options.sketch_gen_options.nb_ops = int(nb_ops_scale[level - 21])
        lab_game_options.sketch_gen_options.max_descs_per_ent = init_usage_map(3)
    elif level >= 11:
        mode = "medium"
        max_quest_lengths = np.round(np.linspace(50, 70, 10))
        nb_materials_scale = np.round(np.linspace(3, 4, 10))
        nb_ops_scale = np.round(np.linspace(3, 5, 10))
        lab_game_options.preset_ops = True
        lab_game_options.max_quest_length = int(max_quest_lengths[level - 11])
        lab_game_options.sketch_gen_options.nb_materials = int(nb_materials_scale[level - 11])
        lab_game_options.sketch_gen_options.nb_ops = int(nb_ops_scale[level - 11])
        lab_game_options.sketch_gen_options.max_descs_per_ent = init_usage_map(2)
    elif level >= 1:
        mode = "easy"
        max_quest_lengths = np.round(np.linspace(20, 30, 10))
        nb_materials_scale = np.round(np.linspace(2, 3, 10))
        nb_ops_scale = np.round(np.linspace(1, 2, 10))
        lab_game_options.preset_ops = True
        lab_game_options.max_quest_length = int(max_quest_lengths[level - 1])
        lab_game_options.sketch_gen_options.nb_materials = int(nb_materials_scale[level - 1])
        lab_game_options.sketch_gen_options.nb_ops = int(nb_ops_scale[level - 1])
        lab_game_options.sketch_gen_options.max_descs_per_ent = init_usage_map(1)
        
    # no descriptors at all for level 1
    if level == 1:
        lab_game_options.sketch_gen_options.max_descs_per_ent = init_usage_map(0)
    
    modes = ["easy", "medium", "hard"]
    mode_idx = modes.index(mode)
    lab_game_options.surface_gen_options.set_difficulty_mode(mode)
    # Set max search steps according to difficulty if not otherwise specified
    if lab_game_options.default_sketch_opts:
        lab_game_options.max_search_steps = ((mode_idx + 1) * 
    MAX_SEARCH_STEPS_PER_MODE)
        

    return make_game(mode, lab_game_options)

def make_game(mode: str, lab_game_options: LabGameOptions
    ) -> textworld.Game:
    """ Make a TextLab game.

    Arguments:
        mode: Difficulty mode, where the different modes correspond to:
        lab_game_options: Options for customizing the game generation.

    Returns:
        game: Generated game.

    Notes:
        Difficulty modes are defined as follows:

        *  easy: nb. operations ranging from 1 to 2, 
        nb. materials ranging from 2 to 3 as the difficulty increases.
        Max number of descriptors per entity is 1;
        * medium: nb. operations ranging from 3 to 5, 
        nb. materials ranging from 3 to 4 as the difficulty increases.
        Max number of descriptors per entity is 2;
        * hard: nb. operations ranging from 4 to 6, 
        nb. materials ranging from 5 to 8 as the difficulty increases.
        Max number of descriptors per entity is 3;


    Returns:
        Generated game.
    """
    
    quest_gen_options = lab_game_options.sketch_gen_options
    max_quest_length = quest_gen_options.max_depth
    surface_gen_options = lab_game_options.surface_gen_options
    quest_gen_options.win_condition = WinConditionType.ALL
    
    # Deal with any missing random seeds.
    seeds = get_seeds_for_game_generation(lab_game_options.seeds)

    

    rng_objects = lab_game_options.rngs['objects']
    rng_quest = lab_game_options.rngs['quest']
    
    n_materials = lab_game_options.sketch_gen_options.nb_materials
    n_ops = lab_game_options.sketch_gen_options.nb_ops
    
    
    all_op_types = KnowledgeBase.default().types.descendants('toe')
    chosen_op_types = rng_objects.choice(all_op_types, n_ops, replace=True)
    
    if lab_game_options.preset_ops:
        surface_gen_options.op_type_map = {'tlq_op_{}'.format(i): chosen_op_types[i] for i in range(n_ops)}
    
    sg = SurfaceGenerator(seed=seeds['surface'],
                                         surface_gen_options=surface_gen_options)
    quest_gen_options.quest_rng = rng_quest
    
    modes = ["easy", "medium", "hard"]
    mode_idx = modes.index(mode)
    
    metadata = {}  # Collect infos for reproducibility.
    metadata["orig_seed"] = lab_game_options.seeds
    metadata["desc"] = "Lab-Game"
    metadata["mode"] = mode
    metadata["seeds"] = seeds
    metadata["world_size"] = 1 # Single room always 
    metadata["max_quest_length"] = max_quest_length
    metadata["surface_gen_options"] = surface_gen_options.serialize()

    
    # Currently unused
    if mode == "easy":
        material_states = ["powder"]
    elif mode == "medium":
        material_states = rng_objects.choice(list(MATERIAL_STATES), n_materials, replace=True)
    elif mode == "hard":
        material_states = list(MATERIAL_STATES)

    M = LabGameMaker(surface_generator=sg)

    # Create the lab room.
    lab = M.new_room("lab")

    M.set_player(lab)
    
    # - Describe the room.
    lab.desc = "The lab is a magical place where you'll learn materials synthesis"    

    # Add materials to the world.
    ent_type = 'm'
    n_max_descs = quest_gen_options.max_descs_per_ent[ent_type]
    for i in range(n_materials):
        mat_state = rng_objects.choice(material_states)
        mat = M.new_lab_entity('m')
        mat.add_property(mat_state)
        lab.add(mat)
        n_descs = rng_objects.randint(0, (n_max_descs + 1))
        for j in range(n_descs):
            mdesc = M.new_lab_entity('mdsc')
            lab.add(mdesc)
            quest_gen_options.ent_desc_map[mat.var.name].append(mdesc.var.name)
    
    # Add operations and their descriptors
    ent_type = 'tlq_op'
    n_max_descs = quest_gen_options.max_descs_per_ent[ent_type]
    ops = []
    
    # Either preset ops 
    if lab_game_options.preset_ops:
        ops = [M.new_tlq_op(dynamic_define=False, op_type=chosen_op_types[i]) for i in range(n_ops)]
        op_type_map = {op.var.name: chosen_op_types[i] for i,op in enumerate(ops)}
        assert op_type_map == surface_gen_options.op_type_map
    else: # or make their classification part of the quest
        ops = [M.new_tlq_op(dynamic_define=True) for i in range(n_ops)]
    
    for op in ops:
        lab.add(op)
        n_descs = rng_objects.randint(0, (n_max_descs + 1))
        for j in range(n_descs):
            odesc = M.new_lab_entity('odsc')
            lab.add(odesc)
            quest_gen_options.ent_desc_map[op.var.name].append(odesc.var.name)

    
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

