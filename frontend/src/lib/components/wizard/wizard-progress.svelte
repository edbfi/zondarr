<script lang="ts">
/**
 * Wizard Progress Component
 *
 * Displays current step / total steps with a progress bar.
 * Applies gold accent glow on completion.
 */

interface Props {
	current: number;
	total: number;
	progress: number;
	stepTitle?: string;
}

const { current, total, progress, stepTitle }: Props = $props();

const isComplete = $derived(current === total && progress >= 100);
</script>

<div class="wizard-progress" class:complete={isComplete}>
	<!-- Step header: counter + title -->
	<div class="step-header">
		<div class="step-counter">
			<span class="current">{current}</span>
			<span class="separator">/</span>
			<span class="total">{total}</span>
		</div>
		{#if stepTitle}
			<span class="step-title">{stepTitle}</span>
		{/if}
	</div>

	<!-- Progress bar -->
	<div class="progress-track">
		<div class="progress-fill" style="width: {progress}%"></div>
	</div>

	<!-- Accessible step label -->
	<span class="step-label" aria-live="polite">Step {current} {'of'} {total}</span>
</div>

<style>
.wizard-progress {
	display: flex;
	flex-direction: column;
	gap: 0.75rem;
	animation: wizard-reveal 0.6s ease-out both;
}

/* Step header: counter + title row */
.step-header {
	display: flex;
	align-items: baseline;
	gap: 0.75rem;
}

/* Step counter */
.step-counter {
	display: flex;
	align-items: baseline;
	gap: 0.25rem;
	font-family: "JetBrains Mono", "Fira Code", monospace;
	font-size: 0.875rem;
	font-variant-numeric: tabular-nums;
	flex-shrink: 0;
}

/* Step title */
.step-title {
	color: hsl(220 10% 70%);
	font-size: 0.8125rem;
	font-weight: 500;
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
	min-width: 0;
}

.current {
	color: hsl(45 90% 55%);
	font-weight: 600;
	font-size: 1.125rem;
}

.separator {
	color: hsl(220 10% 40%);
}

.total {
	color: hsl(220 10% 60%);
}

/* Progress bar track */
.progress-track {
	height: 4px;
	background: hsl(220 10% 18%);
	border-radius: 2px;
	overflow: hidden;
}

/* Progress bar fill */
.progress-fill {
	height: 100%;
	background: linear-gradient(90deg, hsl(45 90% 45%), hsl(45 90% 55%));
	border-radius: 2px;
	transition:
		width 0.4s ease-out,
		box-shadow 0.3s ease;
}

/* Gold glow on completion */
.wizard-progress.complete .progress-fill {
	box-shadow:
		0 0 8px hsl(45 90% 55% / 0.5),
		0 0 16px hsl(45 90% 55% / 0.3);
	animation: pulse-glow 2s ease-in-out infinite;
}

.wizard-progress.complete .current {
	text-shadow: 0 0 8px hsl(45 90% 55% / 0.5);
}

/* Accessible step label */
.step-label {
	font-size: 0.6875rem;
	color: hsl(220 10% 45%);
	letter-spacing: 0.02em;
}

@keyframes pulse-glow {
	0%,
	100% {
		box-shadow:
			0 0 8px hsl(45 90% 55% / 0.5),
			0 0 16px hsl(45 90% 55% / 0.3);
	}
	50% {
		box-shadow:
			0 0 12px hsl(45 90% 55% / 0.6),
			0 0 24px hsl(45 90% 55% / 0.4);
	}
}

@keyframes wizard-reveal {
	from {
		opacity: 0;
		transform: translateY(20px);
	}
	to {
		opacity: 1;
		transform: translateY(0);
	}
}
</style>
