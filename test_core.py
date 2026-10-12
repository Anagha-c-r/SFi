"""Tests for dataset loading, file parsing, validation and payload building.

These use only the standard library and openpyxl, so they run with either
`pytest` or `python -m unittest`.
"""
import io
import json
import unittest
from datetime import date

from app.datasets.registry import all_datasets, get_dataset
from app.services.parsing import ParseError, parse_upload
from app.services.payload import envelope, rows_to_csv, template_csv
from app.services.validation import validate_rows


class RegistryTests(unittest.TestCase):
    def test_all_46_datasets_load(self):
        ds = all_datasets()
        self.assertEqual(len(ds), 46)
        numbers = sorted(d.number for d in ds.values())
        self.assertEqual(numbers, list(range(2, 48)))

    def test_every_dataset_is_complete(self):
        for d in all_datasets().values():
            with self.subTest(dataset=d.code):
                self.assertTrue(d.endpoint.startswith("/api/v1/flows/rest/API_"), d.endpoint)
                self.assertRegex(d.endpoint, r"/[Ss]ubmit\w+$|/\w+Info$")
                self.assertTrue(d.array_key)
                self.assertGreaterEqual(len(d.fields), 5)
                self.assertIsNotNone(d.row_id_field, "every dataset has a ROW ID")
                keys = [f.key for f in d.fields]
                self.assertEqual(len(keys), len(set(keys)), "field keys are unique")
                payload_keys = [f.payload_key for f in d.fields]
                self.assertEqual(len(payload_keys), len(set(payload_keys)), "payload keys are unique")
                for f in d.fields:
                    self.assertIn(f.type, {"string", "number", "date"})


class ParsingTests(unittest.TestCase):
    def test_csv_with_bom_and_blank_lines(self):
        data = "﻿ROW ID,BANK CODE\r\n1,0000001\r\n\r\n2,0000002\r\n".encode("utf-8")
        p = parse_upload("x.csv", data)
        self.assertEqual(p.headers, ["ROW ID", "BANK CODE"])
        self.assertEqual(len(p.rows), 2)

    def test_xlsx(self):
        from datetime import datetime
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.append(["ROW ID", "REPORTING DATE", "AMOUNT"])
        ws.append([1, datetime(2020, 6, 3), 1500.0])
        buf = io.BytesIO()
        wb.save(buf)
        p = parse_upload("x.xlsx", buf.getvalue())
        self.assertEqual(p.rows[0], {"ROW ID": "1", "REPORTING DATE": "2020-06-03", "AMOUNT": "1500"})

    def test_rejects_other_types(self):
        with self.assertRaises(ParseError):
            parse_upload("x.pdf", b"%PDF")


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.ds = get_dataset("card_acquiring_transactions_information")
        self.headers = [f.name for f in self.ds.fields]

    def row(self, **over):
        base = {f.name: f.example for f in self.ds.fields}
        base.update(over)
        return base

    def test_example_row_is_valid_and_normalized(self):
        res = validate_rows(self.ds, self.headers, [self.row()])
        self.assertTrue(res.is_valid, [i.as_dict() for i in res.issues])
        out = res.rows[0]
        self.assertEqual(out["REPORTING DATE"], "03-Jun-2020")
        self.assertEqual(out["VALUE OF TRANSACTIONS"], "365000.00000")  # commas stripped
        self.assertEqual(out["NUMBER OF TRANSACTIONS"], "1650")

    def test_bad_number_and_date(self):
        name_date = next(f.name for f in self.ds.fields if f.type == "date")
        res = validate_rows(self.ds, self.headers, [self.row(**{"VALUE OF TRANSACTIONS": "abc", name_date: "31/31/2020"})])
        self.assertFalse(res.is_valid)
        msgs = {(i.row, i.field) for i in res.issues}
        self.assertIn((1, "VALUE OF TRANSACTIONS"), msgs)
        self.assertIn((1, name_date), msgs)

    def test_headers_match_by_payload_key_or_snake_case(self):
        headers = ["row_id", "bank_code", "REPORTING DATE"]
        res = validate_rows(self.ds, headers, [{"row_id": "", "bank_code": "1", "REPORTING DATE": "2020-06-03"}])
        self.assertEqual(res.unknown_columns, [])
        self.assertEqual(res.rows[0]["ROW ID"], "1")  # generated

    def test_duplicate_row_id_and_unknown_column(self):
        rows = [self.row(**{"ROW ID": "7"}), self.row(**{"ROW ID": "7"})]
        res = validate_rows(self.ds, self.headers + ["EXTRA"], rows)
        self.assertEqual(res.error_count, 1)
        self.assertEqual(res.warning_count, 1)

    def test_missing_required_column(self):
        headers = [h for h in self.headers if "REPORTING" not in h]
        res = validate_rows(self.ds, headers, [{h: "1" for h in headers}])
        self.assertTrue(any(i.row is None and i.level == "error" for i in res.issues))

    def test_empty_file(self):
        res = validate_rows(self.ds, self.headers, [])
        self.assertFalse(res.is_valid)


class PayloadTests(unittest.TestCase):
    def test_envelope_matches_guide_sample_shape(self):
        ds = get_dataset("card_acquiring_transactions_information")
        env = envelope(ds, institution_code="AB1145", reporting_date=date(2022, 6, 3), rows=[{"ROW ID": "1"}])
        self.assertEqual(list(env), ["INSTITUTION_CODE", "REQUEST_ID", "IS_ATTACHED", "REPORTING_DATE", "CARDACQUIRINGTRANS_DATA"])
        self.assertEqual(env["IS_ATTACHED"], "N")
        self.assertEqual(env["REPORTING_DATE"], "03-Jun-2022")
        json.dumps(env)

    def test_csv_mode_empties_array(self):
        ds = get_dataset("card_acquiring_transactions_information")
        env = envelope(ds, institution_code="X", reporting_date=date(2022, 6, 3), rows=[{"ROW ID": "1"}], attached=True)
        self.assertEqual(env["IS_ATTACHED"], "Y")
        self.assertEqual(env[ds.array_key], [])

    def test_csv_and_template(self):
        ds = get_dataset("foreign_exchange_positions_information")
        body = rows_to_csv(ds, [{"ROW ID": "1", "CURRENCY TYPE CODE": "GBP"}]).decode()
        self.assertTrue(body.startswith("ROW ID,"))
        self.assertIn("GBP", body)
        tpl = template_csv(ds).decode().splitlines()
        self.assertEqual(len(tpl), 2)


if __name__ == "__main__":
    unittest.main()
