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
import re
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

actionMap = {"add to repository"     : Actions.FILE_MODIFY,
             "add to branch"         : None,
             "add from branch"       : Actions.FILE_MODIFY,
             "attach to issue"       : None,  # TODO
             "attach to test case"   : None,  # TODO
             "attach to requirement" : None,  # TODO
             "attach to external"    : None,  # TODO
             "break share"           : None,
             "checkin"               : Actions.FILE_MODIFY,
             "duplicate"             : Actions.FILE_MODIFY,  # TODO verify this
             "file destroyed"        : Actions.FILE_DELETE,
             "file moved"            : Actions.FILE_RENAME,
             "file renamed"          : Actions.FILE_RENAME,
             "label"                 : None,  # TODO
             "promote"               : None,
             "promote from"          : Actions.FILE_MODIFY,
             "rebase from"           : Actions.FILE_MODIFY,
             "rebase with merge"     : Actions.FILE_MODIFY,
             "remove"                : Actions.FILE_DELETE,
             "repo destroyed"        : None,  # TODO verify this
             "repo moved"            : None,  # TODO verify this
             "repo renamed"          : None,  # TODO verify this
             "restore"               : Actions.FILE_MODIFY,
             "share"                 : None,
             "rollback file"         : Actions.FILE_MODIFY,
             "rollback rebase"       : Actions.FILE_MODIFY,
             "rollback promote"      : Actions.FILE_MODIFY}


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
    # read -s -p"Enter Surround password:" pw; sscm setclient -zrseoh9-sp:4900 -y"ElchiJo:$pw"; pw=""
    # sscm version
    pass


def verify_git_environment():
    # TODO ensure git is in PATH and correct version
    # git --version
    pass


def find_all_branches_in_mainline_containing_path(mainline, path, file):
    cmd = 'sscm lsbranch -b"%s" -p"%s" -f"%s" | sed -r \'s/ \((baseline|mainline|snapshot)\)$//g\'' % (mainline, path, file)
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdoutdata, stderrdata = p.communicate()
    return filter(None,stdoutdata.split('\n'))


def find_all_files_in_branch_under_path(mainline, branch, path):
    cmd = 'sscm ls -b"%s" -p"%s" -r | grep -v \'Total listed files\' | sed -r \'s/unknown status.*$//g\'' % (branch, path)
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdoutdata, stderrdata = p.communicate()
    lines = filter(None,stdoutdata.split('\n'))
    fileList = []
    for line in lines:
        if line[0] != ' ':
            lastDirectory = line
        elif line[1] != ' ':
            fileList.append("%s/%s" % (lastDirectory, line.strip()))
    return fileList


def find_all_file_versions(branch, path, file):
    cmd = 'sscm history "%s" -b"%s" -p"%s" | tail -n +5' % (file, branch, path)
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdoutdata, stderrdata = p.communicate()
    lines = filter(None,stdoutdata.split('\n'))
    versionList = []
    bFoundOne = False
    for line in lines:
        # TODO compile this RE once, before the loop (for efficiency)
        result = re.search(r"^([\w]+(.*[\w]+)?)(\[(.*)\])?(\t|[ ]{2,})([\w]+(.*[\w]+)?)(\t|[ ]{2,})([\d]+)(\t|[ ]{2,})([\w]+.*)$", line)
        if result:
            if bFoundOne:
                versionList.append((timestamp, action, int(version), author, comment, data))
            bFoundOne = True
            action = result.group(1)
            author = result.group(6)
            version = result.group(9)
            timestamp = result.group(11)
            comment = None
            data = result.group(4)
        else:
            if not comment:
                comment = re.sub("^ Comments \- ", "", line, count=1)
            else:
                comment += "\n" + line
    if bFoundOne:
        versionList.append((timestamp, action, int(version), author, comment, data))
    return versionList


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


def cmd_parse(mainline, path, file, database):
    branches = find_all_branches_in_mainline_containing_path(mainline, path, file)
    for branch in branches:
        sys.stderr.write("\nNow servicing branch '%s' ..." % branch)
        files = find_all_files_in_branch_under_path(mainline, branch, path)
        for file in files:
            versions = find_all_file_versions(mainline, branch, path+file)
            for timestamp, action, version, author, comment, data in versions:
                epoch = int(time.mktime(time.strptime(timestamp, "%m/%d/%y %I:%M %p")))
                if action == "AddToBranch":
                    if is_snapshot_branch(data):
                        branchAction = Actions.BRANCH_SNAPSHOT
                    else:
                        branchAction = Actions.BRANCH_BASELINE
                    add_record_to_database(DatabaseRecord(epoch, branchAction, mainline, branch, path, version, author, comment, data))
                else:
                    add_record_to_database(DatabaseRecord(epoch, actionMap[action], mainline, branch, path+file, version, author, comment, data))


def print_blob_for_file(branch, path, file, version):
    scratchDir = "scratch"
    os.remove("%s" % (scratchDir, file))
    cmd = 'sscm get "%s" -b"%s" -p"%s" -d"%s" -f -i -v%d' % (file, branch, scratchDir, version)
    subprocess.check_call(cmd, shell=True)

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

    if args.command == "parse" and args.mainline and args.path and args.file:
        verify_surround_environment()
        database = create_database()
        # TODO why are [0] required?
        cmd_parse(args.mainline[0], args.path[0], args.file[0], database)
    elif args.command == "export" and args.database:
        cmd_export(args.database[0])
    elif args.command == "all" and args.mainline and args.path and args.file:
        verify_surround_environment()
        database = create_database()
        cmd_parse(args.mainline[0], args.path[0], args.file[0], database)
        cmd_export(database)
    else:
        parser.print_help()
        sys.exit(1)


def parse_arguments():
    parser = argparse.ArgumentParser(prog='export-surround-to-git.py', description='Exports history from Seapine Surround in a format parseable by `git fast-import`.')
    parser.add_argument('-m', '--mainline', nargs=1, help='Mainline branch containing history to export')
    parser.add_argument('-p', '--path', nargs=1, help='Path containing history to export')
    parser.add_argument('-f', '--file', nargs=1, help='Any filename in target path')  #TODO auto-generate this
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
