PLUGIN_NAME = 'Back Content Plugin'
DESCRIPTION = 'This plugin supports the loading of back content via form or JATS XML.'
AUTHOR = 'Andy Byers'
VERSION = '1.2'
SHORT_NAME = 'back_content'
MANAGER_URL = 'bc_index'
JANEWAY_VERSION = "1.3.6"

# Workflow Settings
IS_WORKFLOW_PLUGIN = False
HANDSHAKE_URL = 'bc_article'
ARTICLE_PK_IN_HANDSHAKE_URL = True
STAGE = 'Back Content'
KANBAN_CARD = 'back_content/kanban_card.html'

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
