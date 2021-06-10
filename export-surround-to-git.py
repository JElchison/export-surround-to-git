#!/usr/bin/env python3

# export-surround-to-git.py
#
# Python script to export history from Seapine Surround in a format parsable by `git fast-import`
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

# TODOs
# - dynamically find a tempory folder to store files. Python should have an os module for this
# - try using sscm setclient to handle authentication instead of passing the password here
# - allow the user to name the database file


# attempt to support both Python2.6+ and Python3
from __future__ import print_function
from enum import unique


VERSION = '0.5.0'


# Environment:  For now, this script requires:
#   * Python 2.7
#   * Bash
#   * sscm command-line client (in path)

# Last tested using:
#   * Python 2.7.6
#   * GNU bash, version 4.3.11(1)-release (i686-pc-linux-gnu)
#   * sscm command-line client version:  2013.0.0 Build 23 (Linux)
#   * Git version 1.9.1
#   * Ubuntu 14.04.1 LTS
#   * Linux 3.13.0-35-generic #62-Ubuntu SMP Fri Aug 15 01:58:01 UTC 2014 i686 i686 i686 GNU/Linux


import sys
import argparse
import subprocess
import re
import time
import datetime
import sqlite3
import os
import shutil


#
# globals
#

# temp directory in cwd, holds files fetched from Surround
scratchDir = "scratch"

# for efficiency, compile the history regex once beforehand
# TODO timestamp should match times more explicitly but I want to ensure timestamps are always printed the sameway from sscm
histRegex = re.compile(r"^(?P<action>[\w]+([^\[\]\r\n]*[\w]+)?)(\[(?P<data>[^\[\]\r\n]*?)( v\. [\d]+)?\]| from \[(?P<from>[^\[\]\r\n]*)\] to \[(?P<to>[^\[\]\r\n]*)\])?([\s]+)(?P<author>[\w]+([^\[\]\r\n]*[\w]+)?)([\s]+)(?P<version>[\d]+)([\s]+)(?P<timestamp>\d\d\/[^\[\]\r\n]*)$", re.MULTILINE | re.DOTALL)

# global "mark" number.  incremented before used, as 1 is minimum value allowed.
mark = 0

# local time zone
# TODO how detect this?  right now we assume EST.
timezone = "-0500"

sscm = "sscm"
username = ""
password = ""

# keeps track of snapshot name --> mark number pairing
tagDict = {}

# actions enumeration
class Actions:
    BRANCH_SNAPSHOT = 1
    BRANCH_BASELINE = 2
    FILE_MODIFY = 3
    FILE_DELETE = 4
    FILE_RENAME = 5

# map between Surround action and Action enum
actionMap = {"add"                   : Actions.FILE_MODIFY,
             "add to repository"     : Actions.FILE_MODIFY,
             "add to branch"         : None,
             "add from branch"       : Actions.FILE_MODIFY, # This doesnt feel like a modify. TODO invesitgate
             "attach to issue"       : None,  # TODO maybe use lightweight Git tag to track this
             "attach to test case"   : None,  # TODO maybe use lightweight Git tag to track this
             "attach to requirement" : None,  # TODO maybe use lightweight Git tag to track this
             "attach to observation" : None,  # TODO maybe use lightweight Git tag to track this
             "attach to external"    : None,  # TODO maybe use lightweight Git tag to track this
             "break share"           : None,
             "Change state - Work in Progress" : None,
             "checkin"               : Actions.FILE_MODIFY,
             "delete"                : Actions.FILE_DELETE,
             "duplicate"             : Actions.FILE_MODIFY,
             "file destroyed"        : Actions.FILE_DELETE,
             "file moved"            : Actions.FILE_RENAME,
             "file renamed"          : Actions.FILE_RENAME,
             "in label"              : None,  # TODO maybe treat this like a snapshot branch
             "label"                 : None,  # TODO maybe treat this like a snapshot branch
             "moved"                 : Actions.FILE_RENAME,
             "promote"               : None,
             "promote from"          : Actions.FILE_MODIFY,
             "promote to"            : Actions.FILE_MODIFY,
             "rebase from"           : Actions.FILE_MODIFY,
             "rebase with merge"     : Actions.FILE_MODIFY,
             "remove"                : Actions.FILE_DELETE,
             "renamed"               : Actions.FILE_RENAME,
             "repo destroyed"        : None,  # TODO might need to be Actions.FILE_DELETE
             "repo moved"            : None,  # TODO might need to be Actions.FILE_DELETE
             "repo renamed"          : None,  # TODO might need to be Actions.FILE_DELETE
             "restore"               : Actions.FILE_MODIFY,
             "share"                 : None,
             "rollback file"         : Actions.FILE_MODIFY,
             "rollback rebase"       : Actions.FILE_MODIFY,
             "rollback promote"      : Actions.FILE_MODIFY}


