#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
  pgqdiff.py
  MIT license (c) 2021 Asylum Computer Services LLC
  https://asylumcs.net
"""

import sys
import os
import re
import argparse
import envoy  # pip3 install envoy
import tempfile
import html
import datetime

# from https://raw.githubusercontent.com/c-w/gutenberg/master/gutenberg/_domain_model/text.py

TEXT_START_MARKERS = frozenset((
    "*END*THE SMALL PRINT",
    "*** START OF THE PROJECT GUTENBERG",
    "*** START OF THIS PROJECT GUTENBERG",
    "This etext was prepared by",
    "E-text prepared by",
    "Produced by",
    "Distributed Proofreading Team",
    "Proofreading Team at http://www.pgdp.net",
    "http://gallica.bnf.fr)",
    "      http://archive.org/details/",
    "http://www.pgdp.net",
    "by The Internet Archive)",
    "by The Internet Archive/Canadian Libraries",
    "by The Internet Archive/American Libraries",
    "public domain material from the Internet Archive",
    "Internet Archive)",
    "Internet Archive/Canadian Libraries",
    "Internet Archive/American Libraries",
    "material from the Google Print project",
    "*END THE SMALL PRINT",
    "***START OF THE PROJECT GUTENBERG",
    "This etext was produced by",
    "*** START OF THE COPYRIGHTED",
    # "The Project Gutenberg",    # PROBLEM! shows up in footer
    "http://gutenberg.spiegel.de/ erreichbar.",
    "Project Runeberg publishes",
    "Beginning of this Project Gutenberg",
    "Project Gutenberg Online Distributed",
    "Gutenberg Online Distributed",
    "the Project Gutenberg Online Distributed",
    "Project Gutenberg TEI",
    "This eBook was prepared by",
    "http://gutenberg2000.de erreichbar.",
    "This Etext was prepared by",
    "This Project Gutenberg Etext was prepared by",
    "Gutenberg Distributed Proofreaders",
    "Project Gutenberg Distributed Proofreaders",
    "the Project Gutenberg Online Distributed Proofreading Team",
    "**The Project Gutenberg",
    "*SMALL PRINT!",
    "More information about this book is at the top of this file.",
    "tells you about restrictions in how the file may be used.",
    "l'authorization à les utilizer pour preparer ce texte.",
    "of the etext through OCR.",
    "*****These eBooks Were Prepared By Thousands of Volunteers!*****",
    "We need your donations more than ever!",
    " *** START OF THIS PROJECT GUTENBERG",
    "****     SMALL PRINT!",
    '["Small Print" V.',
    '      (http://www.ibiblio.org/gutenberg/',
    'and the Project Gutenberg Online Distributed Proofreading Team',
    'Mary Meehan, and the Project Gutenberg Online Distributed Proofreading',
    '                this Project Gutenberg edition.',
))

TEXT_END_MARKERS = frozenset((
    "*** END OF THE PROJECT GUTENBERG",
    "*** END OF THIS PROJECT GUTENBERG",
    "***END OF THE PROJECT GUTENBERG",
    "End of the Project Gutenberg",
    "End of The Project Gutenberg",
    "Ende dieses Project Gutenberg",
    "by Project Gutenberg",
    "End of Project Gutenberg",
    "End of this Project Gutenberg",
    "Ende dieses Projekt Gutenberg",
    "        ***END OF THE PROJECT GUTENBERG",
    "*** END OF THE COPYRIGHTED",
    "End of this is COPYRIGHTED",
    "Ende dieses Etextes ",
    "Ende dieses Project Gutenber",
    "Ende diese Project Gutenberg",
    "**This is a COPYRIGHTED Project Gutenberg Etext, Details Above**",
    "Fin de Project Gutenberg",
    "The Project Gutenberg Etext of ",
    "Ce document fut presente en lecture",
    "Ce document fut présenté en lecture",
    "More information about this book is at the top of this file.",
    "We need your donations more than ever!",
    "END OF PROJECT GUTENBERG",
    " End of the Project Gutenberg",
    " *** END OF THIS PROJECT GUTENBERG",
))

LEGALESE_START_MARKERS = frozenset(("<<THIS ELECTRONIC VERSION OF",))
LEGALESE_END_MARKERS = frozenset(("SERVICE THAT CHARGES FOR DOWNLOAD",))

class SourceFile(object):
    """ one of these for each file to be compared """

    def load_file(self, fname, encoding=None):
        """
        Load a file. for errata, allow UTF-8 or legacy 8 bit
        returns text as a list of lines and encoding
        """

        self.fullname = fname
        self.basename = os.path.basename(fname)
        self.dirname = os.path.dirname(fname)

        try:
            with open(fname, "rb") as f:
                raw = f.read()
        except Exception:
            raise IOError("Cannot load file: " + os.path.basename(fname))

        # Remove BOM if present
        if raw[0] == 0xef and raw[1] == 0xbb and raw[2] == 0xbf:
            raw = raw[3:]

        # Try various encodings. (idea from bibimbop)
        if encoding is None:
            encodings = ['utf-8', 'iso-8859-1']
        else:
            encodings = [encoding]

        for enc in encodings:
            try:
                text = raw.decode(enc)
            except Exception:
                continue
            else:
                return text, enc

        raise SyntaxError("Encoding cannot be found for: " + os.path.basename(fname))

    def load_text(self, fname, encoding=None):
        """Load the file as text."""
        text, encoding = self.load_file(fname, encoding)
        self.text = text.splitlines()
        self.encoding = encoding

        # if this is HTML, delete CSS, etc.

        r = envoy.run(f"file {fname}")
        if "HTML" in r.std_out:

            # nothing outside the <body tags
            i = 0
            while i < len(self.text) and not "<body" in self.text[0]:
                del(self.text[0])
            del(self.text[0])  # the <body> tag
            while i < len(self.text) and not "</body" in self.text[i]:
                i += 1
            del(self.text[i])  # the </body> tag
            while i < len(self.text):
                del(self.text[i]) # to the end

            # attempt conversion of remaining HTML to text equivalent
            for i, t in enumerate(self.text):
                t = re.sub("<\/?img", "<", t)  # don't confuse <img... for <i...
                t = re.sub("<\/?i[^>]*>", '_', t)  # protect italics

                t = re.sub(r"<a name=\".*?\">", '', t)
                t = re.sub(r"<a.*?/a>", '', t)

                t = re.sub("<\/?em[^>]*>", '_', t)  # protect emphasis (wrong for gesperrt)
                t = re.sub("<br[^>]+>", "\n", t)  # break converts to line break
                t = html.unescape(t)
                t = re.sub("&aelig;", "æ", t) # not handled by unescape
                t = re.sub("<[^>]+?>", '', t)  # all other tags go (on same line)
                self.text[i] = t

        # delete PG header/footer if present in text or HTML

        # do we expect a PG header?
        hasheader = False
        for i in range(len(self.text)):
            if "gutenberg.org" in self.text[i]:
                hasheader = True
                break

        # yes, this is a posted PG etext, including the legal header/footer
        if hasheader:
            # header: there may be many matches. choose the latest that qualifies
            found_header = -1
            for i in range(min(1000,len(self.text))): # in first 1000 lines
                for token in TEXT_START_MARKERS:
                    if token in self.text[i]:
                        found_header = i
                        # print("h", fname, i, self.text[i])
            if found_header != -1:
                self.text = self.text[found_header+1:]

            # footer
            found_footer = -1
            #print(len(self.text))
            #print( max(0,len(self.text)-1000) )
            for i in range(len(self.text)-1, max(0,len(self.text)-1000), -1): # in last 1000 lines
                for token in TEXT_END_MARKERS:
                    if token in self.text[i]:
                        found_footer = i
                        # print("f", fname, i, self.text[i])
            if found_footer != -1:
                self.text = self.text[:found_footer]

            if found_header != -1 and found_footer == -1:
                raise SyntaxError(f"{fname} missing PG footer")
            if found_header == -1 and found_footer != -1:
                raise SyntaxError(f"{fname} missing PG header")

        # processing for all files
        for i, t in enumerate(self.text):
            t += " "
            t = re.sub("–", "--", t)  # en dash
            t = re.sub("—", "--", t)  # em dash
            t = re.sub("―", "--", t)  # horiz bar
            t = re.sub("‒", "-", t)  # figure dash (to hyphen)
            t = re.sub(r"\s+\*\s+\*\s+\*\s+\*\s+\*\s+", " ", t)  # thought breaks
            t = re.sub("\s\s+", " ", t)  # compress spaces
            t = re.sub("=", "", t)  # hide bold markup
            t = re.sub("_", "", t)  # hide italics markup
            t = re.sub("[“”]", '"', t)  # normalize d quotes
            t = re.sub("[‘’]", "'", t)  # normalize s quotes, apos
            t = re.sub("\[\d+\]", "", t)  # assumed page number
            t = re.sub("» \d+", "", t)  # assumed page number
            t = re.sub("» [ivxlc]+", "", t)  # assumed page number
            t = re.sub("\[Pg \d+\]", "", t)  # assumed page number

            self.text[i] = t

def main():
    parser = argparse.ArgumentParser(description='pgdiff')

    parser.add_argument('--files',
                    dest='files',
                    help='filenames (2)',
                    type=str,
                    nargs=2
                    )
    parser.add_argument('-o', '--outfile', help='output file')
    parser.add_argument('-v', '--verbose', help='verbose', action='store_true')
    args = parser.parse_args()

    file1 = SourceFile()
    file1.load_text(args.files[0])
    file2 = SourceFile()
    file2.load_text(args.files[1])

    # print(file1.basename, len(file1.text), file1.encoding)
    # print(file2.basename, len(file2.text), file2.encoding)

    # save the converted files
    f1 = tempfile.NamedTemporaryFile()
    with open(f1.name, 'w') as fa:
        fa.writelines(file1.text)
    f2 = tempfile.NamedTemporaryFile()
    with open(f2.name, 'w') as fb:
        fb.writelines(file2.text)

    with open("/tmp/rf0001.txt", 'w') as fc:
        fc.writelines(file1.text)
    with open("/tmp/rf0002.txt", 'w') as fd:
        fd.writelines(file2.text)

    r = envoy.run(f"dwdiff {f1.name} {f2.name} -3is")
    # err = r.std_err
    t = r.std_out.splitlines()

    f3 = open(args.outfile, "w")
    f3.write("<pre>")
    f3.write("pgqdif run report <span style='color:red'>experimental</span>\n")
    f3.write(f"run started: {str(datetime.datetime.now())}\n");
    f3.write(f"files: {os.path.basename(args.files[0])} {os.path.basename(args.files[1])}\n")
    f3.write(f"<span style='background-color:#FFFFAA'>close this window to return to the UWB.</span>\n");
    f3.write("\n")
    lastline = ""
    for i, line in enumerate(t):
        if len(line) > 20:
            if line != lastline:
                f3.write(line + "\n")
                lastline = line
    f3.write("</pre>")
    f3.close()

    # temporary files
    f1.close()
    f2.close()

if __name__ == '__main__':
    main()
