#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
from textworld.challenges.lab_game import make_game_from_level
from textworld.generator.lab_game import LabGameOptions
from textworld.generator.process_graph import ProcessGraph
import textworld
import textworld.agents
from textworld.utils import make_temp_directory


def test_game_walkthrough_agent(game_file):
        agent = textworld.agents.WalkthroughAgent()
        env = textworld.start(game_file)
        env.enable_extra_info("score")
        commands = env.game.main_quest.commands
        agent.reset(env)
        game_state = env.reset()

        reward = 0
        done = False
        for walkthrough_command in commands:
            command = agent.act(game_state, reward, done)
            game_state, reward, done = env.step(command)
        assert(done)
        assert(reward == 1)


if __name__ == "__main__":
    
    test_seed = 3241443
    level = 12
    lab_game_options = LabGameOptions()
    lab_game_options.seeds = test_seed
    lab_game_options.force_recompile = True
    game = make_game_from_level(level, lab_game_options)
    
    quest = game.quests[0]
    pg = ProcessGraph()
    pg.from_tw_quest(quest)
    pg.draw()
    
    with make_temp_directory(prefix="test_tw-make") as tmpdir:
        output_folder = "gen_games"
        game_file = Path(output_folder) / ("%s.ulx" % (game.metadata["uuid"]))
        game_file = textworld.generator.compile_game(game, lab_game_options)
        # Solve the game using WalkthroughAgent.
        test_game_walkthrough_agent(game_file)
