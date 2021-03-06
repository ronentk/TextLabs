
from typing import List, Mapping, Union
from dataclasses import dataclass
from tw_textlabs.generator.data import KnowledgeBase
from tw_textlabs.generator.game import Quest, CompactAction
from tw_textlabs.generator.templated_text_generator import TemplatedTextGenerator, templatize_text, templatize_text_list
from tw_textlabs.generator.token_generators import TokenGenerator
from tw_textlabs.generator.process_graph import ProcessGraph, IGNORE_CMD, EntityNode
from numpy.random import RandomState, randint
from tw_textlabs.utils import quest_gen_logger


REVERSE_ACTS = { 'take', 'obtain' } # actions to reverse so that graph flow is more legible


# Descriptions used upon examining entities in game.
descriptions = {
            'm': 'A material.',
            'mx': 'A mixture, which is a type of material. Composed of a number of materials.',
            'tlq_op': 'A TextLabQuest operation.',
            'sa': 'A synthesis apparatus. Operations happen here!',
            'odsc': 'Operator descriptor.',
            'mdsc': 'Material descriptor.',
            'sdsc': 'Synthesis apparatus descriptor.',
            }

propositionals ={
        'describe': '{arg_2} with {arg_1}'
        }

# Basic dynamic tokens
DT_LIST = [
          ("FIRST", "##First|To start##"),
          ("MIDDLE", "##Next|After that|Following that|In the next stage##"),
          ("FINAL", "##Finally|To finish##"),
          ("IMP_REF", "##them|the result##"),
          ("INIT_MATERIALS", "The ##initial|starting## material"),
          ("RESULT", "the ##result of|result obtained by##")
        ]

# Commands to omit from the quest instructions (need to be implicitly 
# understood). Can be configured for each difficulty mode.       
SKIP_ACTIONS_BY_MODE = {
        'easy': { 'op_type': True },
        'medium': { 'obtain': True, 
                    'take': True,
                    'op_type': True
                 },
        'hard': { 'obtain': True, 
                    'take': True,
                    'op_type': True
                 },
        'debug': { }
            
        }
        

# Entity types to replace by implicit references (e.g., 'mix them'). Can be 
# configured for each difficulty mode.       
IMPLICIT_ARGS_BY_MODE = {
        'easy': { },
        'medium': { 'mx': True },
        'hard': { 'mx': True },
        'debug': {}
            
        }

class SurfaceGenerationOptions:
    """ 
    Helper class for generating the text for a sketch.
    Surface text generation parameters controlled by options (SurfaceGenerationOptions).
    
    Arguments:
        difficulty_mode: determines complexity of generated text, by merging
        actions, skipping actions and implicit references. Setting the
        difficulty mode will automatically set the rest of the options unless
        these are explicitly set. Possible options: ["easy", "medium", "hard"]
        
    """
    __slots__ = ['op_type_map','difficulty_mode', 'merge_parallel_actions', 'merge_serial_actions', 'implicit_refs', 'preset_ops', 'seed']

    def __init__(self, options=None, **kwargs):
        if isinstance(options, SurfaceGenerationOptions):
            options = options.serialize()

        options = options or kwargs

        self.seed = options.get("seed", randint(65535))
        self.difficulty_mode = options.get("difficulty_mode", "easy")
        self.merge_parallel_actions = options.get("merge_parallel_actions", True)
        self.merge_serial_actions = options.get("merge_serial_actions", (self.difficulty_mode != "easy"))
        self.implicit_refs = options.get("implicit_refs", (self.difficulty_mode != "easy"))
        self.preset_ops = options.get("preset_ops", False)
        self.op_type_map = options.get("op_type_map", {})

    def set_difficulty_mode(self, mode: str) -> None:
        """Set the generation flags according to difficulty."""
        self.difficulty_mode = mode
        self.merge_parallel_actions = True
        self.merge_serial_actions = (self.difficulty_mode != "easy")
        self.implicit_refs = (self.difficulty_mode == "hard")

    def serialize(self) -> Mapping:
        return {slot: getattr(self, slot) for slot in self.__slots__}

    @classmethod
    def deserialize(cls, data: Mapping) -> "SurfaceGenerationOptions":
        return cls(data)

    def __eq__(self, other) -> bool:
        return (isinstance(other, SurfaceGenerationOptions) and
                all(getattr(self, slot) == getattr(other, slot) for slot in self.__slots__))

    @property
    def uuid(self) -> str:
        """ Generate UUID for this set of surface generator options. """
        def _unsigned(n):
            return n & 0xFFFFFFFFFFFFFFFF
        
        # skip difficulty mode and map
        values = [int(getattr(self, s)) for s in self.__slots__[2:]]
        option = "".join(map(str, values))

        from hashids import Hashids
        hashids = Hashids(salt="TextWorld")
        return  "lab-" + hashids.encode(int(option))


