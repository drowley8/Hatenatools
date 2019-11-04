import sys
import wave
import audioop
import re
import os
import tempfile
import shutil
import subprocess
import time
import numpy as np
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    print("Warning: PIL not found, image extraction won't work")
    HAS_PIL = False

try:
    with open(os.devnull, "w") as null:
        subprocess.call(["ffmpeg", "-h"],
                        stdout=null,
                        stderr=null)
    HAS_FFMPEG = True
except OSError:
    print("Warning: ffmpeg not found, video export unavailable. "
          "Please make sure ffmpeg is installed and can be accessed on your "
          "path.")
    HAS_FFMPEG = False

def AscDec(ascii, LittleEndian=False):
    ret = 0
    l = list(map(ord, ascii.decode("UTF-16LE")))
    if LittleEndian:
        l.reverse()
    for i in l:
        ret = (ret<<8) | i
    return int(ret)

ThumbPalette = (0xFEFEFEFF,
                0x4F4F4FFF,
                0xFFFFFFFF,
                0x9F9F9FFF,
                0xFF0000FF,
                0x770000FF,
                0xFF7777FF,
                0x00FF00FF,
                0x0000FFFF,
                0x000077FF,
                0x7777FFFF,
                0x00FF00FF,
                0xFF00FFFF,
                0x00FF00FF,
                0x00FF00FF,
                0x00FF00FF)

class PPM:
    def __init__(self, forced_speed=None):
        self.Loaded = [False, False, False]
        self.Frames = None
        self.Thumbnail = None
        self.RawThumbnail = None
        self.SoundData = None
        self.forced_speed = forced_speed
    def ReadFile(self, path, DecodeThumbnail=False, ReadFrames=True, \
                 ReadSound=False):
        f = open(path, 'rb')
        ret = self.Read(f.read(), DecodeThumbnail, ReadFrames, ReadSound)
        f.close()
        return ret
    def Read(self, data, DecodeThumbnail=False, ReadFrames=True, \
             ReadSound=False):
        if data[:4] != b'PARA' or len(data) < 0x6a8:
            return False
        AudioOffset = AscDec(data[4:8], True) + 0x6a0
        AudioLenght = AscDec(data[8:12], True)
        self.FrameCount = AscDec(data[12:14], True) + 1
        self.Locked = data[0x10] & 0x01 == 1
        self.ThumbnailFrameIndex = AscDec(data[0x12:0x14], True)
        self.OriginalAuthorName = data[0x14:0x2A].decode("UTF-16LE").\
                                 split(u"\0")[0]
        self.EditorAuthorName = data[0x2A:0x40].decode("UTF-16LE").\
                               split(u"\0")[0]
        self.Username = data[0x40:0x56].decode("UTF-16LE").split(u"\0")[0]
        self.OriginalAuthorID = data[0x56:0x5e][::-1].hex().upper()
        self.EditorAuthorID = data[0x5e:0x66][::-1].hex().upper()
        self.OriginalFilenameC = data[0x66:0x78]
        self.CurrentFilenameC = data[0x78:0x8a]
        self.OriginalFilename = "%s_%s_%s.tmb" % (self.OriginalFilenameC[:3].\
                               hex().upper(), self.OriginalFilenameC[3:-2].\
                               decode(), str(AscDec(self.OriginalFilenameC[-2:]\
                               , True)).zfill(3))
        self.CurrentFilename = "%s_%s_%s.tmb" % (self.CurrentFilenameC[:3].\
                              hex().upper(), self.CurrentFilenameC[3:-2].\
                              decode(), str(AscDec(self.CurrentFilenameC[-2:]\
                              , True)).zfill(3))
        self.PreviousEditAuthorID = data[0x8a:0x92][::-1].hex().upper()
        #self.PartialFilenameC = data[0x92:0x9a]
        self.Date = AscDec(data[0x9a:0x9e], True)
        self.RawThumbnail = data[0xa0:0x6a0]
        if DecodeThumbnail:
            self.GetThumbnail()
        self.Loaded[0] = True
        self.Looped = data[0x06a6] >> 1 & 0x01 == 1
        AnimationOffset = 0x6a8 + AscDec(data[0x06a0:0x6a4], True)


    def GetThumbnail(self, force=False):
        if self.Thumbnail is None or force:
            global ThumbPalette
            if not self.RawThumbnail:
                return False
            out = np.zeros((64, 48), dtype=">u4")
            palette = ThumbPalette
            for ty in range(6):
                for tx in range(8):
                    for y in range(8):
                        for x in range(0, 8, 2):
                            byte = self.RawThumbnail[int((ty*512+tx*64+y*8+x)/2)]
                            out[x+tx*8, y+ty*8] = palette[byte & 0xf]
                            out[x+tx*8+1, y+ty*8] = palette[byte >> 4]
            print(out)
            self.Thumbnail = out
        return self.Thumbnail

