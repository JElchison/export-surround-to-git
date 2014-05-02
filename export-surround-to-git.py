#!/usr/bin/python2
# TODO: is this the right string recommended for python2?  2.7?

# export-surround-to-git.py
#
# Python script to export history from Seapine Surround in a format parseable by `git fast-import`.
#
# Version 1.0.0
#
# Copyright (C) 2014 Jonathan Elchison <JElchison@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.


# Environment:  Assumes running in Bash version TODO.  Assumes sscm client version TODO.


import sys
import argparse
import subprocess

# TODO pep8
# TODO pylint
# TODO spell-check


class Actions:
    BRANCH_SNAPSHOT = 1
    BRANCH_BASELINE = 2
    FILE_MODIFY = 3
    FILE_DELETE = 4
    FILE_RENAME = 5


class DatabaseRecord:
    def DatabaseRecord(self, timestamp, action, mainline, branch, path, version, data):
        self.timestamp = timestamp
        self.action = action
        self.mainline = mainline
        self.branch = branch
        self.path = path
        self.version = version
        self.data = data


def verify_surround_environment():
    # TODO ensure sscm is in PATH and correct version
    # TODO ensure username, password, server, and port are already cached
    pass


def print_usage():
    sys.stderr.write("Usage")
    # TODO


def find_all_branches_in_mainline_containing_path(mainline, path):
    # TODO
    return ("One", "Two")


def find_all_files_in_branch_under_path(mainline, branch, path):
    # TODO
    return ("One", "Two")


def find_all_file_versions(mainline, branch, path):
    # TODO
    return (("timestamp1", "action1", 1, None), ("timestamp2", "addtobranch", 2, "childbranch"))


def add_record_to_database(record, database):
    # TODO
    # TODO: ensure no duplicate records in database
    pass


def get_next_database_record(database):
    # TODO
    return record


def cmd_parse(mainline, path):
    branches = find_all_branches_in_mainline_containing_path(mainline, path)
    for branch in branches:
        files = find_all_files_in_branch_under_path(mainline, branch, path)
        for file in files:
            versions = find_all_file_versions(mainline, branch, path+file)
            for timestamp, action, version, data in versions:
                if action == "checkin" or action == "merge" or action == "add" or action == "rollback":
                    add_record_to_database(DatabaseRecord(timestamp, Actions.FILE_MODOFY, mainline, branch, path+file, version, data))
                if action == "delete":
                    add_record_to_database(DatabaseRecord(timestamp, Actions.FILE_DELETE, mainline, branch, path+file, version, data))
                if action == "rename":
                    add_record_to_database(DatabaseRecord(timestamp, Actions.FILE_RENAME, mainline, branch, path+file, version, data))
                elif action == "addtobranch":
                    if is_snapshot_branch(data):
                        add_record_to_database(DatabaseRecord(timestamp, Actions.BRANCH_SNAPSHOT, mainline, branch, path, version, data))
                    else:
                        add_record_to_database(DatabaseRecord(timestamp, Actions.BRANCH_BASELINE, mainline, branch, path, version, data))


def process_database_record(record):
    if record.action == actions[SNAPSHOT]:
        # TODO
        pass
    else:
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
        database = True  # TODO
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
    verify_surround_environment()
    args, opts = parse_arguments(sys.argv)
    handle_command(args, opts)
    sys.exit(0)


if __name__ == "__main__":
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
    * Walk table in order of timestamp:version
        * For checkin/merge/rollback/add/delete/rename
            * Use git fast-import 'commit' command
        * For snapshot
            * Use git fast-import 'tag' command with 'deleteall' and "Tag Fixup Branches"
    * Integrity check:  Verify Git tags are identical to Surround snapshots
'''
