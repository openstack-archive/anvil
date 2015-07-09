# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright (C) 2012 Yahoo! Inc. All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import os
import tempfile

from anvil import log
from anvil import test


class TestLog(test.TestCase):
    def setUp(self):
        super(TestLog, self).setUp()
        self.test_logger = log.getLogger().logger
        self.test_logger.handlers = []
        self.log_name = tempfile.mkstemp()[1]

    def tearDown(self):
        if os.path.isfile(self.log_name):
            os.remove(self.log_name)
        super(TestLog, self).tearDown()

    def test_logger_has_two_handlers(self):
        log.setupLogging(log.INFO, tee_filename=self.log_name)
        self.assertEqual(len(self.test_logger.handlers), 2)
