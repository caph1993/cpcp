import os

def download(UI, **kwargs):
    #print(kwargs) # For development/debugging
    platform = kwargs['platform']
    fmt_in = kwargs['fmt_in']
    fmt_out = kwargs['fmt_out']
    statement = kwargs['statement']
    url = kwargs.get('url')

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
    UI.print('URL:', url)

    UI.print(f'\n    No download script found for {platform}'
        f'    I will help you to copy/paste the test cases manually.\n')

    if not UI.prompt_bool('You will assist the parsing. OK?'):
        return
    if UI.prompt_bool(f'    Open statement?'):
        xdg_open(statement)
    num=1
    while 1:
        fname = fmt_in.format(num=num)
        if UI.prompt_bool(f'Testcase {num}. Open {fname}?.'):
            xdg_open(fname, touch=True)
        else:
            break
        fname = fmt_out.format(num=num)
        if UI.prompt_bool(f'Testcase {num}. Open {fname}?'):
            xdg_open(fname, touch=True)
        else:
            break
        num+=1
    return