#
# classes
#

class DatabaseRecord:
    def __init__(self, tuple):
        self.init(tuple[0], tuple[1], tuple[2], tuple[3], tuple[4], tuple[5], tuple[6], tuple[7], tuple[8], tuple[9])

    def init(self, timestamp, action, mainline, branch, path, origPath, version, author, comment, data):
        self.timestamp = timestamp
        self.action = action
        self.mainline = mainline
        self.branch = branch
        self.path = path
        self.origPath = origPath
        self.version = version
        self.author = author
        self.comment = comment
        self.data = data
        self.blob_mark = None

    def set_blob_mark(self, mark):
        self.blob_mark = mark

    def get_tuple(self):
        return (self.timestamp, self.action, self.mainline, self.branch, self.path, self.origPath, self.version, self.author, self.comment, self.data)


def verify_surround_environment():
    # verify we have sscm client installed and in PATH
    cmd = sscm + " version"
    with open(os.devnull, 'w') as fnull:
        p = subprocess.Popen(cmd, shell=True, stdout=fnull, stderr=fnull)
        p.communicate()
        return (p.returncode == 0)


def get_lines_from_sscm_cmd(sscm_cmd):
    # helper function to clean each item on a line since sscm has lots of newlines
    p = subprocess.Popen(sscm_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdoutdata, stderrdata = p.communicate()
    stdoutdata = stdoutdata.decode('utf8')
    stderrdata = (stderrdata.strip()).decode('utf8')
    if stderrdata:
        sys.stderr.write('\n')
        sys.stderr.write('[*] sscm error from cmd ' + sscm_cmd + '\n')
        sys.stderr.write('[*]\t error = ' + stderrdata)
    return [real_line for real_line in stdoutdata.splitlines() if real_line]


def find_all_branches_in_mainline_containing_path(mainline, path):
    # use the -o command on lsbranch to get a full path definition of each
    # branch. This will help us parse later
    cmd = sscm + ' lsbranch -b"%s" -p"%s" -o ' % (mainline, path)
    if username and password:
        cmd = cmd + '-y"%s":"%s" ' % (username, password)

    # FTODO this command yields branches that don't include the path specified.
    # we can however filter out the branches by using the -o option to print
    # the full path of each branch and manually parse incorrect branches out
    # NOTE: don't use '-f' with this command, as it really restricts overall usage.
    branches = get_lines_from_sscm_cmd(cmd)

    our_branches = []
    # Parse the branches and find the branches in the path provided
    # We can ignore snapshot branches here. Their parent branch will be found,
    # and it has all snapshot branch information.
    for branch in branches:
        if branch.startswith(path):
            # Since the branch currently shows the full path we need to get the
            # the branch name by getting only the last element in the path
            match = re.search(r'\/([^\/]+)\s\<.+>\s\((baseline|mainline|snapshot)\)', branch)
            if match.group(2) != 'snapshot':
                our_branches.append(match.group(1))

    return our_branches


def find_all_files_in_branches_under_path(mainline, branches, path):
    fileSet = set()
    for branch in branches:
        sys.stderr.write("\n[*] Looking for files in branch '%s' ..." % branch)

        # use all lines from `ls` except for a few
        cmd = sscm + ' ls -b"%s" -p"%s" -r ' % (branch, path)
        if username and password:
            cmd = cmd + '-y"%s":"%s" ' % (username, password)
        #cmd = cmd + '| grep -v \'Total listed files\' | sed -r \'s/unknown status.*$//g\''
        # TODO why were they only looking for files with unkown status
        lines = get_lines_from_sscm_cmd(cmd)

        # directories are listed on their own line, before a section of their files
        # the last line of the output just prints the number of files found so
        # we can ignore it.
        for line in lines[:-1]:
            if (line.strip())[0] == '-':
                # This is a comment and not a file
                continue
            elif line[0] != ' ':
                lastDirectory = line
            elif line[1] != ' ':
                # Extract the file name for this line
                #file = (line.strip().split())[0]
                end_file_index = line.find(" current")
                if end_file_index == -1:
                    end_file_index = line.find(" unknown status")
                if end_file_index == -1:
                    raise Exception("Couldn't find the filename in ls output")
                file = line[:end_file_index].strip()
                fileSet.add("%s/%s" % (lastDirectory, file))

    return fileSet


def is_snapshot_branch(branch, repo):
    # TODO can we eliminate 'repo' as an argument to this function?
    cmd = sscm + ' branchproperty -b"%s" -p"%s" ' % (branch, repo)
    if username and password:
            cmd = cmd + '-y"%s":"%s" ' % (username, password)
    with open(os.devnull, 'w') as fnull:
        result = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=fnull).communicate()[0].decode("utf8")
    return result.find("snapshot") != -1


