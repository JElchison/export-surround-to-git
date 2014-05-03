#!/usr/bin/env python

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
# TODO test with python3


class Actions:
    BRANCH_SNAPSHOT = 1
    BRANCH_BASELINE = 2
    FILE_MODIFY = 3
    FILE_DELETE = 4
    FILE_RENAME = 5

# TODO make these align with strings returned by sscm history
actionMap = {"checkin" : Actions.FILE_MODIFY,
             "merge"   : Actions.FILE_MODIFY,
             "add"     : Actions.FILE_MODIFY,
             "rollback": Actions.FILE_MODIFY,
             "rename"  : Actions.FILE_RENAME,
             "delete"  : Actions.FILE_DELETE}


class DatabaseRecord:
    def DatabaseRecord(self, timestamp, action, mainline, branch, path, version, author, comment, data):
        self.timestamp = timestamp
        self.action = action
        self.mainline = mainline
        self.branch = branch
        self.path = path
        self.version = version
        self.author = author
        self.comment = comment
        self.data = data

    def get_tuple():
        return (self.timestamp, self.action, self.mainline, self.branch, self.path, self.version, self.author, self.comment, self.data)


def verify_surround_environment():
    # TODO ensure sscm is in PATH and correct version
    # TODO ensure username, password, server, and port are already cached
    pass


def find_all_branches_in_mainline_containing_path(mainline, path):
    cmd = 'sscm lsbranch -b"%s" -p"%s" -f"%s"' % (mainline, path, file)
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdoutdata, stderrdata = p.communicate()
    # TODO
    return filter(None,stdoutdata.split('\n'))


def find_all_files_in_branch_under_path(mainline, branch, path):
    cmd = 'sscm ls -b"%s" -p"%s"' % (branch, path)
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdoutdata, stderrdata = p.communicate()
    # TODO
    return filter(None,stdoutdata.split('\n'))


def find_all_file_versions(mainline, branch, path):
    cmd = 'sscm history %s -b"%s" -p"%s" -a"%s"' % (file, branch, path, action)
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdoutdata, stderrdata = p.communicate()
    # TODO
    return filter(None,stdoutdata.split('\n'))


def create_database():
    name = datetime.datetime.fromtimestamp(time.time()).strftime('%Y%m%d%H%M%S') + '.db'
    database = sqlite3.connect(name)
    c = database.cursor()
    c.execute('''CREATE TABLE operations (timestamp INTEGER NOT NULL, action TEXT NOT NULL, mainline TEXT NOT NULL, branch TEXT NOT NULL, path TEXT, version INTEGER, data TEXT, PRIMARY KEY(action, mainline, branch, path, version, data))''')
    database.commit()
    return database 


def add_record_to_database(record, database):
    c = database.cursor()
    c.execute('''INSERT INTO operations VALUES (?, ?, ?, ?, ?, ?, ?)''', record.get_tuple())
    database.commit()


def get_next_database_record(database, c):
    if not c:
        c = database.cursor()
    c.execute('''SELECT * FROM operations ORDER BY timestamp, version ASC''')
    return c, c.fetchone()


def cmd_parse(mainline, path, database):
    branches = find_all_branches_in_mainline_containing_path(mainline, path)
    for branch in branches:
        sys.stderr.write("Now servicing branch '%s' ..." % branch)
        files = find_all_files_in_branch_under_path(mainline, branch, path)
        for file in files:
            versions = find_all_file_versions(mainline, branch, path+file)
            for timestamp, action, version, author, comment, data in versions:
                if action == "addtobranch":
                    if is_snapshot_branch(data):
                        add_record_to_database(DatabaseRecord(timestamp, Actions.BRANCH_SNAPSHOT, mainline, branch, path, version, author, comment, data))
                    else:
                        add_record_to_database(DatabaseRecord(timestamp, Actions.BRANCH_BASELINE, mainline, branch, path, version, author, comment, data))
                else:
                    add_record_to_database(DatabaseRecord(timestamp, actionMap[action], mainline, branch, path+file, version, author, comment, data))


