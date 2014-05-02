#!/usr/bin/python2
# TODO: is this the right string recommended for python2?  2.7?

# export-surround-to-git.py
#
# Python script to export history from Seapine Surround in a format parseable by `git fast-import`.
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

VERSION = '1.0.0'

# Environment:  Assumes running in Bash version TODO.  Assumes sscm client version TODO.


import sys
import argparse
import subprocess
import time
import datetime
import sqlite3

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


def find_all_branches_in_mainline_containing_path(mainline, path):
    cmd = 'sscm lsbranch -b"%s" -p"%s" -f"%s"' % (mainline, path, file)
    p = Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdoutdata, stderrdata = p.communicate()
    return filter(None,stdoutdata.split('\n'))


def find_all_files_in_branch_under_path(mainline, branch, path):
    cmd = 'sscm ls -b"%s" -p"%s"' % (branch, path)
    p = Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdoutdata, stderrdata = p.communicate()
    return filter(None,stdoutdata.split('\n'))


def find_all_file_versions(mainline, branch, path):
    cmd = 'sscm history %s -b"%s" -p"%s" -a"%s"' % (file, branch, path, action)
    p = Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdoutdata, stderrdata = p.communicate()
    return filter(None,stdoutdata.split('\n'))


def create_database():
    name = datetime.datetime.fromtimestamp(time.time()).strftime('%Y%m%d%H%M%S') + '.db'
    conn = sqlite3.connect(name)
    c = conn.cursor()
    c.execute('''CREATE TABLE operations (timestamp INTEGER NOT NULL, action TEXT NOT NULL, mainline TEXT NOT NULL, branch TEXT NOT NULL, path TEXT, version INTEGER, data TEXT, PRIMARY KEY(action, mainline, branch, path, version, data))''')
    return conn


def add_record_to_database(record, database):
    c = database.cursor()
    c.execute('''INSERT INTO operations VALUES (?, ?, ?, ?, ?, ?, ?)''', (record.timestamp, record.action, record.mainline, record.branch, record.path, record.version, record.data))
    


def get_next_database_record(database):
    c = database.cursor()
    c.execute('''SELECT * FROM operations ORDER BY timestamp, version ASC''')
    c.fetchone()
    # TODO make c function-static


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
    if record.action == Actions.BRANCH_SNAPSHOT:
        # TODO
        pass
    else:
        raise Exception("Unknown record action")


def cmd_export(database):
    record = get_next_database_record(database)
    while (record):
        process_database_record(record)
        record = get_next_database_record(database)


def handle_command(parser):
    args = parser.parse_args()

    if args.command == "parse":
        verify_surround_environment()
        database = create_database()
        cmd_parse(database)
    elif args.command == "export":
        database = True  # TODO
        cmd_export(database)
    elif args.command == "all":
        verify_surround_environment()
        database = create_database()
        cmd_parse(database)
        cmd_export(database)
    else:
        parser.print_help()
        sys.exit(1)


def parse_arguments():
    parser = argparse.ArgumentParser(prog='export-surround-to-git.py', description='Exports history from Seapine Surround in a format parseable by `git fast-import`.')
    parser.add_argument('--version', action='version', version='%(prog)s '+VERSION)
    parser.add_argument('command', nargs='?', default='all')
    return parser


def main():
    parser = parse_arguments()
    handle_command(parser)
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
