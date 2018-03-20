"""
From here:
https://github.com/samwyse/sspp/blob/7aabfec3d5fea59ac8558b83178c36bdd1ddbbc6/__init__.py
"""
from glob import glob
from keyword import iskeyword
from os.path import dirname, join, split, splitext

basedir = dirname(__file__)

# Populate __all__ variable
__all__ = []

for name in glob(join(basedir, '*.py')):
    module = splitext(split(name)[-1])[0]
    if not module.startswith('_') and module.isidentifier() and not iskeyword(module):
        try:
            __import__(__name__+'.'+module)
        except Exception as err:
            import logging
            logger = logging.getLogger(__name__)
            logger.error('Exception while loading the %r plug-in.', module)
            raise
        else:
            __all__.append(module)

__all__.sort()
