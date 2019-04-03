#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import sys
from os.path import join as pjoin
from pathlib import Path
import tw_textlabs
from tw_textlabs.challenges import lab_game
from tw_textlabs.generator.lab_game import LabGameOptions
from tw_textlabs.generator.process_graph import ProcessGraph
from tw_textlabs.utils import quest_gen_logger
from tw_textlabs.generator import LabGameMaker
from tw_textlabs.generator.data import KnowledgeBase
from tw_textlabs.generator.surface_generator import SurfaceGenerator
from tw_textlabs.generator.game import Game, World, Quest, UnderspecifiedQuestError, Event
from tw_textlabs.utils import make_temp_directory
from tw_textlabs.generator.quest_generator import QuestGenerationOptions, WinConditionType
import numpy as np


test_seed = 322511
lab_game_options = LabGameOptions()
lab_game_options.seeds = test_seed


n_materials = 3
n_ops = 2



lab_game_options.surface_gen_options.merge_parallel_actions = True
lab_game_options.surface_gen_options.merge_serial_actions = True
surface_gen_options = lab_game_options.surface_gen_options
 # Set quest generation options.
quest_gen_options = QuestGenerationOptions(max_depth=30,
                        max_steps=10000,
                        win_condition=WinConditionType.ALL,
                        quest_rng=lab_game_options.rngs['quest']
                        )
   
sg = SurfaceGenerator(seed=1234,
                     surface_gen_options=surface_gen_options)
M = LabGameMaker(surface_generator=sg)


# Create the lab room.
lab = M.new_room("lab")

M.set_player(lab)

# - Describe the room.
lab.desc = "The lab is a magical place where you'll learn materials synthesis"


# Add materials to the world and their descriptors
ent_type = 'm'
n_max_descs = quest_gen_options.max_descs_per_ent[ent_type]
for i in range(n_materials):
    mat_state = "powder"
    mat = M.new_lab_entity(ent_type)
    mat.add_property(mat_state)
    lab.add(mat)
    n_descs = quest_gen_options.quest_rng.randint(0, (n_max_descs + 1))
    for j in range(n_descs):
        mdesc = M.new_lab_entity('mdsc')
        lab.add(mdesc)
        quest_gen_options.ent_desc_map[mat.var.name].append(mdesc.var.name)
        

# Add operations and their descriptors
ent_type = 'tlq_op'
n_max_descs = quest_gen_options.max_descs_per_ent[ent_type]
ops = [M.new_tlq_op(dynamic_define=True) for i in range(n_ops)]
for op in ops:
    lab.add(op)
    n_descs = quest_gen_options.quest_rng.randint(0, (n_max_descs + 1))
    for j in range(n_descs):
        odesc = M.new_lab_entity('odsc')
        lab.add(odesc)
        quest_gen_options.ent_desc_map[op.var.name].append(odesc.var.name)


#oven = M.new_lab_entity('sa', name='oven')
#lab.add(oven)



quest = M.generate_quest_surface_pair(quest_gen_options)
game = M.build()
pg = ProcessGraph()
pg.from_tw_actions(quest.actions)
pg.draw()
with make_temp_directory(prefix="test_tw-make") as tmpdir:
        output_folder = Path(tmpdir) / "gen_games"
        game_file = Path(output_folder) / ("%s.ulx" % (lab_game_options.uuid))
        game_file = tw_textlabs.generator.compile_game(game, lab_game_options)
        # Solve the game using WalkthroughAgent.
#        test_game_walkthrough_agent(game_file)
        