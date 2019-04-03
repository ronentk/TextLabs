# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT license.


from typing import Tuple

from textworld.core import GameState, Wrapper
from textworld.utils import quest_gen_logger

class Recorder(Wrapper):
    def __init__(self) -> None:
        self.actions = []
        self.last_game_state = None

    def step(self, command: str) -> Tuple[GameState, float, bool]:
        game_state, score, done = super().step(command)
        if not game_state.action:
            quest_gen_logger.warn("Failed to record action: '{}'!".format(command))
        else:
            quest_gen_logger.debug("Recorded action {}".format(game_state.action.name))
        self.actions.append(game_state.action)
        self.last_game_state = game_state
        return game_state, score, done

    def reset(self) -> GameState:
        self.actions = []
        self.last_game_state = None
        self.activate_state_tracking()
        return super().reset()
