<script lang="ts">
/**
 * Wizard Navigation Component
 *
 * Renders Back/Next/Complete buttons with loading state.
 * Applies floating navigation styling with backdrop blur.
 */
import { ArrowLeft, ArrowRight, Check, Loader2 } from '@lucide/svelte';

interface Props {
	isFirstStep: boolean;
	isLastStep: boolean;
	canProceed: boolean;
	loading?: boolean;
	onBack: () => void;
	onNext: () => void;
	onCancel?: () => void;
}

const {
	isFirstStep,
	isLastStep,
	canProceed,
	loading = false,
	onBack,
	onNext,
	onCancel
}: Props = $props();
</script>

<div class="wizard-navigation">
	<div class="nav-content">
		<!-- Back button -->
		<div class="nav-left">
			{#if !isFirstStep}
				<button type="button" class="back-btn" onclick={onBack} disabled={loading}>
					<ArrowLeft class="size-4" />
					Back
				</button>
			{:else if onCancel}
				<button type="button" class="cancel-btn" onclick={onCancel} disabled={loading}>
					Cancel
				</button>
			{:else}
				<div></div>
			{/if}
		</div>

		<!-- Next/Complete button -->
		<div class="nav-right">
			<button
				type="button"
				onclick={onNext}
				disabled={!canProceed || loading}
				class="next-btn {isLastStep ? 'complete-btn' : ''}"
			>
				{#if loading}
					<Loader2 class="size-4 animate-spin" />
					Validating...
				{:else if isLastStep}
					<Check class="size-4" />
					Complete
				{:else}
					Next
					<ArrowRight class="size-4" />
				{/if}
			</button>
		</div>
	</div>
</div>

<style>
.wizard-navigation {
	position: sticky;
	bottom: 0;
	padding: 0.75rem 0;
	animation: wizard-reveal 0.6s ease-out 0.4s both;
	z-index: 10;
	pointer-events: none;
	border-top: 1px solid hsl(220 10% 18%);
	backdrop-filter: blur(12px);
	-webkit-backdrop-filter: blur(12px);
	background: hsl(220 15% 8% / 0.8);
	margin: 0 -1.5rem;
	padding-left: 1.5rem;
	padding-right: 1.5rem;
}

.nav-content {
	max-width: 720px;
	margin: 0 auto;
	display: flex;
	justify-content: space-between;
	align-items: center;
	gap: 1rem;
}

.nav-left,
.nav-right {
	flex: 1;
}

.nav-left {
	display: flex;
	justify-content: flex-start;
}

.nav-right {
	display: flex;
	justify-content: flex-end;
}

/* Base button styles */
button {
	display: inline-flex;
	align-items: center;
	justify-content: center;
	gap: 0.5rem;
	border: none;
	border-radius: 0.5rem;
	font-size: 0.875rem;
	font-weight: 500;
	cursor: pointer;
	transition: all 0.2s ease;
	pointer-events: auto;
	min-height: 44px;
}

button:disabled {
	cursor: not-allowed;
	opacity: 0.5;
	pointer-events: none;
}

/* Back button styling */
.back-btn {
	background: transparent;
	color: hsl(220 10% 60%);
	padding: 0.625rem 1.25rem;
}

.back-btn:hover:not(:disabled) {
	color: hsl(220 10% 80%);
	background: hsl(220 10% 15%);
}

/* Cancel button styling */
.cancel-btn {
	background: transparent;
	color: hsl(0 70% 55%);
	padding: 0.625rem 1.25rem;
	opacity: 0.7;
}

.cancel-btn:hover:not(:disabled) {
	opacity: 1;
	background: hsl(0 70% 55% / 0.1);
}

/* Next button styling */
.next-btn {
	background: hsl(45 90% 55%);
	color: hsl(220 20% 4%);
	font-weight: 600;
	font-size: 0.9375rem;
	padding: 0.75rem 2rem;
	box-shadow:
		0 0 16px hsl(45 90% 55% / 0.3),
		0 4px 12px hsl(0 0% 0% / 0.2);
}

.next-btn:hover:not(:disabled) {
	transform: scale(1.02);
	box-shadow:
		0 0 24px hsl(45 90% 55% / 0.4),
		0 6px 16px hsl(0 0% 0% / 0.3);
}

.next-btn:disabled {
	background: hsl(220 10% 25%);
	color: hsl(220 10% 50%);
	box-shadow: none;
	transform: none;
}

/* Complete button special styling */
.complete-btn {
	background: linear-gradient(135deg, hsl(150 60% 45%), hsl(150 60% 35%));
	box-shadow:
		0 0 16px hsl(150 60% 45% / 0.3),
		0 4px 12px hsl(0 0% 0% / 0.2);
}

.complete-btn:hover:not(:disabled) {
	box-shadow:
		0 0 24px hsl(150 60% 45% / 0.4),
		0 6px 16px hsl(0 0% 0% / 0.3);
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
