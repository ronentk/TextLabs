# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT license.

import os
from subprocess import check_call, CalledProcessError
from os.path import join as pjoin
from pathlib import Path

import tw_textlabs
import tw_textlabs.agents

from tw_textlabs.utils import make_temp_directory

fpath = Path(__file__).parent.parent / 'notebooks' / 'example_lab_config.json'

def test_make_custom_lab_game():
    seed = "32423"
    with make_temp_directory(prefix="test_tw-make-lab") as tmpdir:
        output_folder = pjoin(tmpdir, "gen_games")
        game_file = pjoin(output_folder, "game_%s.ulx" % (seed))
        command = ["tw-make-lab", "custom", "--seed", seed , "--output", game_file, "--surface_mode", "medium", "--merge_serial_actions", "--merge_parallel_actions", "--max_quest_length", "13", "--max_search_steps", "2000", "--lab_config_path", str(fpath)]
        print(' '.join(command))
        try:
            assert check_call(command) == 0
        except CalledProcessError as e:
            print(e.output)
        
        
        assert os.path.isdir(output_folder)
        assert os.path.isfile(game_file)
        
        # Solve the game using WalkthroughAgent.
        agent = tw_textlabs.agents.WalkthroughAgent()
        stats = tw_textlabs.play(game_file, agent=agent, silent=True)
        assert(stats['score'] == 1)
    
def test_make_lab_game_from_level():
    seed = "3311063"
    level = 22
    with make_temp_directory(prefix="test_tw-make-lab") as tmpdir:
        output_folder = pjoin(tmpdir, "gen_games")
        game_file = pjoin(output_folder, "challenge_game%d_%s.ulx" % (level,seed))
        command = ["tw-make-lab", "challenge", "--seed", seed , "--max_search_steps", "2000", "--output", game_file, "--challenge", "tw-lab_game-level%d" % (level)]
        print(' '.join(command))
        try:
            assert check_call(command) == 0
        except CalledProcessError as e:
            print(e.output)
            

        assert os.path.isdir(output_folder)
        assert os.path.isfile(game_file)
        
        # Solve the game using WalkthroughAgent.
        print("Solving game")
        agent = tw_textlabs.agents.WalkthroughAgent()
        stats = tw_textlabs.play(game_file, agent=agent, silent=True)
        assert(stats['score'] == 1)
        
print("Testing custom lab game generation...")
test_make_custom_lab_game()
print("Testing challenge lab game generation...")
test_make_lab_game_from_level()
print("Done!")