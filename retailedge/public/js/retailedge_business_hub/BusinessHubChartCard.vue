<template>
	<article :class="['hub-chart-card', { 'hub-chart-card--wide': wide }]">
		<header class="hub-chart-card__header">
			<div>
				<p class="hub-chart-card__eyebrow">{{ chart.time_basis === "current" ? "Current position" : "Selected period" }}</p>
				<h4>{{ chart.title }}</h4>
				<p v-if="chart.description">{{ chart.description }}</p>
			</div>
			<button
				v-if="chart.available && chart.route"
				type="button"
				class="hub-chart-card__details"
				@click="$emit('open', chart)"
			>
				View details
			</button>
		</header>

		<div v-if="!chart.available" class="hub-chart-card__state">
			<strong>Unavailable</strong>
			<span>{{ chart.reason || "This visual is not available for your current permissions and scope." }}</span>
		</div>

		<div v-else-if="!hasData" class="hub-chart-card__state">
			<strong>No data for this view</strong>
			<span>There is no activity to visualise in the selected scope.</span>
		</div>

		<template v-else>
			<div v-if="chart.series?.length > 1" class="hub-chart-card__legend" aria-label="Chart legend">
				<span v-for="(series, index) in chart.series" :key="series.key">
					<i :class="['hub-chart-card__legend-dot', `series-${index}`]" aria-hidden="true"></i>
					{{ series.label }}
				</span>
			</div>

			<div v-if="chart.chart_type === 'line'" class="hub-line-chart">
				<svg viewBox="0 0 720 230" role="img" :aria-label="chart.title">
					<g class="hub-line-chart__grid">
						<line v-for="tick in yTicks" :key="tick.value" x1="52" x2="704" :y1="tick.y" :y2="tick.y" />
					</g>
					<g class="hub-line-chart__labels">
						<text v-for="tick in yTicks" :key="`label-${tick.value}`" x="44" :y="tick.y + 4" text-anchor="end">
							{{ compactValue(tick.value) }}
						</text>
						<text
							v-for="tick in xTicks"
							:key="`x-${tick.index}`"
							:x="tick.x"
							y="222"
							:text-anchor="tick.anchor"
						>
							{{ tick.label }}
						</text>
					</g>
					<polyline class="hub-line-chart__line series-0" fill="none" :points="linePoints" />
					<g v-for="point in linePointRows" :key="point.key">
						<circle
							class="hub-line-chart__point series-0"
							:cx="point.x"
							:cy="point.y"
							r="5"
							tabindex="0"
							role="button"
							:aria-label="pointAria(point)"
							@click="$emit('drill', chart, point.row, chart.series[0])"
							@keydown.enter.prevent="$emit('drill', chart, point.row, chart.series[0])"
							@keydown.space.prevent="$emit('drill', chart, point.row, chart.series[0])"
						>
							<title>{{ pointTitle(point) }}</title>
						</circle>
					</g>
				</svg>
			</div>

			<div v-else class="hub-bar-chart">
				<div
					v-for="row in chart.rows"
					:key="row.key || row.label"
					class="hub-bar-chart__row"
				>
					<div class="hub-bar-chart__label">
						<span :title="row.label">{{ row.label }}</span>
					</div>
					<div class="hub-bar-chart__series">
						<button
							v-for="(series, index) in chart.series"
							:key="series.key"
							type="button"
							class="hub-bar-chart__bar-button"
							:disabled="!canDrill(row)"
							:title="barTitle(row, series)"
							:aria-label="barTitle(row, series)"
							@click="$emit('drill', chart, row, series)"
						>
							<span
								:class="['hub-bar-chart__bar', `series-${index}`]"
								:style="{ width: barWidth(row, series) }"
							></span>
							<small>{{ formatValue(row[series.key], series.datatype) }}</small>
						</button>
					</div>
				</div>
			</div>
		</template>
	</article>
</template>

