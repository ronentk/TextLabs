# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT license.


import os
import uuid
import numpy as np
from os.path import join as pjoin
from typing import Optional, Mapping, Dict, List

from numpy.random import RandomState

from tw_textlabs import g_rng
from tw_textlabs.utils import maybe_mkdir, str2bool, uniquify, encode_seeds
from tw_textlabs.generator.chaining import ChainingOptions, sample_quest
from tw_textlabs.generator.lab_game import LabGameOptions
from tw_textlabs.generator.game import Game, Quest, Event, World, GameOptions
from tw_textlabs.generator.graph_networks import create_map, create_small_map
from tw_textlabs.generator.text_generation import generate_text_from_grammar

from tw_textlabs.generator import data
from tw_textlabs.generator import inform7
from tw_textlabs.generator.inform7 import generate_inform7_source, compile_inform7_game
from tw_textlabs.generator.inform7 import CouldNotCompileGameError

from tw_textlabs.generator.data import KnowledgeBase
from tw_textlabs.generator.text_grammar import Grammar
from tw_textlabs.generator.maker import GameMaker
from tw_textlabs.generator.lab_game_maker import LabGameMaker
from tw_textlabs.generator.logger import GameLogger

from tw_textlabs.generator.quest_generator import QuestGenerationOptions, WinConditionType
from tw_textlabs.generator.surface_generator import SurfaceGenerator


class TextworldGenerationWarning(UserWarning):
    pass


def make_map(n_rooms, size=None, rng=None, possible_door_states=["open", "closed", "locked"]):
    """ Make a map.

    Parameters
    ----------
    n_rooms : int
        Number of rooms in the map.
    size : tuple of int
        Size (height, width) of the grid delimiting the map.
    """
    rng = g_rng.next() if rng is None else rng

    if size is None:
        edge_size = int(np.ceil(np.sqrt(n_rooms + 1)))
        size = (edge_size, edge_size)

    map = create_map(rng, n_rooms, size[0], size[1], possible_door_states)
    return map


def make_small_map(n_rooms, rng=None, possible_door_states=["open", "closed", "locked"]):
    """ Make a small map.

    The map will contains one room that connects to all others.

    Parameters
    ----------
    n_rooms : int
        Number of rooms in the map (maximum of 5 rooms).
    possible_door_states : list of str, optional
        Possible states doors can have.
    """
    rng = g_rng.next() if rng is None else rng

    if n_rooms > 5:
        raise ValueError("Nb. of rooms of a small map must be less than 6 rooms.")

    map_ = create_small_map(rng, n_rooms, possible_door_states)
    return map_


def make_world(world_size, nb_objects=0, rngs=None):
    """ Make a world (map + objects).

    Parameters
    ----------
    world_size : int
        Number of rooms in the world.
    nb_objects : int
        Number of objects in the world.
    """
    if rngs is None:
        rngs = {}
        rng = g_rng.next()
        rngs['map'] = RandomState(rng.randint(65635))
        rngs['objects'] = RandomState(rng.randint(65635))

    map_ = make_map(n_rooms=world_size, rng=rngs['map'])
    world = World.from_map(map_)
    world.set_player_room()
    world.populate(nb_objects=nb_objects, rng=rngs['objects'])
    return world


def make_world_with(rooms, rng=None):
    """ Make a world that contains the given rooms.

    Parameters
    ----------
    rooms : list of tw_textlabs.logic.Variable
        Rooms in the map. Variables must have type 'r'.
    """
    map = make_map(n_rooms=len(rooms), rng=rng)
    for (n, d), room in zip(map.nodes.items(), rooms):
        d["name"] = room.name

    world = World.from_map(map)
    world.set_player_room()
    return world


def make_quest(world, quest_length, rng=None, rules_per_depth=(), backward=False):
    state = world
    if hasattr(world, "state"):
        state = world.state

    rng = g_rng.next() if rng is None else rng

    # Sample a quest according to quest_length.
    options = ChainingOptions()
    options.backward = backward
    options.max_depth = quest_length
    options.rng = rng
    options.rules_per_depth = rules_per_depth
    chain = sample_quest(state, options)
    event = Event(chain.actions)
    return Quest(win_events=[event])


def make_grammar(options: Mapping = {}, rng: Optional[RandomState] = None) -> Grammar:
    rng = g_rng.next() if rng is None else rng
    grammar = Grammar(options, rng)
    grammar.check()
    return grammar


def make_game_with(world, quests=None, grammar=None):
    game = Game(world, grammar, quests)
    if grammar is None:
        for var, var_infos in game.infos.items():
            var_infos.name = var.name
    else:
        game = generate_text_from_grammar(game, grammar)

    return game


