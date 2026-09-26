<script lang="ts">
/**
 * Quiz Interaction Component
 *
 * Renders question and selectable options.
 * Applies border glow on hover, checkmark animation on selection.
 * Validates answer via onValidate (if provided) with inline feedback and cooldown.
 * Falls back to onComplete directly when onValidate is not provided (preview mode).
 */
import { Check, X } from '@lucide/svelte';
import { onDestroy } from 'svelte';
import { quizDisplayConfigSchema } from '$lib/schemas/wizard';
import type { InteractionComponentProps } from './registry';

const {
	interactionId,
	config: rawConfig,
	onComplete,
	onValidate,
	disabled = false,
	completionData
}: InteractionComponentProps = $props();

// Validate config with display schema (correct_answer_index is optional since
// the backend strips it from public API responses to prevent answer leakage)
const config = $derived(quizDisplayConfigSchema.safeParse(rawConfig).data);
const question = $derived(config?.question ?? '');
const options = $derived(config?.options ?? []);

// Selection state — restore from completion data if navigating back
let selectedIndex = $state<number | null>(
	(() =>
		typeof completionData?.data?.answer_index === 'number'
			? completionData.data.answer_index
			: null)()
);

// Already correct if we have completion data (navigated back to completed step)
const alreadyCorrect = $derived(completionData != null);

// Feedback and cooldown state
let feedbackState = $state<'correct' | 'incorrect' | null>(null);
let inlineError = $state<string | null>(null);
let isSubmitting = $state(false);
let wrongAttempts = $state(0);
let cooldownRemaining = $state(0);
let cooldownInterval = $state<ReturnType<typeof setInterval> | null>(null);

// Track previous completionData for transition detection (initial value intentionally undefined)
let previousCompletionData: InteractionComponentProps['completionData'];
// Flag to suppress $effect feedback after pending submission (multi-interaction step)
let pendingSubmission = $state(false);

// Sync local state with completionData transitions:
// - null→non-null: restore "correct" feedback (navigating back to completed step)
// - non-null→null: reset state (shell cleared completionData after step-level validation failure)
$effect(() => {
	if (previousCompletionData != null && completionData == null && feedbackState === 'correct') {
		feedbackState = null;
		selectedIndex = null;
		wrongAttempts = 0;
		cooldownRemaining = 0;
		inlineError = null;
		if (cooldownInterval) {
			clearInterval(cooldownInterval);
			cooldownInterval = null;
		}
	} else if (previousCompletionData == null && completionData != null) {
		if (pendingSubmission) {
			// Multi-interaction step: answer stored locally but not yet backend-validated
			pendingSubmission = false;
		} else {
			// Navigating back to a completed, backend-validated step
			feedbackState = 'correct';
		}
	}
	previousCompletionData = completionData;
});

// Derived - interaction disabled
const isInteractionDisabled = $derived(
	disabled || isSubmitting || cooldownRemaining > 0 || alreadyCorrect || feedbackState === 'correct'
);

// Derived - has selection
const hasSelection = $derived(selectedIndex !== null);

function selectOption(index: number) {
	if (isInteractionDisabled) return;
	selectedIndex = index;
	// Clear feedback when selecting a new option after wrong answer
	if (feedbackState === 'incorrect') {
		feedbackState = null;
		inlineError = null;
	}
}

function startCooldown() {
	const duration = Math.min(3 + (wrongAttempts - 1) * 2, 10);
	cooldownRemaining = duration;

	if (cooldownInterval) clearInterval(cooldownInterval);
	cooldownInterval = setInterval(() => {
		cooldownRemaining--;
		if (cooldownRemaining <= 0) {
			if (cooldownInterval) {
				clearInterval(cooldownInterval);
				cooldownInterval = null;
			}
		}
	}, 1000);
}

