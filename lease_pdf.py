"""Generate a residential lease agreement PDF from lease details.

Pure-Python via fpdf2 (no system deps — runs fine on Streamlit Cloud). Returns
PDF bytes so callers can hand them straight to st.download_button or embed an
inline preview. This produces an example/template lease populated with the
property, unit, tenant, and financial terms entered when creating the lease.
"""

from __future__ import annotations

from datetime import date

from fpdf import FPDF

LANDLORD_DEFAULT = "RentHarbor Property Management"


def _money(v) -> str:
    try:
        return "$" + format(float(v), ",.2f")
    except (TypeError, ValueError):
        return str(v)


class _Lease(FPDF):
    def header(self) -> None:  # noqa: D401 - fpdf hook
        pass

    def footer(self) -> None:  # noqa: D401 - fpdf hook
        self.set_y(-40)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150)
        self.cell(0, 10, f"Page {self.page_no()}  -  This is a sample lease for "
                          "demonstration; have a licensed professional review before signing.",
                  align="C")
        self.set_text_color(0)


def build_lease_pdf(
    *,
    landlord: str = LANDLORD_DEFAULT,
    property_name: str,
    property_address: str = "",
    unit_label: str,
    tenants: list[str],
    rent,
    deposit,
    due_day,
    late_fee,
    start_date: str,
    end_date: str,
    generated_on: str | None = None,
) -> bytes:
    """Return a residential lease agreement as PDF bytes."""
    generated_on = generated_on or date.today().isoformat()
    tenant_str = ", ".join(t for t in tenants if t) or "________________"
    where = property_name + (f", {property_address}" if property_address else "")

    pdf = _Lease(format="Letter", unit="pt")
    pdf.set_auto_page_break(auto=True, margin=54)
    pdf.set_margins(54, 54, 54)
    pdf.add_page()

    # ---- Title ----
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 24, "RESIDENTIAL LEASE AGREEMENT",
             new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(110)
    pdf.cell(0, 14, f"{landlord}   -   Generated {generated_on}",
             new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_text_color(0)
    pdf.ln(12)

    # ---- Key terms block ----
    terms = [
        ("Landlord", landlord),
        ("Tenant(s)", tenant_str),
        ("Premises", f"{where}  -  Unit {unit_label}"),
        ("Lease term", f"{start_date}  to  {end_date}"),
        ("Monthly rent", _money(rent)),
        ("Security deposit", _money(deposit)),
        ("Rent due", f"Day {due_day} of each month"),
        ("Late fee", _money(late_fee)),
    ]
    label_w = 120
    pdf.set_draw_color(225, 225, 220)
    for label, value in terms:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(label_w, 18, label)
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 18, str(value), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)

    # ---- Clauses ----
    clauses = [
        ("1. Term", f"This Agreement is for a fixed term beginning {start_date} and "
                    f"ending {end_date}. Upon expiration it may convert to a month-to-month "
                    "tenancy if both parties agree in writing."),
        ("2. Rent", f"Tenant shall pay rent of {_money(rent)} per month, due on day "
                    f"{due_day} of each month, payable to the Landlord by the method the "
                    "Landlord designates."),
        ("3. Late Charges", f"If rent is not received within the grace period allowed by "
                            f"law, a late fee of {_money(late_fee)} shall be due as additional rent."),
        ("4. Security Deposit", f"Tenant shall deposit {_money(deposit)} as security, to be "
                                "returned per applicable law after deducting for unpaid rent or "
                                "damage beyond normal wear and tear."),
        ("5. Use of Premises", "The Premises shall be used solely as a private residence for "
                               "the named Tenant(s) and their immediate family."),
        ("6. Maintenance", "Tenant shall keep the Premises clean and notify the Landlord "
                           "promptly of needed repairs. Landlord is responsible for maintaining "
                           "the structure and major systems in habitable condition."),
        ("7. Entry", "Landlord may enter the Premises with reasonable advance notice for "
                     "inspection, repairs, or to show the unit, except in emergencies."),
        ("8. Governing Law", "This Agreement is governed by the laws of the state in which "
                             "the Premises are located."),
    ]
    for title, body in clauses:
        pdf.set_font("Helvetica", "B", 10)
        pdf.multi_cell(0, 15, title, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(40)
        pdf.multi_cell(0, 14, body, new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0)
        pdf.ln(4)

    # ---- Signatures ----
    pdf.ln(14)
    pdf.set_font("Helvetica", "", 10)
    col_w = (pdf.w - 54 * 2 - 24) / 2
    y = pdf.get_y()
    pdf.line(54, y + 24, 54 + col_w, y + 24)
    pdf.line(54 + col_w + 24, y + 24, 54 + col_w * 2 + 24, y + 24)
    pdf.set_y(y + 28)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(col_w, 12, "Landlord signature / date")
    pdf.cell(24, 12, "")
    pdf.cell(col_w, 12, "Tenant signature / date", new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())
