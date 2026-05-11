from __future__ import annotations

import frappe

from retailedge.integrations.coreedge import get_coreedge_status, load_coreedge_attr, log_coreedge_debug


def send_retailedge_notification(event, recipients, context=None, channels=None):
	recipients = recipients or []
	context = context or {}
	channels = channels or []

	status = get_coreedge_status()
	if status["notifications_enabled"]:
		coreedge_func = load_coreedge_attr(
			"coreedge.notifications.send_notification",
			"coreedge.api.send_notification",
		)
		if coreedge_func:
			try:
				result = coreedge_func(
					event=event,
					recipients=recipients,
					context=context,
					channels=channels,
				)
				if isinstance(result, dict):
					return {
						"provider": result.get("provider") or "coreedge",
						"status": result.get("status") or "sent",
						"message": result.get("message") or "CoreEdge notification sent.",
					}

				return {
					"provider": "coreedge",
					"status": "sent",
					"message": "CoreEdge notification sent.",
				}
			except Exception:
				log_coreedge_debug(
					"CoreEdge notification adapter failed; falling back to Frappe logging.",
					context={"event": event, "recipients": recipients},
				)

	if recipients:
		frappe.logger("retailedge.notifications").info(
			"RetailEdge notification fallback | event=%s | recipients=%s | channels=%s | context=%s",
			event,
			recipients,
			channels,
			frappe.as_json(context),
		)
		return {
			"provider": "frappe",
			"status": "fallback",
			"message": "RetailEdge notification recorded with Frappe logging fallback.",
		}

	return {
		"provider": "manual",
		"status": "unavailable",
		"message": "No recipients were supplied for the RetailEdge notification.",
	}