async function handleSubmit() {
	if (selectedIndex === null || isInteractionDisabled) return;

	const completionPayload = {
		interactionId,
		interactionType: 'quiz' as const,
		data: { answer_index: selectedIndex },
		completedAt: new Date().toISOString()
	};

	// Fallback: no onValidate (preview mode) — call onComplete directly
	if (!onValidate) {
		onComplete(completionPayload);
		return;
	}

	// Validate via backend
	isSubmitting = true;
	// Set flag BEFORE await so the $effect (which fires in the microtask gap)
	// won't falsely show "Correct!" when completionData transitions null→non-null
	pendingSubmission = true;
	try {
		const result = await onValidate(completionPayload);

		if (result.valid && !result.pending) {
			pendingSubmission = false;
			feedbackState = 'correct';
			inlineError = null;
		} else if (result.valid && result.pending) {
			// Answer accepted but not yet validated by backend (multi-interaction step)
			// Don't show "Correct!" — flag already set, $effect will see it
			inlineError = null;
		} else {
			pendingSubmission = false;
			wrongAttempts++;
			feedbackState = 'incorrect';
			inlineError = result.error ?? 'Incorrect answer';
			startCooldown();
		}
	} finally {
		isSubmitting = false;
	}
}

function handleKeydown(event: KeyboardEvent, index: number) {
	if (event.key === 'Enter' || event.key === ' ') {
		event.preventDefault();
		selectOption(index);
	}
}

onDestroy(() => {
	if (cooldownInterval) clearInterval(cooldownInterval);
});
</script>

