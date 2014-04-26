#!/usr/bin/python2
# TODO: is this the right string recommended for python2?  2.7?

# TODO:  standard format for headers?
# Author:  Jonathan Elchison <JElchison@Gmail.com>
# License:  TODO
# Environment:  Assumes running in Bash

import sys
import argparse


def parse_arguments():
    # TODO
    pass


def handle_command():
    # TODO
    pass


def main():
    parse_arguments()
    handle_command()
    sys.exit(0)


if __main__ == "export-surround-to-git.py":
    main()


'''
User inputs:
    * Mainline branch <M>
    * Repository path <P>
    * Surround server
    * Surround server port
    * Surround username
    * Surround password

Environment:
    * Python script
    * Executed in Bash

Steps:
    * Find all baseline branches in <M> having <P>
        * sscm lsbranch -b"<M>" -p"<P>" -f"<file>"
    * For each baseline/mainline branch <B>
        * Find all files (including deleted files) in <P>
            * sscm ls -b"<B>" -p"<P>" (doesn't find deleted files)
        * For each file <F>
            * Find all versions of file <F>
                * sscm history <F> -b"<B>" -p"<P>" -a"<action>"
            * For each version <V>
                * Add tuple to table (timestamp, branch, path, file, version, action?)
        * Find all snapshot branches that are children of <B>
            * Will need to write wrapper in "C" for sscm_get_branch() API function
        * For each snapshot branch <SB>
            * Add tuple to table (timestamp, <SB>)
    * Walk table in order of timestamp:version
        * For checkin/merge/rollback/add/delete/rename
            * Use git fast-import 'commit' command
        * For snapshot
            * Use git fast-import 'tag' command with 'deleteall' and "Tag Fixup Branches"
    * Integrity check:  Verify Git tags are identical to Surround snapshots

