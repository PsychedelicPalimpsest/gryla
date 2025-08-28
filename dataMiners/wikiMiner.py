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
    def From_txt(cls, txt : str) -> 'WikiTable':
        txt = txt.strip()

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
        )

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
        
    def search_headers(self, predicate : Callable[[str], bool]):
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
    def From_oldid(cls, oldid : int, lvl : int = 0) -> 'Wiki':
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
            name = name.split('=')[0]


            wiki = Wiki(name, [content])


            while deph <= stack[-1][0]:
                stack.pop(-1)

            stack[-1][1].components.append(wiki)
            stack.append((deph, wiki))
        print(stack[1][1].components[0])
        return stack[0][1]


 
class TypeGenCtx:

    
    def __init__(self):
        pass
    
    def parse_type_content(self, type_content : str) -> ProtocolNode:
        # TODO: THIS
        return ProtocolStrType(type_content)

    def parse_subtable(self, name_col : WikiTable, type_col : WikiTable) -> ProtocolList:
        # As a rule, the names column needs to be symetric with the type table
        assert name_col.width == type_col.width, ValueError("Symmetry violation")
        assert name_col.height == type_col.height, ValueError("Symmetry violation")

        fields = []

        row_itr = zip(name_col.rows, type_col.rows)
        for name_row, type_row in row_itr:
            assert len(name_row) == len(type_row), ValueError("Symmetry violation") 

            if len(name_row) == 0:
                continue
            # Simple types
            elif len(name_row) == 1:
                fields.append((name_row[0].content, self.parse_type_content(type_row[0].content)))
            else:
                # The first elements rowspan tells us how long the recusive type is
                assert name_row[0].rowspan == type_row[0].rowspan, ValueError("Symmetry violation")
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
                    next(row_itr)
        return ProtocolList(
           fields 
        )
        






   


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
    # ctx = TypeGenCtx()
    #tbl = WikiTable.From_txt(test)

    #print(ctx.parse_subtable(tbl.subtable(3, 1, width=2), tbl.subtable(5, 1, width=2)).debug_str())

