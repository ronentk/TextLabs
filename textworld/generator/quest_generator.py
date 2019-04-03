from numpy.random import RandomState, randint
from typing import Mapping, Optional, Sequence, Callable, List, Collection
from dataclasses import dataclass, field
from copy import deepcopy
from enum import Enum
import networkx as nx
from collections import defaultdict

from textworld.generator.data import KnowledgeBase
from textworld.generator.scoring_priority_queue import ScoringPriorityQueue
from textworld.generator.chaining import _Node, _Chainer, Chain, ChainingOptions
from textworld.logic import Action, Proposition, State, Variable, Signature, CompactAction
from textworld.generator.game import gen_commands_from_actions, Quest, Event
from textworld.generator.process_graph import ProcessGraph
from textworld.utils import quest_gen_logger, uniquify

NEW_STATE = -1

# Default mapping defining minimum/maximum uses per device
def init_usage_map(m: int = 2) -> Mapping:
    from textworld.generator.data import KnowledgeBase
    ent_types = uniquify(KnowledgeBase.default().types.descendants('e'))
    return {d: m for d in ent_types}

def default_map() -> Mapping:
    d = defaultdict(list)
    return d 
class QuestNotFoundError(RuntimeError):
    def __init__(self, msg="No quest found within time limit."):
        super().__init__(msg)

class WinConditionType(Enum):
    """
    Used to determine which propositions are relevant for determining the 
    winning conditions.
    """
    OPS = 1 # All operation types are correct and performed in correct order with correct inputs
    ARGS = 2 # All descriptions set properly
    ALL = 3 # union of 1,2.

# These are fixed, our generation options controlled in QuestGenerationOptions
def default_chaining_options():
    options = ChainingOptions()
    options.backward = False
    options.create_variables = False
    options.max_depth = 1000 
    options.max_breadth = 1
    return options
    

@dataclass
class QuestGenerationOptions:
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
    max_depth: int = 30
    max_steps: int = 1000
    nb_ops: int = 2
    nb_materials: int = 3
    win_condition: WinConditionType = WinConditionType.ALL
    quest_rng: RandomState = RandomState(randint(65535))
    max_descs_per_ent: Mapping = field(default_factory=init_usage_map)
    ent_desc_map: Mapping = field(default_factory=default_map)
    preset_ops: bool = False
    quest_reward: int = 1
    


class QuestGenerator:
    """
    Helper class for generating quests (sketches) consistent with domain 
    world-model.
    Can be created with a domain specifc scoring function used to measure the
    utility of a given world state.
    Sketch generation parameters controlled using options (QuestGenerationOptions).
    """
    def __init__(self, start_state: State, scorer: Callable = None, quest_gen_options: QuestGenerationOptions = None) -> None:
        self.start_state = start_state
        self.q = ScoringPriorityQueue(scorer)
        self.options = QuestGenerationOptions() if not quest_gen_options else quest_gen_options
        chainer_options = default_chaining_options()
        chainer_options.rng = quest_gen_options.quest_rng
        self.chainer = _Chainer(self.start_state, chainer_options)
    
    def goal_check(self, node: _Node) -> bool:
        """ Default goal objective is simply a node of the default depth. """
        if node.depth >= self.options.max_depth:
            return True
        else:
            return False
    
    def generate_quest(self) -> Quest:
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
                chain = self.chainer.make_chain(node)
                win_event = self.get_win_conditions(chain)
                win_event.actions = chain.actions
                quest = Quest(win_events=[win_event],
                            actions=chain.actions,
                            reward=self.options.quest_reward)
                return quest
            if not node.valid:
                continue
            # expand node to visit children
            for child in self.chainer.chain(node):
                self.q.push(child)
            steps += 1        
        raise QuestNotFoundError()

    def get_win_conditions(self, chain: Chain) -> Collection[Proposition]:
        """
        Given a chain of actions comprising a quest, return the set of propositions
        which must hold in a winning state. By default this will be the post-conditions
        of the final action.
        
        Parameters
        ----------
        chain:
            Chain of actions leading to goal state.
            
        Returns
        -------
        win_conditions:
           Set of propositions which must hold to end the quest succesfully.
        """

        win_conditions = set()

        # add post-conditions from last action 
        post_props = set(chain.actions[-1].postconditions)
        win_conditions.update(post_props)
        
    
        return Event(conditions=win_conditions)

    
 
