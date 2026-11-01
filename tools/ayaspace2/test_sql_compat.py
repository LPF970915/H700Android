"""Compare the actual adapter SQL with native UPSERT, including promoted choices."""
import itertools
import json
from pathlib import Path
import re
import sqlite3
import unittest

source = (Path(__file__).parent / 'Compat.java').read_text(encoding='utf8')
strings = [json.loads(m[0]) for m in re.finditer(r'"(?:\\.|[^"\\])*"', source)]
def query(prefix):
    found = [s for s in strings if s.startswith(prefix)]
    assert len(found) == 1, prefix
    return found[0]

original_name = query('INSERT INTO identification_history(rom_file_id, filename_game_id)')
original_content = query('INSERT INTO identification_history(rom_file_id, content_exact_seen)')
insert_name = query('INSERT OR IGNORE INTO identification_history(rom_file_id, filename_game_id)')
insert_content = query('INSERT OR IGNORE INTO identification_history(rom_file_id, content_exact_seen)')
update_name = query('UPDATE identification_history SET filename_game_id=')
update_content = query('UPDATE identification_history SET content_exact_seen=')

def connection(initial):
    c = sqlite3.connect(':memory:')
    c.execute('CREATE TABLE identification_history (rom_file_id INTEGER PRIMARY KEY, filename_game_id INTEGER, filename_promoted INTEGER NOT NULL DEFAULT 0 CHECK(filename_promoted IN(0,1)), content_exact_seen INTEGER NOT NULL DEFAULT 0 CHECK(content_exact_seen IN(0,1)))')
    if initial is not None:
        c.execute('INSERT INTO identification_history VALUES (1,?,?,?)', initial)
    c.commit()
    return c

class SqlCompatTest(unittest.TestCase):
    def test_upsert_state_equivalence(self):
        initials = [None] + list(itertools.product([None, 9], [0, 1], [0, 1]))
        operations = [('name', 17), ('name', None), ('content', None)]
        for initial, sequence in itertools.product(initials, itertools.product(operations, repeat=3)):
            with self.subTest(initial=initial, sequence=sequence):
                a, b = connection(initial), connection(initial)
                for kind, value in sequence:
                    if kind == 'name':
                        a.execute(original_name, (1, value))
                        b.execute(insert_name, (1, value))
                        b.execute(update_name, (value, 1))
                    else:
                        a.execute(original_content, (1,))
                        b.execute(insert_content, (1,))
                        b.execute(update_content, (1,))
                    self.assertEqual(a.execute('SELECT * FROM identification_history').fetchall(),
                                     b.execute('SELECT * FROM identification_history').fetchall())
                a.rollback(); b.rollback()
                self.assertEqual(a.execute('SELECT * FROM identification_history').fetchall(),
                                 b.execute('SELECT * FROM identification_history').fetchall())
                a.close(); b.close()

if __name__ == '__main__':
    unittest.main()
