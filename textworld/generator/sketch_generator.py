from numpy.random import RandomState, randint
from typing import Mapping, Optional, Sequence, Callable, List
from dataclasses import dataclass, field
from copy import deepcopy
from enum import Enum

from textworld.generator.data import KnowledgeBase
from textworld.generator.scoring_priority_queue import ScoringPriorityQueue
from textworld.generator.chaining import _Node, _Chainer, Chain, ChainingOptions
from textworld.logic import Action, Proposition, State, Variable, Signature, CompactAction
from textworld.generator.game import gen_commands_from_actions
from textworld.utils import quest_gen_logger, uniquify

NEW_STATE = -1

# Default mapping defining minimum/maximum uses per device
def default_usage_map() -> Mapping:
    from textworld.generator.data import KnowledgeBase
    device_types = uniquify(KnowledgeBase.default().types.descendants('sa'))
    return {d: 1 for d in device_types}
    
class QuestNotFoundError(RuntimeError):
    def __init__(self):
        msg = "No quest found within time limit."
        super().__init__(msg)

class WinConditionType(Enum):
    """
    Used to determine which propositions are relevant for determining the 
    winning conditions.
    """
    LAST_ACTION_POST = 1 # postconditions of the last action in the quest.
    MAT_STATES = 2 # material states match final state
    POST_AND_STATES = 3 # union of 1,2
    RESULTS = 4 # check all result_new and result_mod predicates exist
    ALL = 5 # union of 3,4.

# These are fixed, our generation options controlled in SketchGenerationOptions
def default_chaining_options():
    options = ChainingOptions()
    options.backward = False
    options.create_variables = False
    options.max_depth = 1000 
    options.max_breadth = 1
    return options
    
@dataclass
class SketchGenerationOptions:
    """ 
    Options controlling sketch generation.
    
    Attributes:
        max_depth: 
            Maximum number of actions comprising the minimal winning 
        policy.
        max_steps:
            Maximum number of steps for quest generation search.
       win_condition:
           Controls how winning conditions for the generated quest will be 
           defined. See WinConditionType for the options.
       quest_rng: 
           Random number generator determining order of quests if multiple
           quests generated. Not currently used.
       min_uses_per_device: 
           Generated quest must include at least this number of uses per device.
           Must be specified for each device in 'devices'.
       max_uses_per_device:
           Generated quest may include at most this number of uses per device.
           Must be specified for each device in quest.
    """
    max_depth: int = 10
    max_steps: int = 1000
    win_condition: WinConditionType = WinConditionType.ALL
    quest_rng: RandomState = RandomState(randint(65535))
    min_uses_per_device: Mapping = field(default_factory=default_usage_map)
    max_uses_per_device: Mapping = field(default_factory=default_usage_map)

@dataclass
class DeviceObjectives:
    """ 
    Used during search for valid quest, represents current state of device
    usage at current search node. A device objective will be considered fulfilled
    if max_uses >= nb_uses >= min_uses.
    """
    name: str
    min_uses: int = 1
    max_uses: int = 1
    nb_uses: int = 0 # number of current uses
    
    def completed(self) -> bool:
        return self.nb_uses >= self.min_uses and self.nb_uses <= self.max_uses
    
    def __copy__(self):
        return type(self)(name=self.name,
                    min_uses=self.min_uses,
                    max_uses=self.max_uses,
                    nb_uses=self.nb_uses)
    
    def __deepcopy__(self, memo): # memo is a dict of id's to copies
        id_self = id(self)        # memoization avoids unnecesary recursion
        _copy = memo.get(id_self)
        if _copy is None:
            _copy = type(self)(
                name=deepcopy(self.name, memo), 
                min_uses=deepcopy(self.min_uses, memo),
                max_uses=deepcopy(self.max_uses, memo),
                nb_uses=deepcopy(self.nb_uses, memo)
                )
            memo[id_self] = _copy 
        return _copy
        

