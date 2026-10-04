"""Document-type registry.

Each document type declares:
  * the form fields the UI should collect,
  * a deterministic builder that turns validated input into a LegalDocument,
  * "anchor" fields whose values must survive any AI rewrite unchanged.

The deterministic builders are both the offline fallback and the factual
baseline that the AI core polishes, so the facts never come from the model.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from .schemas import LegalDocument, Section, Signatory, Term

CURRENCIES = ["INR", "USD", "EUR", "GBP", "AUD", "CAD", "SGD", "AED"]


def F(name, label, type="text", required=True, options=None, default="", placeholder="", group=""):
    return {"name": name, "label": label, "type": type, "required": required,
            "options": options or [], "default": default, "placeholder": placeholder, "group": group}


def fdate(value: str) -> str:
    try:
        d = datetime.strptime(value, "%Y-%m-%d")
        return f"{d.day} {d:%B %Y}"
    except (ValueError, TypeError):
        return value


def money(cur: str, amount: str) -> str:
    try:
        amt = f"{float(str(amount).replace(',', '')):,.2f}".rstrip("0").rstrip(".")
    except ValueError:
        amt = amount
    return f"{cur} {amt}"


def S(heading: str, *paras: str) -> Section:
    return Section(heading=heading, body="\n".join(p for p in paras if p))


GOV = lambda d: S(
    "Governing Law and Jurisdiction",
    f"This Agreement is governed by the laws of {d['governing_law']}. The courts of "
    f"{d['governing_law']} have exclusive jurisdiction over any dispute arising out of or in "
    "connection with this Agreement, subject to any mandatory rules of law to the contrary.")

ENTIRE = lambda: S(
    "Entire Agreement and Amendments",
    "This Agreement is the entire agreement between the parties on its subject matter and "
    "replaces all earlier discussions and understandings. It may be amended only in writing "
    "signed by both parties. If any provision is found unenforceable, the remaining provisions "
    "continue in full force. Neither party waives a right by delaying to exercise it.")


# --------------------------------------------------------------------------- Employment
def build_employment(d) -> LegalDocument:
    sal = f"{money(d['currency'], d['salary'])} per year, paid {d['pay_frequency'].lower()}"
    sections = [
        S("Position and Duties",
          f"The Employer employs the Employee as {d['job_title']}. The Employee will perform the "
          "duties normally associated with that role and any other reasonable duties assigned by the Employer.",
          f"Key responsibilities include: {d['responsibilities']}" if d.get("responsibilities") else "",
          "The Employee will devote their full working time to the Employer, act in good faith and "
          "follow the Employer's lawful policies and instructions."),
        S("Term of Employment",
          f"Employment begins on {fdate(d['start_date'])} and continues as {d['employment_type'].lower()} "
          "employment until terminated under this Agreement.",
          f"The first {d['probation_months']} month(s) are a probationary period during which performance "
          "will be assessed." if d.get("probation_months", "0") not in ("", "0") else ""),
        S("Place of Work", f"The Employee's normal place of work is {d['work_location']}. The Employer may "
          "reasonably require travel or a change of location with appropriate notice."),
        S("Compensation", f"The Employee will receive a gross salary of {sal}, subject to statutory deductions.",
          "The Employer will reimburse reasonable, pre-approved business expenses on presentation of receipts."),
        S("Leave", f"The Employee is entitled to {d['annual_leave_days']} days of paid annual leave per year, "
          "in addition to public holidays and any statutory leave, taken at times agreed with the Employer."),
        S("Confidentiality",
          "The Employee must keep confidential, and use only for the Employer's business, all non-public "
          "information about the Employer, its clients, finances, products and strategy, both during and "
          "after employment. This does not apply to information that is public through no fault of the "
          "Employee or that the law requires to be disclosed. On leaving, the Employee must return or "
          "delete all Employer materials."),
        S("Intellectual Property", "All work product, inventions and materials created by the Employee in the "
          "course of employment belong to the Employer. The Employee will sign any documents reasonably "
          "needed to confirm this ownership."),
    ]
    if d.get("non_solicit_months", "0") not in ("", "0"):
        sections.append(S("Non-Solicitation",
            f"For {d['non_solicit_months']} month(s) after employment ends, the Employee will not solicit the "
            "Employer's clients or employees for a competing purpose. The parties agree this restriction is "
            "reasonable and no wider than necessary to protect the Employer's legitimate interests."))
    sections += [
        S("Termination", f"Either party may end this Agreement by giving {d['notice_days']} days' written notice. "
          "The Employer may terminate immediately, without notice or pay in lieu, for serious misconduct, "
          "material breach or conduct that damages the Employer. On termination the Employee will be paid "
          "all salary earned up to the last day of employment."),
        GOV(d), ENTIRE(),
    ]
    return LegalDocument(
        title="Employment Agreement", document_type="employment_contract",
        preamble=f"This Employment Agreement is made on {fdate(d['effective_date'])} between "
                 f"{d['employer_name']} of {d['employer_address']} (the \"Employer\") and "
                 f"{d['employee_name']} of {d['employee_address']} (the \"Employee\").",
        terms=[Term(label="Employer", value=d["employer_name"]), Term(label="Employee", value=d["employee_name"]),
               Term(label="Job Title", value=d["job_title"]), Term(label="Start Date", value=fdate(d["start_date"])),
               Term(label="Employment Type", value=d["employment_type"]), Term(label="Compensation", value=sal),
               Term(label="Notice Period", value=f"{d['notice_days']} days"),
               Term(label="Annual Leave", value=f"{d['annual_leave_days']} days")],
        sections=sections,
        signatories=[Signatory(name=d["employer_name"], role="Employer"),
                     Signatory(name=d["employee_name"], role="Employee")])


# --------------------------------------------------------------------------- NDA
def build_nda(d) -> LegalDocument:
    mutual = d["nda_type"].startswith("Mutual")
    kind = "Mutual Non-Disclosure Agreement" if mutual else "Non-Disclosure Agreement"
    who = ("Each party may disclose and receive Confidential Information. A party disclosing information is the "
           "\"Disclosing Party\" and the party receiving it is the \"Receiving Party\" for that information."
           if mutual else
           f"{d['disclosing_party']} is the \"Disclosing Party\" and {d['receiving_party']} is the \"Receiving Party\".")
    sections = [
        S("Purpose and Roles", f"The parties wish to share confidential information for the following purpose: "
          f"{d['purpose']} (the \"Purpose\").", who),
        S("Definition of Confidential Information",
          "\"Confidential Information\" means all non-public information disclosed by or for the Disclosing Party, "
          "in any form, that is marked confidential or that a reasonable person would understand to be confidential.",
          f"Without limitation it includes: {d['confidential_scope']}"),
        S("Obligations of the Receiving Party", "The Receiving Party will:",
          "- use Confidential Information only for the Purpose;",
          "- keep it confidential using at least the care it uses for its own sensitive information, and no less "
          "than reasonable care;",
          "- limit access to those personnel and advisers who need it and are bound by equivalent duties; and",
          "- promptly notify the Disclosing Party of any unauthorised use or disclosure."),
        S("Exclusions", "These obligations do not apply to information that: (a) is or becomes public through no "
          "fault of the Receiving Party; (b) was lawfully known to the Receiving Party before disclosure; "
          "(c) is lawfully received from a third party without restriction; or (d) is independently developed "
          "without use of the Confidential Information."),
        S("Compelled Disclosure", "If the law or a court requires disclosure, the Receiving Party will, where "
          "lawful, give the Disclosing Party prompt notice and disclose only what is legally required."),
        S("Term and Survival", f"This Agreement applies to disclosures made within {d['term_years']} year(s) of the "
          f"Effective Date. The confidentiality obligations continue for {d['survival_years']} year(s) after "
          "this Agreement ends, and indefinitely for trade secrets."),
        S("Return or Destruction", "On written request or when the Purpose ends, the Receiving Party will return or "
          "securely destroy all Confidential Information and confirm this in writing, except copies it must keep "
          "by law, which remain subject to this Agreement."),
        S("No Licence or Warranty", "Confidential Information remains the property of the Disclosing Party. "
          "Nothing here grants any licence or ownership right, or creates any obligation to enter a further "
          "transaction. Information is provided \"as is\"."),
        S("Remedies", "Unauthorised disclosure may cause harm that damages cannot fully repair, so the Disclosing "
          "Party may seek injunctive relief in addition to any other remedy."),
        GOV(d), ENTIRE(),
    ]
    return LegalDocument(
        title=kind, document_type="nda",
        preamble=f"This {kind} is effective {fdate(d['effective_date'])} between {d['disclosing_party']} of "
                 f"{d['disclosing_address']} and {d['receiving_party']} of {d['receiving_address']}.",
        terms=[Term(label="Party One", value=d["disclosing_party"]), Term(label="Party Two", value=d["receiving_party"]),
               Term(label="Type", value=d["nda_type"]), Term(label="Effective Date", value=fdate(d["effective_date"])),
               Term(label="Purpose", value=d["purpose"]),
               Term(label="Agreement Term", value=f"{d['term_years']} year(s)"),
               Term(label="Confidentiality Survives", value=f"{d['survival_years']} year(s) after termination")],
        sections=sections,
        signatories=[Signatory(name=d["disclosing_party"], role="Disclosing Party" if not mutual else "Party One"),
                     Signatory(name=d["receiving_party"], role="Receiving Party" if not mutual else "Party Two")])


# --------------------------------------------------------------------------- Lease
def build_lease(d) -> LegalDocument:
    rent = money(d["currency"], d["monthly_rent"])
    dep = money(d["currency"], d["security_deposit"])
    pets = ("Pets are permitted only with the Landlord's prior written consent." if d["pets"].startswith("Not")
            else "Pets are permitted, and the Tenant is responsible for any damage or nuisance they cause.")
    sections = [
        S("Premises", f"The Landlord leases to the Tenant the residential property at {d['property_address']} "
          "(the \"Premises\"), together with any fixtures and fittings listed in the move-in inspection."),
        S("Term", f"The lease runs from {fdate(d['lease_start'])} to {fdate(d['lease_end'])}. Unless renewed in "
          "writing, the Tenant must vacate on the end date."),
        S("Rent", f"The Tenant will pay rent of {rent} per month, in advance, on or before day {d['rent_due_day']} "
          "of each month, by the method the Landlord reasonably specifies."
          + (f" Rent unpaid more than 5 days late incurs a late fee of {money(d['currency'], d['late_fee'])}."
             if d.get("late_fee") not in ("", "0", None) else "")),
        S("Security Deposit", f"The Tenant will pay a refundable security deposit of {dep}. The Landlord may deduct "
          "unpaid rent and the cost of damage beyond normal wear and tear, and will return the balance with an "
          "itemised statement within 30 days after the Tenant vacates."),
        S("Use and Occupancy", "The Premises may be used only as a private residence, occupied by the Tenant and "
          "their household. The Tenant must obey the law, avoid nuisance to neighbours and not carry on any "
          "business that disturbs others."),
        S("Utilities and Services", f"{d['utilities']}"),
        S("Maintenance and Repairs", "The Tenant will keep the Premises clean and in good condition and promptly "
          "report defects. The Landlord will maintain the structure and essential installations and make repairs "
          "not caused by the Tenant's misuse."),
        S("Entry by Landlord", "The Landlord may enter the Premises on reasonable prior notice (at least 24 hours) "
          "to inspect, repair or show the property, or at any time in an emergency."),
        S("Pets", pets),
        S("Assignment and Subletting", "The Tenant may not assign this lease or sublet any part of the Premises "
          "without the Landlord's prior written consent."),
        S("Default", "If the Tenant fails to pay rent or breaches this lease and does not remedy it within the notice "
          "period required by law, the Landlord may terminate the lease and recover possession and any amounts due, "
          "following the legal process that applies."),
        S("Return of Premises", "At the end of the term the Tenant will return the Premises and all keys in the same "
          "condition as at the start, apart from normal wear and tear."),
        GOV(d), ENTIRE(),
    ]
    return LegalDocument(
        title="Residential Lease Agreement", document_type="lease_agreement",
        preamble=f"This Residential Lease Agreement is made on {fdate(d['effective_date'])} between "
                 f"{d['landlord_name']} (the \"Landlord\") and {d['tenant_name']} (the \"Tenant\").",
        terms=[Term(label="Landlord", value=d["landlord_name"]), Term(label="Tenant", value=d["tenant_name"]),
               Term(label="Property", value=d["property_address"]),
               Term(label="Lease Term", value=f"{fdate(d['lease_start'])} to {fdate(d['lease_end'])}"),
               Term(label="Monthly Rent", value=rent), Term(label="Rent Due", value=f"Day {d['rent_due_day']} of each month"),
               Term(label="Security Deposit", value=dep)],
        sections=sections,
        signatories=[Signatory(name=d["landlord_name"], role="Landlord"), Signatory(name=d["tenant_name"], role="Tenant")])


# --------------------------------------------------------------------------- Service agreement
def build_service(d) -> LegalDocument:
    fee = money(d["currency"], d["fee"])
    end = f"until {fdate(d['end_date'])}" if d.get("end_date") else "until completed or terminated under this Agreement"
    sections = [
        S("Services", f"The Provider will perform the following services for the Client (the \"Services\"): "
          f"{d['services']}", "The Provider will perform the Services with reasonable skill and care."),
        S("Fees and Payment", f"The Client will pay the Provider {fee} ({d['fee_basis'].lower()}). Invoices are due "
          f"within {d['payment_days']} days of receipt. Late amounts may accrue interest at the maximum rate "
          "permitted by law."),
        S("Term", f"The engagement starts on {fdate(d['start_date'])} and continues {end}."),
        S("Independent Contractor", "The Provider is an independent contractor, not an employee, partner or agent of "
          "the Client. The Provider controls how the Services are performed and is responsible for their own taxes, "
          "insurance and equipment."),
        S("Intellectual Property", "On full payment, the Client owns the deliverables created specifically for it under "
          "this Agreement. The Provider keeps its pre-existing tools, know-how and materials, and grants the Client "
          "a non-exclusive licence to use any of these that are embedded in the deliverables."),
        S("Confidentiality", "Each party will keep the other's non-public information confidential, use it only for "
          "this engagement, and return or delete it on request, except where disclosure is required by law."),
        S("Limitation of Liability", "Neither party is liable for indirect or consequential loss. Except for fraud, "
          "wilful misconduct or liability that cannot lawfully be limited, each party's total liability is limited "
          "to the fees paid or payable under this Agreement."),
        S("Termination", "Either party may terminate on 14 days' written notice. Either party may terminate immediately "
          "for the other's material breach that is not remedied within 7 days of notice. The Client will pay for "
          "Services performed up to termination."),
        GOV(d), ENTIRE(),
    ]
    return LegalDocument(
        title="Service Agreement", document_type="service_agreement",
        preamble=f"This Service Agreement is made on {fdate(d['effective_date'])} between {d['client_name']} "
                 f"(the \"Client\") and {d['provider_name']} (the \"Provider\").",
        terms=[Term(label="Client", value=d["client_name"]), Term(label="Provider", value=d["provider_name"]),
               Term(label="Start Date", value=fdate(d["start_date"])), Term(label="Fee", value=f"{fee} ({d['fee_basis'].lower()})"),
               Term(label="Payment Terms", value=f"{d['payment_days']} days from invoice")],
        sections=sections,
        signatories=[Signatory(name=d["client_name"], role="Client"), Signatory(name=d["provider_name"], role="Provider")])


# --------------------------------------------------------------------------- Registry
@dataclass
class DocType:
    key: str
    label: str
    description: str
    fields: list
    builder: Callable
    anchors: list   # field names whose values must appear verbatim in any AI output


_GOV = F("governing_law", "Governing law (state / country)", placeholder="e.g. Tamil Nadu, India", group="Legal")
_DATE = F("effective_date", "Date of agreement", "date", group="Basics")
_CUR = F("currency", "Currency", "select", options=CURRENCIES, default="INR", group="Money")

REGISTRY: dict[str, DocType] = {t.key: t for t in [
    DocType("employment_contract", "Employment Contract", "Hire an employee with roles, pay and confidentiality.", [
        _DATE,
        F("employer_name", "Employer / company name", group="Parties"),
        F("employer_address", "Employer address", group="Parties"),
        F("employee_name", "Employee full name", group="Parties"),
        F("employee_address", "Employee address", group="Parties"),
        F("job_title", "Job title", group="Role"),
        F("responsibilities", "Key responsibilities", "textarea", False, group="Role"),
        F("start_date", "Start date", "date", group="Role"),
        F("employment_type", "Employment type", "select", options=["Full-time", "Part-time", "Fixed-term"], default="Full-time", group="Role"),
        F("work_location", "Work location", placeholder="e.g. Chennai office / Remote", group="Role"),
        _CUR,
        F("salary", "Annual salary", "number", placeholder="e.g. 900000", group="Money"),
        F("pay_frequency", "Pay frequency", "select", options=["Monthly", "Bi-weekly", "Weekly"], default="Monthly", group="Money"),
        F("probation_months", "Probation (months)", "number", False, default="3", group="Terms"),
        F("notice_days", "Notice period (days)", "number", default="30", group="Terms"),
        F("annual_leave_days", "Paid leave (days / year)", "number", default="18", group="Terms"),
        F("non_solicit_months", "Non-solicitation (months, 0 = none)", "number", False, default="0", group="Terms"),
        _GOV], build_employment, ["employer_name", "employee_name", "job_title"]),

    DocType("nda", "Non-Disclosure Agreement", "Protect confidential information shared with another party.", [
        _DATE,
        F("nda_type", "Type", "select", options=["One-way (unilateral)", "Mutual"], default="One-way (unilateral)", group="Basics"),
        F("disclosing_party", "Disclosing party (Party One)", group="Parties"),
        F("disclosing_address", "Disclosing party address", group="Parties"),
        F("receiving_party", "Receiving party (Party Two)", group="Parties"),
        F("receiving_address", "Receiving party address", group="Parties"),
        F("purpose", "Purpose of sharing information", placeholder="e.g. evaluating a website redesign project", group="Scope"),
        F("confidential_scope", "What is confidential?", "textarea", placeholder="e.g. source code, pricing, client lists, business plans", group="Scope"),
        F("term_years", "Agreement term (years)", "number", default="2", group="Terms"),
        F("survival_years", "Confidentiality continues (years after end)", "number", default="3", group="Terms"),
        _GOV], build_nda, ["disclosing_party", "receiving_party"]),

    DocType("lease_agreement", "Residential Lease", "Rent a home with rent, deposit and house rules.", [
        _DATE,
        F("landlord_name", "Landlord name", group="Parties"),
        F("tenant_name", "Tenant name(s)", group="Parties"),
        F("property_address", "Property address", "textarea", group="Property"),
        F("lease_start", "Lease start", "date", group="Property"),
        F("lease_end", "Lease end", "date", group="Property"),
        _CUR,
        F("monthly_rent", "Monthly rent", "number", group="Money"),
        F("security_deposit", "Security deposit", "number", group="Money"),
        F("rent_due_day", "Rent due on day of month", "number", default="5", group="Money"),
        F("late_fee", "Late fee (optional)", "number", False, default="0", group="Money"),
        F("utilities", "Utilities & services", "textarea", default="The Tenant pays for electricity, water, internet and gas. The Landlord pays property taxes and building maintenance charges.", group="Terms"),
        F("pets", "Pets", "select", options=["Not allowed without consent", "Allowed"], default="Not allowed without consent", group="Terms"),
        _GOV], build_lease, ["landlord_name", "tenant_name", "property_address"]),

    DocType("service_agreement", "Freelance / Service Agreement", "Engage a freelancer or contractor for defined work.", [
        _DATE,
        F("client_name", "Client name", group="Parties"),
        F("provider_name", "Service provider / freelancer name", group="Parties"),
        F("services", "Services to be performed", "textarea", group="Work"),
        F("start_date", "Start date", "date", group="Work"),
        F("end_date", "End date (optional)", "date", False, group="Work"),
        _CUR,
        F("fee", "Fee", "number", group="Money"),
        F("fee_basis", "Fee basis", "select", options=["Fixed project fee", "Per hour", "Per month"], default="Fixed project fee", group="Money"),
        F("payment_days", "Payment due (days after invoice)", "number", default="15", group="Money"),
        _GOV], build_service, ["client_name", "provider_name"]),
]}
