"""Generates a synthetic (fake) skills assessment letter PDF for testing the redactor."""
import fitz

doc = fitz.open()
page = doc.new_page()

text = """VETASSESS
Skills Assessment Outcome Letter

Date of Letter: 2 July 2026
Reference Number: VET-2026-884213

Applicant Name: Jordan Alexander Price
Date of Birth: 14 March 1994
Passport Number: PA1938204
Client ID: CL-7729104

Address:
42 Wattle Grove
Northcote VIC 3070
Australia

Email: jordan.price94@example.com
Phone: 0412 555 018

Dear Jordan,

We are pleased to advise that your application for a skills assessment in the
occupation of ICT Business Analyst (ANZSCO 261111) has been assessed as
SUITABLE for the purposes of skilled migration to Australia.

This assessment is valid for a period of three years from the date of this
letter and may be used to support an Expression of Interest under the
General Skilled Migration program.

Should you have any questions regarding this outcome, please contact our
office quoting your reference number above.

Yours sincerely,
Skills Assessment Team
VETASSESS
"""

page.insert_text((50, 50), text, fontsize=11)
doc.save("test_letter.pdf")
print("Wrote test_letter.pdf")
