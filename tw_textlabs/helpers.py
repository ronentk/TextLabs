# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT license.


import os
from typing import Optional, Mapping, Tuple

from tw_textlabs.utils import g_rng

from tw_textlabs.core import Environment, Agent
from tw_textlabs.generator.game import Game
from tw_textlabs.generator.lab_game import LabGameOptions
from tw_textlabs.envs import GlulxEnvironment
from tw_textlabs.envs import JerichoEnvironment

from tw_textlabs.agents import HumanAgent
from tw_textlabs.agents.walkthrough import WalkthroughDone

from tw_textlabs.generator import make_game, compile_game, make_lab_game


def start(path: str) -> Environment:
    """ Starts a TextWorld environment to play a game.

    Args:
        path: Path to the game file.

    Returns:
        TextWorld environment running the provided game.

    """
    # Check the game file exists.
    if not os.path.isfile(path):
        msg = "Unable to find game '{}'.".format(os.path.abspath(path))
        raise IOError(msg)

    # Guess the backend from the extension.
    backend = "glulx" if path.endswith(".ulx") else "zmachine"

    if backend == "zmachine":
        env = JerichoEnvironment(path)
    elif backend == "glulx":
        env = GlulxEnvironment(path)
    else:
        msg = "Unsupported backend: {}".format(backend)
        raise ValueError(msg)

    return env


def play(game_file: str, agent: Optional[Agent] = None, max_nb_steps: int = 1000,
         wrapper: Optional[callable] = None, silent: bool = False) -> None:
    """ Convenience function to play a text-based game.

    Args:
        game_file: Path to the game file.
        agent: Agent that will play the game. Default: HumanAgent(autocompletion=True).
        max_nb_steps: Maximum number of steps allowed. Default: 1000.
        wrapper: Wrapper to apply to the environment.
        silent: Do not render anything to screen.

    Notes:
        Use script :command:`tw-play` for more options.
    """
    msg = ""
    env = start(game_file)
    if agent is None:
        try:
            agent = HumanAgent(autocompletion=False)
        except AttributeError:
            agent = HumanAgent()
    
    env.enable_extra_info("score")
    agent.reset(env)
    if wrapper is not None:
        env = wrapper(env)
    
    game_state = env.reset()
    if not silent:
        env.render(mode="human")

    reward = 0
    done = False
    try:
        for _ in range(max_nb_steps):
            command = agent.act(game_state, reward, done)
            game_state, reward, done = env.step(command)

            if not silent:
                env.render(mode="human")

            if done:
                break

    except KeyboardInterrupt:
        pass  # Stop the game.
    except WalkthroughDone:
        print("completed all commands")
    finally:
        env.close()

    if not silent:
        msg = "Done after {} steps. Score {}/{}."
        msg = msg.format(game_state.nb_moves, game_state.score, game_state.max_score)
        print(msg)
    stats = {'move count': game_state.nb_moves, 
             'score': game_state.score}
    return stats


def make_custom_lab(options: LabGameOptions) -> Tuple[str, Game]:
    """ Makes a text-based game.

    Arguments:
        options:
            For customizing the game generation (see
            :py:class:`tw_textlabs.GameOptions <tw_textlabs.generator.game.GameOptions>`
            for the list of available options).
        path: Path of the compiled game (.ulx or .z8). Also, the source (.ni)
              and metadata (.json) files will be saved along with it.

    Returns:
        A tuple containing the path to the game file, and its corresponding Game's object.
    """
    game = make_lab_game(options)
    game_file = compile_game(game, options)
    return game_file, game
