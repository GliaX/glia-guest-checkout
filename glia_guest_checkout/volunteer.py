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

	# one record per email: repeat sign-ups update the existing row
	existing = frappe.db.get_value("Volunteer Interest", {"email": email}, "name")
	if existing:
		doc = frappe.get_doc("Volunteer Interest", existing)
	else:
		doc = frappe.new_doc("Volunteer Interest")
	doc.full_name = name[:140]
	doc.email = email
	if skills:
		doc.skills = skills[:1000]
	if message:
		doc.message = message[:5000]
	doc.status = doc.status or "New"
	doc.flags.ignore_permissions = True
	x = doc.save(ignore_permissions=True) if existing else doc.insert(ignore_permissions=True)
	doc = x

	frappe.enqueue(
		"glia_guest_checkout.volunteer.notify_team",
		interest_name=doc.name,
		queue="short",
		enqueue_after_commit=True,
	)
	return {"ok": True, "interest": doc.name}


def notify_team(interest_name: str):
	interest = frappe.get_doc("Volunteer Interest", interest_name)
	message = f"""
	<div style="font-family:Ubuntu,Arial,sans-serif;color:#032e38;max-width:560px">
	  <h2 style="margin:0 0 12px">New volunteer interest</h2>
	  <p><strong>{escape_html(interest.full_name)}</strong> · {escape_html(interest.email)}</p>
	  <p>{escape_html(interest.skills or "")}</p>
	  <p style="color:#5b6b70;font-size:13px">Recorded in ERPNext as Lead {escape_html(interest.name)}.</p>
	</div>
	"""
	try:
		frappe.sendmail(
			recipients=["info@glia.org"],
			subject=f"Volunteer interest: {interest.full_name}",
			message=message,
			reference_doctype="Volunteer Interest",
			reference_name=interest.name,
			now=True,
		)
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"Volunteer notification failed ({interest.name})")
