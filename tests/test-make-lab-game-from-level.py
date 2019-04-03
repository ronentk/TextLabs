#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
from tw_textlabs.challenges.lab_game import make_game_from_level
from tw_textlabs.generator.lab_game import LabGameOptions
from tw_textlabs.generator.process_graph import ProcessGraph
import tw_textlabs
import tw_textlabs.agents
from tw_textlabs.utils import make_temp_directory


def test_game_walkthrough_agent(game_file):
        agent = tw_textlabs.agents.WalkthroughAgent()
        env = tw_textlabs.start(game_file)
        env.enable_extra_info("score")
        agent.reset(env)
        stats = tw_textlabs.play(game_file, agent=agent, silent=True)
        print(stats)
        assert(stats['score'] == 1)

if __name__ == "__main__":
    
    test_seed = 7114110
    level = 14
    lab_game_options = LabGameOptions()
    lab_game_options.seeds = test_seed
    lab_game_options.max_quest_length = 100
    lab_game_options.force_recompile = True
    game = make_game_from_level(level, lab_game_options)
    
    quest = game.quests[0]
    pg = ProcessGraph()
    pg.from_tw_actions(quest.actions)
    pg.draw()
    
    with make_temp_directory(prefix="test_tw-make") as tmpdir:
        output_folder = Path(tmpdir) / "gen_games"
        game_file = Path(output_folder) / ("%s.ulx" % (game.metadata["uuid"]))
        game_file = tw_textlabs.generator.compile_game(game, lab_game_options)
        # Solve the game using WalkthroughAgent.
        test_game_walkthrough_agent(game_file)
