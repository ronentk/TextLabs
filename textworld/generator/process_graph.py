#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import List, Iterable
from dataclasses import dataclass
from networkx import DiGraph
import networkx as nx
from networkx.drawing.nx_agraph import graphviz_layout

from textworld.generator.game import Quest
from textworld.logic import Variable, Action
from textworld.generator.data import KnowledgeBase


# Possible material states
MATERIAL_STATES = {'powder', 'liquid', 'solid'}
GENERATOR_DUMMY_TYPE = 'G' # dummy node used as source node of graph
IGNORE_CMD = 'IGNORE'
IGNORED_ACTS = {}


# node colors by type
color_map = {
            'dsc': 'xkcd:cream',
            'op': 'cyan',
            'm': 'red',
            'toe': 'xkcd:purple',
            'sa': 'green'
        }

# operation types, for graph visualization
type_map = {
        'grndtoe': 'grinding',
        'cmptoe': 'compacting',
        'melttoe': 'melting',
        'idtoe': 'unknown',
        'mixtoe': 'mixing',
        'drytoe': 'drying'
        }

@dataclass
class EntityNode:
    """
    Represents a node in the ProcessGraph, generally each node corresponds to an
    entity variable in TextWorld plus a "generation id" which tracks state changes
    to an entity over time, so we can create a new node for each state change to
    show a process.
    
    Attributes:
        var: TextWorld variable representing an entity.
        g: The generation id of a node. Each state change of an entity will 
        entail creation of a new node with `g` increased by 1. This will happen 
        for example when a material changes state or a device over multiple
        uses.
        
    """
    var: Variable
    g: int = 0
    
    def __hash__(self):
        return hash((self.var, self.g))
    
    def __str__(self):
        if KnowledgeBase.default().types.is_descendant_of(self.var.type, ['toe']):
            return type_map[self.var.type]
        elif self.g > 0:
            return '%s@g%d' % (self.var.name, self.g)
        else:
            return '%s' % (self.var.name)
    
    def __repr__(self):
        return '%s_%s@g%d' % (self.var.name, self.var.type, self.g)

@dataclass
class ActionEdge:
    """
    Represents the external interface to an edge in the ProcessGraph.
    
    Attributes:
        action: Label of this edge, the action it represents.
        source: Source EntityNode
        target: Target EntityNode
    """
    action: str
    source: EntityNode
    target: EntityNode
    
    def __hash__(self):
        return hash((self.source, self.target, self.action))
    
    def __str__(self):
        return '%s(%s,%s)' % (self.action, self.source, self.target)
    
    def __repr__(self):
        return '%r(%r,%r)' % (self.action, self.source, self.target)
    
    
def node_to_color(node: EntityNode) -> str:
    """ Return node's color string as per the entity type. """
    color = 'gray' # default
    for node_type in color_map.keys():
        if node.var.type == GENERATOR_DUMMY_TYPE: # handle separately since not in type tree
            return color
        elif KnowledgeBase.default().types.is_descendant_of(node.var.type, node_type):
            color = color_map[node_type]
    
    return color


def edges_to_actions(edges):
    """ Convert list of networkx OutEdgeView obkects to ActionEdges. """
    return [ActionEdge(action=d['action'],source=u,target=v) for u,v,d in edges]
    
