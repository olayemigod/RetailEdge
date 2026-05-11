from __future__ import annotations

from typing import Any

import frappe

from retailedge.integrations.coreedge import get_coreedge_status, load_coreedge_attr, log_coreedge_debug


def create_payment_request_for_sales_invoice(sales_invoice, user: str | None = None, method: str | None = None):
	invoice = _resolve_sales_invoice(sales_invoice)
	if not invoice:
		return _response(
			provider="manual",
			status="unavailable",
			message=f"Sales Invoice {sales_invoice} was not found.",
		)

	status = get_coreedge_status()
	if status["payments_enabled"]:
		coreedge_func = load_coreedge_attr(
			"coreedge.payments.create_payment_request",
			"coreedge.api.create_payment_request",
		)
		if coreedge_func:
			try:
				result = coreedge_func(sales_invoice=invoice, user=user, method=method)
				return _normalize_coreedge_result(result)
			except TypeError:
				try:
					result = coreedge_func(invoice, user=user, method=method)
					return _normalize_coreedge_result(result)
				except Exception:
					log_coreedge_debug(
						"CoreEdge payment adapter failed; falling back from RetailEdge.",
						context={"sales_invoice": invoice.name},
					)
			except Exception:
				log_coreedge_debug(
					"CoreEdge payment adapter failed; falling back from RetailEdge.",
					context={"sales_invoice": invoice.name},
				)

	return _create_erpnext_payment_request(invoice=invoice, user=user, method=method)


def _resolve_sales_invoice(sales_invoice):
	if hasattr(sales_invoice, "doctype") and getattr(sales_invoice, "doctype", None) == "Sales Invoice":
		return sales_invoice

	if not sales_invoice or not frappe.db.exists("Sales Invoice", sales_invoice):
		return None

	return frappe.get_doc("Sales Invoice", sales_invoice)


def _create_erpnext_payment_request(invoice, user: str | None = None, method: str | None = None):
	make_payment_request = load_coreedge_attr(
		"erpnext.accounts.doctype.payment_request.payment_request.make_payment_request"
	)
	if not make_payment_request:
		return _response(
			provider="manual",
			status="fallback",
			message="ERPNext Payment Request helper is unavailable. Create the payment request manually.",
		)

	try:
		result = make_payment_request(
			dt="Sales Invoice",
			dn=invoice.name,
			payment_request_type="Inward",
			return_doc=True,
		)
	except TypeError:
		try:
			result = make_payment_request(dt="Sales Invoice", dn=invoice.name, payment_request_type="Inward")
		except Exception as exc:
			return _response(
				provider="manual",
				status="fallback",
				message=f"ERPNext payment request fallback failed: {exc}",
			)
	except Exception as exc:
		return _response(
			provider="manual",
			status="fallback",
			message=f"ERPNext payment request fallback failed: {exc}",
		)

	payment_request_name = _extract_value(result, "name")
	payment_url = _extract_value(result, "payment_url") or _extract_value(result, "url")
	return _response(
		provider="erpnext",
		status="created" if payment_request_name else "fallback",
		payment_request=payment_request_name,
		payment_url=payment_url,
		message="ERPNext payment request created." if payment_request_name else "ERPNext fallback returned without a payment request name.",
	)


def _normalize_coreedge_result(result: Any):
	if isinstance(result, dict):
		return {
			"provider": result.get("provider") or "coreedge",
			"status": result.get("status") or "created",
			"payment_request": result.get("payment_request"),
			"payment_url": result.get("payment_url"),
			"message": result.get("message") or "CoreEdge payment request created.",
		}

	return _response(
		provider="coreedge",
		status="created",
		payment_request=_extract_value(result, "name"),
		payment_url=_extract_value(result, "payment_url") or _extract_value(result, "url"),
		message="CoreEdge payment request created.",
	)


def _extract_value(value: Any, fieldname: str):
	if isinstance(value, dict):
		return value.get(fieldname)

	return getattr(value, fieldname, None)


def _response(
	*,
	provider: str,
	status: str,
	message: str,
	payment_request: str | None = None,
	payment_url: str | None = None,
):
	return {
		"provider": provider,
		"status": status,
		"payment_request": payment_request,
		"payment_url": payment_url,
		"message": message,
	}
