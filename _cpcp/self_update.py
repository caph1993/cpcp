from urllib.request import urlopen

def get_latest(self):
    latest = urlopen(META.releases_url)
    latest = json.loads(latest.read().decode())
    latest_version = latest.get('tag_name')
    
    for asset in latest.get('assets', []):
        if asset['name']==META.bintag:
            url = asset['browser_download_url']
            size = asset['size']
    return 


def self_updater(self):
    self.UI.print('Checking for updates...')
    latest = urlopen(META.releases_url)
    latest = json.loads(latest.read().decode())
    latest_version = latest.get('tag_name')
    if latest_version==META.version:
        self.UI.print('You have the latest version')
    else:
        self.UI.print(f'Version {latest_version} is out.')
        url = None
        for asset in latest.get('assets', []):
            if asset['name']==META.bintag:
                url = asset['browser_download_url']
                size = asset['size']
        if url==None:
            self.UI.print('You seem to have the latest version')
        elif META.binary:
            resp = urlopen(url)
            blocksize = size//15
            self.UI.print('Downloading:')
            self.UI.print('Total:    '+'-'*16)
            self.UI.print('Progress: ', end='')
            with TemporaryDirectory() as tmp:
                tgt = os.path.join(tmp, META.bintag)
                with open(tgt, 'wb') as f:
                    for i in range(16):
                        f.write(resp.read(blocksize))
                        self.UI.print('.', end='')
                self.UI.print()
                try:
                    shutil.move(tgt, META.binary)
                except:
                    shutil.move(tgt, META.binary+latest_version)
            self.UI.print('Done. Restart the app.')
        else:
            self.UI.print('You are in dev mode, use git pull to update')
            self.UI.print('Latest release at', url)
    return 
