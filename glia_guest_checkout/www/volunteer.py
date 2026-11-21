import frappe


def get_context(context):
	context.no_cache = 1
	context.title = "Volunteer with Glia"
	context.roles = [
		{"title": "Clinicians & trainers",
		 "text": "Emergency and critical-care clinicians who can teach, review protocols or run trainings with local teams."},
		{"title": "Design & engineering",
		 "text": "CAD, 3D printing, electronics and manufacturing help — from a single part to a production run."},
		{"title": "Fundraising & events",
		 "text": "Host a fundraiser, run a table at an event, or connect us with a community that wants to help."},
		{"title": "Communications",
		 "text": "Writing, video, photography and social media that put Glia's work in front of the right people."},
		{"title": "Operations & admin",
		 "text": "Shipping, data entry, translation, bookkeeping — the quiet work that keeps everything moving."},
	]
