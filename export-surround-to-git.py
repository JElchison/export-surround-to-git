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
import os
import shutil

# TODO pep8
# TODO pylint
# TODO spell-check
# TODO test with python3
# TODO make exception handlers as specific as possible
# TODO add verbose comments
# TODO see other TODOs


scratchDir = "scratch/"
mark = 0

class Actions:
    BRANCH_SNAPSHOT = 1
    BRANCH_BASELINE = 2
    FILE_MODIFY = 3
    FILE_DELETE = 4
    FILE_RENAME = 5

actionMap = {"add"                   : Actions.FILE_MODIFY,
             "add to repository"     : Actions.FILE_MODIFY,
             "add to branch"         : None,
             "add from branch"       : Actions.FILE_MODIFY,
             "attach to issue"       : None,  # TODO
             "attach to test case"   : None,  # TODO
             "attach to requirement" : None,  # TODO
             "attach to external"    : None,  # TODO
             "break share"           : None,
             "checkin"               : Actions.FILE_MODIFY,
             "delete"                : Actions.FILE_DELETE,
             "duplicate"             : Actions.FILE_MODIFY,  # TODO verify this
             "file destroyed"        : Actions.FILE_DELETE,
             "file moved"            : Actions.FILE_RENAME,
             "file renamed"          : Actions.FILE_RENAME,
             "label"                 : None,  # TODO
             "promote"               : None,
             "promote from"          : Actions.FILE_MODIFY,
             "promote to"            : Actions.FILE_MODIFY,
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
    def __init__(self, tuple):
        self.init(tuple[0], tuple[1], tuple[2], tuple[3], tuple[4], tuple[5], tuple[6], tuple[7], tuple[8])

    def init(self, timestamp, action, mainline, branch, path, version, author, comment, data):
        self.timestamp = timestamp
        self.action = action
        self.mainline = mainline
        self.branch = branch
        self.path = path
        self.version = version
        self.author = author
        self.comment = comment
        self.data = data

    def get_tuple(self):
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
    #print "\ncmd =", cmd
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdoutdata, stderrdata = p.communicate()
    sys.stderr.write(stderrdata)
    return filter(None,stdoutdata.split('\n'))


def find_all_files_in_branch_under_path(mainline, branch, path):
    cmd = 'sscm ls -b"%s" -p"%s" -r | grep -v \'Total listed files\' | sed -r \'s/unknown status.*$//g\'' % (branch, path)
    #print "\ncmd =", cmd
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdoutdata, stderrdata = p.communicate()
    sys.stderr.write(stderrdata)
    lines = filter(None,stdoutdata.split('\n'))
    fileList = []
    for line in lines:
        if line[0] != ' ':
            lastDirectory = line
        elif line[1] != ' ':
            fileList.append("%s/%s" % (lastDirectory, line.strip()))
    return fileList


def is_snapshot_branch(branch, repo):
    cmd = 'sscm bp -b"%s" -p"%s"' % (branch, repo)
    with open(os.devnull, 'w') as fnull:
        result = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=fnull).communicate()[0]
    return result.find("snapshot") != -1


def find_all_file_versions(mainline, branch, path):
    repo, file = os.path.split(path)
    cmd = 'sscm history "%s" -b"%s" -p"%s" | tail -n +5' % (file, branch, repo)
    #print "\ncmd =", cmd
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdoutdata, stderrdata = p.communicate()
    sys.stderr.write(stderrdata)
    lines = filter(None,stdoutdata.split('\n'))
    histRegex = re.compile(r"^(?P<action>[\w]+([^\[\]]*[\w]+)?)(\[(?P<data>[^\[\]]*?)( v\. [\d]+)?\])?([\s]+)(?P<author>[\w]+([^\[\]]*[\w]+)?)([\s]+)(?P<version>[\d]+)([\s]+)(?P<timestamp>[\w]+[^\[\]]*)$")
    versionList = []
    bFoundOne = False
    for line in lines:
        result = histRegex.search(line)
        if result:
            if bFoundOne:
                versionList.append((timestamp, action, int(version), author, comment, data))
            bFoundOne = True
            action = result.group("action")
            author = result.group("author")
            version = result.group("version")
            timestamp = result.group("timestamp")
            comment = None
            data = result.group("data")
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
    c.execute('''CREATE TABLE operations (timestamp INTEGER NOT NULL, action INTEGER NOT NULL, mainline TEXT NOT NULL, branch TEXT NOT NULL, path TEXT, version INTEGER, author TEXT, comment TEXT, data TEXT, PRIMARY KEY(action, mainline, branch, path, version, author, comment, data))''')
    database.commit()
    return database 


