#!/usr/bin/env python

# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT license.


import argparse

import tw_textlabs
import tw_textlabs.agents


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("games", metavar="game", nargs="+")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    agent = tw_textlabs.agents.WalkthroughAgent()

    for i, game in enumerate(args.games, start=1):
        print("{}. Testing {} ...".format(i, game))
        env = tw_textlabs.start(game)
        env.activate_state_tracking()
        agent.reset(env)
        game_state = env.reset()

        if args.verbose:
            env.render()

        reward = 0
        done = False
        while not done:
            command = agent.act(game_state, reward, done)
            assert command in game_state.admissible_commands
            game_state, reward, done = env.step(command)

            if args.verbose:
                env.render()


if __name__ == "__main__":
    main()