@dataclass
class CommandSurface:
    """
    Represents the surface mention corresponding to one or more actions (possibly
    grouped together).
    string: 
        command mention string appearing in the surface.
    cnt:
        id to differentiate between identical commands appearing in the 
        surface at different times.
    """
    string: str
    # 
    cnt: int 
    
    def ignore(self):
        return self.string == IGNORE_CMD
    
    def __hash__(self):
        return hash((self.string, self.cnt))
    
    def __str__(self):
        return '%s_%d' % (self.string, self.cnt)
    
    def __repr__(self):
        return '%r_%r)' % (self.string, self.cnt)


def get_cmd_count(cmd: str, cmd_sur_list: List[CommandSurface]) -> int:
    cmd_list = [cs.string for cs in cmd_sur_list]
    return cmd_list.count(cmd)
    
def compact_action_to_unary_cmd(compact_action: CompactAction) -> str:
    arg = compact_action.vars[0] if compact_action.vars else ''
    return compact_action.name + ' ' + arg.name

def get_action_counts(actions_list: List[str]) -> Mapping:
    unique_acts = set(actions_list)
    return {a: actions_list.count(a) for a in unique_acts}

def list_to_contents_str(l: List[str]) -> str:
    """ 
    Given a list of entities [X,Y,Z], return string "X, Y and Z" ( or just "X" 
    for single entity)
    """
    if len(l) > 1:
        res = '%s and %s' % (', '.join(l[:-1]), l[-1])
    elif len(l) == 1:
        res = l[0]
    else:
        res = ''
    return res