<script>
export default {
	name: "BusinessHubChartCard",
	emits: ["open", "drill"],
	props: {
		chart: {
			type: Object,
			required: true,
		},
		wide: {
			type: Boolean,
			default: false,
		},
	},
	computed: {
		hasData() {
			return Boolean(
				this.chart?.rows?.length &&
					(this.chart.series || []).some((series) =>
						this.chart.rows.some((row) => Number(row?.[series.key] || 0) !== 0)
					)
			);
		},
		maxValue() {
			let maximum = 0;
			for (const row of this.chart.rows || []) {
				for (const series of this.chart.series || []) {
					maximum = Math.max(maximum, Math.abs(Number(row?.[series.key] || 0)));
				}
			}
			return maximum || 1;
		},
		linePointRows() {
			const rows = this.chart.rows || [];
			const series = this.chart.series?.[0];
			if (!rows.length || !series) return [];
			const left = 52;
			const right = 704;
			const top = 18;
			const bottom = 194;
			const range = right - left;
			const height = bottom - top;
			const max = this.maxValue;
			return rows.map((row, index) => {
				const x = rows.length === 1 ? (left + right) / 2 : left + (range * index) / (rows.length - 1);
				const value = Number(row?.[series.key] || 0);
				const y = bottom - (Math.max(value, 0) / max) * height;
				return { key: row.key || index, x, y, value, row };
			});
		},
		linePoints() {
			return this.linePointRows.map((point) => `${point.x},${point.y}`).join(" ");
		},
		yTicks() {
			const top = 18;
			const bottom = 194;
			return [0, 0.25, 0.5, 0.75, 1].map((ratio) => ({
				value: this.maxValue * ratio,
				y: bottom - (bottom - top) * ratio,
			}));
		},
		xTicks() {
			const points = this.linePointRows;
			if (!points.length) return [];
			const indexes = points.length <= 3
				? points.map((_, index) => index)
				: [0, Math.floor((points.length - 1) / 2), points.length - 1];
			return [...new Set(indexes)].map((index, position, selected) => ({
				index,
				x: points[index].x,
				label: points[index].row.label,
				anchor: position === 0 ? "start" : position === selected.length - 1 ? "end" : "middle",
			}));
		},
	},
	methods: {
		canDrill(row) {
			if (row?.key === "__other__") return false;
			return Boolean(
				(row?.from_date && row?.to_date) ||
				(row?.drill_field && row?.drill_value)
			);
		},
		compactValue(value) {
			const number = Number(value || 0);
			if (!Number.isFinite(number)) return "0";
			try {
				return new Intl.NumberFormat(undefined, {
					notation: "compact",
					compactDisplay: "short",
					maximumFractionDigits: 1,
				}).format(number);
			} catch (_error) {
				return number.toLocaleString(undefined, { maximumFractionDigits: 1 });
			}
		},
		formatValue(value, datatype = "Float") {
			const number = Number(value || 0);
			if (datatype === "Currency") {
				const formatter = window.retailedge?.formatPlainValue;
				if (formatter) {
					try {
						return formatter(number, { fieldtype: "Currency" });
					} catch (_error) {
						// fall through
					}
				}
				return number.toLocaleString(undefined, {
					minimumFractionDigits: 2,
					maximumFractionDigits: 2,
				});
			}
			if (datatype === "Int") return Math.round(number).toLocaleString();
			return number.toLocaleString(undefined, { maximumFractionDigits: 2 });
		},
		barWidth(row, series) {
			const value = Math.abs(Number(row?.[series.key] || 0));
			const percent = Math.max(0, Math.min(100, (value / this.maxValue) * 100));
			return `${percent}%`;
		},
		barTitle(row, series) {
			return `${row.label}: ${series.label} ${this.formatValue(row?.[series.key], series.datatype)}`;
		},
		pointTitle(point) {
			const series = this.chart.series?.[0] || {};
			return `${point.row.label}: ${series.label || ""} ${this.formatValue(point.value, series.datatype)}`;
		},
		pointAria(point) {
			return `${this.pointTitle(point)}. Open the detailed report for this period.`;
		},
	},
};
</script>

