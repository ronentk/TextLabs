# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT license.


import os
from os.path import join as pjoin

from nose.tools import nottest

import tw_textlabs


@nottest
def test_losing_game():
    MAX_NB_STEPS = 1000  # Just in case.
    env = tw_textlabs.start("./games/zork1.z5")
    walkthrough_file = os.path.abspath(pjoin(env.game_filename, "..", "solutions", "zork1.txt"))
    with open(walkthrough_file) as f:
        commands = f.readlines()
    agent = tw_textlabs.agents.WalkthroughAgent(commands)

    env.seed(1234)  # In order for the walkthrough to lead to a death.
    game_state = env.reset()
    # env.render()

    done = False
    for t in range(MAX_NB_STEPS):
        command = agent.act(game_state, 0, done)
        game_state, reward, done = env.step(command)
        # env.render()

        if done:
            break

    print("Done after {} steps. Score {}/{}.".format(game_state.nb_moves, game_state.score, game_state.max_score))
    assert game_state.has_lost
    assert not game_state.has_won


@nottest
def test_winning_game():
    MAX_NB_STEPS = 1000  # Just in case.
    env = tw_textlabs.start("./games/zork1.z5")
    walkthrough_file = os.path.abspath(pjoin(env.game_filename, "..", "solutions", "zork1.txt"))
    with open(walkthrough_file) as f:
        commands = f.readlines()
    agent = tw_textlabs.agents.WalkthroughAgent(commands)

    env.seed(1)  # In order for the walkthrough to work.
    game_state = env.reset()

    # env.render()

    done = False
    for t in range(MAX_NB_STEPS):
        command = agent.act(game_state, 0, done)
        game_state, reward, done = env.step(command)
        # env.render()

        if done:
            break

    print("Done after {} steps. Score {}/{}.".format(game_state.nb_moves, game_state.score, game_state.max_score))
    assert game_state.has_won
    assert not game_state.has_lost
