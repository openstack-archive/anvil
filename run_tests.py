#!/usr/bin/env python

"""
To run all tests
    python run_tests.py

To run a single test:
    python run_tests.py
        functional.test_extensions:TestExtensions.test_extensions_json

To run a single test module:
    python run_tests.py functional.test_extensions

"""
import logging
import os
import sys

# Configure logging
logging.basicConfig(format='%(levelname)s: %(message)s')
ROOT_LOGGER = logging.getLogger("")
ROOT_LOGGER.setLevel(logging.WARNING)
LOGGER = logging.getLogger(__name__)

# TODO!
TESTS = []


def parse_suite_filter():
    """ Parses out -O or --only argument and returns the value after it as the
    filter. Removes it from sys.argv in the process. """

    our_suite_filter = None
    if '-O' in sys.argv or '--only' in sys.argv:
        for i in range(len(sys.argv)):
            if sys.argv[i] in ['-O', '--only']:
                if len(sys.argv) > i + 1:
                    # Remove -O/--only settings from sys.argv
                    sys.argv.pop(i)
                    our_suite_filter = sys.argv.pop(i)
                    break
    return our_suite_filter


if __name__ == '__main__':
    suite_filter = parse_suite_filter()
    if suite_filter:
        TESTS = [t for t in TESTS if filter in str(t)]
        if not TESTS:
            print 'No test configuration by the name %s found' % filter
            sys.exit(2)
    #Run test suites
    if len(TESTS) > 1:
        cwd_directory = os.getcwd()
        for test_num, test_cls in enumerate(TESTS):
            try:
                result = test_cls().run()
                if result:
                    LOGGER.error("Run returned %s for test %s. Exiting" %
                                 (result, test_cls.__name__))
                    sys.exit(result)
            except Exception, e:
                print "Error:", e
                LOGGER.exception(e)
                sys.exit(1)
            # Collect coverage from each run. They'll be combined later in .sh
            if '--with-coverage' in sys.argv:
                coverage_file = os.path.join(cwd_directory, ".coverage")
                target_file = "%s.%s" % (coverage_file, test_cls.__name__)
                try:
                    if os.path.exists(target_file):
                        LOGGER.info("deleting %s" % target_file)
                        os.unlink(target_file)
                    if os.path.exists(coverage_file):
                        LOGGER.info("Saving %s to %s" % (coverage_file,
                                                         target_file))
                        os.rename(coverage_file, target_file)
                except Exception, e:
                    LOGGER.exception(e)
                    print ("Failed to move coverage file while running test"
                           ": %s. Error reported was: %s" %
                           (test_cls.__name__, e))
                    sys.exit(1)
    else:
        for test_num, test_cls in enumerate(TESTS):
            try:
                result = test_cls().run()
                if result:
                    LOGGER.error("Run returned %s for test %s. Exiting" %
                                 (result, test_cls.__name__))
                    sys.exit(result)
            except Exception, e:
                print "Error:", e
                LOGGER.exception(e)
                sys.exit(1)