def make_game(options: GameOptions) -> Game:
    """
    Make a game (map + objects + quest).

    Arguments:
        options:
            For customizing the game generation (see
            :py:class:`tw_textlabs.GameOptions <tw_textlabs.generator.game.GameOptions>`
            for the list of available options).

    Returns:
        Generated game.
    """
    rngs = options.rngs

    # Generate only the map for now (i.e. without any objects)
    world = make_world(options.nb_rooms, nb_objects=0, rngs=rngs)

    # Sample a quest.
    chaining_options = options.chaining.copy()
    # Go, examine, look and inventory shouldn't be used for chaining.
    exclude = ["go.*", "examine.*", "look.*", "inventory.*"]
    chaining_options.rules_per_depth = [options.kb.rules.get_matching(".*", exclude=exclude)]
    chaining_options.backward = True
    chaining_options.create_variables = True
    chaining_options.rng = rngs['quest']
    chaining_options.restricted_types = {"r", "d"}
    chain = sample_quest(world.state, chaining_options)

    subquests = []
    for i in range(1, len(chain.nodes)):
        if chain.nodes[i].breadth != chain.nodes[i - 1].breadth:
            event = Event(chain.actions[:i])
            subquests.append(Quest(win_events=[event]))

    event = Event(chain.actions)
    subquests.append(Quest(win_events=[event]))

    # Set the initial state required for the quest.
    world.state = chain.initial_state

    # Add distractors objects (i.e. not related to the quest)
    world.populate(options.nb_objects, rng=rngs['objects'])

    grammar = make_grammar(options.grammar, rng=rngs['grammar'])
    game = make_game_with(world, subquests, grammar)
    game.change_grammar(grammar)
    game.metadata["uuid"] = options.uuid

    return game

def make_lab_game(options: LabGameOptions) -> Game:

    """
    Make a lab game (map + devices + quest).

    Arguments:
    nb_devices: Number of devices in the world.
    : Options for the grammar.

    Returns:
    Generated game.
    """

    max_quest_length = options.quest_gen_options.max_depth
    surface_gen_options = options.surface_gen_options
    max_search_steps = options.quest_gen_options.max_steps

    seeds = options.seeds
    metadata = {}  # Collect infos for reproducibility.
    metadata["desc"] = "Lab-Game"
    metadata["mode"] = "custom"
    metadata["seeds"] = seeds
    metadata["world_size"] = 1 # Single room always 
    metadata["max_quest_length"] = max_quest_length

    rng_quest = options.rngs['quest']

    sg = SurfaceGenerator(seed=seeds['surface'],
                        surface_gen_options=surface_gen_options)
    
    devices = options.lab_config.devices
    material_states = options.lab_config.material_states
    min_uses_per_device = options.lab_config.min_uses_per_device
    max_uses_per_device = options.lab_config.max_uses_per_device
    device_types = uniquify(KnowledgeBase.default().types.descendants('sa'))
    
    M = LabGameMaker(surface_generator=sg)
    # Create the lab room.
    lab = M.new_room("lab")
    # - Describe the room.
    lab.desc = "The lab is a magical place where you'll learn materials synthesis!"
    
    # Used so that Inform7 will be able to reference names of any of the
    # devices (needed for the single argument hack), but we only want the player
    # to be able to interact with the chosen ones.
    limbo = M.new_room("Limbo")
    limbo.desc = "Storeroom for unused devices."
    
    M.set_player(lab)
    
    # Add materials to the lab.
    for mat_state in material_states:
        mat = M.new_lab_entity('m')
        mat.add_property(mat_state)
        lab.add(mat)
        
    if options.lab_config.lab_container_available:
        # Add lab_container to the world.
        lab_container = M.new_lab_container()
        lab.add(lab_container)
        
    
    # Add devices to the world. We add all device types but only the available
    # ones to the lab room
    for device_type in device_types:
        device = M.new_lab_entity(device_type)
        if device_type in devices:
            lab.add(device)
        else:
            limbo.add(device)
            
            
    quest_gen_options = QuestGenerationOptions(max_depth=max_quest_length,
                            max_steps=max_search_steps,
                            win_condition=WinConditionType.ALL,
                            quest_rng=rng_quest,
                            min_uses_per_device=min_uses_per_device,
                            max_uses_per_device=max_uses_per_device
                            )
    
    quest = M.generate_quest_surface_pair(quest_gen_options)
    game = M.build()
    game.metadata = metadata
    # TODO add uuid based on rest of settings
    uuid = "tw-custom-lab-game-{specs}-{surface_gen}-{seeds}"
    uuid = uuid.format(specs=encode_seeds((quest_gen_options.max_depth, max_search_steps)), 
                        surface_gen=surface_gen_options.uuid,
                       seeds=encode_seeds([seeds[k] for k in sorted(seeds)]))
    game.metadata["uuid"] = uuid
    return game

def compile_game(game: Game, options: Optional[GameOptions] = None):
    """
    Compile a game.

    Arguments:
        game: Game object to compile.
        options:
            For customizing the game generation (see
            :py:class:`tw_textlabs.GameOptions <tw_textlabs.generator.game.GameOptions>`
            for the list of available options).


    Returns:
        The path to compiled game.
    """
    options = options or GameOptions()
    
    folder, filename = os.path.split(options.path)
    if not filename:
        filename = game.metadata.get("uuid", str(uuid.uuid4()))

    filename, ext = os.path.splitext(filename)
    if not ext:
        ext = options.file_ext  # Add default extension, if needed.

    source = generate_inform7_source(game)

    maybe_mkdir(folder)
    game_json = pjoin(folder, filename + ".json")
    game_file = pjoin(folder, filename + ext)

    already_compiled = False  # Check if game is already compiled.
    if not options.force_recompile and os.path.isfile(game_file) and os.path.isfile(game_json):
        already_compiled = game == Game.load(game_json)
        msg = ("It's highly unprobable that two games with the same id have different structures."
               " That would mean the generator has been modified."
               " Please clean already generated games found in '{}'.".format(folder))
        assert already_compiled, msg

    if not already_compiled or options.force_recompile:
        game.save(game_json)
        compile_inform7_game(source, game_file)

    return game_file
