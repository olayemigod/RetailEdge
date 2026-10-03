from __future__ import annotations

from retailedge.bank_transaction_bridge import repair_imported_pending_bank_transactions


def execute():
	repair_imported_pending_bank_transactions(dry_run=False)