<div class="quiz-interaction">
	<!-- Question -->
	<h3 class="question">{question}</h3>

	<!-- Options -->
	<div class="options" role="radiogroup" aria-label="Quiz options">
		{#each options as option, index}
			<!-- biome-ignore lint/a11y/useSemanticElements: The existing custom radio has explicit checked state and keyboard selection. -->
			<button
				type="button"
				role="radio"
				aria-checked={selectedIndex === index}
				class="option"
				class:selected={selectedIndex === index && !feedbackState}
				class:correct={selectedIndex === index && feedbackState === 'correct'}
				class:incorrect={selectedIndex === index && feedbackState === 'incorrect'}
				onclick={() => selectOption(index)}
				onkeydown={(e) => handleKeydown(e, index)}
				disabled={isInteractionDisabled}
			>
				<span
					class="option-indicator"
					class:indicator-correct={selectedIndex === index && feedbackState === 'correct'}
					class:indicator-incorrect={selectedIndex === index && feedbackState === 'incorrect'}
				>
					{#if selectedIndex === index && feedbackState === 'correct'}
						<Check class="check-icon" />
					{:else if selectedIndex === index && feedbackState === 'incorrect'}
						<X class="x-icon" />
					{:else if selectedIndex === index}
						<Check class="check-icon" />
					{/if}
				</span>
				<span class="option-text">{option}</span>
			</button>
		{/each}
	</div>

	<!-- Feedback messages -->
	{#if feedbackState === 'correct'}
		<p class="quiz-success">Correct!</p>
	{:else if feedbackState === 'incorrect' && inlineError}
		<p class="quiz-error">
			{inlineError}
			{#if cooldownRemaining > 0}
				<span class="cooldown-text"> — wait {cooldownRemaining}s</span>
			{/if}
		</p>
	{/if}

	<!-- Submit button (hidden once correct or already completed) -->
	{#if feedbackState !== 'correct' && !alreadyCorrect}
		<button
			type="button"
			class="wizard-accent-btn submit-btn"
			onclick={handleSubmit}
			disabled={!hasSelection || isInteractionDisabled}
		>
			{#if isSubmitting}
				Checking...
			{:else if cooldownRemaining > 0}
				Wait {cooldownRemaining}s...
			{:else}
				Submit Answer
			{/if}
		</button>
	{/if}
</div>

<style>
.quiz-interaction {
	display: flex;
	flex-direction: column;
	gap: 1.5rem;
	padding: 2rem 0;
}

/* Question */
.question {
	font-family: "Instrument Serif", "Playfair Display", Georgia, serif;
	font-size: 1.5rem;
	font-weight: 500;
	color: var(--wizard-text);
	margin: 0;
	line-height: 1.4;
}

/* Options container */
.options {
	display: flex;
	flex-direction: column;
	gap: 0.875rem;
}

/* Individual option — 44px min touch target */
.option {
	display: flex;
	align-items: center;
	gap: 1rem;
	min-height: 44px;
	padding: 1.125rem 1.5rem;
	background: var(--wizard-input-bg);
	border: 2px solid var(--wizard-input-border);
	border-radius: 0.75rem;
	cursor: pointer;
	transition: all 0.2s ease;
	text-align: left;
}

.option:hover:not(:disabled):not(.selected):not(.correct):not(.incorrect) {
	border-color: var(--wizard-accent-border-hover);
	box-shadow: 0 0 12px var(--wizard-accent-glow-sm);
	background: var(--wizard-input-hover-bg);
}

.option:focus-visible {
	outline: none;
	border-color: var(--wizard-accent);
	box-shadow: 0 0 0 3px var(--wizard-accent-glow-md);
}

.option.selected {
	border-color: var(--wizard-accent);
	background: var(--wizard-accent-bg-subtle);
	box-shadow: 0 0 16px var(--wizard-accent-glow-md);
}

.option.correct {
	border-color: var(--wizard-success);
	background: hsl(150 60% 45% / 0.08);
	box-shadow: 0 0 16px var(--wizard-success-glow-sm);
}

.option.incorrect {
	border-color: var(--wizard-error);
	background: var(--wizard-error-bg);
	box-shadow: 0 0 16px var(--wizard-error-glow-sm);
}

.option:disabled {
	cursor: not-allowed;
	opacity: 0.5;
}

.option.correct:disabled,
.option.incorrect:disabled {
	opacity: 1;
}

/* Option indicator (circle/check/x) */
.option-indicator {
	flex-shrink: 0;
	width: 1.5rem;
	height: 1.5rem;
	display: flex;
	align-items: center;
	justify-content: center;
	background: var(--wizard-indicator-bg);
	border: 2px solid var(--wizard-ring-border);
	border-radius: 50%;
	transition: all 0.2s ease;
}

.option.selected .option-indicator {
	background: var(--wizard-accent);
	border-color: var(--wizard-accent);
	animation: check-pop 0.3s ease;
}

.option-indicator.indicator-correct {
	background: var(--wizard-success);
	border-color: var(--wizard-success);
	animation: check-pop 0.3s ease;
}

.option-indicator.indicator-incorrect {
	background: var(--wizard-error);
	border-color: var(--wizard-error);
	animation: check-pop 0.3s ease;
}

/* Check icon */
.option-indicator :global(.check-icon) {
	width: 0.875rem;
	height: 0.875rem;
	color: var(--wizard-bg);
	stroke-width: 3;
}

/* X icon */
.option-indicator :global(.x-icon) {
	width: 0.875rem;
	height: 0.875rem;
	color: var(--wizard-bg);
	stroke-width: 3;
}

/* Option text */
.option-text {
	font-size: 1rem;
	color: var(--wizard-text-secondary);
	line-height: 1.5;
}

.option.selected .option-text {
	color: var(--wizard-text);
}

.option.correct .option-text {
	color: var(--wizard-text);
}

/* Feedback messages */
.quiz-success {
	font-size: 0.875rem;
	font-weight: 600;
	color: var(--wizard-success);
	margin: 0;
}

.quiz-error {
	font-size: 0.875rem;
	color: var(--wizard-error);
	margin: 0;
	padding: 0.75rem 1rem;
	background: var(--wizard-error-bg);
	border: 1px solid var(--wizard-error-border);
	border-radius: 0.5rem;
}

.cooldown-text {
	font-weight: 500;
	opacity: 0.8;
}

/* Submit button layout */
.submit-btn {
	align-self: flex-start;
	min-width: 200px;
	min-height: 44px;
	padding: 1rem 2.5rem;
	font-size: 1.0625rem;
	border-radius: 0.625rem;
	margin-top: 0.5rem;
}

/* Checkmark pop animation */
@keyframes check-pop {
	0% {
		transform: scale(0.8);
	}
	50% {
		transform: scale(1.1);
	}
	100% {
		transform: scale(1);
	}
}
</style>