def find_all_file_versions(mainline, branch, path):
    repo, file = os.path.split(path)

    #repo = 'T-BCE1-SW-Development/Male_Hair_Removal/MightyLi/Software/Source'
    #file = 'motor.c'

    cmd = sscm + ' history "%s" -b"%s" -p"%s" ' % (file, branch, repo)
    if username and password:
        cmd = cmd + '-y"%s":"%s" ' % (username, password)
    lines = get_lines_from_sscm_cmd(cmd)

    # this is complicated because the comment for a check-in will be on the line *following* a regex match
    versionList = []
    comment = None
    bFoundOne = False
    # The first 4 lines are just the header of this printout
    for line in lines[4:]:
        #sys.stderr.write("\n=== Trying line = " + line)

        result = histRegex.search(line)
        if result:
            # we have a new match.
            #sys.stderr.write("\n******* line match!")

            if bFoundOne:
                # before processing this match, we need to commit the previously found version
                versionList.append((timestamp, action, origFile, int(version), author, comment, data))
            # set bFoundOne once we've found our first version
            bFoundOne = True
            action = result.group("action")
            origFile = result.group("from")
            to = result.group("to")
            author = result.group("author")
            version = result.group("version")
            timestamp = result.group("timestamp")
            # reset comment
            comment = None
            if origFile and to:
                # we're in a rename/move scenario
                data = to
            else:
                # we're (possibly) in a branch scenario
                data = result.group("data")
        else:
            # no match.  this must be a comment line (or the start of a new history line, with a line break).
            #sys.stderr.write("\n------- no line match")

            if not comment:
                # start of comment
                comment = re.sub("^ Comments \- ", "", line, count=1)
            else:
                # continuation of comment
                comment += "\n" + line

                # check for a multi-line comment that is actually a version match
                commentLines = [real_line for real_line in comment.splitlines() if real_line]
                substrings = []
                # '-1' on following line is because we don't need to check the last comment line again.
                # (we just checked it above.)
                for i in range(len(commentLines) - 1):
                    substrings.append('\n'.join(commentLines[i:len(commentLines)]))
                for substring in substrings:
                    #sys.stderr.write("\n----- Trying substring = " + substring)

                    result = histRegex.search(substring)
                    if result:
                        # we have a new match

                        # pull off end part of comment that we're recording as a version
                        if result.start("action") == 0:
                            # using the entire comment
                            comment = None
                        else:
                            # leaving behind the previous comment
                            comment = substring[:result.start("action")-1]

                        if bFoundOne:
                            # before processing this match, we need to commit the previously found version
                            versionList.append((timestamp, action, origFile, int(version), author, comment, data))
                        # set bFoundOne once we've found our first version
                        bFoundOne = True
                        action = result.group("action")
                        origFile = result.group("from")
                        to = result.group("to")
                        author = result.group("author")
                        version = result.group("version")
                        timestamp = result.group("timestamp")
                        # reset comment
                        comment = None
                        if origFile and to:
                            # we're in a rename/move scenario
                            data = to
                        else:
                            # we're (possibly) in a branch scenario
                            data = result.group("data")

                        #sys.stderr.write("\n******* comment match! action = '" + str(action) + "' comment = '" + str(comment) + "'")
                        break

    # before moving on, we need to commit the last found version
    if bFoundOne:
        versionList.append((timestamp, action, origFile, int(version), author, comment, data))

    #sys.stderr.write("\nreturning versionList = " + str(versionList))

    return versionList