class SurfaceGenerator:
    """ 
    Helper class for generating the text for a sketch. This includes the quest description (instructions), 
    and names/descriptions of the entities comprising the quest.
    Arguments:
        seed: sets specified seed for the random number generator used for 
        text generation. 
        surface_gen_options: options controlling Surface text generation parameters  (SurfaceGenerationOptions).
    """
    def __init__(self, surface_gen_options: Union[SurfaceGenerationOptions, Mapping] = {} ):
        self.seed = surface_gen_options.seed
        self.rng = RandomState(self.seed)
        self.surface_gen_options = SurfaceGenerationOptions(surface_gen_options)
        self.difficulty_mode = self.surface_gen_options.difficulty_mode
        self.merge_parallel_actions = self.surface_gen_options.merge_parallel_actions
        self.merge_serial_actions = self.surface_gen_options.merge_serial_actions
        self.implicit_refs = self.surface_gen_options.implicit_refs
        self.ttg = TemplatedTextGenerator(self.seed)
        self.ttg.register_token_generators(DT_LIST)
   
    def get_parallel_actions(self, pg: ProcessGraph) -> Mapping[str, CommandSurface]:
        """
        Get all parallel actions in action graph. Specifically, all incoming edges
        to nodes with in degree > 1. This is to allow merging of multiple 
        identical commands to one. For example, this would change the sequence 
        "mix X. Mix Y. Mix Z." into "Mix X,Y and Z"
        
        Parameters
        ----------
        pg: Process Graph representing a material synthesis procedure.
        
        Returns
        -------
        mapping:
            mapping between the string ids of the parallel actions and their
            corresponding CommandSurface.
        """
        parallel_action_map = {}
        # TODO only works if no mixtures as start materials
        num_start_mats = len([v for v in pg.ent_states_map.keys() if v.type == 'm'])
        
        # find all nodes with in degree greater than 1
        parallel_acts_targets = [n for n in pg.G.nodes() if pg.G.in_degree(n) > 1]
        
        for node in parallel_acts_targets:
            node_act_map = {}
            incoming_actions = pg.get_incoming_actions(node)
            # Get number of incoming actions of each type.
            act_counts = get_action_counts([ae.action for ae in incoming_actions])
            for ae in incoming_actions:
                action = ae.action
                if action in SKIP_ACTIONS_BY_MODE[self.difficulty_mode]:
                    continue
                if (act_counts[ae.action]): 
                    if (act_counts[action] > 1):
                        if KnowledgeBase.default().types.is_descendant_of(ae.source.var.type, 'm'):
                            # If we're merging actions, and all starting materials participate
                            # in action, the action argument should be simply 'materials'
                            if (act_counts[action] == num_start_mats) and self.surface_gen_options.implicit_refs:
                                cmd = '%s the materials' % (action)
    
                            # If not all starting materials participating, refer to 
                            # each by name (e.g., X, Y and Z)
                            else:
                                target_mats = [ae.source.var.name for ae in \
                                               incoming_actions if ae.action == action]
                                cmd = '%s %s' % (action,
                                                 list_to_contents_str(
                                                templatize_text_list(target_mats)))
                        elif KnowledgeBase.default().types.is_descendant_of(ae.source.var.type, 'dsc'):
                            target_descs = [ae.source.var.name for ae in \
                                               incoming_actions if ae.action == action]
                            arg_1 = list_to_contents_str(templatize_text_list(target_descs))
                            arg_2 = templatize_text(ae.target.var.name)
                            arg_str = propositionals[ae.action].format(**{'arg_1': arg_1,
                                                    'arg_2': arg_2})
                            cmd = '%s %s' % (action, arg_str)
                        # if there are commands with an identical surface
                        # representation, differentiate between them using cnt
                        cnt = get_cmd_count(cmd, 
                                            list(parallel_action_map.values()))
                        
                        # index each edge in action graph, such that it refers 
                        # to relevant surface text.
                        node_act_map[str(ae)] = CommandSurface(cmd, cnt)
            parallel_action_map.update(node_act_map)
        return parallel_action_map

    def get_serial_actions(self, pg: ProcessGraph) -> Mapping[str, CommandSurface]:
        """
        Get all serial actions in action graph. Specifically, all chains of at
        least 2 consecutive actions on a single material. This is to allow 
        merging of multiple identical commands to one. For example, this would
        change the sequence "grind X. melt X." to "grind and melt X"
        
        Parameters
        ----------
        pg: Process Graph representing a material synthesis procedure.
        
        Returns
        -------
        mapping:
            mapping between the string ids of the serial actions and their
            corresponding CommandSurface.
        """
        serial_act_to_surface_map = {}
        for var, state_nodes in pg.ent_states_map.items():
            if KnowledgeBase.default().types.is_descendant_of(var.type,'m'):
                if len(state_nodes) > 2: # >2 state changes, we can merge them
                    ap = pg.get_actions_path(state_nodes[0], state_nodes[-1])
                    actions = [ae.action for ae in ap if ae.action not in SKIP_ACTIONS_BY_MODE[self.difficulty_mode]]
                    if len(actions) > 1:
                        cmd = '%s %s' % (list_to_contents_str(actions),
                                         templatize_text(var.name))
                    elif len(actions) == 1:
                        cmd = '%s %s' % (templatize_text(actions[0]), var.name)
                    else:
                        cmd = IGNORE_CMD
                    # if there are commands with an identical surface
                    # representation, differentiate between them using cnt
                    cnt = get_cmd_count(cmd,
                                        list(serial_act_to_surface_map.values()))
                    for ae in ap:
                        serial_act_to_surface_map[str(ae)] = CommandSurface(cmd,
                                                  cnt)
        return serial_act_to_surface_map
                      
    
        
    def assign_actions_to_ops(self, pg: ProcessGraph) -> ProcessGraph:
        """
        For each operation node, replace incoming "assign" edges with the action name.
        """
        op_nodes = [n for n in pg.G.nodes() if n.var.type == 'tlq_op']
        for op in op_nodes:
            if self.surface_gen_options.preset_ops:
                op_type = self.surface_gen_options.op_type_map[op.var.name]
            else:
                op_type = pg.get_op_type(op)
            action_with_id = '{} ({})'.format(templatize_text(op_type), 
                              templatize_text(op.var.name))
            pg.rename_edges(op, 'op_ia_assign', action_with_id)
            
        dsc_nodes = [n for n in pg.G.nodes() if \
                     KnowledgeBase.default().types.is_descendant_of(n.var.type, 'dsc')]
        for node in dsc_nodes:
            pg.rename_edges(node, 'dlink', 'describe', incoming=False)
        
            
    
    def build_quest_to_surface_map(self, quest: Quest) -> Mapping:
        """
        Build map of all actions comprising this quest and their corresponding
        surface mention (CommandSurface).
        """
        pg = ProcessGraph()
        pg.from_tw_actions(quest.actions)
        self.assign_actions_to_ops(pg)
        action_to_surface_map = {}
        
        for ae in pg.topological_sort_actions():
            if ae.action in SKIP_ACTIONS_BY_MODE[self.difficulty_mode]:
                action_to_surface_map[str(ae)] = CommandSurface(IGNORE_CMD, 0)
            else:
                # Handle implicit references - replace material types
                # with implicit ref such as 'them' - currently doesn't
                # differentiate between plural and singular
                if self.implicit_refs and ae.source.var.type in \
                IMPLICIT_ARGS_BY_MODE[self.difficulty_mode]:
                    arg_name = templatize_text('IMP_REF')
                else:
                    arg_name = (ae.target.var.name if ae.action \
                                in REVERSE_ACTS else ae.source.var.name)
                    arg_name = templatize_text(arg_name)
                    
                if ae.action in propositionals:
                    arg_1 = arg_name
                    arg_2 = (ae.source.var.name if ae.action \
                                in REVERSE_ACTS else ae.target.var.name)
                    arg_2 = templatize_text(arg_2)
                    arg_str = propositionals[ae.action].format(**{'arg_1': arg_1,
                                            'arg_2': arg_2})
                else:
                    arg_str = arg_name
                    
                cmd = '%s %s' % (ae.action, arg_str)
                
                cnt = get_cmd_count(cmd, list(action_to_surface_map.values()))
                action_to_surface_map[str(ae)] = CommandSurface(cmd, cnt)

        # Handle parallel/serial action merging according to flags.
        if self.merge_parallel_actions:
            action_to_surface_map.update(self.get_parallel_actions(pg))
        if self.merge_serial_actions:
            action_to_surface_map.update(self.get_serial_actions(pg))
        
        # Count amount of actions each CommandSurface covers, so that we will 
        # only append the command surface to the generated text when the last
        # action of the command is taken.
        cmd_sur_list = [str(cs) for cs in action_to_surface_map.values()]
        cmds_num_use_left = {str(cs): cmd_sur_list.count(str(cs)) for cs in cmd_sur_list}
        return action_to_surface_map, cmds_num_use_left
     
    def replace_mixtures_by_ref(self, pg: ProcessGraph) -> ProcessGraph:
        """ Implicit references for operation results- substitutions such as 'grind MX' with 'grind the result of OP' """
        if self.surface_gen_options.implicit_refs:
            mix_nodes = [n for n in pg.G.nodes() if n.var.type == 'mx']
            for mix in mix_nodes:
                source_op = pg.get_source_op(mix)
                if source_op:
                    tg_string =  "~~RESULT~~ ~~{}~~".format(source_op.var.name)
                    tg = TokenGenerator(symbol=mix.var.name,
                                                     tgstring=tg_string,
                                                     seed=self.ttg.seed,
                                                     token_generator_map=self.ttg.token_generators_dict)
                    self.ttg.register_token_generator(tg, override=True)             
        
        
    def entity_to_name(self, entity_type: str, internal_name: str = None) -> str:
        """Generate name for each entity mentioned. """
        entity_name = self.ttg.generate_entity(entity_type, internal_name)
        return entity_name
        
    def quest_to_surface(self, quest: Quest) -> str:
        """
        Generate surface corresponding to given quest (action graph).
        
        Parameters
        ----------
        quest: TextWorld Quest.
        
        Returns
        -------
        surface:
            Text description overlaying the given Quest.
        
        """
        ttg_string = ""
        pg = ProcessGraph()
        pg.from_tw_actions(quest.actions)
        self.assign_actions_to_ops(pg)
        self.replace_mixtures_by_ref(pg)
        action_to_surface_map, cmds_num_use_left = self.build_quest_to_surface_map(quest)
        actions = pg.topological_sort_actions()
        actual_cmds = []
        if self.difficulty_mode == "debug":
            return [str(ae) for ae in actions]
        
        for ae in actions:
            cmd_surface = action_to_surface_map[str(ae)]
            if cmd_surface.ignore():
                continue
            
            # only append the command surface to the generated text when the last
            # action of the command is taken.
            if cmds_num_use_left[str(cmd_surface)] > 0:
                cmds_num_use_left[str(cmd_surface)] -= 1
            if cmds_num_use_left[str(cmd_surface)] == 0:
                actual_cmds.append(cmd_surface.string)
        
        # Start with sentence describing initial materials
        start_material_names = [mat.name for mat in pg.get_start_material_vars()]
        start_material_desc = templatize_text('INIT_MATERIALS') + \
        ('s are ' if len(start_material_names) > 1 else ' is ') + \
        ('%s' % list_to_contents_str(templatize_text_list(start_material_names))) + '. '
        # Add the surface corresponding to each command
        first_action = actual_cmds.pop(0)
        last_action = actual_cmds.pop()
        first_action_string = '~~FIRST~~, ' + first_action + '. ' 
        mid_actions_string = '. '.join(['~~MIDDLE~~, ' + mid_action for mid_action in actual_cmds]) + ('. ' if actual_cmds else '')
        final_action_string = '~~FINAL~~, ' + last_action + '.'
        ttg_string = start_material_desc + first_action_string + mid_actions_string + final_action_string
        return self.ttg.instantiate_template_text(ttg_string)
    
    
    
            
        
        