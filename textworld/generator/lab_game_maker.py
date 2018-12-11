# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT license.



from typing import Iterable, Union, Optional
try:
    from typing import Collection
except ImportError:
    # Collection is new in Python 3.6 -- fall back on Iterable for 3.5
    from typing import Iterable as Collection

import textworld

from textworld.generator.data import KnowledgeBase
from textworld.logic import State, Proposition, Action, Signature
from textworld.generator.game import Game, World, Quest, UnderspecifiedQuestError, Event
from textworld.generator.surface_generator import SurfaceGenerator, descriptions
from textworld.generator.chaining import Chain
from textworld.generator.maker import GameMaker, WorldEntity
from textworld.generator.sketch_generator import LabSketchGenerator, convert_to_compact_action, SketchGenerationOptions, WinConditionType
from textworld.utils import quest_gen_logger
from textworld.generator.process_graph import MATERIAL_STATES


def get_material_state_facts(state: State, material_type: str = 'm', 
                             mat_states: Union[str] = MATERIAL_STATES
                             ) -> Collection[Proposition]:
    """
    Get all facts from current game state describing material states.
    """
    mat_state_facts = set()
    for mat_state in mat_states:
        mat_state_facts.update(state.facts_with_signature(Signature(mat_state,[material_type])))
    return mat_state_facts

def get_result_facts(state: State, 
                     result_types: Union[str] = {'result_mod', 'result_new'}
                     ) -> Collection[Proposition]:
    """
    Get all facts from current game state describing result propositions.
    These are used to record events of production or modification of materials.
    """
    result_facts = set()
    for fact in state.facts:
        if fact.name in result_types:
            result_facts.update(set([fact]))
    return result_facts
    

def get_win_conditions(chain: Chain, 
                       win_condition_type: WinConditionType = WinConditionType.ALL
                       ) -> Collection[Proposition]:
    """
    Given a chain of actions comprising a quest, return the set of propositions
    which must hold in a winning state.
    
    Parameters
    ----------
    win_condition_type:
        Type of win condition used to determine the relevant propositions.
        
    Returns
    -------
    win_conditions:
        Set of propositions which must hold as post-conditions of the last 
        action of the quest.
    """
    win_conditions = set()
    if win_condition_type in [WinConditionType.MAT_STATES,
                         WinConditionType.POST_AND_STATES,
                         WinConditionType.ALL]:
        # disregard final state of mixture to remain agnostic to mixing order.
        # See #12. Note that if mixture state is post condition of last action
        # and these are part of winning condition, it will be included.
        base_material_states = get_material_state_facts(chain.final_state, material_type='m').difference(get_material_state_facts(chain.final_state, material_type='mx'))
        
        # Include mixture compositions as winning condition
        win_conditions.update(
        base_material_states.union(
                chain.final_state.facts_with_signature(Signature('component', ['m', 'mx']))))
    if win_condition_type in [WinConditionType.LAST_ACTION_POST,
                         WinConditionType.POST_AND_STATES,
                         WinConditionType.ALL]:
        if len(chain.actions) == 0:
            raise UnderspecifiedQuestError()

        # Disregard state of mixture if postcondition of mixing action
        # since we don't want mixing order to affect the winning condition
        post_props = set(chain.actions[-1].postconditions)
        if 'mix' in chain.actions[-1].name:
            mixture_state_props = {prop for prop in post_props if prop.name in MATERIAL_STATES and prop.arguments[0].type == 'mx'}
            post_props.difference_update(mixture_state_props)
        
        # The default winning conditions are the postconditions of the
        # last action in the quest.
        win_conditions.update(post_props)
        
    if win_condition_type in [WinConditionType.ALL, WinConditionType.RESULTS]:
        result_facts = get_result_facts(chain.final_state)
        win_conditions.update(result_facts)
        
    
   
    return Event(conditions=win_conditions)

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
        self._quests = []
        self.rooms = []
        self.paths = []
        self._types_counts = KnowledgeBase.default().types.count(State())
        self.player = self.new(type='P')
        self.inventory = self.new(type='I')
        self.sg = surface_generator
        self._game = None
        self._quests_str = []
        self._distractors_facts = []


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
        game = Game(world, quests=self._quests)

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

        game.metadata["desc"] = "Generated with textworld.GameMaker."

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
        game_file = textworld.generator.compile_game(self._working_game, path, force_recompile=True)
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

    
    def generate_quest_surface_pair(self, quest_gen_options: SketchGenerationOptions) -> Quest:
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
    
    def generate_quest(self, quest_gen_options: SketchGenerationOptions) -> Quest:
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
        quest_gen = LabSketchGenerator(start_state=world.state,
                                      quest_gen_options=quest_gen_options)
        quest_gen.set_device_objectives()
        chain = quest_gen.generate_quest()
        quest_gen_logger.info("Found quest: %s" % (str([convert_to_compact_action(a) for a in chain.actions])))
        win_event = get_win_conditions(chain,
                                    quest_gen_options.win_condition)
        win_event.actions = chain.actions
        quest = Quest(win_events=[win_event], commands=self.i7_commands_from_actions(chain.actions),
                      actions=chain.actions)
        self._quests = [quest]
#        self._quests_str = [[convert_to_compact_action(a) for a in chain.actions]]
        return quest

    def set_quest_description(self, surface: str) -> None:
        """ Set quest description with given Surface text"""
        if len(self._quests) > 0:
            self._quests[0].desc = surface

    def action_to_i7_command(self, action: Action) -> str:
        """ Convert an action to the corresponding command in Inform7"""
        action_vars = convert_to_compact_action(action)
        i7command_template = KnowledgeBase.default().inform7_commands[action.name]
        new_cmd = []
        ents = [self._entities[v.name] for v in action_vars.vars]
        ents.reverse()
        for w in i7command_template.split(' '):
            if (('{' in w) and ('}' in w)):
                new_cmd.append(ents.pop().name)
            else:
                new_cmd.append(w)
        assert(len(ents) == 0)
        return ' '.join(new_cmd)
        
        
    def i7_commands_from_actions(self, actions: Iterable[Action]) -> Iterable[str]:
        """Get list of all Inform7 commands corresponding to list of actions. """
        return [self.action_to_i7_command(a) for a in actions]
    
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
    
    def new_lab_container(self, name: Optional[str] = None,
            desc: Optional[str] = None, absolute_name: Optional[str] = None, 
            num_uses: Optional[int] = 1) -> WorldEntity:
        """ 
        Create new lab_container entity.

        Args:
            name: The name of the entity.
            desc: The description of the entity.
            num_uses: Maximum number of separate mixtures that can be created
            using this lab_container. Currently only one use per lab_container
            is supported.

        Returns:
            The newly created `lab_container` entity.

        """
        lab_container = self.new_lab_entity('lc')
        lab_container.add_property('open')
#        lab_container.add_property('unsealed') # TODO not yet used
        for n in range(num_uses):
            # TODO single-arg-mvp: hack that only works if we have one mixture.
            mix = self.new_lab_entity(entity_type='mx')
            lab_container.add(mix)
        return lab_container
        

