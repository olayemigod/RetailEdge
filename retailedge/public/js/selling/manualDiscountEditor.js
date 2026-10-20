export const MANUAL_PERCENTAGE = "manual_discount_percentage";
export const MANUAL_AMOUNT = "manual_discount_amount";
export const MANUAL_MODE = "manual_discount_mode";
export const MANUAL_VALUE = "manual_discount_value";

const PERCENTAGE = "percentage";
const AMOUNT = "amount";

function editorState(row = {}) {
	const percentage = Number(row?.[MANUAL_PERCENTAGE] || 0);
	const amount = Number(row?.[MANUAL_AMOUNT] || 0);
	if (percentage) return { [MANUAL_MODE]: PERCENTAGE, [MANUAL_VALUE]: percentage };
	if (amount) return { [MANUAL_MODE]: AMOUNT, [MANUAL_VALUE]: amount };
	return { [MANUAL_MODE]: "", [MANUAL_VALUE]: "" };
}

export function withManualDiscountEditorColumns(columns = []) {
	const result = [];
	for (const column of columns) {
		result.push(column);
		if (column?.fieldname !== "rate") continue;
		result.push(
			{
				fieldname: MANUAL_MODE,
				label: "Discount",
				fieldtype: "Select",
				options: [
					{ value: PERCENTAGE, label: "Percentage" },
					{ value: AMOUNT, label: "Amount / unit" },
				],
				default: "",
			},
			{
				fieldname: MANUAL_VALUE,
				label: "Value",
				fieldtype: "Float",
				default: "",
				read_only_depends_on: `eval:!doc.${MANUAL_MODE}`,
			},
		);
	}
	return result;
}

function previousRow(row, index, previousRows = []) {
	const temporaryKey = String(row?.__temporary_key || "").trim();
	if (temporaryKey) {
		const matched = previousRows.find((candidate) => String(candidate?.__temporary_key || "").trim() === temporaryKey);
		if (matched) return matched;
	}
	const sameReference = previousRows.find((candidate) => candidate === row);
	return sameReference || previousRows[index] || {};
}

export function normaliseManualDiscountRows(nextRows = [], previousRows = []) {
	return nextRows.map((row, index) => {
		const prior = previousRow(row, index, previousRows);
		if ((row?.item_code || "") !== (prior?.item_code || "")) {
			return clearManualDiscount(row);
		}
		const priorEditor = {
			...editorState(prior),
			...(prior?.[MANUAL_MODE] !== undefined ? { [MANUAL_MODE]: prior[MANUAL_MODE] } : {}),
			...(prior?.[MANUAL_VALUE] !== undefined ? { [MANUAL_VALUE]: prior[MANUAL_VALUE] } : {}),
		};
		const mode = String(row?.[MANUAL_MODE] || "");
		if (mode !== String(priorEditor[MANUAL_MODE] || "")) {
			return {
				...row,
				[MANUAL_PERCENTAGE]: 0,
				[MANUAL_AMOUNT]: 0,
				[MANUAL_MODE]: mode,
				[MANUAL_VALUE]: "",
			};
		}
		const value = row?.[MANUAL_VALUE] === "" ? 0 : Number(row?.[MANUAL_VALUE]);
		if (mode === PERCENTAGE) {
			return {
				...row,
				[MANUAL_PERCENTAGE]: Number.isFinite(value) ? value : 0,
				[MANUAL_AMOUNT]: 0,
			};
		}
		if (mode === AMOUNT) {
			return {
				...row,
				[MANUAL_PERCENTAGE]: 0,
				[MANUAL_AMOUNT]: Number.isFinite(value) ? value : 0,
			};
		}
		return clearManualDiscount(row);
	});
}

export function clearManualDiscount(row = {}) {
	return {
		...row,
		[MANUAL_PERCENTAGE]: 0,
		[MANUAL_AMOUNT]: 0,
		[MANUAL_MODE]: "",
		[MANUAL_VALUE]: "",
	};
}

export function clearLockedManualDiscounts(rows = []) {
	return rows.map((row) => clearManualDiscount(row));
}