class ProcessGraph(object):
    """
    Helper class to represent a materials synthesis action graph / quest in a 
    format facilitating easy visualization in process form. This is also used
    by the SurfaceGenerator to create the textual description of a quest.
    """
    def __init__(self) -> None:
        self.G = DiGraph()

        # For each material we hold a list of nodes representing it over time 
        # as its state changes
        self.ent_states_map = {}
    
    def init_ent(self, e: Variable):
        """ Create and initialize new EntityNode. """
        if not e in self.ent_states_map:
            self.ent_states_map[e] = [EntityNode(var=e, g=0)]
            
    def curr_state(self, e: Variable):
        """ Return the last (current) state for a given entity variable. """
        return self.ent_states_map[e][-1]
    
    def add_new_state(self, e: Variable):
        """ 
        Add new state for a given entity variable (except Operation entities). 
        This creates a new EntityNode with g increased by 1. 
        """
        if KnowledgeBase.default().types.is_descendant_of(e.type, ['op']):
            return self.ent_states_map[e]
        else:
            new_state_node = EntityNode(var=e, g=(self.curr_state(e).g + 1))
            self.ent_states_map[e].append(new_state_node)
            return new_state_node
    
    def topological_sort_actions(self):
        """
        Return edges in "topological order", meaning we iterate over nodes
        in topological order and for each node iterate over its outgoing
        edges.
        """
        edge_list = []
        for n in nx.topological_sort(self.G):
            edge_list += edges_to_actions(self.G.out_edges(n, data=True))
        return edge_list
    
    def get_incoming_actions(self, node: EntityNode) -> List[ActionEdge]:
        """ Return the incoming actions to a given EntityNode. """
        return edges_to_actions(self.G.in_edges(node, 
                                                    data=True))
        
    def get_actions_path(self, source: EntityNode, target: EntityNode
                         ) -> List[ActionEdge]:
        """ 
        Return list of ActionEdges comprising the shortest path between a
        source and target node in the graph.
        """
        action_path = []
        path_nodes = nx.shortest_path(self.G, source, target)
        if len(path_nodes) < 2:
            return action_path
        edges = [e for e in zip(path_nodes[:-1],path_nodes[1:])] # get edges comprising path
        for u,v in edges:
            action_path.append(ActionEdge(action=self.G.edges()[(u,v)]['action'], source=u, target=v))
        return action_path
            
            
    def get_start_material_nodes(self) -> List[EntityNode]:
        """ Get nodes of all materials at start of process (g=0). """
        return [n for n in self.G.nodes() if (n.var.type=='m') and (n.g == 0)]

    def get_start_material_vars(self) -> List[Variable]:
        """ Get variables of all materials at start of process (g=0). """
        return [mat.var for mat in self.get_start_material_nodes()]
    
        
    def from_tw_actions(self, actions: Iterable[Action]) -> DiGraph:
        """ Construct internal graph given a TextWorld Quest. """
        # TODO verify validity?
        from textworld.generator.quest_generator import convert_to_compact_action
        G = nx.DiGraph()
        action_vars = [convert_to_compact_action(a) for a in actions]
        for action_var in action_vars:
            action_name = action_var.name
            if action_name == 'op_o_obtain':
                # add change state var as arg to this action so it gets processed
                action_var.vars.insert(0, action_var.change_state_vars[0])
            ents = action_var.vars
            for e in ents:
                self.init_ent(e)
            
            # ignore actions with single arg
            if len(ents) != 2:
                continue
            
            is_state_change_action = len(action_var.change_state_vars) > 0
            
            if not is_state_change_action:  
                G.add_edge(self.curr_state(ents[0]), self.curr_state(ents[1]), action=action_name)

            # assuming just one material changes state per action
            else:
                assert(len(action_var.change_state_vars) == 1)
                v = action_var.change_state_vars[0]
                assert(v == ents[0])
                
                # second argument is the source for new one (such as device)
                source = self.curr_state(ents[1]) 
                # Add a new state for the device, we assume that each operation
                # on a material is at a new state.
                if self.curr_state(v) in G.nodes():
                    # entity already exists in graph
                    target = self.add_new_state(v) 
                else:
                    # entity doesn't exist yet in graph, connect init node
                    target = self.curr_state(v)

                # Add 'result' type edge which corresponds to 'obtain' action
                G.add_edge(source, target, action='obtain')

        # add Generator dummy node to be source of graph (cosmetic)
        self.generator = EntityNode(var=Variable(name='START', type=GENERATOR_DUMMY_TYPE), g=0)
        G.add_node(self.generator)
        self.G = G
        materials = self.get_start_material_nodes()
        for m in materials:
            self.G.add_edge(self.generator, m, action='take')

    def get_op_type(self, node: EntityNode) -> str:
        assert(KnowledgeBase.default().types.is_descendant_of(node.var.type, 'tlq_op'))
        op_type_node = [n for n in self.G.neighbors(node) if KnowledgeBase.default().types.is_descendant_of(n.var.type, 'toe')]
        assert(len(op_type_node) == 1)
        op_type_node = op_type_node[0]
        return op_type_node.var.type
    
    def get_source_op(self, node: EntityNode) -> EntityNode:
        assert(KnowledgeBase.default().types.is_descendant_of(node.var.type, ['m', 'sa']))
        # return first operation node producing target node
        for n in self.ent_states_map[node.var]:
            for s,t in self.G.in_edges(n):
                if s.var.type == 'tlq_op':
                    return s
        return None
    
    def rename_edges(self, node: EntityNode, orig: str, target: str, incoming: bool = True) -> None:
        """ Rename a node's incoming or outgoing edges """
        edges =  [e for e in self.G.in_edges(node)] if incoming else [e for e in self.G.out_edges(node)]
        for edge in edges:
            act = self.G.edges()[edge]['action']
            self.G.edges()[edge]['action'] = act.replace(orig, target)
        
    
    def draw(self):
        """ Draw the ProcessGraph. """
        connected_nodes = [n for n in self.G.nodes() if self.G.degree(n) > 0]
        connected_G = self.G.subgraph(connected_nodes)
        
        # Hierarchical layout
        pos = graphviz_layout(connected_G, prog='dot')
        edge_labels = dict([((u,v,),d['action'])
             for u,v,d in self.G.edges(data=True)])
        
        node_labels = { n: str(n) for n in connected_G.nodes() }
        
        # Add dummy source node
        node_labels.update({self.generator: 'START'})
        
        node_colors = [node_to_color(n) for n in connected_G.nodes()]    
        nx.draw(connected_G,pos, labels=node_labels, with_labels=True, node_color=node_colors)
        nx.draw_networkx_edge_labels(connected_G, pos, edge_labels=edge_labels)
            
            
        