class SketchGenerator:
    """
    Helper class for generating quests (sketches) consistent with domain 
    world-model.
    Can be created with a domain specifc scoring function used to measure the
    utility of a given world state.
    Sketch generation parameters controlled using options (SketchGenerationOptions).
    """
    def __init__(self, start_state: State, scorer: Callable = None, quest_gen_options: SketchGenerationOptions = None) -> None:
        self.start_state = start_state
        self.q = ScoringPriorityQueue(scorer)
        self.options = SketchGenerationOptions() if not quest_gen_options else quest_gen_options
        chainer_options = default_chaining_options()
        chainer_options.rng = quest_gen_options.quest_rng
        self.chainer = _Chainer(self.start_state, chainer_options)
    
    def goal_check(self, node: _Node) -> bool:
        """ Default goal objective is simply a node of the default depth. """
        if node.depth >= self.options.max_depth:
            return True
        else:
            return False
    
    def generate_quest(self) -> Optional[Chain]:
        """ 
        Breadth-First-Search for a game state satisfying goal state objectives,
        within the specified number of search steps.
        """
        steps = 0
        self.q.push(self.chainer.root())
        quest_gen_logger.info("Searching for quest satisfying constraints...")
        while not self.q.queue.empty() and (steps < self.options.max_steps):
            node = self.q.get_next()
            quest_gen_logger.debug("Step #%d | Action is %s | Q size: %d" % (steps,
                                   gen_commands_from_actions([node.action] \
                                    if node.action else []), self.q.size()))
            if self.goal_check(node):
                quest_gen_logger.info("Found solution!")
                quest_gen_logger.debug("Reached goal state: %s" %
                                       (str(node.state)))
                return self.chainer.make_chain(node)
            if not node.valid:
                continue
            # expand node to visit children
            for child in self.chainer.chain(node):
                self.q.push(child)
            steps += 1        
        raise QuestNotFoundError()
 
# Convert Action to compact form and store information about variables changing state.
def convert_to_compact_action(action: Action) -> CompactAction:
    compact_action = gen_commands_from_actions([action], compact_actions=True)[0]
    change_state_vars = []
    for var in compact_action.vars:
        # check if action causes a new state for involved variables.
        # Currently only checking materials
        # TODO - clean up
        state_change_props = [prop for prop in action.added if (var in \
                        prop.arguments and 'result' in prop.name and \
                        KnowledgeBase.default().types.is_descendant_of(
                                var.type,'m'))]
        if state_change_props:
            change_state_vars.append(var)
    compact_action.change_state_vars = change_state_vars
    return compact_action
    


# Check if any device in this state has been used more than allowed.
def check_max_uses(node: _Node) -> bool:
    for device_obj in node.data['device_objs'].values():
        if LabSketchGenerator.use_device_check(node, device_name=device_obj.name):
            if (node.data['device_objs'][device_obj.name].nb_uses > \
                node.data['device_objs'][device_obj.name].max_uses):
                return False
    return True
    
# Currently disallowing mixing mixtures (only allowed to mix base materials)
def check_mixing_mixture(node: _Node) -> bool:
    action = node.action
    short_action_name = action.name.split('/')[0]
    if not short_action_name in ['mix']:
        return True
    target_mat = convert_to_compact_action(action).vars[0]
    return target_mat.type != 'mx'

# Check whether a base material being mixed
def heur_mix_base_mat(node: _Node) -> bool:
    if not node.action:
        return False
    action = node.action
    short_action_name = action.name.split('/')[0]
    if not short_action_name in ['mix']:
        return False
    target_mat = convert_to_compact_action(action).vars[0]
    return target_mat.type == 'm'

def check_open_close_act(node: _Node) -> bool:
    """ Check whether this action was open/close on a lab_container type """
    if not node.action:
        return False
    c_act = convert_to_compact_action(node.action)
    short_action_name = c_act.name.split('/')[0]
    return (short_action_name in ['open', 'close'] and 
    KnowledgeBase.default().types.is_descendant_of(
                                c_act.vars[0].type,'lc'))
        
        
    

def check_name_in_prop_list(name: str, prop_list: Sequence[Proposition]) -> bool:
        for prop in prop_list:
            if name in prop.names:
                return True
        return False
    
    
