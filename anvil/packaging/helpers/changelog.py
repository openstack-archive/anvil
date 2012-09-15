# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Based off of http://www.brianlane.com/nice-changelog-entries.html
#
# git-changelog - Output a rpm changelog
#
# Copyright (C) 2009-2010  Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author: David Cantrell <dcantrell@redhat.com>
# Author: Brian C. Lane <bcl@redhat.com>

import abc
import re
import textwrap

import iso8601

from anvil import shell as sh
from anvil import utils

PER_CALL_AM = 50


class GitChangeLog(object):
    __meta__ = abc.ABCMeta

    def __init__(self, wkdir):
        self.wkdir = wkdir
        self.date_buckets = None

    def _parse_mailmap(self):
        mapping = {}
        mailmap_fn = sh.joinpths(self.wkdir, '.mailmap')
        for line in sh.load_file(mailmap_fn).splitlines():
            line = line.strip()
            if not line.startswith('#') and ' ' in line:
                try:
                    (canonical_email, alias) = [x for x in line.split(' ') if x.startswith('<')]
                    mapping[alias] = canonical_email
                except (TypeError, ValueError, IndexError):
                    pass
        return mapping

    def _get_commit_detail(self, commit, field, am=1):
        detail_cmd = ['git', 'log', '--color=never', '-%s' % (am), "--pretty=format:%s" % (field), commit]
        (stdout, _stderr) = sh.execute(*detail_cmd, cwd=self.wkdir)
        ret = stdout.strip('\n').splitlines()
        if len(ret) == 1:
            ret = ret[0]
        else:
            ret = filter(lambda x: x.strip() != '', ret)
            ret = "\n".join(ret)
        return ret

    def get_log(self):
        if self.date_buckets is None:
            self.date_buckets = self._get_log()
        return self.date_buckets

    def _skip_entry(self, summary, date, email, name):
        email = email.lower().strip()
        if email in ['jenkins@review.openstack.org']:
            return True
        summary = summary.lower().strip()
        if summary.startswith('merge commit'):
            return True
        if summary.startswith("merge branch"):
            return True
        if summary.startswith("merge remote"):
            return True
        if not all([summary, date, email, name]):
            return True
        return False

    def _get_log(self):
        log_cmd = ['git', 'log', '--pretty=oneline', '--color=never']
        (sysout, _stderr) = sh.execute(*log_cmd, cwd=self.wkdir)
        lines = sysout.strip('\n').splitlines()

        # Extract the raw commit details
        try:
            mmp = self._parse_mailmap()
        except IOError:
            mmp = {}
        log = []
        with utils.progress_bar("Git changelog analysis", len(lines) + 1) as pb:
            for i in range(0, len(lines), PER_CALL_AM):
                pb.update(i)

                line = lines[i]
                fields = line.split(' ')
                if not len(fields):
                    continue

                # See: http://opensource.apple.com/source/Git/Git-26/src/git-htmldocs/pretty-formats.txt
                commit_id = fields[0]
                details = self._get_commit_detail(commit_id, "[%s][%ai][%aE][%an]", PER_CALL_AM)
                for det in details.splitlines():
                    details_m = re.match(r"^\s*\[(.*?)\]\[(.*?)\]\[(.*?)\]\[(.*?)\]\s*$", det)
                    if not details_m:
                        continue
                    (summary, date, author_email, author_name) = details_m.groups()
                    author_email = mmp.get(author_email, author_email)
                    date = iso8601.parse_date(date)
                    if self._skip_entry(summary, date, author_email, author_name):
                        continue
                    log.append({
                        'summary': summary,
                        'when': date,
                        'author_email': author_email,
                        'author_name': author_name,
                    })

        # Bucketize the dates by day
        date_buckets = {}
        for entry in log:
            day = entry['when'].date()
            if day in date_buckets:
                date_buckets[day].append(entry)
            else:
                date_buckets[day] = [entry]

        return date_buckets

    @abc.abstractmethod
    def format_log(self):
        raise NotImplementedError()


class RpmChangeLog(GitChangeLog):
    def format_log(self):
        date_buckets = self.get_log()
        lines = []
        dates = date_buckets.keys()
        for d in reversed(sorted(dates)):
            summaries = date_buckets[d]
            for msg in summaries:
                header = "* %s %s <%s>" % (d.strftime("%a %b %d %Y"),
                                           msg['author_name'], msg['author_email'])
                lines.append(header)
                summary = msg['summary']
                sublines = textwrap.wrap(summary, 77)
                if len(sublines):
                    lines.append("- %s" % sublines[0])
                    if len(sublines) > 1:
                        for subline in sublines[1:]:
                            lines.append("  %s" % subline)
        # Replace utf8 oddities with ? just incase
        contents = "\n".join(lines)
        contents = contents.decode('utf8').encode('ascii', 'replace')
        return contents
