from urllib.request import urlopen
from html.parser import HTMLParser


def download(UI, problem, platform):
    #print(problem, platform) # For development/debugging
    num = Parser().download_sample_io(
        UI, platform.url, problem.sample_io)
    UI.print(f'    Sucess:     {num} samples downloaded')
    return

# https://github.com/johnathan79717/codeforces-parser/blob/master/parse.py
class Parser(HTMLParser):

    def download_sample_io(self, UI, url, sample_io):
        self.sample_io = sample_io
        self.num_tests = 0
        self.testcase = None
        self.start_copy = False
        UI.print('Retrieving', url)

        html = urlopen(url).read()
        
        self.feed(html.decode('utf-8'))
        # .encode('utf-8') Should fix special chars problems?
        return self.num_tests

    def handle_starttag(self, tag, attrs):
        if tag == 'div':
            if attrs == [('class', 'input')]:
                self.num_tests += 1
                fname = self.sample_io.format(
                    io_num=self.num_tests,
                    io_ext='in')
                self.testcase = open(fname, 'wb')
            elif attrs == [('class', 'output')]:
                fname = self.sample_io.format(
                    io_num=self.num_tests,
                    io_ext='out')
                self.testcase = open(fname, 'wb')
        elif tag == 'pre':
            if self.testcase != None:
                self.start_copy = True

    def handle_endtag(self, tag):
        if tag == 'br':
            if self.start_copy:
                self.testcase.write('\n'.encode('utf-8'))
                self.end_line = True
        if tag == 'pre':
            if self.start_copy:
                if not self.end_line:
                    self.testcase.write('\n'.encode('utf-8'))
                self.testcase.close()
                self.testcase = None
                self.start_copy = False

    def handle_entityref(self, name):
        if self.start_copy:
            self.testcase.write(self.unescape(('&%s;' % name)).encode('utf-8'))

    def handle_data(self, data):
        if self.start_copy:
            self.testcase.write(data.strip('\n').encode('utf-8'))
            self.end_line = False
 
