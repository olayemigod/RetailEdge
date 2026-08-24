__version__ = "0.0.1"

# Internal Transfer Payment Entries legitimately produce two distinct bank
# statement legs. Install the narrow leg-aware duplicate/conflict policy once
# when the RetailEdge package is imported; ordinary Payment Entries retain the
# existing document-level duplicate identity.
from retailedge.bank_internal_transfer_identity import install_internal_transfer_bank_leg_identity

install_internal_transfer_bank_leg_identity()
