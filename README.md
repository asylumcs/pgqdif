# pgqdiff
text/HTML quick diff protram used before/during upload to Project Gutenberg.
It may be used standalone by cloning this repo locally. It is also
part of the Uploader's Workbench (UWB) at Project Gutenberg.

## Overview

This is a Python program used to compare a text file to an HTML file.
It accepts two source files and produces a report file in HTML for display in
a browser, where color-coding may be used.

## Usage

### Standalone

As a standalone program use this command line:

    python3 pgqdiff.py --files file1.txt file2.htm -o report.htm

You may also include "-v" to get verbose reports.

### In the UWB

This is one of the tests available in the
[UWB](https://uwb.pglaf.org).
Currently it runs there in 'verbose' mode, providing all reports.
You must have a user account on the pglaf server to use the UWB.

## Requirements

This program requires these Python packages:

- envoy (pip3 install envoy)
