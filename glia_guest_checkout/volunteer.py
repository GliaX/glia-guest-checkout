"""Volunteer interest form for the website.

The site previously pointed volunteers at blog posts with no way to raise a hand.
Submissions land in the CRM as Leads (source "Volunteer") and a copy is emailed to
info@glia.org so nobody has to watch the desk for them.
"""

from __future__ import annotations

import frappe
from frappe.utils import escape_html, validate_email_address


def record_interest(name: str, email: str, skills: str | None = None, message: str | None = None) -> dict:
	email = (email or "").strip().lower()
	if not email:
		frappe.throw("Please add your email so we can reply.")
	validate_email_address(email, throw=True)
	name = (name or "").strip() or email.split("@")[0]

	existing = frappe.db.get_value("Lead", {"email_id": email}, "name")
	if existing:
		lead = frappe.get_doc("Lead", existing)
		lead.status = lead.status or "Open"
	else:
		lead = frappe.new_doc("Lead")
		lead.email_id = email
		lead.lead_name = name[:140]
		lead.company_name = ""
		lead.source = "Volunteer"
		lead.status = "Open"
	lead.notes = ((lead.notes or "") + f"\n\nVolunteer interest:\nSkills: {skills or '-'}\nMessage: {message or '-'}").strip()[:5000]
	lead.flags.ignore_permissions = True
	lead.save(ignore_permissions=True) if existing else lead.insert(ignore_permissions=True)

	frappe.enqueue(
		"glia_guest_checkout.volunteer.notify_team",
		lead_name=lead.name,
		queue="short",
		enqueue_after_commit=True,
	)
	return {"ok": True, "lead": lead.name}


def notify_team(lead_name: str):
	lead = frappe.get_doc("Lead", lead_name)
	message = f"""
	<div style="font-family:Ubuntu,Arial,sans-serif;color:#032e38;max-width:560px">
	  <h2 style="margin:0 0 12px">New volunteer interest</h2>
	  <p><strong>{escape_html(lead.lead_name)}</strong> · {escape_html(lead.email_id)}</p>
	  <p>{escape_html(lead.notes or "")}</p>
	  <p style="color:#5b6b70;font-size:13px">Recorded in ERPNext as Lead {escape_html(lead.name)}.</p>
	</div>
	"""
	try:
		frappe.sendmail(
			recipients=["info@glia.org"],
			subject=f"Volunteer interest: {lead.lead_name}",
			message=message,
			reference_doctype="Lead",
			reference_name=lead.name,
			now=True,
		)
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"Volunteer notification failed ({lead.name})")