<style scoped>
.hub-chart-card {
	display: grid;
	gap: 14px;
	min-width: 0;
	padding: 16px;
	border: 1px solid var(--edge-color-border, #dfe3e8);
	border-radius: 12px;
	background: var(--edge-color-surface, #ffffff);
}
.hub-chart-card--wide {
	grid-column: 1 / -1;
}
.hub-chart-card__header {
	display: flex;
	align-items: flex-start;
	justify-content: space-between;
	gap: 14px;
}
.hub-chart-card__header h4 {
	margin: 2px 0 4px;
	color: var(--edge-color-ink-950, #101828);
	font-size: .98rem;
	font-weight: 700;
}
.hub-chart-card__header p {
	margin: 0;
	color: var(--edge-color-ink-500, #667085);
	font-size: .78rem;
	line-height: 1.4;
}
.hub-chart-card__eyebrow {
	text-transform: uppercase;
	letter-spacing: .06em;
	font-size: .66rem !important;
	font-weight: 700;
	color: var(--edge-color-brand-600, #2563eb) !important;
}
.hub-chart-card__details {
	flex: 0 0 auto;
	padding: 0;
	border: 0;
	background: transparent;
	color: var(--edge-color-brand-600, #2563eb);
	font-size: .76rem;
	font-weight: 700;
	cursor: pointer;
}
.hub-chart-card__details:hover,
.hub-chart-card__details:focus-visible {
	text-decoration: underline;
}
.hub-chart-card__state {
	display: grid;
	gap: 4px;
	min-height: 120px;
	align-content: center;
	justify-items: center;
	padding: 20px;
	border-radius: 10px;
	background: var(--edge-color-surface-muted, #f8fafc);
	text-align: center;
}
.hub-chart-card__state span {
	max-width: 34rem;
	color: var(--edge-color-ink-500, #667085);
	font-size: .78rem;
	line-height: 1.4;
}
.hub-chart-card__legend {
	display: flex;
	flex-wrap: wrap;
	gap: 12px;
	color: var(--edge-color-ink-500, #667085);
	font-size: .72rem;
}
.hub-chart-card__legend > span {
	display: inline-flex;
	align-items: center;
	gap: 5px;
}
.hub-chart-card__legend-dot {
	width: 8px;
	height: 8px;
	border-radius: 999px;
}
.series-0 {
	stroke: var(--edge-color-brand-600, #2563eb);
	background: var(--edge-color-brand-600, #2563eb);
	fill: var(--edge-color-brand-600, #2563eb);
}
.series-1 {
	stroke: var(--edge-color-success, #12b76a);
	background: var(--edge-color-success, #12b76a);
	fill: var(--edge-color-success, #12b76a);
}
.hub-line-chart {
	min-width: 0;
	overflow: hidden;
}
.hub-line-chart svg {
	display: block;
	width: 100%;
	min-height: 210px;
}
.hub-line-chart__grid line {
	stroke: var(--edge-color-border, #dfe3e8);
	stroke-width: 1;
}
.hub-line-chart__labels text {
	fill: var(--edge-color-ink-500, #667085);
	font-size: 11px;
}
.hub-line-chart__line {
	stroke-width: 3;
	stroke-linecap: round;
	stroke-linejoin: round;
}
.hub-line-chart__point {
	cursor: pointer;
	stroke: var(--edge-color-surface, #ffffff);
	stroke-width: 2;
}
.hub-line-chart__point:focus {
	outline: none;
	stroke: var(--edge-color-ink-950, #101828);
	stroke-width: 3;
}
.hub-bar-chart {
	display: grid;
	gap: 10px;
}
.hub-bar-chart__row {
	display: grid;
	grid-template-columns: minmax(7rem, 11rem) minmax(0, 1fr);
	align-items: center;
	gap: 10px;
}
.hub-bar-chart__label {
	min-width: 0;
	color: var(--edge-color-ink-700, #344054);
	font-size: .75rem;
	font-weight: 600;
}
.hub-bar-chart__label span {
	display: block;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}
.hub-bar-chart__series {
	display: grid;
	gap: 4px;
}
.hub-bar-chart__bar-button {
	position: relative;
	display: grid;
	grid-template-columns: minmax(0, 1fr) auto;
	align-items: center;
	gap: 8px;
	min-height: 22px;
	padding: 0;
	border: 0;
	background: transparent;
	text-align: left;
	cursor: pointer;
}
.hub-bar-chart__bar-button:disabled {
	cursor: default;
}
.hub-bar-chart__bar-button::before {
	content: "";
	position: absolute;
	left: 0;
	right: 4.5rem;
	top: 4px;
	bottom: 4px;
	border-radius: 999px;
	background: var(--edge-color-surface-muted, #f8fafc);
}
.hub-bar-chart__bar {
	position: relative;
	display: block;
	z-index: 1;
	min-width: 2px;
	height: 10px;
	border-radius: 999px;
	transition: width .18s ease;
}
.hub-bar-chart__bar-button small {
	position: relative;
	z-index: 1;
	min-width: 4rem;
	color: var(--edge-color-ink-500, #667085);
	font-size: .68rem;
	text-align: right;
	font-variant-numeric: tabular-nums;
}
:global(:root[data-edge-appearance="dark"]) .hub-chart-card {
	background: var(--edge-color-surface);
	border-color: var(--edge-color-border);
}
:global(:root[data-edge-appearance="dark"]) .hub-chart-card__header h4 {
	color: var(--edge-color-ink-950);
}
:global(:root[data-edge-appearance="dark"]) .hub-chart-card__state,
:global(:root[data-edge-appearance="dark"]) .hub-bar-chart__bar-button::before {
	background: var(--edge-color-surface-muted);
}
@media (max-width: 720px) {
	.hub-chart-card__header {
		flex-direction: column;
	}
	.hub-bar-chart__row {
		grid-template-columns: 1fr;
		gap: 4px;
	}
	.hub-bar-chart__bar-button::before {
		right: 4rem;
	}
	.hub-line-chart svg {
		min-height: 190px;
	}
}
@media (prefers-reduced-motion: reduce) {
	.hub-bar-chart__bar {
		transition: none;
	}
}
</style>
