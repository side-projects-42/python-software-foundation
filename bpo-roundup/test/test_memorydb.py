import unittest, os, shutil, time

from roundup import hyperdb

from db_test_base import DBTest, ROTest, SchemaTest, config, setupSchema
import memorydb

class memorydbOpener:
    module = memorydb

    def nuke_database(self):
        # really kill it
        self.db = None

    db = None
    def open_database(self):
        if self.db is None:
            self.db = self.module.Database(config, 'admin')
        return self.db

    def setUp(self):
        self.open_database()
        setupSchema(self.db, 1, self.module)

    def tearDown(self):
        if self.db is not None:
            self.db.close()

    # nuke and re-create db for restore
    def nukeAndCreate(self):
        self.db.close()
        self.nuke_database()
        self.db = self.module.Database(config, 'admin')
        setupSchema(self.db, 0, self.module)


class memorydbDBTest(memorydbOpener, DBTest, unittest.TestCase):
    pass


class memorydbROTest(memorydbOpener, ROTest, unittest.TestCase):
    def setUp(self):
        self.db = self.module.Database(config)
        setupSchema(self.db, 0, self.module)


class memorydbSchemaTest(memorydbOpener, SchemaTest, unittest.TestCase):
    pass


from session_common import SessionTest
class memorydbSessionTest(memorydbOpener, SessionTest, unittest.TestCase):
    def setUp(self):
        self.db = self.module.Database(config, 'admin')
        setupSchema(self.db, 1, self.module)
        self.sessions = self.db.sessions

# vim: set filetype=python ts=4 sw=4 et si