def add_record_to_database(record, database):
    c = database.cursor()
    #print "Inserting =", record.get_tuple()
    try:
        c.execute('''INSERT INTO operations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', record.get_tuple())
    except sqlite3.IntegrityError as e:
        #sys.stderr.write("\nDetected duplicate record %s" % str(record.get_tuple()))
        pass
    database.commit()


def cmd_parse(mainline, path, file, database):
    sys.stderr.write("[+] Beginning parse phase...")
    branches = find_all_branches_in_mainline_containing_path(mainline, path, file)
    for branch in branches:
        sys.stderr.write("\n[*] Parsing branch '%s' ..." % branch)
        files = find_all_files_in_branch_under_path(mainline, branch, path)
        for file in files:
            #sys.stderr.write("\n[*] \tParsing file '%s' ..." % file)
            versions = find_all_file_versions(mainline, branch, file)
            #sys.stderr.write("\n[*] \t\tversions = %s" % versions)
            for timestamp, action, version, author, comment, data in versions:
                epoch = int(time.mktime(time.strptime(timestamp, "%m/%d/%Y %I:%M %p")))
                if action == "add to branch":
                    if is_snapshot_branch(data, os.path.split(file)[0]):
                        branchAction = Actions.BRANCH_SNAPSHOT
                    else:
                        branchAction = Actions.BRANCH_BASELINE
                    add_record_to_database(DatabaseRecord((epoch, branchAction, mainline, branch, path, version, author, comment, data)), database)
                else:
                    add_record_to_database(DatabaseRecord((epoch, actionMap[action], mainline, branch, file, version, author, comment, data)), database)
    sys.stderr.write("\n[+] Parse phase complete")


def translate_branch_name(name):
    # pre-processing
    name = re.sub(r'[\/]+', r'/', name)

    # apply rules from git check-ref-format
    name = name.replace("/.", "/_")
    name = re.sub(r'\.lock($|\/)', r'_lock', name)
    name = re.sub(r'[\.]+', r'_', name)
    for char in name:
        if char < '\040' or char == '\177':
            char = '_'
    name = name.replace(" ", "-")
    name = re.sub(r'[\~\^\:\?\*\[\\]+', r'_', name)
    name = re.sub(r'(^[\/]|[\/\.]$)', r'_', name)
    name = name.replace("@{", "__")
    return name


def print_blob_for_file(branch, fullPath, version=None):
    global mark

    path, file = os.path.split(fullPath)
    localPath = scratchDir + file
    if os.path.isfile(localPath):
        os.remove(localPath)
    if version:
        cmd = 'sscm get "%s" -b"%s" -p"%s" -d"%s" -f -i -v%d' % (file, branch, path, scratchDir, version)
    else:
        cmd = 'sscm get "%s" -b"%s" -p"%s" -d"%s" -f -i' % (file, branch, path, scratchDir)
    with open(os.devnull, 'w') as fnull:
        subprocess.Popen(cmd, shell=True, stdout=fnull, stderr=fnull).communicate()

    mark = mark + 1
    print "blob"
    print "mark :%d" % mark
    print "data %d" % os.path.getsize(localPath)
    with open(localPath, "rb") as f:
        print f.read()
    return mark


def process_database_record(record):
    global mark
    # TODO how detect local time zone?  does Surround store time in UTC?
    timezone = "-0500"

    if record.action == Actions.BRANCH_SNAPSHOT:
        print "reset TAG_FIXUP"
        print "from refs/heads/%s" % translate_branch_name(record.branch)
        print
        files = find_all_files_in_branch_under_path(record.mainline, record.data, record.path)
        startMark = None
        for file in files:
            blobMark = print_blob_for_file(record.branch, file)
            if not startMark:
                startMark = blobMark
        mark = mark + 1
        print "commit TAG_FIXUP"
        print "mark :%d" % mark
        print "author %s <%s> %s %s" % (record.author, record.author, record.timestamp, timezone)
        print "committer %s <%s> %s %s" % (record.author, record.author, record.timestamp, timezone)
        if record.comment:
            print "data %d" % len(record.comment)
            print record.comment
        else:
            print "data 0"
        print "merge refs/heads/%s" % translate_branch_name(record.branch)
        print "deleteall"
        iterMark = startMark
        for file in files:
            print "M 100644 :%d %s" % (iterMark, file)
            iterMark = iterMark + 1
        if iterMark != mark:
            raise Exception("Marks fell out of sync while tagging '%s'." % record.data)
        print "tag %s" % translate_branch_name(record.data)
        print "from TAG_FIXUP"
        print "tagger %s <%s> %s %s" % (record.author, record.author, record.timestamp, timezone)
        if record.comment:
            print "data %d" % len(record.comment)
            print record.comment
        else:
            print "data 0"
    elif record.action == Actions.BRANCH_BASELINE:
        print "reset refs/heads/%s" % translate_branch_name(record.data)
        print "from refs/heads/%s" % translate_branch_name(record.branch)
    elif record.action == Actions.FILE_MODIFY or record.action == Actions.FILE_DELETE or record.action == Actions.FILE_RENAME:
        if record.action == Actions.FILE_MODIFY:
            blobMark = print_blob_for_file(record.branch, record.path, record.version)
        mark = mark + 1
        print "commit refs/heads/%s" % translate_branch_name(record.branch)
        print "mark :%d" % mark
        print "author %s <%s> %s %s" % (record.author, record.author, record.timestamp, timezone)
        print "committer %s <%s> %s %s" % (record.author, record.author, record.timestamp, timezone)
        if record.comment:
            print "data %d" % len(record.comment)
            print record.comment
        else:
            print "data 0"
        if record.data:
            print "merge refs/heads/%s" % translate_branch_name(record.data)
        if record.action == Actions.FILE_MODIFY: 
            print "M 100644 :%d %s" % (blobMark, record.path)
        elif record.action == Actions.FILE_DELETE:
            print "D %s" % record.path
        elif record.action == Actions.FILE_RENAME:
            print "R %s %s" % (record.path, record.data)
        print
    else:
        raise Exception("Unknown record action")


def get_next_database_record(database, c):
    if not c:
        c = database.cursor()
        c.execute('''SELECT * FROM operations ORDER BY timestamp, version ASC''')
    return c, c.fetchone()


def cmd_export(database):
    sys.stderr.write("\n[+] Beginning export phase...\n")
    count = 0
    c, record = get_next_database_record(database, None)
    count = count + 1
    while (record):
        process_database_record(DatabaseRecord(record))
        c, record = get_next_database_record(database, c)
        count = count + 1
        if count % 10 == 0:
            print "progress", time.strftime('%Y-%m-%d', time.localtime(record[0]))

    # cleanup
    shutil.rmtree(scratchDir)
    if os.path.isfile("./.git/TAG_FIXUP"):
        # TODO why doesn't this work?  is this too early since we're piping our output?
        os.remove("./.git/TAG_FIXUP")

    sys.stderr.write("\n[+] Export complete.  Your new Git repository is ready to use.\nDon't forget to run `git repack` at some future time to improve data locality and access performance.\n\n")


def cmd_verify(database):
    # TODO
    pass


def handle_command(parser):
    args = parser.parse_args()

    if args.command == "parse" and args.mainline and args.path and args.file:
        verify_surround_environment()
        database = create_database()
        cmd_parse(args.mainline[0], args.path[0], args.file[0], database)
    elif args.command == "export" and args.database:
        verify_git_environment()
        cmd_export(args.database[0])
    elif args.command == "verify" and args.database:
        verify_git_environment()
        cmd_verify(args.database[0])
    elif args.command == "all" and args.mainline and args.path and args.file:
        verify_surround_environment()
        verify_git_environment()
        database = create_database()
        cmd_parse(args.mainline[0], args.path[0], args.file[0], database)
        cmd_export(database)
        cmd_verify(database)
    else:
        parser.print_help()
        sys.exit(1)


def parse_arguments():
    parser = argparse.ArgumentParser(prog='export-surround-to-git.py', description='Exports history from Seapine Surround in a format parseable by `git fast-import`.', formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-m', '--mainline', nargs=1, help='Mainline branch containing history to export')
    parser.add_argument('-p', '--path', nargs=1, help='Path containing history to export')
    parser.add_argument('-f', '--file', nargs=1, help='Any filename in target path')  #TODO auto-generate this
    parser.add_argument('-d', '--database', nargs=1, help='Path to local database (only used when resuming an export)')
    parser.add_argument('--version', action='version', version='%(prog)s '+VERSION)
    parser.add_argument('command', nargs='?', default='all')
    parser.epilog = "Example flow:\n\tsscm setclient ...\n\tgit init my-new-repo\n\tcd my-new-repo\n\texport-surround-to-git.py -m Sandbox -p \"Sandbox/Merge Test\" -f blah.txt | git fast-import --stats --export-marks=marks.txt"
    return parser


def main():
    parser = parse_arguments()
    handle_command(parser)
    sys.exit(0)


if __name__ == "__main__":
    main()
