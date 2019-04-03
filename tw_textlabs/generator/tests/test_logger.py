# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT license.


import numpy as np
from os.path import join as pjoin

import tw_textlabs
from tw_textlabs import g_rng
from tw_textlabs.utils import make_temp_directory
from tw_textlabs.generator.logger import GameLogger


def test_logger():
    rng = np.random.RandomState(1234)
    game_logger = GameLogger()

    for _ in range(10):
        options = tw_textlabs.GameOptions()
        options.nb_rooms = 5
        options.nb_objects = 10
        options.quest_length = 3
        options.quest_breadth = 3
        options.seeds = rng.randint(65635)

        game = tw_textlabs.generator.make_game(options)
        game_logger.collect(game)

    with make_temp_directory(prefix="tw_textlabs_tests") as tests_folder:
        filename = pjoin(tests_folder, "game_logger.pkl")
        game_logger.save(filename)
        game_logger2 = GameLogger.load(filename)
        assert game_logger is not game_logger2
        assert game_logger.stats() == game_logger2.stats()
