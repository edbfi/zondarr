<script lang="ts">
/**
 * Click Interaction Component
 *
 * Renders a confirmation button with configurable text.
 * Calls onComplete with acknowledgment data when clicked.
 */
import { clickConfigSchema } from '$lib/schemas/wizard';
import type { InteractionCompletionData, InteractionComponentProps } from './registry';

const {
	interactionId,
	config: rawConfig,
	onComplete,
	disabled = false,
	completionData
}: InteractionComponentProps = $props();

// Validate config with Zod schema, falling back gracefully for partial configs
const config = $derived(clickConfigSchema.safeParse(rawConfig).data);
const buttonText = $derived(config?.button_text ?? 'I Understand');

function handleClick() {
	onComplete({
		interactionId,
		interactionType: 'click',
		data: { acknowledged: true },
		completedAt: new Date().toISOString()
	});
}
</script>

<div class="click-interaction">
	<button type="button" class="wizard-accent-btn confirm-btn" onclick={handleClick} {disabled}>
		{buttonText}
	</button>
</div>

<style>
.click-interaction {
	display: flex;
	justify-content: center;
	padding: 2rem 0;
}

/* Override accent button sizing for primary CTA */
.confirm-btn {
	gap: 0.5rem;
	min-width: 200px;
	min-height: 44px;
	padding: 1rem 2.5rem;
	font-size: 1.0625rem;
	border-radius: 0.625rem;
	box-shadow:
		0 0 20px var(--wizard-accent-glow-lg),
		0 4px 12px var(--wizard-shadow-sm);
}

.confirm-btn:hover:not(:disabled) {
	box-shadow:
		0 0 28px var(--wizard-accent-glow-2xl),
		0 6px 16px var(--wizard-shadow-md);
}
</style>
