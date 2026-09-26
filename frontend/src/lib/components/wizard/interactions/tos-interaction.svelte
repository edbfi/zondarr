<script lang="ts">
/**
 * Terms of Service Interaction Component
 *
 * Renders terms content and acceptance checkbox.
 * Requires checkbox before enabling proceed.
 * Records acceptance timestamp.
 */
import { Check } from '@lucide/svelte';
import { tosConfigSchema } from '$lib/schemas/wizard';
import type { InteractionComponentProps } from './registry';

const {
	interactionId,
	config: rawConfig,
	onComplete,
	disabled = false,
	completionData
}: InteractionComponentProps = $props();

// Validate config with Zod schema, falling back gracefully for partial configs
const config = $derived(tosConfigSchema.safeParse(rawConfig).data);
const checkboxLabel = $derived(config?.checkbox_label ?? 'I accept the terms of service');

// Checkbox state — restore from completion data if navigating back
let accepted = $state((() => completionData?.data?.accepted === true)());

// Derived - can proceed only when accepted
const canProceed = $derived(accepted);

function handleAccept() {
	if (!accepted) return;

	onComplete({
		interactionId,
		interactionType: 'tos',
		data: {
			accepted: true,
			accepted_at: new Date().toISOString()
		},
		completedAt: new Date().toISOString()
	});
}

function toggleAccepted() {
	accepted = !accepted;
}
</script>

<div class="tos-interaction">
	<!-- Custom checkbox with card -->
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
	<!-- biome-ignore lint/a11y/useKeyWithClickEvents: The nested native checkbox button owns keyboard activation; the card is an additional pointer target. -->
	<!-- biome-ignore lint/a11y/useSemanticElements: This ARIA group labels existing controls without introducing native fieldset layout. -->
	<div class="checkbox-card" onclick={toggleAccepted} role="group">
		<label class="checkbox-container">
			<!-- biome-ignore lint/a11y/useSemanticElements: This native button supplies keyboard activation for the custom checked state. -->
			<button
				type="button"
				role="checkbox"
				aria-checked={accepted}
				class="checkbox"
				class:checked={accepted}
				onclick={(e) => {
	e.stopPropagation();
	toggleAccepted();
}}
				{disabled}
			>
				{#if accepted}
					<Check class="check-icon" />
				{/if}
			</button>
			<span class="checkbox-label">{checkboxLabel}</span>
		</label>
	</div>

	<!-- Accept button -->
	<button
		type="button"
		class="wizard-accent-btn accept-btn"
		onclick={handleAccept}
		disabled={!canProceed || disabled}
	>
		Accept & Continue
	</button>
</div>

<style>
.tos-interaction {
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 2rem;
	padding: 2rem 0;
}

/* Subtle card around checkbox area */
.checkbox-card {
	width: 100%;
	padding: 1.25rem 1.5rem;
	background: var(--wizard-input-bg);
	border: 1px solid var(--wizard-input-border);
	border-radius: 0.75rem;
	cursor: pointer;
}

/* Checkbox container */
.checkbox-container {
	display: flex;
	align-items: center;
	gap: 1rem;
	cursor: pointer;
	max-width: 100%;
}

/* Custom checkbox button — increased size for touch targets */
.checkbox {
	flex-shrink: 0;
	width: 1.75rem;
	height: 1.75rem;
	display: flex;
	align-items: center;
	justify-content: center;
	background: var(--wizard-input-hover-bg);
	border: 2px solid var(--wizard-ring-border);
	border-radius: 0.5rem;
	cursor: pointer;
	transition: all 0.2s ease;
}

.checkbox:hover:not(:disabled) {
	border-color: var(--wizard-accent);
	background: var(--wizard-indicator-bg);
}

.checkbox:focus-visible {
	outline: none;
	box-shadow:
		0 0 0 2px var(--wizard-bg),
		0 0 0 4px var(--wizard-focus-ring);
}

.checkbox.checked {
	background: var(--wizard-accent);
	border-color: var(--wizard-accent);
}

.checkbox:disabled {
	cursor: not-allowed;
	opacity: 0.5;
}

/* Check icon */
.checkbox :global(.check-icon) {
	width: 1.125rem;
	height: 1.125rem;
	color: var(--wizard-bg);
	stroke-width: 3;
}

/* Checkbox label */
.checkbox-label {
	font-size: 1rem;
	line-height: 1.5;
	color: var(--wizard-text-secondary);
	user-select: none;
}

/* Accept button sizing */
.accept-btn {
	min-width: 200px;
	min-height: 44px;
	padding: 1rem 2.5rem;
	font-size: 1.0625rem;
	border-radius: 0.625rem;
}
</style>
