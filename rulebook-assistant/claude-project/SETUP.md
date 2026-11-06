# No-code route: Claude Projects

Takes about 10 minutes in claude.ai. No API key or code needed.

## Set it up

1. Go to claude.ai, open **Projects**, and create a project named **Rulebook Assistant**.
2. Open the project's instructions and paste in everything from `project-instructions.txt`.
3. Add these 6 files from `Data Sources` to the project's knowledge:

   | Doc | Upload this file | Version |
   | --- | --- | --- |
   | 1 | `1 California RFP.docx` | 1.0 |
   | 2 | `2 Kansas UX assets - 1.1.docx` | 1.1 |
   | 3 | `3 Compliance rules - 1.1.docx` | 1.1 |
   | 4 | `4 Skills and rates.docx` | 1.0 |
   | 5 | `5 Contract library - 1.1.docx` | 1.1 |
   | 6 | `6 Past bids.docx` | 1.0 |

   Do not upload the older `2 Kansas UX assets.docx`, `3 Compliance rules.docx` or
   `5 Contract library.docx`. They are superseded, and the assistant could quote them.

4. Test it with the questions below.

## Test questions

| Question | A correct answer says |
| --- | --- |
| What is our fallback on limitation of liability? | Cap at 2x contract value; general counsel approves anything outside it (Contract library v1.1) |
| What is our preferred data breach notice period? | 48 hours, not the 72 in version 1.0 (Contract library v1.1) |
| How many Kansas notice templates are there? | 10 eligibility notices (Kansas UX assets v1.1) |
| Is there a compliance rule for Medi-Cal threshold languages? | First line "Not in the rulebook", then an escalation line; RFP R-05 and rule C-10 appear only as closest material |
| What is the parking policy at the Sacramento office? | First line "Not in the rulebook", then "Escalate to: the rulebook owner" |
| Who approves a warranty redline outside the fallback? | First line "Conflict:". The playbook table says the delivery manager; its introduction says anything outside the fallback goes to legal at H5 (Contract library v1.1) |

## At each release

The Document Register is the record of which files are current.

1. Update `Rulebook Agent Document Register.xlsx`.
2. In the project, remove the superseded file and add the new one.
3. Update the version table in `project-instructions.txt` and paste it into the project again.
4. Run the test questions again.

## Limits of this route

- Citations are written by the model as text, so they are less exact than the API route's
  citations, and nothing checks them against the documents.
- Claude shows no cache statistics here, so you can't see hits or costs per question.
- Check your plan's rules on data handling and who can see the project before sharing it.
