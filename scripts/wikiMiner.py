"""
A powerful tool for parsing packets from the Packet section of the minecraft wiki,
originally from wiki.vg.

Wiki url: https://minecraft.wiki/w/Minecraft_Wiki:Protocol_documentation

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



from typing import *
import requests
from dataclasses import dataclass
BASE_URL = "https://minecraft.wiki/api.php?action=query&format=json&prop=revisions&rvslots=*&rvprop=content&revids={}"



def consume_line(x : str) -> Tuple[str, str | None]:
    i = x.find('\n')
    return (x, None) if i == -1 else (x[:i].rstrip(), x[i+1:])

@dataclass
class WikitableCell:
    content : str
    
    isHeader : bool = False
    
    x : int = 1
    y : int = 1

    rowspan : int = 1
    colspan : int = 1


class WikiTable:
    rows : List[List[WikitableCell]]

    width : int
    height : int

    def __init__(self, rows : List[List[WikitableCell]], width : int, height : int):
        self.rows = rows

        self.width = width
        self.height = height
    @classmethod
    def From_txt(cls, txt : str) -> Tuple['WikiTable', str | None]:
        """
        Parse a standered wikitable, where txt is at the start if the wikitable (With allowence for whitespace).
        

        :return: A tuple, the first element being the parsed table obj, the secound being the rest of
                 the string after the table (None if EOS). 
        """

        txt = txt.lstrip()

        rows = []
        curRow = []

        line1, head = consume_line(txt)

        rowspans = []

        assert line1.strip().startswith("{|")
        assert head is not None

        x, y = 0, 0
        width = -1
        height = -1

        while True:
            line, head = consume_line(head)
            line = line.lstrip()

            
            # handle end of tables/files
            if head is None or line.lstrip().startswith("|}"):
                break

            if not len(line):
                continue

            # handle invalid lines
            if line[0] != '!' and line[0] != '|' and len(line.strip()) != 0:
                if len(curRow) == 0:
                   raise ValueError(f"Cannot parse WikiTable due to line: \"{line}\"")
                else:
                    curRow[-1].content += "\n" + line
                continue

            isHeader = line and line[0] == "!"
            line = line[1:].lstrip()
            
            # handle new rows
            if line and line[0] == "-":
                if y == 0 and len(curRow) == 0:
                    # WTF??????
                    continue


                width = max(width, x - 1)

                assert not isHeader
                y += 1
                x = 0

                rows.append(curRow)
                curRow = []

                rowspans = [cell for cell in rowspans if cell.y + cell.rowspan > y]
                continue

            # skip over large cells
            while True:
                for cell in rowspans:
                    isOverlapping = cell.x <= x and cell.y <= y and cell.x + cell.colspan > x and cell.y + cell.rowspan > y
                    if not isOverlapping:
                        continue
                    x += cell.colspan
                    break
                else:
                    break

            # parse arguments
            cellColspan = 1
            cellRowspan = 1
            while True:
                if line.startswith("colspan="):
                    cellColspan = int(line.split('"')[1])
                    line = line[line.find('"') + 1:]
                    line = line[line.find('"') + 1:].lstrip()
                elif line.startswith("rowspan="):
                    cellRowspan = int(line.split('"')[1])
                    line = line[line.find('"') + 1:]
                    line = line[line.find('"') + 1:].lstrip()
                else:
                    break

            if line.startswith('|'):
                line=line[1:].lstrip()
            

            cell = WikitableCell(
                line.rstrip(),
                isHeader,
                x,
                y,
                cellRowspan,
                cellColspan
            )

            if cellRowspan != 1:
                rowspans.append(cell)
            curRow.append(cell)

            x += cellColspan
        # last row edgecase
        rows.append(curRow)



        height = len(rows)

        return WikiTable(
            rows,
            width,
            height
        ), head




    def debug_print(self, colWidth = 5, rowHeight=2):
        """
        Gives you the shape of the table. 

        """
        lines =  [
            
            [' ' for _ in range((self.width + 10) * colWidth) ]
            for _ in range((self.height + 1) * rowHeight)
        ]
        
        for row in self.rows:
            for cell in row:
                ox = cell.x * colWidth
                oy = cell.y * rowHeight
                mx = ox + cell.colspan * colWidth
                my = oy + cell.rowspan * rowHeight
                
                for x in range(ox+1, mx):
                    lines[oy][x] = lines[my][x] = '─'
                for y in range(oy + 1, my):
                    lines[y][ox] = lines[y][mx] = '│'
        print(*("".join(line) for line in lines), sep="\n")
    def subtable(self, x, y, width=-1, height=-1):
        width = width if width != -1 else self.width + 1
        height = height if height != -1 else self.height + 1
        

        rows = [
            [WikitableCell(
                cell.content, cell.isHeader, 
                cell.x - x, cell.y - y,
                cell.rowspan, cell.colspan)
                for cell in row if (
                    cell.x >= x and cell.y >= y and
                    cell.x < x + width and cell.y < y + height
            )]
            for row in self.rows
        ]

        real_width = 0
        for row in rows:
            for cell in row:
                real_width = max(real_width, cell.x + cell.colspan)
        return WikiTable(rows, real_width, len(rows))
        
    def search_headers(self, predicate : Callable[[str], bool]) -> List[WikitableCell]:
        # Headers can only exist on the first row
        return [
            cell for cell in self.rows[0]
            if cell.isHeader and predicate(cell.content)
        ]
        


    def get(self, x : int, y : int) -> None | WikitableCell:
        l = [cell for cell in  self.rows[y] if cell.x == x]
        return None if len(l) == 0 else l[0]





class ProtocolNode:
    def debug_str(self) -> str:
        raise NotImplemented("Not implmented")

class ProtocolStrType(ProtocolNode):

    def __init__(self, txt : str) -> None:
        self.txt = txt
    def debug_str(self) -> str:
        return self.txt

class ProtocolTypeBinary(ProtocolNode):
    def __init__(self, descriptor : ProtocolNode, content : ProtocolNode) -> None:
        self.descriptor = descriptor
        self.content = content
    def debug_str(self) -> str:
        return self.descriptor.debug_str() + " & " + self.content.debug_str()

class ProtocolList(ProtocolNode):

    # A str of unresolver or primative
    fields : List[Tuple[str, ProtocolNode]]

    def __init__(self, fields):
        self.fields = fields
    def debug_str(self) -> str:
        return "{\n\t" + ("\n\t".join(
            (f"{name} : {tp.debug_str().replace('\n', '\n\t')}"   for name, tp in self.fields)
        )) + "\n}"


class Wiki:
    name : str
    components : List['Wiki | str']
    def __init__(self, name, components) -> None:
        self.name = name
        self.components = components
    def debug(self) -> str:
        return f"{self.name}[{',\n'.join( (("Content of len: " + str(len(component)) if type(component) is str else component.debug()) for component in self.components))}]".replace("\n", "\n\t")


    @classmethod
    def From_oldid(cls, oldid : int) -> 'Wiki':
        jso = requests.get(BASE_URL.format(oldid )).json()
        wikiContent = jso["query"]["pages"]["290319"]["revisions"][0]["slots"]["main"]["*"]
        
        # WARNING: This is a bad assumption
        segments = wikiContent.split("\n=")
        
        # Initial segment is not part of anything
        components = [segments[0]]
        segments = segments[1:]


        stack = [(-1, Wiki("root", components))]

        for segment in segments:
            # Another HORRIBLE asssumption
            deph = segment.find(' ')
            assert deph != -1

            contentStart = segment.find('\n')
            content = '' if contentStart == -1 else segment[contentStart:].strip() 

            name = segment[deph:]
            name = name.split('=')[0].strip()


            wiki = Wiki(name, [content])


            while deph <= stack[-1][0]:
                stack.pop(-1)

            stack[-1][1].components.append(wiki)
            stack.append((deph, wiki))

        assert type(stack[0][1]) is Wiki, "Wiki stack corruption"
        return stack[0][1]
    

class SymmetryError(Exception):
    pass

class TypeGenCtx:

    
    def __init__(self):
        pass
    
    def parse_type_content(self, type_content : str) -> ProtocolNode:
        # TODO: THIS
        return ProtocolStrType(type_content)

    def parse_subtable(self, name_col : WikiTable, type_col : WikiTable) -> ProtocolList:
        # Generally a, a type is symmetric across the table, with violation of this
        # rule either being an indication of a special condition, or a formatting
        # error on the part of the wiki editors. 

        # Only check height, as width can change with Enums
        if name_col.height != type_col.height: raise SymmetryError()

        fields = []

        row_itr = zip(name_col.rows, type_col.rows)
        for name_row, type_row in row_itr:

            if len(name_row) != len(type_row):
                # When this happens typically there is a formatting
                # issue on the Wiki itself, exept in the 'no fields' condition
                if len(name_row) and name_row[0].content.strip() == "''no fields''":
                    # Now consume N rows
                    for _ in range(name_row[0].rowspan):
                        try: next(row_itr)
                        except StopIteration: break
                    continue
#                 elif len(name_row) and name_row[0].content.strip() == "Action" and name_row[0].isHeader:

                else:
                    raise SymmetryError()

            if len(name_row) == 0:
                continue
            # Simple types
            elif len(name_row) == 1:
                fields.append((name_row[0].content, self.parse_type_content(type_row[0].content)))
            else:
                # The first elements rowspan tells us how long the recusive type is
                if name_row[0].rowspan != type_row[0].rowspan: raise SymmetryError()
                fields.append((
                    name_row[0].content,
                    ProtocolTypeBinary(
                        self.parse_type_content(type_row[0].content),
                        self.parse_subtable(
                            name_col.subtable(name_row[0].colspan, name_row[0].y, height=name_row[0].rowspan),
                            type_col.subtable(name_row[0].colspan, name_row[0].y, height=name_row[0].rowspan)
                        )
                    )
                ))
                # Now consume N rows
                for _ in range(name_row[0].rowspan):
                    try: next(row_itr)
                    except StopIteration: break
        return ProtocolList(
           fields 
        )

class Packet:

    def __init__(self, preamble : str, packetId : str, resourceId : str | None, typeDefinition : ProtocolList) -> None:
        """
        :param preamble: The description the wiki gives before the definition, this is often blank (zero len)
        :param packetId: The hex byte used to identify the packet on the network
        :param resourceid: The name Minecraft knows it by, this is absent (set to None) for older version
        :param typeDefinition: The parsed type object for this packet 
        """



        self.preamble = preamble
        self.packetId = packetId
        self.resourceId = resourceId
        self.typeDefinition = typeDefinition


def parse_modern_packet_id(id_col : str) -> Dict[str, str]:
    # Example packet id:
    # ''protocol:''<br/><code>0x00</code><br/><br/>''resource:''<br/><code>intention</code>
    # Which tend to follow the format:
    # [''{Key}:''<br/><code>{Value}</code><br/><br/>]

    ret = {}
    txt = id_col


    # Fix for: Legacy Server List Ping
    # Likely to be seen earlier
    if id_col.startswith("0x"):
        return {"protocol": id_col}

    while txt:
        assert txt.startswith("''"), f"Packet id format error, see: {id_col}"
        txt = txt[2:]
        nameEnd = txt.find(":''")

        assert nameEnd != -1

        name = txt[:nameEnd]
        
        # Skip br
        txt = txt[txt.find(">") +1: ]

        assert txt.startswith("<code>")
        txt = txt[len("<code>"):]
        value = txt[:txt.find("<")]


        # Skip to </code>
        txt = txt[txt.find(">") +1: ]
        while txt and txt.startswith("<br"):
            # Skip brs
            txt = txt[txt.find(">") +1: ]

        ret[name] = value
    return ret



def modern_packet_parse(packet : Wiki, ctx : TypeGenCtx):
    assert len(packet.components)

    txt = packet.components[0]
    name = packet.name

    assert type(txt) is str

    preamble = ""
    
    # Create the preamble and seek txt to first table
    while txt:
        line, head = consume_line(txt)

        if line.startswith("{|"):
            break

        txt = head
        preamble += line + "\n"

    if txt is None or not len(txt):
        raise Exception(f"Cannot find packet table for {packet.name}. Intervention required!")

    packetTable, txt = WikiTable.From_txt(txt)


    if packetTable.get(0, 0).content.strip() != "Packet ID":
        raise Exception(f"Packet {packet.name} not of expected packet table format. Intervention required!")

    packetId = parse_modern_packet_id(packetTable.get(0, 1).content)
    assert "protocol" in packetId

    nameHeader = packetTable.search_headers(lambda cont: cont.strip() == "Field Name")
    typeHeader = packetTable.search_headers(lambda cont: cont.strip() == "Field Type")


    assert 1 == len(nameHeader)
    assert 1 == len(typeHeader)

    nameCol = packetTable.subtable(nameHeader[0].x, 1, width=nameHeader[0].colspan)
    typeCol = packetTable.subtable(typeHeader[0].x, 1, width=typeHeader[0].colspan)

    try:
        packetType = ctx.parse_subtable(nameCol, typeCol)
    except SymmetryError as e: 
        print(f"Symmetry error in packet {packet.name}. Intervention required!")
        return None
 #       raise e
    except Exception as e:
        print(f"Unknown exception condition in {packet.name}. Intervention required!")
        raise e
    return Packet(
        preamble,
        packetId["protocol"],
        packetId.get("resource"),
        packetType
    )





MODERN_WIKI_WHITELIST = ["Status", "Login", "Handshaking", "Configuration", "Play"]        
MODERN_WIKI_IGNORELIST = ["Definitions", "Packet format", "Navigation"]
def modern_wiki_parse(root : Wiki, ):
    assert root.name == "root"

    ctx = TypeGenCtx()

    for packet_mode_tree in root.components:
        if type(packet_mode_tree) is str:
            continue

        if packet_mode_tree.name in MODERN_WIKI_IGNORELIST:
            continue

        if not packet_mode_tree.name in MODERN_WIKI_WHITELIST:
            # We only allow defined headers to ENSURE we understand what we are doing
            raise Exception(f"Unknown wiki header '{packet_mode_tree.name}'")

        packet_mode_ret = {}

        for destination in packet_mode_tree.components:
            if type(destination) is str:
                continue
        
            assert destination.name in ["Clientbound", "Serverbound"], f"Unknown destination {destination.name}"

            packet_wikis : List[Wiki] = [c for c in destination.components if type(c) is not str]
            
            packets = [modern_packet_parse(w, ctx) for w in packet_wikis]
             


                        
            
    
            
        
        
        




   


test = """
{| class="wikitable"
! Packet ID
! State
! Bound To
! colspan="2"| Field Name
! colspan="2"| Field Type
! Notes
|-
| rowspan="15"| ''protocol:''<br/><code>0x2D</code><br/><br/>''resource:''<br/><code>merchant_offers</code>
| rowspan="15"| Play
| rowspan="15"| Client
| colspan="2"| Window ID
| colspan="2"| {{Type|VarInt}}
| The ID of the window that is open; this is an int rather than a byte.
|-
| rowspan="10"| Trades
| Input item 1
| rowspan="10"| {{Type|Prefixed Array}}
| Trade Item
| See below. The first item the player has to supply for this villager trade. The count of the item stack is the default "price" of this trade.
|-
| Output item
| {{Type|Slot}}
| The item the player will receive from this villager trade.
|-
| Input item 2
| {{Type|Prefixed Optional}} Trade Item
| The second item the player has to supply for this villager trade.
|-
| Trade disabled
| {{Type|Boolean}}
| True if the trade is disabled; false if the trade is enabled.
|-
| Number of trade uses
| {{Type|Int}}
| Number of times the trade has been used so far. If equal to the maximum number of trades, the client will display a red X.
|-
| Maximum number of trade uses
| {{Type|Int}}
| Number of times this trade can be used before it's exhausted.
|-
| XP
| {{Type|Int}}
| Amount of XP the villager will earn each time the trade is used.
|-
| Special Price
| {{Type|Int}}
| Can be zero or negative. The number is added to the price when an item is discounted due to player reputation or other effects.
|-
| Price Multiplier
| {{Type|Float}}
| Can be low (0.05) or high (0.2). Determines how much demand, player reputation, and temporary effects will adjust the price.
|-
| Demand
| {{Type|Int}}
| If positive, causes the price to increase. Negative values seem to be treated the same as zero.
|-
| colspan="2"| Villager level
| colspan="2"| {{Type|VarInt}}
| Appears on the trade GUI; meaning comes from the translation key <code>merchant.level.</code> + level.
1: Novice, 2: Apprentice, 3: Journeyman, 4: Expert, 5: Master.
|-
| colspan="2"| Experience
| colspan="2"| {{Type|VarInt}}
| Total experience for this villager (always 0 for the wandering trader).
|-
| colspan="2"| Is regular villager
| colspan="2"| {{Type|Boolean}}
| True if this is a regular villager; false for the wandering trader.  When false, hides the villager level and some other GUI elements.
|-
| colspan="2"| Can restock
| colspan="2"| {{Type|Boolean}}
| True for regular villagers and false for the wandering trader. If true, the "Villagers restock up to two times per day." message is displayed when hovering over disabled trades.
|}
"""

if __name__ == "__main__":
    wiki = Wiki.From_oldid(3024144)
    modern_wiki_parse(wiki)
    # wiki.parse_datatypes()
    # ctx = TypeGenCtx()
    #tbl = WikiTable.From_txt(test)

    #print(ctx.parse_subtable(tbl.subtable(3, 1, width=2), tbl.subtable(5, 1, width=2)).debug_str())

