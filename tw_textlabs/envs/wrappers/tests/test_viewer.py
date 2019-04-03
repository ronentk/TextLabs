# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT license.


import tw_textlabs

from tw_textlabs import g_rng
from tw_textlabs.utils import make_temp_directory, get_webdriver
from tw_textlabs.generator import compile_game
from tw_textlabs.envs.wrappers import HtmlViewer


def test_html_viewer():
    # Integration test for visualization service
    num_nodes = 3
    num_items = 10
    options = tw_textlabs.GameOptions()
    options.seeds = 1234
    options.nb_rooms = num_nodes
    options.nb_objects = num_items
    options.quest_length = 3
    options.grammar.theme = "house"
    options.grammar.include_adj = True
    game = tw_textlabs.generator.make_game(options)

    game_name = "test_html_viewer_wrapper"
    with make_temp_directory(prefix=game_name) as tmpdir:
        options.path = tmpdir
        game_file = compile_game(game, options)

        env = tw_textlabs.start(game_file)
        env = HtmlViewer(env, open_automatically=False, port=8080)
        env.reset()  # Cause rendering to occur.

    # options.binary_location = "/bin/chromium"
    driver = get_webdriver()

    driver.get("http://127.0.0.1:8080")
    nodes = driver.find_elements_by_class_name("node")
    assert len(nodes) == num_nodes
    items = driver.find_elements_by_class_name("item")

    objects = [obj for obj in game.world.objects if obj.type != "I"]
    assert len(items) == len(objects)

    env.close()
    driver.close()