def create_database():
    # database file is created in cwd
    name = datetime.datetime.fromtimestamp(time.time()).strftime('%Y%m%d%H%M%S') + '.db'
    database = sqlite3.connect(name)
    c = database.cursor()
    # we intentionally avoid duplicates via the PRIMARY KEY
    c.execute('''CREATE TABLE operations (timestamp INTEGER NOT NULL, action INTEGER NOT NULL, mainline TEXT NOT NULL, branch TEXT NOT NULL, path TEXT, origPath TEXT, version INTEGER, author TEXT, comment TEXT, data TEXT, PRIMARY KEY(action, mainline, branch, path, origPath, version, author, data))''')
    database.commit()
    return database


def add_record_to_database(record, database):
    c = database.cursor()
    try:
        c.execute('''INSERT INTO operations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', record.get_tuple())
    except sqlite3.IntegrityError as e:
        # TODO is there a better way to detect duplicates?  is sqlite3.IntegrityError too wide a net?
        #sys.stderr.write("\nDetected duplicate record %s" % str(record.get_tuple()))
        pass
    database.commit()

    if record.action == Actions.FILE_RENAME:
        c.execute('''UPDATE operations SET origPath=? WHERE action=? AND mainline=? AND branch=? AND path=? AND (origPath IS NULL OR origPath='') AND version<=?''', (record.origPath, Actions.FILE_MODIFY, record.mainline, record.branch, record.path, record.version))
        database.commit()


def cmd_parse(mainline, path, database):
    sys.stderr.write("[+] Beginning parse phase...")

    branches = find_all_branches_in_mainline_containing_path(mainline, path)

    # NOTE how we're passing branches, not branch.  this is to detect deleted files.
    filesToWalk = find_all_files_in_branches_under_path(mainline, branches, path)

    for branch in branches:
        sys.stderr.write("\n[*] Parsing branch '%s' ..." % branch)

        for fullPathWalk in filesToWalk:
            #sys.stderr.write("\n[*] \tParsing file '%s' ..." % fullPathWalk)

            pathWalk, fileWalk = os.path.split(fullPathWalk)

            versions = find_all_file_versions(mainline, branch, fullPathWalk)
            #sys.stderr.write("\n[*] \t\tversions = %s" % versions)
            for timestamp, action, origPath, version, author, comment, data in versions:
                # TODO American date formats are not the only time format. This should be configurable
                epoch = int(time.mktime(time.strptime(timestamp, "%d/%m/%Y %H:%M")))
                # branch operations don't follow the actionMap
                if action == "add to branch":
                    if is_snapshot_branch(data, pathWalk):
                        branchAction = Actions.BRANCH_SNAPSHOT
                    else:
                        branchAction = Actions.BRANCH_BASELINE
                    # each add to branch command happens once for a new branch, but will show up on each file
                    # that is a part of the branch added too. To ensure there are no duplicates use an empty
                    # string for origPath (its irrelevant in the export phase for this action) and set the version
                    # to one. We cant use None/NULL for these values as SQLITE doesnt consider NULL==NULL as a true
                    # statement.
                    add_record_to_database(DatabaseRecord((epoch, branchAction, mainline, branch, path, "NULL", 1, author, comment, data)), database)
                else:
                    if origPath:
                        if action == "renamed":
                            origFullPath = os.path.join(pathWalk, origPath)
                            data = os.path.join(pathWalk, data)
                        elif action == "moved":
                            origFullPath = os.path.join(origPath, fileWalk)
                            data = os.path.join(data, fileWalk)
                    else:
                        origFullPath = None
                    add_record_to_database(DatabaseRecord((epoch, actionMap[action], mainline, branch, fullPathWalk, origFullPath, version, author, comment, data)), database)

    sys.stderr.write("\n[+] Parse phase complete")


# Surround has different naming rules for branches than Git does for branches/tags.
# this function performs a one-way translation from Surround to Git.
def translate_branch_name(name):
    #
    # pre-processing
    #

    # 6. cannot contain multiple consecutive slashes
    # replace multiple with single
    name = re.sub(r'[\/]+', r'/', name)

    #
    # apply rules from `git check-ref-format`
    #

    # 1. no slash-separated component can begin with a dot .
    name = name.replace("/.", "/_")
    # 1. no slash-separated component can end with the sequence .lock
    name = re.sub(r'\.lock($|\/)', r'_lock', name)
    # 3. cannot have two consecutive dots ..  anywhere
    name = re.sub(r'[\.]+', r'_', name)
    # 4. cannot have ASCII control characters (i.e. bytes whose values are lower than \040, or \177 DEL) anywhere
    for char in name:
        if char < '\040' or char == '\177':
            # TODO I'm not sure that modifying 'char' here actually modifies 'name'.  Check this and fix if necessary.
            char = '_'
    # 4. cannot have space anywhere.
    # replace with dash for readability.
    name = name.replace(" ", "-")
    # 4. cannot have tilde ~, caret ^, or colon : anywhere
    # 5. cannot have question-mark ?, asterisk *, or open bracket [ anywhere
    # 10. cannot contain a \
    name = re.sub(r'[\~\^\:\?\*\[\\]+', r'_', name)
    # 6. cannot begin or end with a slash /
    # 7. cannot end with a dot .
    name = re.sub(r'(^[\/]|[\/\.]$)', r'_', name)
    # 8. cannot contain a sequence @{
    name = name.replace("@{", "__")
    # 9. cannot be the single character @
    if name == "@":
        name = "_"

    return name


# this is the function that prints most file data to the stream
def print_blob_for_file(branch, fullPath, timestamp=None):
    global mark

    time_struct = time.localtime(timestamp)
    time_string = time.strftime("%Y%m%d%H:%M:59", time_struct)

    path, file = os.path.split(fullPath)
    localPath = os.path.join(scratchDir, file)
    if os.path.isfile(localPath):
        os.remove(localPath)
    if timestamp:
        # get specified version. You would think the -v option would get the
        # version of the file you want, but this does not work for deleted files.
        # we need to use the time stamp with -s
        cmd = sscm + ' get "%s" -b"%s" -p"%s" -d"%s" -f -i -s"%s" ' % (file, branch, path, scratchDir, time_string)
        if username and password:
            cmd = cmd + '-y"%s":"%s" ' % (username, password)
    else:
        # get newest version
        cmd = sscm + ' get "%s" -b"%s" -p"%s" -d"%s" -f -i ' % (file, branch, path, scratchDir)
        if username and password:
            cmd = cmd + '-y"%s":"%s" ' % (username, password)
    with open(os.devnull, 'w') as fnull:
        subprocess.Popen(cmd, shell=True, stdout=fnull, stderr=fnull).communicate()

    # git fast-import is very particular about the format of the blob command.
    # The data must be given in raw bytes for it to parse the files correctly.
    mark = mark + 1
    sys.stdout.buffer.write(b'blob\n')
    sys.stdout.buffer.write(b'mark :%d\n' % mark)
    line = open(localPath, 'rb').read()
    sys.stdout.buffer.write(b'data %d\n' % len(line))
    sys.stdout.buffer.write(line)
    sys.stdout.buffer.write(b'\n')
    sys.stdout.flush()
    return mark


def process_database_record_group(c):
    global mark

    # will contain a list of the MODIFY, DELETE, and RENAME records in this
    # group to be processed later
    normal_records = []

    while r := c.fetchone():
        record = DatabaseRecord(r)

        if record.action == Actions.BRANCH_SNAPSHOT:
            # the basic idea here is to use a "TAG_FIXUP" branch, as recommended in the manpage for git-fast-import.
            # this is necessary since Surround version-controls individual files, and Git controls the state of the entire branch.
            # the purpose of this commit it to bring the branch state to match the snapshot exactly.

            print("reset TAG_FIXUP")
            print("from refs/heads/%s" % translate_branch_name(record.branch))

            # get all files contained within snapshot
            files = find_all_files_in_branches_under_path(record.mainline, [record.data], record.path)
            startMark = None
            for file in files:
                blobMark = print_blob_for_file(record.data, file)
                if not startMark:
                    # keep track of what mark represents the start of this snapshot data
                    startMark = blobMark

            mark = mark + 1
            print("commit TAG_FIXUP")
            print("mark :%d" % mark)
            # we don't have the legit email addresses, so we just use the author as the email address
            print("author %s <%s> %s %s" % (record.author, record.author, record.timestamp, timezone))
            print("committer %s <%s> %s %s" % (record.author, record.author, record.timestamp, timezone))
            if record.comment:
                print("data %d" % len(record.comment))
                print(record.comment)
            else:
                print("data 0")

            # 'deleteall' tells Git to forget about previous branch state
            print("deleteall")
            # replay branch state from above-recorded marks
            iterMark = startMark
            for file in files:
                print("M 100644 :%d %s" % (iterMark, file))
                iterMark = iterMark + 1
            if iterMark != mark:
                raise Exception("Marks fell out of sync while tagging '%s'." % record.data)

            # finally, tag our result
            print("tag %s" % translate_branch_name(record.data))
            print("from TAG_FIXUP")
            print("tagger %s <%s> %s %s" % (record.author, record.author, record.timestamp, timezone))
            if record.comment:
                print("data %d" % len(record.comment))
                print(record.comment)
            else:
                print("data 0")

            # save off the mapping between the tag name and the tag mark
            tagDict[translate_branch_name(record.data)] = mark

        elif record.action == Actions.BRANCH_BASELINE:
            # the idea hers is to simply 'reset' to create our new branch, the name of which is contained in the 'data' field

            print("reset refs/heads/%s" % translate_branch_name(record.data))

            parentBranch = translate_branch_name(record.branch)
            if is_snapshot_branch(parentBranch, os.path.split(record.path)[0]):
                # Git won't let us refer to the tag directly (maybe this will be fixed in a future version).
                # for now, we have to refer to the associated tag mark instead.
                # (if this is fixed in the future, we can get rid of tagDict altogether)
                print("from :%d" % tagDict[parentBranch])
            else:
                # baseline branch
                print("from refs/heads/%s" % parentBranch)

        elif record.action == Actions.FILE_MODIFY or record.action == Actions.FILE_DELETE or record.action == Actions.FILE_RENAME:
            # this is the usual case
            # We process these at the end as we need to loop through the list
            # several times to get the print order right
            normal_records.append(record)

        else:
            raise Exception("Unknown record action")

        # Flush our buffer. We are going to print a lot, so this helps everything
        # stay in the right order.
        sys.stdout.flush()

    # Here we are going to combine all the "normal records" into a single commit
    if len(normal_records):
        unique_comments = {}

        for record in normal_records:
            if record.action == Actions.FILE_MODIFY:
                    blob_mark = print_blob_for_file(record.branch, record.path, record.timestamp)
                    record.set_blob_mark(blob_mark)
            if record.comment:
                if record.comment not in unique_comments:
                    unique_comments[record.comment] = []
                unique_comments[record.comment].append(record.path)

        mark = mark + 1
        print("commit refs/heads/%s" % translate_branch_name(normal_records[0].branch))
        print("mark :%d" % mark)
        print("author %s <%s> %s %s" % (normal_records[0].author, normal_records[0].author, normal_records[0].timestamp, timezone))
        print("committer %s <%s> %s %s" % (normal_records[0].author, normal_records[0].author, normal_records[0].timestamp, timezone))
        if len(unique_comments):
            full_comment = ""
            for comment, files in unique_comments.items():
                full_comment += (comment + "\n")
                # If we're combining multiple comments lets tell the user which
                # file(s) each comment is associated with
                if len(unique_comments) > 1:
                    full_comment += "Above comment references the following files:\n"
                    for file in files:
                        full_comment += "- %s\n" % file
                    full_comment += "\n"
            print("data %d" % len(full_comment))
            print(full_comment)
        else:
            print("data 0")

        for record in normal_records:
            if record.action == Actions.FILE_MODIFY:
                if record.origPath and record.origPath != "NULL":
                    # looks like there was a previous rename.  use the original name.
                    print("M 100644 :%d %s" % (record.blob_mark, record.origPath))
                else:
                    # no previous rename.  good to use the current name.
                    print("M 100644 :%d %s" % (record.blob_mark, record.path))
            elif record.action == Actions.FILE_DELETE:
                print("D %s" % record.path)
            elif record.action == Actions.FILE_RENAME:
                # NOTE we're not using record.path here, as there may have been multiple renames in the file's history
                print("R %s %s" % (record.origPath, record.data))
            else:
                raise Exception("Unknown record action")

        # Flush our buffer. We are going to print a lot, so this helps everything
        # stay in the right order.
        sys.stdout.flush()


def cmd_export(database):
    sys.stderr.write("\n[+] Beginning export phase...\n")

    if not os.path.exists(scratchDir):
        os.mkdir(scratchDir)

    # Group the database by timestamp, branch and author. This will allow us to find
    # each unique timestamp for each branch (multiple branches can have
    # actions performed at the same time, and a checking aught to have only one author).
    # We want to then go through each operation in these groups as we will group
    # all Surround actions in these timestamps as a single commit
    c1 = database.cursor()
    c2 = database.cursor()
    c1.execute('''SELECT timestamp, branch FROM operations GROUP BY timestamp, branch, author ORDER BY timestamp ASC''')

    count = 0
    records_group = []
    while record := c1.fetchone():
        c2.execute("SELECT * FROM operations WHERE timestamp == %d AND branch == '%s' ORDER BY action ASC" % (record[0], record[1]))
        process_database_record_group(c2)
        count = count + 1
        # print progress every 5 operations
        if count % 5 == 0 and record:
            # just print the date we're currently servicing
            print("progress", time.strftime('%Y-%m-%d', time.localtime(record[0])))

    # cleanup
    try:
        shutil.rmtree(scratchDir)
    except OSError:
        pass
    if os.path.isfile("./.git/TAG_FIXUP"):
        # TODO why doesn't this work?  is this too early since we're piping our output, and then `git fast-import` just creates it again?
        os.remove("./.git/TAG_FIXUP")

    sys.stderr.write("\n[+] Export complete.  Your new Git repository is ready to use.\nDon't forget to run `git repack` at some future time to improve data locality and access performance.\n\n")


def cmd_verify(mainline, path):
    # TODO verify that all Surround baseline branches are identical to their Git counterparts
    # TODO verify that all Surround snapshot branches are identical to their Git counterparts
    # should be able to do this without database
    pass


def handle_command(parser):
    args = parser.parse_args()

    if args.install:
        global sscm
        sscm = args.install[0]

    if args.username and args.password:
        global username
        global password
        username = args.username[0]
        password = args.password[0]

    if args.command == "parse" and args.mainline and args.path:
        verify_surround_environment()
        database = create_database()
        cmd_parse(args.mainline[0], args.path[0], database)
    elif args.command == "export" and args.database:
        verify_surround_environment()
        database = sqlite3.connect(args.database[0])
        cmd_export(database)
    elif args.command == "all" and args.mainline and args.path:
        # typical case
        verify_surround_environment()
        database = create_database()
        cmd_parse(args.mainline[0], args.path[0], database)
        cmd_export(database)
    elif args.command == "verify" and args.mainline and args.path:
        # the 'verify' operation must take place after the export has completed.
        # as such, it will always be conducted as its own separate operation.
        verify_surround_environment()
        cmd_verify(args.mainline[0], args.path[0])
    else:
        parser.print_help()
        sys.exit(1)


def parse_arguments():
    parser = argparse.ArgumentParser(prog='export-surround-to-git.py', description='Exports history from Seapine Surround in a format parsable by `git fast-import`.', formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-m', '--mainline', nargs=1, help='Mainline branch containing history to export')
    parser.add_argument('-p', '--path', nargs=1, help='Path containing history to export')
    parser.add_argument('-d', '--database', nargs=1, help='Path to local database (only used when resuming an export)')
    parser.add_argument('-u', '--username', nargs=1, help='Username for the scm server')
    parser.add_argument('-pw', '--password', nargs=1, help='Password for the scm server')
    parser.add_argument('-i', '--install', nargs=1, help='Full path to sscm executable')
    parser.add_argument('--version', action='version', version='%(prog)s ' + VERSION)
    parser.add_argument('command', nargs='?', default='all')
    parser.epilog = "Example flow:\n\tsscm setclient ...\n\tgit init my-new-repo\n\tcd my-new-repo\n\texport-surround-to-git.py -m Sandbox -p \"Sandbox/Merge Test\" -f blah.txt | git fast-import --stats --export-marks=marks.txt\n\t...\n\tgit repack ..."
    return parser


def main():
    parser = parse_arguments()
    handle_command(parser)
    sys.exit(0)


if __name__ == "__main__":
    main()
