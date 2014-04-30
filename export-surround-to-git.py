#!/usr/bin/python2
# TODO: is this the right string recommended for python2?  2.7?

# TODO:  standard format for headers?
# Author:  Jonathan Elchison <JElchison@Gmail.com>
# License:  TODO
# Environment:  Assumes running in Bash version TODO.  Assumes sscm client version TODO.

import sys
import argparse
import subprocess

# TODO pep8
# TODO pylint


map actions = {(SNAPSHOT, "<snapshot>")}


class DatabaseRecord {
    def DatabaseRecord(self, timestamp, action, mainline, branch, path, version):
        self.timestamp = timestamp
        self.action = action
        self.mainline = mainline
        self.branch = branch
        self.path = path
        self.version = version
}


def print_usage():
    sys.stderr.output("Usage")
    # TODO


def find_all_branches_in_mainline_containing_path(mainline, path):
    # TODO
    return ("One", "Two")


def find_all_files_in_branch_under_path(mainline, branch, path):
    # TODO
    return ("One", "Two")


def find_all_file_versions(mainline, branch, path):
    # TODO
    return ((1, "timestamp1"), (2, "timestamp2"))


def find_all_child_snapshots(mainline, branch):
    # TODO


def add_record_to_database(record):
    # TODO


def get_next_database_record():
    # TODO
    return record


def cmd_parse(mainline, path):
    branches = find_all_branches_in_mainline_containing_path(mainline, path)
    for branch in branches:
        files = find_all_files_in_branch_under_path(mainline, branch, path)
        for file in files:
            versions = find_all_file_versions(mainline, branch, path+file)
            for version in versions:
                add_record_to_database(DatabaseRecord(timestamp, action, mainline, branch, path+file, version))
    snapshots = find_all_child_snapshots(mainline, branch)
    for snapshot in snapshots:
        add_record_to_database(DatabaseRecord(timestamp, actions[SNAPSHOT], mainline, branch, None, None))


def process_database_record(record):
    if record.action == actions[SNAPSHOT]:
        # TODO
    else
        raise Exception("Unknown record action")


def cmd_export(database):
    record = get_next_database_record(database)
    while (record):
        process_database_record(record)
        record = get_next_database_record(database)


def handle_command(args, opts):
    command = args[0]

    if command == "parse":
        database = create_database()
        cmd_parse(database)
    elif command == "export":
        database = # TODO
        cmd_export(database)
    elif command == "all":
        database = create_database()
        cmd_parse(database)
        cmd_export(database)
    else:
        print_usage()
        raise Exception("Unknown command")


def parse_arguments():
    # TODO
    pass


def main():
    try:
        args, opts = parse_arguments(sys.argv)
        handle_command(args, opts)
        sys.exit(0)
    except Exception as e:
        sys.stderr.output(e)
        sys.exit(1)


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
'''
