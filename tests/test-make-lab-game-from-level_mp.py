#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import multiprocessing as mp
import numpy as np
from pathlib import Path
import tqdm
from itertools import repeat
import tw_textlabs
import tw_textlabs.agents
from tw_textlabs.challenges.lab_game import make_game_from_level
from tw_textlabs.generator.lab_game import LabGameOptions
from tw_textlabs.utils import make_temp_directory
import pandas as pd


def starmap_with_kwargs(pool, fn, kwargs_iter):
    args_for_starmap = zip(repeat(fn), kwargs_iter)
    return pool.starmap(apply_kwargs, args_for_starmap)

def apply_kwargs(fn, kwargs):
    res = None
    try: 
        res = fn(**kwargs)
    finally:
        return res

def make_and_play_game(level, lab_game_options):
    game = make_game_from_level(level, lab_game_options)
    if game:
        with make_temp_directory(prefix="test_tw-make") as tmpdir:
            output_folder = Path(tmpdir) / "gen_games"
            game_file = output_folder / ("%s.ulx" % (game.metadata["uuid"]))
            lab_game_options.path = game_file
            game_file = tw_textlabs.generator.compile_game(game, lab_game_options)
            # Solve the game using WalkthroughAgent.
            agent = tw_textlabs.agents.WalkthroughAgent()
            stats = tw_textlabs.play(game_file, agent=agent, silent=True)
            game.metadata.update({'quest_desc': game.main_quest.desc})
            game.metadata.update(stats)
    return game
    

if __name__ == "__main__":
    
    test_seed = 2321193
    np.random.seed(test_seed)
    mode = "medium"
    num_trials = 30
    cores = min(mp.cpu_count(), num_trials)
    print("Utilizing %d cores..." % (cores))
    p = mp.Pool(cores)
    seeds = [np.random.randint(low=0, high=np.iinfo(np.int32).max) for i in range(num_trials)]
    levels = np.round(np.linspace(1, 30, num_trials))
    
    
    params = [{'level': int(levels[i]), 
               'lab_game_options': LabGameOptions(seed=seeds[i])} for i in range(num_trials)]
    results = list(tqdm.tqdm(starmap_with_kwargs(p, make_and_play_game, params), total=num_trials))
    
    rows = []
    for param_dict, game in zip(params, results):
        row = {'found_quest': (game != None),
               'level': param_dict['level'],
               'seed': param_dict['lab_game_options'].seeds
               }
        
        if game:
            row.update(game.metadata)
        rows.append(row)
    result_df = pd.DataFrame(rows)
    
    tests_folder = Path(__file__).parent.absolute()
    result_df.to_csv(str(tests_folder / ('test-make-game-from-level_seed_%d-%d.csv' % (num_trials, test_seed))))