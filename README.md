export-surround-to-git
======================

Python script to export history from Seapine Surround in a format parsable by `git fast-import`.

This method is capable of preserving complete history, timestamps, authors, comments, branches, snapshots, etc.


# Project Status

This project was last tested using the following environment:

```
#   * Python 2.7.6
#   * GNU bash, version 4.3.11(1)-release (i686-pc-linux-gnu)
#   * sscm command-line client version:  2013.0.0 Build 23 (Linux)
#   * Git version 1.9.1
#   * Ubuntu 14.04.1 LTS
#   * Linux 3.13.0-35-generic #62-Ubuntu SMP Fri Aug 15 01:58:01 UTC 2014 i686 i686 i686 GNU/Linux
```

On my end, and with others that I know, most of us have abandoned hope in this project due to deficiencies in Surround's API and/or CLI. Further, we've learned that some of the [issues](https://github.com/JElchison/export-surround-to-git/issues) are technically intractible, like #34.

As such, this project is '''currently abandoned'''.  Interested parties are encouraged to fork and build upon this work.  Alternatively, there have already been a number of forks, so maybe some of those folks have had better luck.

Status of this project will be reevaluated should Seapine improve their API and/or CLI.


# Usage
```
usage: export-surround-to-git.py [-h] [-m MAINLINE] [-p PATH] [-d DATABASE]
                                 [--version]
                                 [command]

Exports history from Seapine Surround in a format parsable by `git fast-import`.

positional arguments:
  command

optional arguments:
  -h, --help            show this help message and exit
  -m MAINLINE, --mainline MAINLINE
                        Mainline branch containing history to export
  -p PATH, --path PATH  Path containing history to export
  -d DATABASE, --database DATABASE
                        Path to local database (only used when resuming an
                        export)
  --version             show program's version number and exit
```

## Example flow
```
sscm setclient ...
git init my-new-repo
cd my-new-repo
export-surround-to-git.py -m Sandbox -p "Sandbox/Merge Test" | git fast-import --stats --export-marks=marks.txt
...
git repack ...
```


# Further Reading

See the [manpage for git fast-import](https://www.kernel.org/pub/software/scm/git/docs/git-fast-import.html).
