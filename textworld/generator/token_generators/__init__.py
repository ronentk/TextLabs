"""
Based on https://github.com/BNMetrics/factory_pattern_sample
"""

from importlib import import_module
from pathlib import Path
from textworld.generator.token_generators.token_generator import TokenGenerator
from textworld.generator.token_generators.token_generator import DYN_TOKEN_MARKER

root = Path(__file__).parent.absolute()

def normalize_name(s):
    return ''.join(x.capitalize() for x in s.split('_'))

def grab(token_name, *args, **kwargs):

    try:
        if '.' in token_name:
            module_name, class_name = token_name.rsplit('.', 1)
        else:
            module_name = token_name
            class_name = normalize_name(token_name)

        token_module = import_module('.' + module_name, package='token_generators')

        token_class = getattr(token_module, class_name)

        instance = token_class(*args, **kwargs)

    except (AttributeError, AssertionError, ModuleNotFoundError):
        raise ImportError('{} is not part of our token collection!'.format(token_name))
    else:
        if not issubclass(token_class, TokenGenerator):
            raise ImportError("We currently don't have {}, but you are welcome to send in the request for it!".format(token_class))

    return instance


def grab_all(*args, **kwargs):
    all_tokens = []
    all_token_names = [path.stem for path in root.iterdir() if (path.is_file() and path.name != '__init__.py')]
    for token_name in all_token_names:
        try:
            instance = grab(token_name, *args, **kwargs)
            all_tokens.append(instance)
        except:
            pass
    return all_tokens