class TMB:
    def __init__(self):
        self.Loaded = False
        self.Thumbnail = None
        self.RawThumbnail = None
    def ReadFile(self, path, DecodeThumbnail=False):
        print("Readfile")
        f = open(path, "rb")
        #data = f.read()
        #print(data)
        ret = self.Read(f.read(), DecodeThumbnail)
        f.close()
        return ret
    def Read(self, data, DecodeThumbnail=False):
        print("Read")
        if data[:4] != b'PARA' or len(data) < 0x6a8:
            return False
        self.AudioOffset = AscDec(data[4:8], True) + 0x6a0
        print(f"Audio Offset: {self.AudioOffset}")
        self.AudioLenght = AscDec(data[8:12], True)
        print(f"Audio Lengh: {self.AudioLenght}")
        self.FrameCount = AscDec(data[12:14], True) + 1
        print(f"Frame Count: {self.FrameCount}")
        self.Locked = data[0x10] & 0x01 == 1
        print(f"Locked: {self.Locked}")
        self.ThumbnailFrameIndex = AscDec(data[0x12:0x14], True)
        print(f"Thumbnail Frame Index: {self.ThumbnailFrameIndex}")
        self.OriginalAuthorName = data[0x14:0x2A].decode("UTF-16LE").\
                                 split(u"\0")[0]
        print(f"Original Author: {self.OriginalAuthorName}")
        self.EditorAuthorName = data[0x2A:0x40].decode("UTF-16LE").\
                               split(u"\0")[0]
        print(f"Editor Author: {self.EditorAuthorName}")
        self.Username = data[0x40:0x56].decode("UTF-16LE").split(u"\0")[0]
        print(f"Username: {self.Username}")
        self.OriginalAuthorID = data[0x56:0x5e][::-1].hex().upper()
        print(f"Original Author ID: {self.OriginalAuthorID}")
        self.EditorAuthorID = data[0x5e:0x66][::-1].hex().upper()
        print(f"Editor Author ID: {self.EditorAuthorID}")
        self.PreviousEditAuthorID = data[0x8a:0x92][::-1].hex().upper()
        print(f"PreviousEditAuthorID: {self.PreviousEditAuthorID}")
        self.OriginalFilenameC = data[0x66:0x78]
        self.CurrentFilenameC = data[0x78:0x8a]
        self.OriginalFilename = "%s_%s_%s.tmb" % (self.OriginalFilenameC[:3].\
                               hex().upper(), self.OriginalFilenameC[3:-2].\
                               decode(), str(AscDec(self.OriginalFilenameC[-2:]\
                               , True)).zfill(3))
        print(f"Original Filename: {self.OriginalFilename}")
        self.CurrentFilename = "%s_%s_%s.tmb" % (self.CurrentFilenameC[:3].\
                              hex().upper(), self.CurrentFilenameC[3:-2].\
                              decode(), str(AscDec(self.CurrentFilenameC[-2:]\
                              , True)).zfill(3))
        print(f"Current Filename: {self.CurrentFilename}")
        self.PartialFilenameC = data[0x92:0x9a]
        self.Date = AscDec(data[0x9a:0x9e], True)
        print(f"Date: {self.Date}")
        self.RawThumbnail = data[0xa0:0x6a0]
        if DecodeThumbnail:
            self.GetThumbnail()
        self.Loaded = True
        return self.Loaded

    def GetThumbnail(self, force=False):
        if self.Thumbnail is None or force:
            global ThumbPalette
            if not self.RawThumbnail:
                return False
            out = np.zeros((64, 48), dtype=">u4")
            palette = ThumbPalette
            for ty in range(6):
                for tx in range(8):
                    for y in range(8):
                        for x in range(0, 8, 2):
                            byte = self.RawThumbnail[int((ty*512+tx*64+y*8+x)/2)]
                            out[x+tx*8, y+ty*8] = palette[byte & 0xf]
                            out[x+tx*8+1, y+ty*8] = palette[byte >> 4]
            self.Thumbnail = out
        return self.Thumbnail

def WriteImage(image, outputPath):
    print("Saving image...")
    if HAS_PIL is False:
        print("Error: PIL not found!")
        return False
    out = image.tostring("F")
    out = Image.frombytes("RGBA", (len(image), len(image[0])), out)
    filetype = outputPath[outputPath.rfind(".")+1:]
    out.save(outputPath, filetype)
    return True

def main():
    print("===PPM3.py===")
    if len(sys.argv) < 3:
        print("Usage:\n"
              "    PPM3.py <Mode> <Input> [<Output>] [<Frame>]\n\n"
              "    <Mode>:\n"
              "        -t: Extracts the thumbnail to the file <Output>\n"
              "        -f: Extract the frame(s) to <Output>\n"
              "        -s: Dumps the sound files to the folder <Output>\n"
              "        -S: Same as mode -s, but will also dump the raw sound "
              "data files\n"
              "        -e: Exports the flipnote to an MKV\n"
              "        -m: Prints ou the metadata. Can also write it to "
              "<Output> which also supports unicode characters\n"
              "        -oa: Search a directory for an original author that "
              "matches the RegEx\n"
              "    <Frame>\n"
              "        Only used in mode -f\n"
              "        Set this to the exact frame you want to extract "
              "(starting at 1) and it will be saved as a file to <Output>\n"
              "        If not specified, it will extract all frames to the "
              "folder <Output>")
        sys.exit()

    if sys.argv[1] == "-t":
        print("Reading the flipnote file...")
        if os.path.isfile(sys.argv[2]) is False:
            print("Error\nSpecified file doesn't exist!")
            sys.exit()
        flipnote = TMB()
        isflip = flipnote.ReadFile(sys.argv[2], True)
        if isflip is not True:
            print("Error!\nThe given file is not a Flipnote PPM file or "
                  "TMB file!")
            sys.exit()
        print("Dumping the thumbnail...")
        WriteImage(flipnote.GetThumbnail(), sys.argv[3])
        print("Done!")

    elif sys.argv[1] == "-f":
        if len(sys.argv) < 4:
            print("Error!")
            print("<Output> not specified!")
            sys.exit()
        print("Reading the flipnote file...")
        if os.path.isfile(sys.argv[2]) is False:
            print("Error\nSpecified file doesn't exist!")
            sys.exit()
        flipnote = PPM().ReadFile(sys.argv[2])

if __name__ == "__main__":
    main()
