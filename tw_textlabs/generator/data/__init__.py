# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT license.


from collections import OrderedDict
import os
import glob
from os.path import join as pjoin
from shutil import copyfile, copytree, rmtree
from typing import Optional, Mapping, List
from dataclasses import dataclass
from tw_textlabs.logic import GameLogic
from tw_textlabs.generator.vtypes import VariableType, VariableTypeTree
from tw_textlabs.utils import maybe_mkdir, RegexDict

BUILTIN_DATA_PATH = os.path.dirname(__file__)
LOGIC_DATA_PATH = pjoin(BUILTIN_DATA_PATH, 'logic')
TEXT_GRAMMARS_PATH = pjoin(BUILTIN_DATA_PATH, 'text_grammars')


def _maybe_copyfile(src, dest, force=False, verbose=False):
    if not os.path.isfile(dest) or force:
        copyfile(src=src, dst=dest)
    else:
        if verbose:
            print("Skipping {} (already exists).".format(dest))


def _maybe_copytree(src, dest, force=False, verbose=False):
    if os.path.exists(dest):
        if force:
            rmtree(dest)
        else:
            if verbose:
                print("Skipping {} (already exists).".format(dest))
            return

    copytree(src=src, dst=dest)


def create_data_files(dest: str = './tw_textlabs_data', verbose: bool = False, force: bool = False):
    """
    Creates grammar files in the target directory.

    Will NOT overwrite files if they alredy exist (checked on per-file basis).

    Parameters
    ----------
    dest :
        The path to the directory where to dump the data files into.
    verbose :
        Print when skipping an existing file.
    force :
        Overwrite all existing files.
    """

    # Make sure the destination folder exists.
    maybe_mkdir(dest)

    # Knowledge base related files.
    _maybe_copytree(LOGIC_DATA_PATH, pjoin(dest, "logic"), force=force, verbose=verbose)

    # Text generation related files.
    _maybe_copytree(TEXT_GRAMMARS_PATH, pjoin(dest, "text_grammars"), force=force, verbose=verbose)


def _to_type_tree(types):
    vtypes = []

    for vtype in sorted(types):
        if vtype.parents:
            parent = vtype.parents[0]
        else:
            parent = None
        vtypes.append(VariableType(vtype.name, vtype.name, parent))

    return VariableTypeTree(vtypes)


def _to_regex_dict(rules):
    # Sort rules for reproducibility
    # TODO: Only sort where needed
    rules = sorted(rules, key=lambda rule: rule.name)

    rules_dict = OrderedDict()
    for rule in rules:
        rules_dict[rule.name] = rule

    return RegexDict(rules_dict)

@dataclass
class Inform7Command:
    """ 
    Represents the Inform7 command. 
    Possible command formats are:
        '<command>'
        '<command> args[0]'
        '<command> args[0] <preposition> args[1]'
        
    """
    command: str
    args: List[str] = None
    preposition: str = ''
    
    def __repr__(self):
        if not self.args:
            return self.command
        elif len(self.args) == 1:
            return '{} {}'.format(self.command, self.args[0])
        elif len(self.args) == 2:
            return '{} {} {} {}'.format(self.command, 
                                        self.args[0],
                                        self.preposition,
                                        self.args[1])
        else:
            args = '_'.join(self.args) if self.args else ''
            return '{}_{}{}'.format(self.command, args, '_' + self.preposition)
        
    def __str__(self):
        if not self.args:
            return self.command
        elif len(self.args) == 1:
            return '{} {}'.format(self.command, self.args[0])
        elif len(self.args) == 2:
            return '{} {} {} {}'.format(self.command, 
                                        self.args[0],
                                        self.preposition,
                                        self.args[1])
        else:
            args = '_'.join(self.args) if self.args else ''
            return '{}_{}{}'.format(self.command, args, '_' + self.preposition)
        
    def __dict__(self):
        d = {
                'command': self.command,
                'args': self.args,
                'preposition': self.preposition,
                'string': self.__str__()
            }
        return d

def to_i7_cmd_struct(i7_cmd: str) -> Inform7Command:
    sp = i7_cmd.split(' ')
    prep = ''
    short_cmd_name = sp[0] # assuming action name is first word in command sentence
    cmd_args = [(w.strip('{}'), i) for i,w in enumerate(sp) if (('{' in w) and ('}' in w))]
    if len(cmd_args) == 2:
        prep = sp[cmd_args[0][1] + 1]
    return  Inform7Command(short_cmd_name, [c for c,i in cmd_args], prep)
        

class KnowledgeBase:
    def __init__(self, logic: GameLogic, text_grammars_path: str):

        self.logic = logic
        self.text_grammars_path = text_grammars_path

        self.types = _to_type_tree(self.logic.types)
        self.rules = _to_regex_dict(self.logic.rules.values())
        self.constraints = _to_regex_dict(self.logic.constraints.values())
        self.inform7_commands = {i7cmd.rule: i7cmd.command for i7cmd in self.logic.inform7.commands.values()}
        self.inform7_events = {i7cmd.rule: i7cmd.event for i7cmd in self.logic.inform7.commands.values()}
        self.inform7_predicates = {i7pred.predicate.signature: (i7pred.predicate, i7pred.source) for i7pred in self.logic.inform7.predicates.values()}
        self.inform7_variables = {i7type.name: i7type.kind for i7type in self.logic.inform7.types.values()}
        self.inform7_variables_description = {i7type.name: i7type.definition for i7type in self.logic.inform7.types.values()}
        self.inform7_addons_code = self.logic.inform7.code

    @classmethod
    def default(cls):
        return KB

    @classmethod
    def load(cls, target_dir: Optional[str] = None):
        if target_dir is None:
            if os.path.isdir("./tw_textlabs_data"):
                target_dir = "./tw_textlabs_data"
            else:
                target_dir = BUILTIN_DATA_PATH

        # Load knowledge base related files.
        paths = glob.glob(pjoin(target_dir, "logic", "*"))
        logic = GameLogic.load(paths)

        # Load text generation related files.
        text_grammars_path = pjoin(target_dir, "text_grammars")
        return cls(logic, text_grammars_path)

    def get_reverse_action(self, action):
        r_action = action.inverse()
        for rule in self.rules.values():
            r_action.name = rule.name
            if rule.match(r_action):
                return r_action

        return None

    @classmethod
    def deserialize(cls, data: Mapping) -> "KnowledgeBase":
        logic = GameLogic.deserialize(data["logic"])
        text_grammars_path = data["text_grammars_path"]
        return cls(logic, text_grammars_path)

    def serialize(self) -> str:
        data = {
            "logic": self.logic.serialize(),
            "text_grammars_path": self.text_grammars_path,
        }
        return data
    
    def all_commands(self):
        cmds = {}
        for i7_cmd in self.inform7_commands.values():
            i7_cmd_struct = to_i7_cmd_struct(i7_cmd)
            cmds.update({str(i7_cmd_struct): i7_cmd_struct})
        return cmds


# On module load.
KB = KnowledgeBase.load()