def print_blob_for_file(path):
    # TODO sscm get file/version to local path
    mark = mark + 1
    print "blob"
    print "mark :%d" % mark
    with open(path, "rb") as f:
        f.seek(os.SEEK_END)
        fileSize = f.tell()
        print "data %d" % fileSize
        f.seek(os.SEEK_SET)
        print f.read()
    print
    return mark


def process_database_record(record):
    if record.action == Actions.BRANCH_SNAPSHOT:
        print "reset TAG_FIXUP" % record.data
        print "from %s" % record.branch
        print
        files = find_all_files_in_branch_under_path(mainline, branch, path)
        for file in files:
            blobMark = print_blob_for_file(file)
            if not startMark:
                startMark = blobMark
        mark = mark + 1
        print "commit TAG_FIXUP" % record.branch
        print "mark :%d" % mark
        print "author %s %s" % (record.author, record.timestamp)
        print "committer %s %s" % (record.author, record.timestamp)
        print "data %d" % len(record.comment)
        print record.comment
        print "from TAG_FIXUP"
        print "merge %s" % record.branch
        print "deleteall"
        iterMark = startMark
        for file in files:
            print "M 100644 :%d %s" % (iterMark, file)
            iterMark = iterMark + 1
        print
        if iterMark != mark:
            raise Exception("Marks fell out of sync while tagging '%s'." % record.data)
        print "tag %s" % record.data
        print "from TAG_FIXUP"
        print "tagger %s %s" % (record.author, record.timestamp)
        print "data %d" % len(record.comment)
        print record.comment
        print
    if record.action == Actions.BRANCH_BASELINE:
        print "reset refs/heads/%s" % record.data
        print "from %s" % record.branch
        print
    if record.action == Actions.FILE_MODIFY or record.action == Actions.FILE_DELETE or record.action == Actions.FILE_RENAME:
        if record.action == Actions.FILE_MODIFY:
            blobMark = print_blob_for_file(record.path)
        mark = mark + 1
        print "commit refs/heads/%s" % record.branch
        print "mark :%d" % mark
        print "author %s %s" % (record.author, record.timestamp)
        print "committer %s %s" % (record.author, record.timestamp)
        print "data %d" % len(record.comment)
        print record.comment
        print "from %s" % record.branch
        if record.data:
            print "merge %s" % record.data
        if record.action == Actions.FILE_MODIFY: 
            print "M 100644 :%d %s" % (blobMark, record.path)
        elif record.action == Actions.FILE_DELETE:
            print "D %s" % record.path
        elif record.action == Actions.FILE_RENAME:
            print "R %s %s" % (record.path, record.data)
        print
    else:
        raise Exception("Unknown record action")


def cmd_export(database):
    c, record = get_next_database_record(database, None)
    while (record):
        process_database_record(record)
        c, record = get_next_database_record(database, c)
    # TODO `rm .git/TAG_FIXUP`


def handle_command(parser):
    args = parser.parse_args()

    if args.command == "parse" and args.mainline and args.path:
        verify_surround_environment()
        database = create_database()
        cmd_parse(args.mainline, args.path, database)
    elif args.command == "export" and args.database:
        cmd_export(args.database)
    elif args.command == "all" and args.mainline and args.path:
        verify_surround_environment()
        database = create_database()
        cmd_parse(args.mainline, args.path, database)
        cmd_export(database)
    else:
        parser.print_help()
        sys.exit(1)


def parse_arguments():
    parser = argparse.ArgumentParser(prog='export-surround-to-git.py', description='Exports history from Seapine Surround in a format parseable by `git fast-import`.')
    parser.add_argument('-m', '--mainline', nargs=1, help='Mainline branch containing history to export')
    parser.add_argument('-p', '--path', nargs=1, help='Path containing history to export')
    parser.add_argument('-d', '--database', nargs=1, help='Path to local database to resume an export')
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
