import subprocess, os, platform

def sys_open(filepath):
    if not os.path.exists(filepath):
        with open(filepath,'w'):
            pass
    if platform.system() == 'Darwin':
        subprocess.call(('open', filepath))
    elif platform.system() == 'Windows':
        os.startfile(filepath)
    else: # Linux
        subprocess.call(('xdg-open', filepath))
    return


def download(UI, problem, platform):
    #UI.print(problem) # For development/debugging
    #UI.print(platform) # For development/debugging
    sample_io = problem.sample_io
    statement = problem.statement
    url = platform.get('url')

    # Get url
    if url==None:
        prefill = ''
        if os.path.exists(statement):
            with open(statement) as f:
                prefill = f.read()
            prefill = prefill[prefill.find('url='):]
            prefill = prefill[4:prefill.find('"')]
        url = UI.ask_string(
            'Type the problem url (html or pdf): ',
            prefill=prefill,
            check=lambda s: s.lower()=='q' or (s.startswith('http') and ' ' not in s.strip()), 
            msg='URL can not contain spaces and must start with http or https',
        )
        if url==None:
            return
        url = url.strip()

    # Save light statement file
    UI.print('\nCreating statement redirector for quick access...')
    UI.print(f'    Source:      {url}')
    UI.print(f'    Destination: {statement}')
    html_stmt = '''<html><head>
    <meta http-equiv="refresh" content="0; url={url}"/>
    </head></html>'''
    with open(statement, 'w') as f:
        f.write(html_stmt.format(url=url))

    # Save samples
    if not UI.confirm('You will assist the parsing. OK?'):
        return
    if UI.confirm(f'    Open statement?'):
        sys_open(statement)
    num=1
    while 1:
        fname = sample_io.format(io_num=num, io_ext='in')
        if UI.confirm(f'Testcase {num}. Open {fname}?.'):
            sys_open(fname)
        else:
            break
        fname = sample_io.format(io_num=num, io_ext='out')
        if UI.confirm(f'Testcase {num}. Open {fname}?'):
            sys_open(fname)
        else:
            break
        num+=1
    return


