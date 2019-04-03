#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import tw_textlabs
from tw_textlabs.generator import LabGameMaker
from tw_textlabs.generator.lab_game import LabGameOptions
from tw_textlabs.generator.surface_generator import SurfaceGenerator
from tw_textlabs.generator.process_graph import ProcessGraph
from tw_textlabs.generator.data import KnowledgeBase

lab_game_options = LabGameOptions()
lab_game_options.seeds = 1234
quest_gen_options = lab_game_options.sketch_gen_options
surface_gen_options = lab_game_options.surface_gen_options

sg = SurfaceGenerator(seed=lab_game_options.seeds['surface'],
                surface_gen_options=surface_gen_options)
M = LabGameMaker(sg)

lab = M.new_room("lab")

M.set_player(lab)

# - Describe the room.
lab.desc = "The lab is a magical place where you'll learn materials synthesis"

mdsc = M.new_lab_entity('mdsc', name='MAT-DESCRIPTOR')
odesc = M.new_lab_entity('odsc', name='OP-DESCRIPTOR')
mat_1 = M.new_lab_entity('m', name="metal")
mat_2 = M.new_lab_entity('m', name="powder")
sa_0 = M.new_lab_entity('sa', name="silica tube")
op = M.new_tlq_op(dynamic_define=False, op_type='idtoe', name="mixing")
all_ents = [mdsc, odesc, mat_1, mat_2, op, sa_0]
for ent in all_ents:
    lab.add(ent)
    
commands = ['take metal', 
            'take powder', 
            'dlink MAT-DESCRIPTOR to metal', 
            'dlink OP-DESCRIPTOR to mixing',
            'op_ia_assign metal to mixing',
           'op_ia_assign powder to mixing',
           'op_run mixing',
           'op_o_obtain mixing',
           'take mixing',
           'locate mixing at silica tube']

quest = M.set_quest_from_commands(commands)

#pg = ProcessGraph()
#pg.from_tw_actions(quest.win_events[0].actions)
#pg.draw()
kb = KnowledgeBase.default()
all_cmds = kb.all_commands()
