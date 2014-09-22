export-surround-to-git
======================

Python script to export history from Seapine Surround in a format parseable by `git fast-import`.

This method is capable of preserving complete history, timestamps, authors, comments, branches, snapshots, etc.


# Usage
```
usage: export-surround-to-git.py [-h] [-m MAINLINE] [-p PATH] [-f FILE]
                                 [-d DATABASE] [--version]
                                 [command]

Exports history from Seapine Surround in a format parseable by `git fast-import`.

positional arguments:
  command

optional arguments:
  -h, --help            show this help message and exit
  -m MAINLINE, --mainline MAINLINE
                        Mainline branch containing history to export
  -p PATH, --path PATH  Path containing history to export
  -f FILE, --file FILE  Any filename in target path
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
export-surround-to-git.py -m Sandbox -p "Sandbox/Merge Test" -f blah.txt | git fast-import --stats --export-marks=marks.txt
...
git repack ...
```


# Further Reading

See the [manpage for git fast-import](https://www.kernel.org/pub/software/scm/git/docs/git-fast-import.html).
