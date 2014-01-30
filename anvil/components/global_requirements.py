from anvil import shell as sh

from anvil.components import base_install as binstall


class GlobalRequirements(binstall.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        binstall.PythonInstallComponent.__init__(self, *args, **kargs)
        app_dir = self.get_option('app_dir')
        tools_dir = sh.joinpths(app_dir, 'tools')
        self.requires_files = [
            sh.joinpths(tools_dir, 'pip-requires'),
            sh.joinpths(app_dir, 'global-requirements.txt'),
        ]
