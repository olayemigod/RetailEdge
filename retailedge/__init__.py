__version__ = "0.0.1"

# Internal Transfer Payment Entries legitimately produce two distinct bank
# statement legs. Install the narrow leg-aware duplicate/conflict policy once
# when the RetailEdge package is imported; ordinary Payment Entries retain the
# existing document-level duplicate identity.
from retailedge.bank_internal_transfer_identity import install_internal_transfer_bank_leg_identity

install_internal_transfer_bank_leg_identity()

# Frappe's frappe.throw() records a server message before raising. The
# Internal Transfer confirmation guard therefore performs leg-aware validation
# before the legacy document-level validator so a legitimate opposite bank leg
# does not succeed while still showing a false duplicate error to the user.
from retailedge.bank_internal_transfer_confirmation_guard import (
	install_internal_transfer_confirmation_guard,
)

install_internal_transfer_confirmation_guard()
