# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT license.


import numpy as np

from typing import Union, Dict, Optional

from tw_textlabs import g_rng


def get_seeds_for_game_generation(seeds: Optional[Union[int, Dict[str, int]]] = None
                                  ) -> Dict[str, int]:
    """ Get all seeds needed for game generation.

    Parameters
    ----------
    seeds : optional
        Seeds for the different generation processes.
        If None, seeds will be sampled from `tw_textlabs.g_rng`.
        If a int, it acts as a seed for a random generator that will be
            used to sample the other seeds.
        If dict, the following keys can be set:
                'map': control the map generation;
                'objects': control the type of objects and their location;
                'quest': control the quest generation;
                'surface': control the text generation;
            For any key missing, a random number gets assigned (sampled from `tw_textlabs.g_rng`).

    Returns
    -------
        Seeds that will be used for the game generation.
    """
    keys = ['map', 'objects', 'quest', 'surface']

    def _key_missing(seeds):
        return not set(seeds.keys()).issuperset(keys)

    if type(seeds) is int:
        rng = np.random.RandomState(seeds)
        seeds = {}
    elif seeds is None or _key_missing(seeds):
        rng = g_rng.next()

    # Check if we need to generate missing seeds.
    for key in keys:
        if key not in seeds:
            seeds[key] = rng.randint(65635)

    return seeds
