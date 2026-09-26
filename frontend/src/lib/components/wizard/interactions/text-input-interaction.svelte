<script lang="ts">
/**
 * Text Input Interaction Component
 *
 * Renders labeled input with placeholder.
 * Implements client-side validation for required, min_length, max_length.
 * Displays validation errors inline.
 */
import { textInputConfigSchema } from '$lib/schemas/wizard';
import type { InteractionComponentProps } from './registry';

const {
	interactionId,
	config: rawConfig,
	onComplete,
	disabled = false,
	completionData
}: InteractionComponentProps = $props();

// Validate config with Zod schema, falling back gracefully for partial configs
const config = $derived(textInputConfigSchema.safeParse(rawConfig).data);
const label = $derived(config?.label ?? 'Your response');
const placeholder = $derived(config?.placeholder ?? '');
const isRequired = $derived(config?.required ?? true);
const minLength = $derived(config?.min_length);
const maxLength = $derived(config?.max_length);

// Unique ID for label/input association (supports multiple instances per step)
const inputId = $derived(`wizard-text-input-${interactionId}`);

// Input state — restore from completion data if navigating back
let inputValue = $state(
	(() => (typeof completionData?.data?.text === 'string' ? completionData.data.text : ''))()
);
let touched = $state(false);

// Validation
const validationError = $derived.by(() => {
	if (!touched) return null;

	const value = inputValue.trim();

	if (isRequired && value.length === 0) {
		return 'This field is required';
	}

	if (minLength != null && value.length < minLength) {
		return `Must be at least ${minLength} characters`;
	}

	if (maxLength != null && value.length > maxLength) {
		return `Must be at most ${maxLength} characters`;
	}

	return null;
});

const isValid = $derived.by(() => {
	const value = inputValue.trim();

	if (isRequired && value.length === 0) return false;
	if (minLength != null && value.length < minLength) return false;
	if (maxLength != null && value.length > maxLength) return false;

	return true;
});

// Character count display
const charCount = $derived(inputValue.length);
const showCharCount = $derived(minLength != null || maxLength != null);

function handleBlur() {
	touched = true;
}

function handleSubmit() {
	touched = true;
	if (!isValid) return;

	onComplete({
		interactionId,
		interactionType: 'text_input',
		data: { text: inputValue.trim() },
		completedAt: new Date().toISOString()
	});
}

function handleKeydown(event: KeyboardEvent) {
	if (event.key === 'Enter' && !event.shiftKey) {
		event.preventDefault();
		handleSubmit();
	}
}
</script>

<div class="text-input-interaction">
	<!-- Label -->
	<label for={inputId} class="input-label">{label}</label>

	<!-- Input container -->
	<div class="input-container">
		<input
			id={inputId}
			type="text"
			class="text-input"
			class:error={validationError}
			bind:value={inputValue}
			onblur={handleBlur}
			onkeydown={handleKeydown}
			{placeholder}
			{disabled}
			aria-invalid={!!validationError}
			aria-describedby={validationError ? 'input-error' : undefined}
		>

		<!-- Character count -->
		{#if showCharCount}
			<!-- biome-ignore format: Keep the character count adjacent to its maximum. -->
			<div class="char-count" class:warning={maxLength != null && charCount > maxLength}>
				{charCount}{#if maxLength != null}/{maxLength}{/if}
			</div>
		{/if}
	</div>

	<!-- Validation error -->
	{#if validationError}
		<p id="input-error" class="error-message">{validationError}</p>
	{/if}

	<!-- Submit button -->
	<button
		type="button"
		class="wizard-accent-btn submit-btn"
		onclick={handleSubmit}
		disabled={!isValid || disabled}
	>
		Continue
	</button>
</div>

<style>
.text-input-interaction {
	display: flex;
	flex-direction: column;
	gap: 1rem;
	padding: 2rem 0;
	width: 100%;
}

/* Label */
.input-label {
	font-size: 0.9375rem;
	font-weight: 500;
	color: var(--wizard-text-secondary);
}

/* Input container */
.input-container {
	position: relative;
	width: 100%;
}

/* Text input */
.text-input {
	width: 100%;
	min-height: 44px;
	padding: 0.875rem 1rem;
	font-size: 1rem;
	color: var(--wizard-text);
	background: var(--wizard-input-bg);
	border: 1px solid var(--wizard-input-border);
	border-radius: 0.625rem;
	outline: none;
	transition: all 0.2s ease;
}

.text-input::placeholder {
	color: var(--wizard-placeholder);
}

.text-input:focus {
	border-color: var(--wizard-accent);
	box-shadow: 0 0 0 3px var(--wizard-accent-glow-sm);
}

.text-input.error {
	border-color: var(--wizard-error);
}

.text-input.error:focus {
	box-shadow: 0 0 0 3px var(--wizard-error-glow-sm);
}

.text-input:disabled {
	cursor: not-allowed;
	opacity: 0.5;
}

/* Character count */
.char-count {
	position: absolute;
	right: 0.75rem;
	top: 50%;
	transform: translateY(-50%);
	font-size: 0.75rem;
	font-family: "JetBrains Mono", "Fira Code", monospace;
	font-variant-numeric: tabular-nums;
	color: var(--wizard-placeholder);
}

.char-count.warning {
	color: var(--wizard-error);
}

/* Error message */
.error-message {
	font-size: 0.8125rem;
	color: var(--wizard-error);
	margin: 0;
}

/* Submit button layout */
.submit-btn {
	align-self: stretch;
	min-height: 44px;
	padding: 1rem 2.5rem;
	font-size: 1.0625rem;
	border-radius: 0.625rem;
	margin-top: 0.5rem;
}
</style>
