"""No-network unit tests for cross-engine schema normalization and comparison."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import verify_database_migration as verify


def schema():
    return {
        "columns": {
            "id": {"type": "integer", "nullable": False, "default": ("generated",)},
            "active": {"type": "boolean", "nullable": False, "default": ("literal", True)},
        },
        "primary_key": ("id",),
        "unique_constraints": (("active",),),
        "indexes": ((("active",), (), False, False, ""),),
        "foreign_keys": (),
    }


class SchemaNormalizationTests(unittest.TestCase):
    def test_equivalent_datetime_types(self):
        self.assertEqual(verify.normalize_type("DATETIME"), verify.normalize_type("timestamp without time zone"))

    def test_equivalent_current_timestamp_defaults(self):
        self.assertEqual(
            verify.normalize_default("CURRENT_TIMESTAMP", "timestamp"),
            verify.normalize_default("now()", "timestamp"),
        )

    def test_equivalent_boolean_defaults(self):
        self.assertEqual(verify.normalize_default("1", "boolean"), verify.normalize_default("true", "boolean"))
        self.assertEqual(verify.normalize_default("0", "boolean"), verify.normalize_default("false", "boolean"))

    def test_sequence_default_matches_sqlite_integer_primary_key(self):
        self.assertEqual(verify.normalize_default(None, "integer", generated=True),
                         verify.normalize_default("nextval('t_id_seq'::regclass)", "integer", generated=True))

    def test_string_default_content_is_not_case_or_whitespace_normalized(self):
        self.assertNotEqual(verify.normalize_default("'A  B'", "text"),
                            verify.normalize_default("'a b'::text", "text"))

    def test_schema_difference_names_table_and_property(self):
        source = schema()
        target = schema()
        target["columns"]["active"]["nullable"] = True
        target["primary_key"] = ("active", "id")
        target["unique_constraints"] = ()
        target["indexes"] = ((("id",), (), True, False, ""),)
        target["foreign_keys"] = (("id", "other", "id", "NO ACTION", "CASCADE"),)
        differences = verify.compare_table_schema("purchases", source, target)
        self.assertTrue(any("purchases.active: nullable differs" in item for item in differences))
        self.assertTrue(any("purchases: primary key column order differs" in item for item in differences))
        self.assertTrue(any("purchases: UNIQUE constraints differs" in item for item in differences))
        self.assertTrue(any("purchases: indexes/unique/indexed columns differs" in item for item in differences))
        self.assertTrue(any("purchases: foreign keys differs" in item for item in differences))

    def test_matching_schema_has_no_differences(self):
        self.assertEqual(verify.compare_table_schema("purchases", schema(), schema()), [])


if __name__ == "__main__":
    unittest.main()