# Convert Action to compact form and store information about variables changing state.
def convert_to_compact_action(action: Action) -> CompactAction:
    compact_action = gen_commands_from_actions([action], compact_actions=True)[0]
    change_state_vars = []
    # recording the state change upon performing the obtain action - maybe not
    # most accurate semantically but we only use it currently for creating ProcessGraph
    # and in that case it makes sense (obtain corresponds to a 'result' edge)
    processed = [prop for prop in action.preconditions if ('output' in prop.name)]
    if processed:
        assert(len(processed) == 1)
        processed_var = processed[0].arguments[0]
        change_state_vars.append(processed_var)            
    compact_action.change_state_vars = change_state_vars
    return compact_action
    

    
    

def check_name_in_prop_list(name: str, prop_list: Sequence[Proposition]) -> bool:
        for prop in prop_list:
            if name in prop.names:
                return True
        return False

class LabQuestGenerator(QuestGenerator):
    """
    Helper class for the generating lab-specific quests.
    """
    def __init__(self, **kwargs):
        super(LabQuestGenerator, self).__init__(**kwargs)
#        self.max_nb_op_use = 2
        self.base_materials = self.get_base_materials()
        self.states = {}
        self.descs_per_ent = None
        # types and actions we want to ignore (for example to set later independently, like descriptors)
        self.ignore_act_list = ['locate', 'drop']
        self.ignore_types_list = KnowledgeBase.default().types.descendants('dsc') + ['dsc']
        self.ignore_sigs = [Signature('in',['tlq_op', 'I'])]
        self.q.set_scorer(self.lab_quest_scorer)

        # validity checks for every search state
        self.node_checks = {
                'check_depth': self.check_depth,
                'check_node_state': self.check_node_state,
                # 'ignore_types': self.check_ignore_type,
                'ignore_acts': self.check_ignore_act,
                'ignore_sigs': self.check_ignore_sigs
                }

        # goal node checks
        self.goal_check_fns = {
            'all_ops_used': self.all_ops_used,
            'all_mats_merged': self.all_mats_merged,
            'end_after_op': self.is_after_op_state,
        }

        # feature extractor functions for a given state w/ their weight
        self.feature_extractor_fns = {
            'is_new_state': (self.check_existing_state, 2), # 1 if state is new, 0 if not
            'nb_ops_used': (self.nb_ops_used, 1), # number of ops already used
            'nb_mat_ccs': (self.nb_mat_ccs, -1) # 1 if all precursor/solvent materials used in synthesis route
        }
      
    def lab_quest_scorer(self, node: _Node) -> int:
        """ 
        Simple heuristic score function for search states. The higher the score,
        the lower the search priority.
        """
        BASE_SCORE = 100
        features = [fn(node) * weight for (fn_name, (fn, weight)) in self.feature_extractor_fns.items()]
        return BASE_SCORE - sum(features)

    def set_desc_alloc_per_ent(self, chosen_args: List[Variable], chosen_ents: List[Variable], max_arg_use: int):
        nb_ents = len(chosen_ents)
        nb_args = len(chosen_args)
        arg_use_per_ent = []
        args_used = 0
        args_left = nb_args - args_used
        for i in range(nb_ents - 1):
            curr_use = min(self.options.quest_rng.randint(0, (max_arg_use+1)), args_left)
            arg_use_per_ent.append(curr_use)
            args_used += curr_use
            args_left = nb_args - args_used
        arg_use_per_ent.append(args_left)
        assert(sum(arg_use_per_ent) == nb_args)
        assert(len(arg_use_per_ent) == nb_ents)
        self.options.quest_rng.shuffle(arg_use_per_ent)
        return { ent: arg_use for (ent,arg_use) in \
                zip(chosen_ents, arg_use_per_ent) }
        
    def generate_quest(self) -> Quest:
        """ 
        Breadth-First-Search for a game state satisfying goal state objectives,
        within the specified number of search steps.
        """
        steps = 0
        start_node = self.chainer.root()
        curr_node = self.apply_all_descriptions(start_node)
        self.q.push(curr_node)
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
                              
                chain = self.chainer.make_chain(node)
                win_event = self.get_win_conditions(chain)
                win_event.actions = chain.actions
                quest = Quest(win_events=[win_event],
                            actions=chain.actions,
                            reward=self.options.quest_reward)
                return quest
            if not node.valid:
                continue
            # expand node to visit children
            for child in self.chainer.chain(node):
                self.q.push(child)
            steps += 1        
        raise QuestNotFoundError()
    
    @staticmethod
    def nb_ops_used(node: _Node) -> int:
        """ Return the number of ops used up until now in this state. """
        used_ops = list(node.state.facts_with_signature(Signature('used',['tlq_op'])))
        return len(used_ops)

    def nb_mat_ccs(self, node: _Node) -> int:
        """ 
        Return number of connected components in graph spanning base materials.
        Materials are connnected iff they're merged. 
        """
        
        # get all materials and descendants in game
        all_mats =  [self.start_state.variables_of_type(t) for t in KnowledgeBase.default().types.descendants('m') + ['m']]
        all_mats =  set([item for items in all_mats for item in items])
        
        # get all 'component' propositions to link between the materials
        component_props = [p for p in node.state.facts if p.name == "component"]
        
        # build the graph and return number of ccs (only count ccs with any base materials)
        G = nx.Graph()
        G.add_nodes_from([m for m in all_mats])
        edges = [(p.arguments[0], p.arguments[1]) for p in component_props]
        G.add_edges_from(edges)
        ccs = [cc for cc in nx.connected_components(G) if len(cc.intersection(self.base_materials)) > 0]
        return len(ccs)

    def all_ops_used(self, node: _Node) -> bool:
        """ Check that nb. of ops used is in required range. """
        nb_used_ops = self.nb_ops_used(node)
        return (nb_used_ops >= self.options.nb_ops)

    def all_mats_merged(self, node: _Node) -> bool:
        """ Check that all base materials incorporated into synthesis route. """
        return (self.nb_mat_ccs(node) == 1)

    @staticmethod
    def is_after_op_state(node: _Node) -> bool:
        """ Check that action that led to this state was to obtain op output  """
        return 'op_o_obtain' in node.action.name
        
    def get_base_materials(self) -> List[str]:
        """ TODO currently assuming start state materials are all precursors, this should be expanded to include solvents """
        materials = []
        for mat in self.start_state.variables_of_type('m'):
            materials.append(mat)
        return set(materials)
    
        
    def check_existing_state(self, state: State) -> int:
        for k,existing_state in self.states.items():
            if state == existing_state:
                return k
        return NEW_STATE
    
    def check_node_state(self, node: _Node) -> bool:
        return self.check_existing_state(node.state) != NEW_STATE
    
    def check_depth(self, node: _Node) -> bool:
        return node.depth <= self.options.max_depth

    # check that none of the target types of this action are in the ignore list.
    def check_ignore_type(self, node: _Node) -> bool:
        if node.action:
            c_action = convert_to_compact_action(node.action)
            for var in c_action.vars:
                if var.type in self.ignore_types_list:
                    return False
        return True

    # check that none of the target types of this action are in the ignore list.
    def check_ignore_act(self, node: _Node) -> bool:
        if node.action:
            c_action = convert_to_compact_action(node.action)
            return not c_action.name in self.ignore_act_list
        else:
            return True

    # check that none of the facts in the current state are in the ignore list for signatures.
    def check_ignore_sigs(self, node: _Node) -> bool:
        for sig in self.ignore_sigs:
            if node.state.facts_with_signature(sig):
                return False
        return True


    
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
        
        # check state is valid
        self.check_node(node)
        
    # Run domain specific validity checks for given state
    def check_node(self, node: _Node) -> None:
        for check_name,check in self.node_checks.items():
            if check(node) == False:
                quest_gen_logger.debug("failed at check: %s" % (check_name))
                node.valid = False
    
    # Check if final quest state domain specific conditions hold. 
    def goal_check(self, node: _Node) -> bool:
        self.update_visit_data(node)
        for check_fn in self.goal_check_fns.values():
            if check_fn(node) == False:
                return False
        return True


    def get_win_conditions(self, chain: Chain) -> Collection[Proposition]:
        """
        Given a chain of actions comprising a quest, return the set of propositions
        which must hold in a winning state.
        
        Parameters
        ----------
        chain:
            Chain of actions leading to goal state.
            
        Returns
        -------
        win_conditions:
            Set of propositions which must hold to end the quest succesfully.
        """

        win_condition_type = self.options.win_condition

        win_conditions = set()

        final_state = chain.final_state
        pg = ProcessGraph()
        pg.from_tw_actions(chain.actions)

        if win_condition_type in [WinConditionType.OPS,
                            WinConditionType.ALL]:
            
            # require all operations to have the correct inputs
            processed_props = set([prop for prop in final_state.facts if prop.name == 'processed'])
            component_props = set([prop for prop in final_state.facts if prop.name == 'component'])
            win_conditions.update(processed_props)
            win_conditions.update(component_props)

            # require all operations to be set to correct type
            op_type_props = set([prop for prop in final_state.facts if prop.name == 'tlq_op_type'])
            win_conditions.update(op_type_props)

            # precedence propositions enforcing minimal ordering restraints between ops
            tG = nx.algorithms.dag.transitive_closure(pg.G)
            op_nodes = [n for n in tG.nodes() if KnowledgeBase.default().types.is_descendant_of(n.var.type, ["op"])]
            op_sg = nx.algorithms.dag.transitive_reduction(tG.subgraph(op_nodes))
            for e in op_sg.edges():
                op_1_node, op_2_node = e
                prec_prop = Proposition('preceeds', [op_1_node.var, op_2_node.var])
                win_conditions.update({prec_prop})

        if win_condition_type in [WinConditionType.ARGS,
                            WinConditionType.ALL]:
            # require all descriptions to be set correctly
            desc_props = set([prop for prop in final_state.facts if prop.name == 'describes'])
            win_conditions.update(desc_props)
            
        # add post-conditions from last action 
        post_props = set(chain.actions[-1].postconditions)
        win_conditions.update(post_props)
    
        return Event(conditions=win_conditions)

    def get_node_with_action(self, node: _Node, c_action: CompactAction) -> _Node:
        for curr_node in self.chainer.chain(node):
            curr_c_action = convert_to_compact_action(curr_node.action)
            if c_action == curr_c_action:
                return curr_node
        raise QuestNotFoundError("Couldn't add requested action to quest: {}".format(str(c_action)))

    def apply_all_descriptions(self, node: _Node) -> _Node:
        """ 
        Add descriptions to all described entities according to predefined allocation (set in
        QuestGenerationOptions).
        """
        curr_node = node
        for ent_name, desc_names in self.options.ent_desc_map.items():
            ent_var = node.state.variable_named(ent_name)
            for desc_name in desc_names:
                desc_var = node.state.variable_named(desc_name)
                new_node = self.apply_descriptor(curr_node, desc_var, ent_var)
                curr_node = new_node
        return curr_node

    def apply_descriptor(self, node: _Node, desc_var: Variable, target_var: Variable) -> _Node:
        actions = [CompactAction(name="take", vars=[desc_var]),
                    CompactAction(name="dlink", vars=[desc_var, target_var])]
        curr_node = node
        for act in actions:
            new_node = self.get_node_with_action(curr_node, act)
            curr_node = new_node
        return curr_node




        
            

     
        
    