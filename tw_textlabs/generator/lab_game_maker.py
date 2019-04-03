# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT license.

from typing import Iterable, Union, Optional
try:
    from typing import Collection
except ImportError:
    # Collection is new in Python 3.6 -- fall back on Iterable for 3.5
    from typing import Iterable as Collection

import networkx as nx

import tw_textlabs

from tw_textlabs.generator.data import KnowledgeBase
from tw_textlabs.logic import State, Proposition, Action, Signature
from tw_textlabs.generator.game import Game, World, Quest, UnderspecifiedQuestError, Event
from tw_textlabs.generator.surface_generator import SurfaceGenerator, descriptions
from tw_textlabs.generator.chaining import Chain
from tw_textlabs.generator.maker import GameMaker, WorldEntity
from tw_textlabs.generator.quest_generator import LabQuestGenerator, convert_to_compact_action, QuestGenerationOptions, WinConditionType
from tw_textlabs.utils import quest_gen_logger
from tw_textlabs.generator.lab_game import LabGameOptions
from tw_textlabs.generator.process_graph import MATERIAL_STATES, ProcessGraph

    

class LabGameMaker(GameMaker):
    """ 
    Stateful utility class for handcrafting text-based materials 
    synthesis quests.

    Attributes:
        player (WorldEntity): Entity representing the player.
        inventory (WorldEntity): Player's inventory entity.
        rooms (List[WorldRoom]): The rooms present in this world.
    """

    def __init__(self, surface_generator: SurfaceGenerator) -> None:
        """
        Creates an empty world, with a player and an empty inventory.
        """
        self._entities = {}
        self.quests = []
        self.rooms = []
        self.paths = []
        self._types_counts = KnowledgeBase.default().types.count(State())
        self.player = self.new(type='P')
        self.inventory = self.new(type='I')
        self.sg = surface_generator
        self._game = None
        self._quests_str = []
        self._distractors_facts = []
        # define global op types
        self.globals = {}
        for t in KnowledgeBase.default().types.descendants('toe'):
            op_type = self.new(type=t)
            op_type.add_property('initialized')
            self.globals[t] = op_type


    def get_world(self) -> World:
        """ Create a `World` instance given the defined facts.

        Parameters
        ----------

        Returns
        -------
            Generated world.
        """
        world = World.from_facts(self.facts)
        return world

    def build(self, validate: bool = True) -> Game:
        """ Create a `Game` instance given the defined facts.

        Parameters
        ----------
        validate : optional
            If True, check if the game is valid, i.e. respects all constraints.

        Returns
        -------
            Generated game.
        """
        if validate:
            self.validate()  # Validate the state of the world.

        world = World.from_facts(self.facts)
        game = Game(world, quests=self.quests)

        # Keep names and descriptions that were manually provided.
        for k, var_infos in game.infos.items():
            if k in self._entities:
                var_infos.name = self._entities[k].name
                var_infos.desc = self._entities[k].desc

            # If we can, reuse information generated during last build.
            if self._game is not None and k in self._game.infos:
                # var_infos.desc = self._game.infos[k].desc
                var_infos.name = self._game.infos[k].name
                var_infos.adj = self._game.infos[k].adj
                var_infos.noun = self._game.infos[k].noun
                var_infos.room_type = self._game.infos[k].room_type

        game.metadata["desc"] = "Generated with tw_textlabs.GameMaker."

        self._game = game  # Keep track of previous build.
        return self._game

    def compile(self, path: str) -> str:
        """
        Compile this game.

        Parameters
        ----------
        name :
            Name of the generated game file (without extension).

        Returns
        -------
        game_file
            Path to the game file.
        """
        self._working_game = self.build()
        options = tw_textlabs.GameOptions()
        options.path = path
        options.force_recompile = True
        game_file = tw_textlabs.generator.compile_game(self._working_game, options)
        return game_file

    def __contains__(self, entity) -> bool:
        """
        Checks if the given entity exists in the world
        :param entity: The entity to check
        :return: True if the entity is in the world; otherwise False
        """
        for room in self.rooms:
            if entity in room:
                return True

        for path in self.paths:
            if entity == path.door:
                return True

        if entity in self.inventory:
            return True

        return False

    
    def generate_quest_surface_pair(self, quest_gen_options: QuestGenerationOptions) -> Quest:
        """
        Generate a materials synthesis quest and corresponding surface using the
        the supplied generation options.
        
        Parameters
        ----------
        quest_gen_options:
            Options controlling quest generation.
            
        Returns
        -------
        quest:
            Generated quest, whose description (quest.desc) is the corresponding
            surface.
        """
        quest = self.generate_quest(quest_gen_options=quest_gen_options)
        surface = self.sg.quest_to_surface(quest)
        self.set_quest_description(surface)
        return quest
    
    def generate_quest(self, quest_gen_options: QuestGenerationOptions) -> Quest:
        """
        Generate a materials synthesis quest using the
        the supplied generation options.
        
        Parameters
        ----------
        quest_gen_options:
            Options controlling quest generation.
            
        Returns
        -------
        quest:
            Generated quest.
            
        """
        world = self.get_world()
        quest_gen = LabQuestGenerator(start_state=world.state,
                                      quest_gen_options=quest_gen_options)
        quest = quest_gen.generate_quest()
        quest_gen_logger.info("Found quest: %s" % (str([convert_to_compact_action(a) for a in quest.actions])))
        self.quests = [quest]
        return quest

    def set_quest_description(self, surface: str) -> None:
        """ Set quest description with given Surface text"""
        if len(self.quests) > 0:
            self.quests[0].desc = surface
    
    def new_lab_entity(self, entity_type: str, name: Optional[str] = None,
            desc: Optional[str] = None) -> WorldEntity:
        """ 
        Create new lab entity given its type.

        Args:
            entity_type: Type of the entity.
            name: The name of the entity.
            desc: The description of the entity.

        Returns:
            The newly created lab entity.

        """
        # zero-indexing so number of existing entities is the id of next to generate
        int_name = '%s_%d' % (entity_type, self._types_counts[entity_type])
        name = self.sg.entity_to_name(entity_type, int_name) if not name else name
        desc = descriptions[entity_type] if not desc else desc
        
        lab_entity = self.new(type=entity_type, name=name, desc=desc)
        return lab_entity
    
    def new_tlq_op(self, name: Optional[str] = None,
            desc: Optional[str] = None, absolute_name: Optional[str] = None, 
            op_type: Optional[str] = None, dynamic_define: Optional[bool] = False) -> WorldEntity:
        """ 
        Create new TextLabs operation entity.

        Args:
            name: The name of the entity.
            desc: The description of the entity.
            op_type: The type of this op - must be of type tlq op enum (abbrv. 'toe'). If set, dynamic_define=False 
            dynamic_define: True to preset this op type, False to allow it to be defined during game time.

        Returns:
            The newly created tlq_op entity.

        """
        
        if not op_type:
            op_type = 'idtoe'
        else: # dynamic_define can only be set if op_type not set
            assert(not dynamic_define)
        
        lab_op = self.new_lab_entity('tlq_op', name=name, desc=desc)

        if dynamic_define:
            lab_op.add_property('undefined')
        else:
            lab_op.add_property('defined')
            
        # set type of operation
        self.add_fact("tlq_op_type", self.globals[op_type], lab_op)

        # initialize state as unused and with nothing in input slot
        lab_op.add_property('unused')
        lab_op.add_property('empty_a')

        # to support performing ops on multiple materials
        mix = self.new_lab_entity(entity_type='mx')
        lab_op.add(mix, input_slot='a')

        return lab_op
        