class LabSketchGenerator(SketchGenerator):
    """
    Helper class for the generating lab-specific quests.
    """
    def __init__(self, **kwargs):
        super(LabSketchGenerator, self).__init__(**kwargs)
        self.device_objectives = []
        self.start_materials = self.get_start_materials()
        self.states = {}
        self.q.set_scorer(self.lab_quest_scorer)
        self.set_device_objectives()
        # validity checks for every search state
        self.node_checks = {
                'check_max_uses': check_max_uses,
                'check_mixing_mixture': check_mixing_mixture,
                'check_depth': self.check_depth,
                'check_node_state': self.check_node_state
                }
      
    def lab_quest_scorer(self, node: _Node) -> int:
        """ 
        Simple heuristic score function for search states. The higher the score,
        the lower the search priority.
        """
        score = 10
        
        # TODO these should be grouped as "heuristic functions"
        
        # Reward expanding unseen states
        if self.check_existing_state(node.state) == NEW_STATE:
            score -= 2
        # Reward mixing a base material into a mixture
        if heur_mix_base_mat(node):
            score -= 3
        # Penalize open/closing a container (not needed in these quests)
        if check_open_close_act(node):
            score += 5
        
        
        return score
    
    def get_start_materials(self) -> List[str]:
        materials = []
        for mat in self.start_state.variables_of_type('m'):
                materials.append(mat)
        return materials
    
    def check_active_mixture(self, state: State, mixture: Variable) -> bool:
        """ 
        Return whether given mixture is active in given state. 
        An active mixture is a mixture containing some other material.
        """
        all_active_mixture_props = list(state.facts_with_signature(Signature('component',['m','mx'])))
        mxs = [mx for (m, mx) in [prop.names for prop in all_active_mixture_props]]
        return (mixture.name in mxs)
            
            
    # return true if any of the mixtures contains all start materials
    def check_materials_same_mixture(self, state: State) -> bool:
        if len(self.start_materials) == 1:
            return True # no mixture if only one start material
        
        mixtures = self.start_state.variables_of_type('mx')

        # Check all materials contained in some mixture
        for mat in self.start_materials:
            mat_mixed_props = [Proposition('component', arguments=[mat, mixture]) for mixture in mixtures]
            if not state.any_facts(mat_mixed_props):
                return False
        
        # Check that only one parent mixture not (contained by other mixture and active)
        n_parent_mixtures = 0
        for mixture in mixtures:
            # check if active (out of potential)
            if not self.check_active_mixture(state, mixture):
                continue
            # check if contained in other mixtures
            mixed_props = [Proposition('component', arguments=[mixture, mx]) for mx in mixtures]
            
            if state.any_facts(mixed_props):
                continue
            else:
                n_parent_mixtures += 1
                
        return (n_parent_mixtures == 1)
        
    
    def set_device_objectives(self) -> None:
        """ Set device objectives for all devices to be used in this quest. """
        all_device_types = KnowledgeBase.default().types.descendants('sa')
        for device_type in all_device_types:
            for device in self.start_state.variables_of_type(device_type):
                # Only add device objectives for devices in Lab (not in Limbos)
                if self.start_state.is_fact(Proposition('at', arguments=[device,
                                    self.start_state.variable_named('r_0')])):
                    device_objective = DeviceObjectives(name=device.name,
                    min_uses=self.options.min_uses_per_device[device_type],
                    max_uses=self.options.max_uses_per_device[device_type])
                    self.device_objectives.append(device_objective)
    
    
    
    def use_device_check(node: _Node, device_name: str) -> bool:
        # check if this state completes a device objective
        action = node.action # the action that lead to this state
        return check_name_in_prop_list(device_name, action.postconditions)
    
    def check_existing_state(self, state: State) -> int:
        for k,existing_state in self.states.items():
            if state == existing_state:
                return k
        return NEW_STATE
    
    def check_node_state(self, node: _Node) -> bool:
        return self.check_existing_state(node.state) != NEW_STATE
    
    def check_depth(self, node: _Node) -> bool:
        return node.depth <= self.options.max_depth
    
    # Checks whether state is new, store it if so and return its id
    def register_state(self, state: State) -> int:
        res = self.check_existing_state(state)
        if res != NEW_STATE:
            return res
        else:
            state_id = len(self.states) + 1
            self.states[state_id] = state
            return state_id
    
    # Handle update of data upon visiting new node.
    def update_visit_data(self, node: _Node) -> None:
        self.register_state(node.state)
        # Copy device obj. information from parent node or create new if needed
        if not 'device_objs' in node.data:
            node.data['device_objs'] = {}
            if node.parent:
                dev_objs = node.parent.data['device_objs'].values()
            else:
                dev_objs = self.device_objectives
    
            for device_obj in dev_objs:
                node.data['device_objs'][device_obj.name] = deepcopy(device_obj)

        action = node.action # the action that lead to this state
        if not action:
            return
        
        # check state is valid
        self.check_node(node)
        
        # Update device objective use counts
        for device_obj in node.data['device_objs'].values():
            if LabSketchGenerator.use_device_check(node,
                                                device_name=device_obj.name):
                quest_gen_logger.debug("Used device %s" % (device_obj.name))
                node.data['device_objs'][device_obj.name].nb_uses += 1

    # Run domain specific validity checks for given state
    def check_node(self, node: _Node) -> None:
        for check_name,check in self.node_checks.items():
            if check(node) == False:
                quest_gen_logger.debug("failed at check: %s" % (check_name))
                node.valid = False
    
    # Check if final quest state domain specific conditions hold. 
    def goal_check(self, node: _Node) -> bool:
        self.update_visit_data(node)
        for device_obj in node.data['device_objs'].values():
            if not device_obj.completed():
                return False
        if not self.check_materials_same_mixture(node.state):
            return False
        return True
        
            

     
        
    