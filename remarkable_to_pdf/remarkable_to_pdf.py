import os
import contextlib
import struct

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from typing import BinaryIO

BRUSH_TYPES = {
    15: {'pressure': False, 'direction': False, 'speed': False, 'width': True}
}
COLORS = [(0, 0, 0), (.5, .5, .5), (1, 1, 1)]

class RmReader:
    def __init__(self, root, num_pages):
        self.root = root
        self.num_pages = num_pages
        self.datas = []
        for page in range(self.num_pages):
            with open(os.path.join(self.root, f"{page}.rm"), 'br') as f:
                self.datas.append(f.read())
        self.page = 0
        self.data = self.datas[0]
        self.offsets = [0] * num_pages

    def set_page(self, page: int):
        self.page = page
        self.data = self.datas[page]
    
    def next(self, len=4):
        b = self.data[self.offsets[self.page]:self.offsets[self.page]+len]
        self.offsets[self.page] = self.offsets[self.page] + 4
        return b
    
    def next_custom(self, fmt):
        res = struct.unpack_from(fmt, self.data, self.offsets[self.page])
        self.offsets[self.page] = self.offsets[self.page] + struct.calcsize(fmt)
        return res if len(res) > 1 else res[0]

    def next_int(self):
        return self.next_custom("<I")
    
    def next_float(self):
        return self.next_custom("<f")

class RmPage:
    def __init__(self, reader, page=0):
        self.page = page
        print("Creating page number", page)

        expected_header=b'reMarkable .lines file, version=5          '
        welcome_message, self.num_layers = reader.next_custom(f"<{len(expected_header)}sI")

        self.layers = [RmLayer(reader, layer) for layer in range(self.num_layers)]
    
    def __str__(self):
        return f"RmPage{{layers={self.layers}}}"

class RmLayer:
    def __init__(self, reader, layer=0):
        self.layer = layer

        self.num_lines = reader.next_int()

        self.lines = [RmLine(reader) for line in range(self.num_lines)]
    
    def __str__(self):
        return f"RmLayer{{num_lines={self.num_lines}}}"
    
    def __repr__(self):
        return self.__str__()

class RmLine:
    def __init__(self, reader: RmReader):
        self.brush_type, self.color, self.padding, self.brush_size, self.foo, self.num_points = reader.next_custom("<IIIfII")

        self.points = []
        for point in range(self.num_points):
            self.points.append(self.read_point(reader))
    
    def read_point(self, reader: RmReader):
        return {
            'x': reader.next_float(),
            'y': reader.next_float(),
            'speed': reader.next_float(),
            'direction': reader.next_float(),
            'width': reader.next_float(),
            'pressure': reader.next_float()
        }
    
    def __str__(self):
        return f"""RmLine{{
    brush_type: {self.brush_type}
    color: {self.color}
    padding: {self.padding}
    brush_size: {self.brush_size}
    num_points: {self.num_points}
    points: {self.points}
}}"""


class RmDoc:
    def __init__(self, root, num_pages):
        reader = RmReader(root, num_pages)
        self.pages = []        
        for page in range(num_pages):
            reader.set_page(page)
            self.pages.append(RmPage(reader, page))
    
    def __str__(self):
        return f"RmDoc{{num_pages={len(self.pages)}}}"

class RmWriter:
    def __init__(self, doc: RmDoc, path: str):
        self.doc = doc
        self.canvas = canvas.Canvas(path, A4)
        self.width, self.height = A4
        self.size_factor = self.width / 1404
    
    def draw_line(self, line: RmLine):
        self.canvas.setStrokeColorRGB(*COLORS[line.color])
        self.canvas.setLineWidth(self.trans_size(line.brush_size))
        for i in range(1, line.num_points):
            self.draw_line_segment(line.points[i-1], line.points[i])
    
    def draw_line_segment(self, p1, p2):
        self.canvas.line(*self.trans_coords(p1['x'], p1['y']), *self.trans_coords(p2['x'], p2['y']))
    
    def trans_coords(self, x, y):
        return x / 1404 * self.width, self.height - y / 1872 * self.height
    
    def trans_size(self, size):
        return size * self.size_factor
        
    def draw_page(self, page):
        page = self.doc.pages[page]

        for layer in page.layers:
            for line in layer.lines:
                self.draw_line(line)
        
        self.canvas.showPage()
    
    def draw(self):
        for page in range(len(self.doc.pages)):
            self.draw_page(page)
        self.canvas.save()

if __name__ == "__main__":
    doc = RmDoc("/home/ole-magnus/Documents/kystverket/999aac10-27f9-4204-94bf-6b26928d33f9", 7)
    
    drawer = RmWriter(doc, 'out.pdf')
    drawer.draw()