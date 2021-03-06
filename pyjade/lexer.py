import re
from collections import deque

class Token:
    def __init__(self, **kwds):
        self.buffer = None
        self.__dict__.update(kwds)
    def __str__(self):
        return self.__dict__.__str__()
def regexec (regex, input):
    matches = regex.match(input)
    if matches:
        return (input[matches.start():matches.end()],)+matches.groups()
    return None

class Lexer(object):
    RE_INPUT = re.compile(r'\r\n|\r')
    RE_COMMENT = re.compile(r'^ *\/\/(-)?([^\n]*)')
    RE_TAG = re.compile(r'^(\w[-:\w]*)')
    RE_FILTER = re.compile(r'^:(\w+)')
    RE_DOCTYPE = re.compile(r'^(?:!!!|doctype) *([^\n]+)?')
    RE_ID = re.compile(r'^#([\w-]+)')
    RE_CLASS = re.compile(r'^\.([\w-]+)')
    RE_TEXT = re.compile(r'^(?:\| ?)?([^\n]+)')
    RE_EXTENDS = re.compile(r'^extends? +([^\n]+)')
    RE_PREPEND = re.compile(r'^prepend +([^\n]+)')
    RE_APPEND = re.compile(r'^append +([^\n]+)')
    RE_BLOCK = re.compile(r'''^block(( +(?:(prepend|append) +)?([^\n]*))|\n)''')
    RE_YIELD = re.compile(r'^yield *')
    RE_INCLUDE = re.compile(r'^include +([^\n]+)')
    RE_ASSIGNMENT = re.compile(r'^(-\s+var\s+)?(\w+) += *([^;\n]+)( *;? *)')
    RE_MIXIN = re.compile(r'^mixin +([-\w]+)(?: *\((.*)\))?')
    RE_CALL = re.compile(r'^\+([-\w]+)(?: *\((.*)\))?')
    RE_CONDITIONAL = re.compile(r'^(?:- *)?(if|unless|else if|elif|else)\b([^\n]*)')
    RE_BLANK = re.compile(r'^\n *\n')
    # RE_WHILE = re.compile(r'^while +([^\n]+)')
    RE_EACH = re.compile(r'^(?:- *)?(?:each|for) +([\w, ]+) +in +([^\n]+)')
    RE_CODE = re.compile(r'^(!?=|-)([^\n]+)')
    RE_ATTR_INTERPOLATE = re.compile(r'#\{([^}]+)\}')
    RE_ATTR_PARSE = re.compile(r'''^['"]|['"]$''')
    RE_INDENT_TABS = re.compile(r'^\n(\t*) *')
    RE_INDENT_SPACES = re.compile(r'^\n( *)')
    RE_COLON = re.compile(r'^: *')
    # RE_ = re.compile(r'')
    def __init__(self,str,**options):
        self.options = options
        self.input = self.RE_INPUT.sub('\n',str)
        self.colons = self.options.get('colons',False)
        self.deferredTokens = deque()
        self.lastIndents = 0
        self.lineno = 1
        self.stash = deque()
        self.indentStack = deque()
        self.indentRe = None
        self.pipeless = False

    def tok(self,type,val=None):
        return Token(type=type,line=self.lineno,val=val)

    def consume(self,len):
        self.input = self.input[len:]

    def scan(self,regexp,type):
        captures = regexec(regexp,self.input)
        # print regexp,type, self.input, captures
        if captures:
            # print captures
            self.consume(len(captures[0]))
            # print 'a',self.input
            if len(captures)==1: return self.tok(type,None)
            return self.tok(type,captures[1])

    def defer(self,tok):
        self.deferredTokens.append(tok)

    def lookahead(self,n):
        # print self.stash
        fetch = n-len(self.stash)
        while True:
            fetch -=1
            if not fetch>=0: break
            self.stash.append(self.next())
        return self.stash[n-1]

    def indexOfDelimiters(self,start,end):
        str,nstart,nend,pos = self.input,0,0,0
        for i,s in enumerate(str):
            if start == s: nstart +=1
            elif end == s:
                nend +=1
                if nend==nstart:
                    pos = i
                    break
        return pos

    def stashed (self):
        # print self.stash
        return len(self.stash) and self.stash.popleft()

    def deferred (self):
        return len(self.deferredTokens) and self.deferredTokens.popleft()

    def eos (self):
        # print 'eos',bool(self.input)
        if self.input: return
        if self.indentStack:
            self.indentStack.popleft()
            return self.tok('outdent')
        else:
            return self.tok('eos')

    def blank(self):
        if self.pipeless: return
        captures = regexec(self.RE_BLANK,self.input)
        if captures:
            self.consume(len(captures[0])-1)
            return self.next()

    def comment(self):
        captures = regexec(self.RE_COMMENT,self.input)
        if captures:
            self.consume(len(captures[0]))
            tok = self.tok('comment',captures[2])
            tok.buffer = '-'!=captures[1]
            return tok

    def tag(self):
        captures = regexec(self.RE_TAG,self.input)
        # print self.input,captures,re.match('^(\w[-:\w]*)',self.input)
        if captures:
            self.consume(len(captures[0]))
            name = captures[1]
            if name.endswith(':'):
                name = name[:-1]
                tok = self.tok('tag',name)
                self.defer(self.tok(':'))
                while self.input[0]== ' ': self.input = self.input[1:]
            else:
                tok = self.tok('tag',name)
            return tok

    def filter(self):
        return self.scan(self.RE_FILTER, 'filter')

    def doctype(self):
        # print self.scan(self.RE_DOCTYPE, 'doctype')
        return self.scan(self.RE_DOCTYPE, 'doctype')

    def id(self):
        return self.scan(self.RE_ID, 'id')

    def className(self):
        return self.scan(self.RE_CLASS, 'class')

    def text(self):
        return self.scan(self.RE_TEXT, 'text')

    def extends(self):
        return self.scan(self.RE_EXTENDS, 'extends')

    def prepend(self):
        captures = regexec(self.RE_PREPEND,self.input)
        if captures:
            self.consume(len(captures[0]))
            mode,name = 'prepend',captures[1]
            tok = self.tok('block',name)
            tok.mode = mode
            return tok

    def append(self):
        captures = regexec(self.RE_APPEND,self.input)
        if captures:
            self.consume(len(captures[0]))
            mode,name = 'append',captures[1]
            tok = self.tok('block',name)
            tok.mode = mode
            return tok

    def block(self):
        captures = regexec(self.RE_BLOCK,self.input)
        if captures:
            self.consume(len(captures[0]))
            mode = captures[3] or 'replace'
            name = captures[4] or ''
            tok = self.tok('block',name)
            tok.mode = mode
            return tok

    def _yield(self):
        return self.scan(self.RE_YIELD, 'yield')

    def include(self):
        return self.scan(self.RE_INCLUDE, 'include')

    def assignment(self):
        captures = regexec(self.RE_ASSIGNMENT,self.input)
        if captures:
            self.consume(len(captures[0]))
            name,val = captures[2:4]
            tok = self.tok('assignment')
            tok.name = name
            tok.val = val
            return tok

    def mixin(self):
        captures = regexec(self.RE_MIXIN,self.input)
        if captures:
            self.consume(len(captures[0]))
            tok = self.tok('mixin',captures[1])
            tok.args = captures[2]
            return tok

    def call(self):
        captures = regexec(self.RE_CALL,self.input)
        if captures:
            self.consume(len(captures[0]))
            tok = self.tok('call',captures[1])
            tok.args = captures[2]
            return tok

    def conditional(self):
        captures = regexec(self.RE_CONDITIONAL,self.input)
        if captures:
            self.consume(len(captures[0]))
            type,sentence = captures[1:]
            tok = self.tok('conditional',type)
            tok.sentence = sentence
            return tok

    # def _while(self):
    #     captures = regexec(self.RE_WHILE,self.input)
    #     if captures:
    #         self.consume(len(captures[0]))
    #         return self.tok('code','while(%s)'%captures[1])

    def each(self):
        captures = regexec(self.RE_EACH,self.input)
        if captures:
            self.consume(len(captures[0]))
            tok = self.tok('each',None)
            tok.keys = map(lambda x:x.strip(),captures[1].split(','))
            tok.code = captures[2]
            return tok

    def code(self):
        captures = regexec(self.RE_CODE,self.input)
        if captures:
            self.consume(len(captures[0]))
            flags, name = captures[1:]
            tok = self.tok('code',name)
            tok.escape = flags.startswith('=')
            #print captures
            tok.buffer = '=' in flags 
            # print tok.buffer
            return tok

    def attrs(self):
        if '(' == self.input[0]:
            index = self.indexOfDelimiters('(',')')
            string = self.input[1:index]
            tok = self.tok('attrs')
            l = len(string)
            colons = self.colons
            states = ['key']
            class Namespace:
                key = u''
                val = u''
                quote = u''
                literal = True
                def reset(self):
                    self.key = self.val = self.quote = u''
                    self.literal = True
                def __str__(self):
                    return dict(key=self.key,val=self.val,quote=self.quote,literal=self.literal).__str__()
            ns = Namespace()
            

            def state():
                return states[-1]

            def interpolate(attr):
                attr, num = self.RE_ATTR_INTERPOLATE.subn(lambda matchobj:'%s+%s+%s'%(ns.quote,matchobj.group(1),ns.quote),attr)
                return attr, (num>0)

            self.consume(index+1)
            from utils import odict
            tok.attrs = odict()
            tok.static_attrs = set()
            str_nums = map(str,range(10))
            def parse(c):
                real = c
                if colons and ':'==c: c = '='
                ns.literal = ns.literal and (state() not in ('object','array','expr'))
                if c in (',','\n'):
                    s = state()
                    if s in ('expr','array','string','object'):
                        ns.val += c
                    else:
                        states.append('key')
                        ns.val = ns.val.strip()
                        ns.key = ns.key.strip()
                        if not ns.key: return
                        # ns.literal = ns.quote
                        if not ns.literal:
                            if '!'==ns.key[-1]:
                                ns.literal = True
                                ns.key = ns.key[:-1]
                        ns.key = ns.key.strip("'\"")
                        if not ns.val:
                            tok.attrs[ns.key] = True
                        else:
                            tok.attrs[ns.key], is_interpolated = interpolate(ns.val)
                            ns.literal = ns.literal and not is_interpolated
                        if ns.literal:
                            tok.static_attrs.add(ns.key)
                        ns.reset()
                elif '=' == c:
                    s = state()
                    if s == 'key char':
                        ns.key += real
                    elif s in ('val','expr','array','string','object'): ns.val+= real
                    else: states.append('val')
                elif '(' == c:
                    if state() in ('val','expr'): states.append('expr')
                    ns.val+=c
                elif ')' == c:
                    if state() in ('val','expr'): states.pop()
                    ns.val+=c
                elif '{' == c:
                    if 'val'==state(): states.append('object')
                    ns.val+=c
                elif '}' == c:
                    if 'object'==state(): states.pop()
                    ns.val+=c
                elif '[' == c:
                    if 'val'==state(): states.append('array')
                    ns.val+=c
                elif ']' == c:
                    if 'array'==state(): states.pop()
                    ns.val+=c
                elif c in ('"',"'"):
                    s = state()
                    if 'key'==s: states.append('key char')
                    elif 'key char'==s: states.pop()
                    elif 'string'==s: 
                        if c==ns.quote: states.pop()
                        ns.val +=c
                    else:
                        states.append('string')
                        ns.val +=c
                        ns.quote = c
                elif ''== c: pass
                else:
                    s = state()
                    ns.literal = ns.literal and (s in ('key','string') or c in str_nums)
                    # print c, s, ns.literal
                    if s in ('key','key char'): ns.key += c
                    else: ns.val += c

            for char in string:
                parse(char)

            parse(',')

            return tok

    def indent(self):
        if self.indentRe:
            captures = regexec(self.indentRe,self.input)
        else:
            regex = self.RE_INDENT_TABS
            captures = regexec(regex,self.input)
            if captures and not captures[1]:
                regex = self.RE_INDENT_SPACES
                captures = regexec(regex,self.input)
            if captures and captures[1]: self.indentRe = regex

        if captures:

            indents = len(captures[1])
            self.lineno += 1
            self.consume(indents+1)

            if not self.input: return self.tok('newline')
            if self.input[0] in (' ','\t'):
                raise Exception('Invalid indentation, you can use tabs or spaces but not both')

            if '\n' == self.input[0]: return self.tok('newline')

            if self.indentStack and indents< self.indentStack[0]:
                while self.indentStack and self.indentStack[0]>indents:
                    self.stash.append(self.tok('outdent'))
                    self.indentStack.popleft()
                tok = self.stash.pop()
            elif indents and (not self.indentStack or indents != self.indentStack[0]):
                self.indentStack.appendleft(indents)
                tok = self.tok('indent',indents)
            else:
                tok = self.tok('newline')

            return tok

    def pipelessText(self):
        if self.pipeless:
            if '\n' == self.input[0]: return
            i = self.input.find('\n')
            if -1 == i: i = len(self.input)
            str = self.input[:i]
            self.consume(len(str))
            return self.tok('text',str)

    def colon(self):
        return self.scan(self.RE_COLON,':')

    def advance(self):
        return self.stashed() or self.next()

    def next(self):
        return self.deferred() \
            or self.blank() \
            or self.eos() \
            or self.pipelessText() \
            or self._yield() \
            or self.doctype() \
            or self.extends() \
            or self.append() \
            or self.prepend() \
            or self.block() \
            or self.include() \
            or self.mixin() \
            or self.call() \
            or self.conditional() \
            or self.each() \
            or self.assignment() \
            or self.tag() \
            or self.filter() \
            or self.code() \
            or self.id() \
            or self.className() \
            or self.attrs() \
            or self.indent() \
            or self.comment() \
            or self.colon() \
            or self.text()

            ##or self._while() \

