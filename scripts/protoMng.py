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

class ProtoNode:
    def __init__(self):
        raise Exception("CANNOT INIT BASE") 

    def serialize(self, indentation : int = 0) -> str:
        raise Exception("Not implmented")

    @classmethod
    def Deserialize(cls, stream : StringIO) -> 'ProtoNode':
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
    
    def serialize(self, indentation: int = 0) -> str:
        return f"\"{self.raw_contents}\""

    @classmethod
    def Deserialize(cls, stream: StringIO) -> 'ProtoString':
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
    

    VALID_CONTENTS = hexdigits + "xX_." 

    def __init__(self, raw_contents : str):
        self.raw_contents = raw_contents

    def serialize(self, indentation: int = 0) -> str:
        return self.raw_contents
    
    @classmethod
    def Deserialize(cls, stream: StringIO) -> 'ProtoNumber':
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
                if c not in digits + "_.":
                    raise ValueError(f'Invalid number in decimal mode: {c}')


        return ProtoNumber(raw)


class ListStyle(enum.Enum):
    ROOT = enum.auto()

    PARAM = enum.auto()

    BRACKET = enum.auto()


    def end_token(self) -> str:
        return {
            self.ROOT: '',
            self.PARAM: ')',
            self.BRACKET: ']'
        }[self]
    
    def start_token(self) -> str:
        return {
            self.ROOT: '',
            self.PARAM: '(',
            self.BRACKET: '['
        }[self]
class ProtoList(ProtoNode):
    style : ListStyle
    contents : List[ProtoNode]
    def __init__(self, contents : List[ProtoNode], style : ListStyle):
        self.style = style
        self.contents = contents

    def serialize(self, indentation: int = 0) -> str:
        out = self.style.start_token()
        for c in self.contents:
            out += '\n' + ('\t' * (indentation + 1) ) + c.serialize(indentation=indentation+1) + ","

        out += ("\n" + ('\t' * indentation) if len(self.contents) else "") + self.style.end_token()
        return out

    
    @classmethod
    def Deserialize(cls, stream: StringIO, force_root : bool = False) -> 'ProtoList':
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
            contents.append(id.Deserialize(stream))

            while (c := stream.read(1)) != ender and c != ',':
                if c not in whitespace:
                    raise ValueError(f"Parsing error: {c}{stream.read()}")
            if c == ender:
                break
        return ProtoList(contents, style) 




class ProtoDict(ProtoNode):

    contents : List[Tuple[ProtoNode, ProtoNode]]
    def __init__(self, contents : List[Tuple[ProtoNode, ProtoNode]]):
        self.contents = contents

    def serialize(self, indentation: int = 0) -> str:
        out = '{'
        for key, value in self.contents:
            out += "\n"
            out += '\t' * (indentation + 1)
            out += key.serialize(indentation + 2)
            out += ": "
            out += value.serialize(indentation + 2)
            out += ","
        if self.contents:
            out += "\n"
        out += '\t' * indentation + "}"
        return out


    @classmethod
    def Deserialize(cls, stream: StringIO) -> 'ProtoDict':
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

    def serialize(self, indentation: int = 0) -> str:
        out = self.name
        if self.attached_params is not None:
            out += self.attached_params.serialize(indentation+1)
        if self.attached_list is not None:
            out += self.attached_params.serialize(indentation+1)
        if self.attached_dict is not None:
            out += self.attached_dict.serialize(indentation+1)
        return out


    @classmethod
    def Deserialize(cls, stream: StringIO) -> 'ProtoType':

        name = ""
        while (c := stream.read(1)) in (ascii_letters + "_"):
            name += c


        params = None
        lIst = None
        dIct = None


        while c not in ('', ']', ')', '}', ','):
            if c == '[':
                assert lIst is None, ValueError("Multiple attached lists are not legal")

                stream.seek(stream.tell() - 1)
                lIst = ProtoList.Deserialize(stream)
            elif c == '(':
                assert params is None, ValueError("Multiple attached params are not legal")

                stream.seek(stream.tell() - 1)
                params = ProtoList.Deserialize(stream)
            elif c == '{':
                assert dIct is None, ValueError("Multiple attached dicts are not legal")

                stream.seek(stream.tell() - 1)
                dIct = ProtoDict.Deserialize(stream)
            elif c not in whitespace:
                raise ValueError(f"Unknown char found in Object: '{c}'")
 
            c = stream.read(1)

        if c in (']', ')', '}'):
            stream.seek(stream.tell() - 1)
        return ProtoType(name, params, lIst, dIct)
            



def identify_protonode(char : str) -> Type | None:
    if char in whitespace:
        return None
    if char == '"':
        return ProtoString
    if char in digits:
        return ProtoNumber

    if char in ascii_letters:
        return ProtoType
    
        
if __name__ == "__main__":
    i = StringIO("{1:true(){2:false}}")

    print(ProtoDict.Deserialize(i).serialize())
    print([i.read()])



