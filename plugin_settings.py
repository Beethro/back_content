PLUGIN_NAME = 'Back Content Plugin'
DESCRIPTION = 'This plugin supports the loading of back content via form or JATS XML.'
AUTHOR = 'Andy Byers'
VERSION = '1.0'
SHORT_NAME = 'back_content'
MANAGER_URL = 'bc_index'
IS_WORKFLOW_PLUGIN = True
HANDSHAKE_URL = 'bc_article'
STAGE = 'Back Content'

from utils import models

def install():
    new_plugin, created = models.Plugin.objects.get_or_create(name=SHORT_NAME, version=VERSION, enabled=True)

    if created:
        print('Plugin {0} installed.'.format(PLUGIN_NAME))
    else:
        print('Plugin {0} is already installed.'.format(PLUGIN_NAME))


def hook_registry():
    # On site load, the load function is run for each installed plugin to generate
    # a list of hooks.
    pass
