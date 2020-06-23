import importlib.util
import os, traceback


class Downloader:

    def __init__(self):
        self.path = os.path.abspath(
            'cpcp/download_plugins')
        self.plugins = {}
        self._reimport('fallback')

    def download(self, UI, problem, platform):
        try:
            self._reimport(platform.name)
        except FileNotFoundError:
            pass
        
        if platform.name in self.plugins:
            tool = platform.name
        else:
            tool = 'fallback'
        UI.print(f'\nUsing {tool} downloader... (ctrl+c to interrupt)')
        UI.print('-'*15+'\n')
        plugin = self.plugins[tool]
        try:
            plugin.download(UI, problem, platform)
        except:
            UI.print(traceback.format_exc())

    def _reimport(self, platform):
        plugin = os.path.join(self.path, f'{platform}.py')

        spec = importlib.util.spec_from_file_location(
            f'download_plugins.{platform}', plugin)
        
        the_plugin = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(the_plugin)

        #importlib.reload(the_plugin)
        
        self.plugins[platform] = the_plugin
        return
