# Questions for CBK about the GDI API guide

These problems came up while turning *CBK Integration GDI BSD User Guide* (v1.0, 236 pages) into the portal's dataset files. Each one is a guess in the code until CBK confirms it. Send this list to CBK's GDI support before going live.

## Blocking: the answer changes what we send

1. **Endpoints that repeat.**
   - #8 Accounts Attributes uses `API_DEPOSITCONTRACTSINFOSYNC/1.0/submitDepositContractsData`, the same endpoint as #15 Deposit Contracts.
   - #36 Credit Report Requests and #41 Sources of Information both use `API_TERMINALSINFORMA/1.0/submitTerminalsInfo`, the same endpoint as #26 Terminals Information.

   These look like copy-paste errors. The correct endpoints are needed. The portal marks these three datasets with a warning.

2. **Request format.** The guide says the header is `Content-Type: multipart/mixed` and the body is `form-data`, but every sample is a plain JSON object. We need to know:
   - For JSON (`IS_ATTACHED=N`), is the body raw `application/json`, or a form field holding the JSON?
   - For CSV (`IS_ATTACHED=Y`), what is the file part called?

   The guide links curl files for each dataset, but they are not embedded in the PDF. Please send them. The portal currently sends raw JSON, and multipart with a part named `file` (configurable through `CBK_FILE_FIELD`).

3. **Date format.** The guide says `{DD-MMM-YYYY}` (03-Jun-2020), but the samples use `2020-06-03`, `5/23/2020`, `11/23/2019` and `03-Jan-22`. Which format do the top-level `REPORTING_DATE` and the row-level dates use? The portal defaults to DD-MMM-YYYY, and each institution can change it in Settings.

4. **Field names.** In many datasets the field table and the sample payload name the same field differently. Examples:
   - `MRP FXB CODE` in the table is `MRB FXB/CODE` in the sample (#47).
   - `BUSINESS REPORTING DAY, MONTH & YEAR` in the table is `REPORTING DATE` in the sample (most datasets).
   - `DATE OF RECOVERY` in the table is `RECOVERY DATE` in the sample (#28).

   The portal sends the **sample payload's** names. Each dataset JSON file records both names (`name` and `payload_key`), so it's a one-line fix per field once CBK confirms.

5. **Keys only in the sample.** Some keys appear in the sample payload but not in the field table: `CUSTOMER CATEGORY` (#6) and `DATE DOWNLOADED` (#37). The portal accepts them as optional columns.

## Needed for complete validation

6. **Business rules templates.** Every section links an Excel file, "CBK Data Template (CBs & MFBs)", with the business rules and code lists (`CDCH07`, `CUSTID01`, `FXTXNPS`, `SCFNDT04`, and so on). They are not embedded in the PDF. With them, the portal can check codes and value ranges before a file goes to CBK, instead of waiting for CBK's email.

7. **Mandatory fields.** Only `INSTITUTION_CODE`, `IS_ATTACHED` and `REPORTING_DATE` are marked mandatory (`*`). Which row-level fields are mandatory?

8. **Size limit.** What size triggers `MaximumSizeExceeded`? The portal switches to CSV above `JSON_ROW_LIMIT` rows (default 5,000).

9. **Validation results.** The guide says results arrive by email, referenced by the request number. Is there an API to fetch the status of a `RequestNo`? With one, the portal could update submissions automatically instead of someone recording CBK's result by hand.

10. **Wrong data types.** A few fields are typed `Number` but hold text, such as `CUSTOMER NAME` and `CURRENCY CODE` (#47). The portal treats names, codes and IDs as text.

## Minor

11. Section 11, Collateral Information, is missing from the guide's table of contents.
12. #31's endpoint has a double slash: `/rest//API_WEEKLYCOUNTERFEI`. The portal removes the extra slash.
