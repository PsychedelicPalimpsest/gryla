"""
Copyright (C) 2025 - PsychedelicPalimpsest


This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""



import enum
from typing import *
from string import digits, ascii_letters, punctuation, whitespace, hexdigits

from io import StringIO

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class SerializationCtx:
    # ===== Formatting settings =====
    
    # Strip out comments, even if they were parsed
    # Note: If False, will not be able to get them back if they were not parsed
    DO_STRIP_COMMENTS : bool = False
    DO_INDENTATION : bool = True
    DO_LEADING_COMMA : bool = True

    # Do non-required new lines
    DO_NEWLINE : bool = True

    INDENTATION_MULTIPLIER : int = 4


    ONELINER_THRESHOLD : int = 4

    
    # Parsing context vars

    indentation_level : int = 0
    


    def mutate_for_oneliner(self) -> 'SerializationCtx':
        return replace(self, DO_NEWLINE = False)


    def mutate_for_indentation(self) -> 'SerializationCtx':
        return replace(self, indentation_level = self.indentation_level + 1 )

    def indent(self) -> str:
        return (" " * (self.indentation_level * self.INDENTATION_MULTIPLIER) ) if self.DO_INDENTATION else ""



class ProtoNode:
    def __init__(self):
        raise Exception("CANNOT INIT BASE") 


    def determine_size(self) -> int:
        """ Gives a value used to determine formatting size """
        return 1
    def contains_forces_forced_newline(self) -> bool:
        return False

    def style_comment(self) -> bool:
        return False 

    def serialize(self, ctx : SerializationCtx) -> str:
        """
        Serialize and format text. Must respect ctx.
        Conventions:
            - It is the callers responsibility to handle what comes next
            - The indentation returned by ctx.indent() is that which _WAS_
              used to indent that item to the CURRENT LEVEL. 
            - Assume this item is currently indented
            - The SerializationCtx is all the function knows or cares about

        """
        raise Exception("Not implmented")

    @classmethod
    def Deserialize(cls, stream : StringIO, allow_comments = False) -> 'ProtoNode':
        """
        Parse from string. 

        Conventions: 
            - Stream should be set the first char of the token
            - At return the stream should be put directly at the 
              of the thing being parsed. It it the callers responsibility
              to handle ws


        """
        raise Exception("Not implmented")

class ProtoString(ProtoNode):
    ESCAPE_DICT = {
            'a': '\a',
            'b': '\b',
            'f': '\f',
            'n': '\n',
            'r': '\r',
            't': '\t',
            'v': '\v',
            '\\': '\\',
            '\'': '\'',
            '"': '"',
    }
    ESCAPE_DICT_REVERSED = {
        v: k for k, v in ESCAPE_DICT.items()
    }

    VALID_LETTERS = digits + ascii_letters + punctuation + " "

    @classmethod
    def escape_string(cls, unescaped : str) -> str:
        escaped = ""   
        for c in unescaped:
            if c in cls.ESCAPE_DICT_REVERSED:
                escaped += "\\" + cls.ESCAPE_DICT_REVERSED[c]
            elif c in cls.VALID_LETTERS:
                escaped += c
            else:
                escaped += "\\x" + format(ord(c), "x")
        return escaped

    raw_contents : str
    def __init__(self, raw_contents : str):
        self.raw_contents = raw_contents
    
    def serialize(self, ctx: SerializationCtx) -> str:
        return f"\"{self.raw_contents}\""

    @classmethod
    def Deserialize(cls, stream: StringIO, allow_comments=False) -> 'ProtoNode':
        raw = ""

        first = stream.read(1)

        assert first == '"'

        isEscaped = False
        while '"' != (c := stream.read(1)) or isEscaped:
            if isEscaped and c not in cls.ESCAPE_DICT:
                raise ValueError(f"Cannot parse string due to unknown escaped charicter: {c}")
            

            raw += c
            isEscaped = not isEscaped and c == '\\'
        return ProtoString(raw)
            
class ProtoNumber(ProtoNode):
    raw_contents : str
    

    VALID_CONTENTS = hexdigits + "xXbB_.-" 

    def __init__(self, raw_contents : str):
        self.raw_contents = raw_contents

    def serialize(self, ctx: SerializationCtx) -> str:
        return self.raw_contents
    
    
    @classmethod
    def Deserialize(cls, stream: StringIO, allow_comments=False) -> 'ProtoNode':
        raw = ""
        while (c := stream.read(1)) in cls.VALID_CONTENTS and c != '':
            raw += c
        if c != '':
            stream.seek(stream.tell() - 1)
        

        # Validate
        if raw.startswith('0x') or raw.startswith('0X'):
            for c in raw[2:]:
                if c not in hexdigits + '_':
                    raise ValueError(f"Invalid number in hex mode: {c}")
        elif raw.startswith('0b') or raw.startswith('0B'):
            for c in raw[2:]:
                if c not in '01_':
                    raise ValueError(f'Invalid number in binary mode: {c}')
        else:
            for c in raw:
                if c not in digits + "-_.":
                    raise ValueError(f'Invalid number in decimal mode: {c}')


        return ProtoNumber(raw)


class ListStyle(enum.Enum):
    ROOT = enum.auto()

    PARAM = enum.auto()

    BRACKET = enum.auto()

    # Not use within the nowmal protolist
    CURLY_BRACKET = enum.auto()


    def end_token(self) -> str:
        return {
            self.ROOT: '',
            self.PARAM: ')',
            self.BRACKET: ']',
            self.CURLY_BRACKET: '}'
        }[self]
    
    def start_token(self) -> str:
        return {
            self.ROOT: '',
            self.PARAM: '(',
            self.BRACKET: '[',
            self.CURLY_BRACKET: '{'
        }[self]

class ProtoList(ProtoNode):
    style : ListStyle
    contents : List[ProtoNode]
    def __init__(self, contents : List[ProtoNode], style : ListStyle):
        self.style = style
        self.contents = contents

    def determine_size(self) -> int:
        return max(1, len(self.contents)) + max((0, *(c.determine_size() for c in self.contents)))

    def contains_forces_forced_newline(self) -> bool:
        return any((type(c) is ProtoComment for c in self.contents))

    def serialize(self, ctx: SerializationCtx) -> str:
        out = self.style.start_token()

        # Determine if a oneliner is required
        if self.determine_size() <= ctx.ONELINER_THRESHOLD:
            ctx = ctx.mutate_for_oneliner()

        had_previous_forced_nl = False
        child_ctx_base = ctx.mutate_for_indentation()

        for i, c in enumerate(self.contents):
            if child_ctx_base.DO_STRIP_COMMENTS and c.style_comment():
                continue


            if child_ctx_base.DO_NEWLINE and not had_previous_forced_nl:
                out += '\n'
            if child_ctx_base.DO_NEWLINE:
                out += child_ctx_base.indent()

            out += c.serialize(child_ctx_base)
            had_previous_forced_nl = c.style_comment()


            
            if not c.style_comment() and ((child_ctx_base.DO_LEADING_COMMA and child_ctx_base.DO_NEWLINE) or i+1 != len(self.contents) ):
                out += ','
                if not child_ctx_base.DO_NEWLINE:
                    out += ' '
            

        if ctx.DO_NEWLINE:
            out += '\n'
            if ctx.DO_INDENTATION:
                out += ctx.indent()
        out += self.style.end_token()
        return out

    @classmethod
    def Deserialize(cls, stream: StringIO, allow_comments=False, force_root : bool = False) -> 'ProtoNode':
        first = stream.read(1) if not force_root else ''

        style = ListStyle.ROOT if force_root else {
            '(' : ListStyle.PARAM,
            '[' : ListStyle.BRACKET
        }.get(first)

        if style is None:
            raise ValueError(f"Unknown begining token for list: {first}")


        ender = style.end_token()

        contents = []


        while (c := stream.read(1)) != ender and c != '':
            id = identify_protonode(c)

            if id is None:
                continue

            stream.seek(stream.tell() - 1)
            node = id.Deserialize(stream)

            if not(type(node) is ProtoComment and not allow_comments):
                contents.append(node)


            while (c := stream.read(1)) != ender and c != ',':
                if c not in whitespace:
                    raise ValueError(f"Parsing error: {c}{stream.read()}")
            if c == ender:
                break
        return ProtoList(contents, style) 


class _ProtoKV(ProtoNode):
    key : ProtoNode
    value : ProtoNode
    def __init__(self, key : ProtoNode, value : ProtoNode):
        self.key = key
        self.value = value

    def determine_size(self) -> int:
        return max(self.key.determine_size(), self.value.determine_size())
    
    @classmethod
    def Deserialize(cls, stream: StringIO, allow_comments=False) -> 'ProtoNode':
        raise Exception("Cannot parse ProtoKV")

    def serialize(self, ctx: SerializationCtx) -> str:
        return self.key.serialize(ctx) + ": " + self.value.serialize(ctx)


class ProtoDict(ProtoList):

    contents : List['_ProtoKV | ProtoComment']
    def __init__(self, contents : List[Tuple[ProtoNode, ProtoNode] | 'ProtoComment']):
        self.contents = [_ProtoKV(c[0], c[1]) if type(c) is tuple else c for c in contents]
        self.style = ListStyle.CURLY_BRACKET


    @classmethod
    def Deserialize(cls, stream: StringIO, allow_comments=False) -> 'ProtoNode':
        assert stream.read(1) == '{'

        contents = []
        while (c := stream.read(1)) != '}':
            assert c != '', 'Unexpected EOF'

            if c == ',':
                continue
            
            k_id = identify_protonode(c)

            if k_id is None:
                # Skip ws
                continue
            stream.seek(stream.tell() - 1)

            key : ProtoNode = k_id.Deserialize(stream)

            if type(key) is ProtoComment:
                if allow_comments:
                    contents.append(key)
                continue
            
            while (c := stream.read(1)) != ':':
                assert c in whitespace, f"Unexpected token {c}"
                assert c != '', "Unexpected EOF"
            while (v_id := identify_protonode(c := stream.read(1))) is None:
                assert c != '', "Unexpected EOF"
            stream.seek(stream.tell() - 1)

            value : ProtoNode = v_id.Deserialize(stream)
            
            contents.append((key, value))
        return ProtoDict(contents)


class ProtoType(ProtoNode):
    name : str

    attached_params : None | ProtoList
    attached_list : None | ProtoList
    attached_dict : None | ProtoDict

    def __init__(self, name : str,
                attached_params : None | ProtoList,
                attached_list : None | ProtoList,
                attached_dict : None | ProtoDict):
        self.name = name
        self.attached_params = attached_params
        self.attached_list = attached_list
        self.attached_dict = attached_dict

    def determine_size(self) -> int:
        return 1 + (
            (self.attached_dict.determine_size() if self.attached_dict is not None else 0)
            +
            (self.attached_list.determine_size() if self.attached_list is not None else 0)
            +
            (self.attached_params.determine_size() if self.attached_params is not None else 0)
        )
    def contains_forces_forced_newline(self) -> bool:
        return any(
            self.attached_params is not None and self.attached_params.contains_forces_forced_newline(),
            self.attached_list is not None and self.attached_list.contains_forces_forced_newline(),
            self.attached_dict is not None and self.attached_dict.contains_forces_forced_newline()
        )

    def serialize(self, ctx: SerializationCtx) -> str:
        out = self.name


        base_ctx_child = ctx.mutate_for_indentation()

        if self.attached_params is not None:
            out += self.attached_params.serialize(base_ctx_child)
        if self.attached_list is not None:
            out += self.attached_list.serialize(base_ctx_child)
        if self.attached_dict is not None:
            out += self.attached_dict.serialize(base_ctx_child)
        return out


    @classmethod
    def Deserialize(cls, stream: StringIO, allow_comments=False) -> 'ProtoNode':
        name = ""
        while (c := stream.read(1)) in (ascii_letters + "_"):
            name += c


        params = None
        lIst = None
        dIct = None


        while c not in ('', ']', ')', '}', ',', ':', '#'):
            if c == '[':
                assert lIst is None, ValueError("Multiple attached lists are not legal")

                stream.seek(stream.tell() - 1)
                lIst = ProtoList.Deserialize(stream, allow_comments=allow_comments)
            elif c == '(':
                assert params is None, ValueError("Multiple attached params are not legal")

                stream.seek(stream.tell() - 1)
                params = ProtoList.Deserialize(stream, allow_comments=allow_comments)
            elif c == '{':
                assert dIct is None, ValueError("Multiple attached dicts are not legal")

                stream.seek(stream.tell() - 1)
                dIct = ProtoDict.Deserialize(stream, allow_comments=allow_comments)
            elif c not in whitespace:
                raise ValueError(f"Unknown char found in Object: '{c}'")
 
            c = stream.read(1)

        if c in (']', ')', '}'):
            stream.seek(stream.tell() - 1)
        return ProtoType(name, params, lIst, dIct)
            

class ProtoComment(ProtoNode):
    contents : str
    def __init__(self, contents : str):
        self.contents = contents

    def style_comment(self) -> bool:
        return True



    @classmethod
    def Deserialize(cls, stream: StringIO, allow_comments=False) -> 'ProtoNode':
        assert stream.read(1) == '#'


        contents = ''

        while (c := stream.read(1)) != '\n' and c != '':
            contents += c

        return ProtoComment(contents.strip())
    
    def serialize(self, ctx: SerializationCtx) -> str:
        return f"# {self.contents}\n" 


def identify_protonode(char : str) -> Type | None:
    if char in "([":
        return ProtoList
    if char == "{":
        return ProtoDict

    if char in whitespace:
        return None
    if char == '"':
        return ProtoString
    if char in digits + '-':
        return ProtoNumber

    if char in ascii_letters:
        return ProtoType
    if char == '#':
        return ProtoComment
        
if __name__ == "__main__":
    i = StringIO("""{
        1 : [1, 2, 3, 4, 5, 0b01001],
        2: "as\\nd"
        # Foo
        # Bar
        1:true(){2:false, 3:false}}""")

    print(ProtoDict.Deserialize(i, allow_comments=True).serialize(SerializationCtx()))
    print([i.read()])



