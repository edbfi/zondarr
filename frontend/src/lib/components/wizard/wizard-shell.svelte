<script lang="ts">
/**
 * Wizard Shell Component
 *
 * Main orchestrator for wizard flows. Manages step sequencing, progress tracking,
 * and session persistence. Renders markdown content with XSS sanitization.
 * Interactions are rendered internally via the interaction type registry.
 */
import { browser } from "$app/env";
import type { WizardDetailResponse } from "$lib/api/client";
import { validateStep } from "$lib/api/client";
import { getInteractionType, type InteractionCompletionData } from "./interactions";
import { getCachedLanguages, getLanguageLabel, loadLanguages } from "./language-cache";
import LanguageSwitcher from "./language-switcher.svelte";
import { renderMarkdown } from "./markdown-utils";
import WizardNavigation from "./wizard-navigation.svelte";
import WizardProgress from "./wizard-progress.svelte";

/** Translation shape from the backend API. */
interface StepTranslation {
	language_code: string;
	title: string;
	content_markdown: string;
}

/** Extended step type with translation fields (added by multilingual feature). */
type TranslatableStep = typeof wizard.steps[number] & {
	primary_language?: string;
	translations?: StepTranslation[];
};

interface Props {
	wizard: WizardDetailResponse;
	onComplete: (completionToken?: string | null) => void;
	onCancel?: () => void;
	mode?: "preview" | "join";
	/**
	 * Caller-provided namespace forwarded to interaction components that
	 * persist transient state to sessionStorage (e.g. timer deadlines).
	 * The join flow passes the invite code here so that two invites sharing
	 * the same wizard don't cross-contaminate per-interaction storage keys.
	 * Callers that don't supply one fall back to the wizard id, which is
	 * stable enough for the preview path but does NOT isolate cross-invite
	 * sessions — only the join flow needs the invite-scoped value.
	 */
	storageScope?: string;
}

const { wizard, onComplete, onCancel, mode = "join", storageScope }: Props = $props();

// Forward to interactions. Defaulting to wizard.id keeps the legacy single-
// wizard preview case working, while the join page supplies the invite code
// to isolate per-invite session state. Always passes a non-empty string so
// timer-interaction's $derived sees a stable scoped key.
const interactionStorageScope = $derived(storageScope ?? wizard.id);

// Language data (shared cache, used for native name display)
let languagesLoaded = $state(getCachedLanguages().length > 0);
loadLanguages().then(() => { languagesLoaded = true; });

// Reactive state
let currentStepIndex = $state(0);
let interactionCompletions = $state<
	Map<string, Map<string, InteractionCompletionData>>
>(new Map());
let isValidating = $state(false);
let validationError = $state<string | null>(null);
let progressToken = $state<string | null>(null);
let progressTokens = $state<Map<number, string | null>>(new Map());

// Derived values
const currentStep = $derived(wizard.steps[currentStepIndex]);
const isFirstStep = $derived(currentStepIndex === 0);
const isLastStep = $derived(currentStepIndex === wizard.steps.length - 1);
const progress = $derived(
	((currentStepIndex + 1) / wizard.steps.length) * 100,
);

// Current step's interactions
const currentInteractions = $derived(currentStep?.interactions ?? []);
const hasInteractions = $derived(currentInteractions.length > 0);
const isMultiInteraction = $derived(currentInteractions.length > 1);

// Current step's completions
const currentCompletions = $derived(
	interactionCompletions.get(currentStep?.id ?? "") ?? new Map(),
);

// Can proceed: zero interactions = true; otherwise all must be completed
const canProceed = $derived(
	!hasInteractions ||
		currentInteractions.every((i) => currentCompletions.has(i.id)),
);

// Count completions for progress display
const completedCount = $derived(currentCompletions.size);
const totalCount = $derived(currentInteractions.length);

// --- Language / translation state ---
let selectedLanguage = $state<string | null>(null);

// Cast current step to include optional translation fields
const translatableStep = $derived(currentStep as TranslatableStep | undefined);

// Build the list of available languages for the current step
const availableLanguages = $derived.by(() => {
	const step = translatableStep;
	if (!step) return [];
	// Reference languagesLoaded to re-derive when cache populates
	void languagesLoaded;
	const primary = step.primary_language ?? "en";
	const langs: { code: string; label: string }[] = [
		{ code: primary, label: getLanguageLabel(primary) },
	];
	if (step.translations) {
		for (const t of step.translations) {
			if (t.language_code !== primary) {
				langs.push({ code: t.language_code, label: getLanguageLabel(t.language_code) });
			}
		}
	}
	return langs;
});

// Effective language: selected if available for this step, else primary
const effectiveLanguage = $derived.by(() => {
	const step = translatableStep;
	if (!step) return null;
	const primary = step.primary_language ?? "en";
	if (!selectedLanguage) return primary;
	if (selectedLanguage === primary) return primary;
	if (step.translations?.some((t) => t.language_code === selectedLanguage)) {
		return selectedLanguage;
	}
	return primary;
});

// Translated title
const displayTitle = $derived.by(() => {
	const step = translatableStep;
	if (!step) return "";
	const lang = effectiveLanguage;
	const primary = step.primary_language ?? "en";
	if (lang && lang !== primary) {
		const t = step.translations?.find((tr) => tr.language_code === lang);
		if (t) return t.title;
	}
	return step.title ?? "";
});

// Render markdown content with sanitization, using translated content when available
const renderedMarkdown = $derived.by(() => {
	const step = translatableStep;
	if (!step) return "";
	const lang = effectiveLanguage;
	const primary = step.primary_language ?? "en";
	let markdown = step.content_markdown;
	if (lang && lang !== primary) {
		const t = step.translations?.find((tr) => tr.language_code === lang);
		if (t) markdown = t.content_markdown;
	}
	if (!markdown) return "";
	return renderMarkdown(markdown);
});

function handleLanguageSelect(code: string) {
	selectedLanguage = code;
}

// Wrap sessionStorage access so a SecurityError in restrictive storage
// environments (privacy mode, sandboxed iframes) cannot abort callers mid-flight
// and leave the wizard in a broken state. Matches the defensive pattern used
// in timer-interaction.svelte.
function safeRemoveItem(key: string) {
	try {
		sessionStorage.removeItem(key);
	} catch {
		// ignore storage errors (privacy mode, sandboxed iframes)
	}
}

function safeGetItem(key: string): string | null {
	try {
		return sessionStorage.getItem(key);
	} catch {
		// ignore storage errors (privacy mode, sandboxed iframes)
		return null;
	}
}

function safeSetItem(key: string, value: string) {
	try {
		sessionStorage.setItem(key, value);
	} catch {
		// ignore storage errors (quota, privacy mode, sandboxed iframes)
	}
}

// Restore language selection from sessionStorage
$effect(() => {
	if (browser) {
		const savedLang = safeGetItem(`wizard-${wizard.id}-language`);
		if (savedLang) {
			selectedLanguage = savedLang;
		}
	}
});

// Persist language selection to sessionStorage
$effect(() => {
	if (browser && selectedLanguage) {
		safeSetItem(`wizard-${wizard.id}-language`, selectedLanguage);
	}
});

// Restore progress from sessionStorage on mount (skip in preview mode).
// Silently discard any saved state that doesn't match the current wizard
// shape — out-of-range step index, missing tokens for prior steps, or
// completions referencing removed interactions all produce a "dead Next"
// button if accepted as-is. Restarting at step 0 is safe because nothing
// has been persisted server-side at this point.
$effect(() => {
	if (browser && mode !== "preview") {
		const saved = safeGetItem(`wizard-${wizard.id}-progress`);
		if (!saved) return;

		const discard = () => {
			safeRemoveItem(`wizard-${wizard.id}-progress`);
			safeRemoveItem(`wizard-${wizard.id}-language`);
			selectedLanguage = null;
		};

		try {
			const parsed = JSON.parse(saved);
			const savedIndex = parsed.stepIndex;

			// stepIndex must be a non-negative integer within the current wizard.
			if (
				typeof savedIndex !== "number" ||
				!Number.isInteger(savedIndex) ||
				savedIndex < 0 ||
				savedIndex >= wizard.steps.length
			) {
				discard();
				return;
			}

			// Build the progressTokens map first so we can validate prior steps.
			let restoredTokens = new Map<number, string | null>();
			if (parsed.progressTokens) {
				restoredTokens = new Map(
					parsed.progressTokens as [number, string | null][],
				);
			}

			// Non-zero stepIndex requires a usable progress token for each prior step.
			if (savedIndex > 0) {
				for (let i = 0; i < savedIndex; i++) {
					const token = restoredTokens.get(i);
					if (!token) {
						discard();
						return;
					}
				}

				// The current-step token (singular) must also be present and
				// consistent with the archived token for the previous step.
				// The persist $effect writes both from the same source, so any
				// divergence here means a tampered/corrupted record that would
				// otherwise produce a backend rejection on the next Next press.
				const currentToken = parsed.progressToken;
				const expectedToken = restoredTokens.get(savedIndex - 1);
				if (
					typeof currentToken !== "string" ||
					!currentToken ||
					currentToken !== expectedToken
				) {
					discard();
					return;
				}
			} else {
				// stepIndex === 0: the persist $effect only writes a non-null
				// progressToken or non-empty progressTokens after a successful
				// backend round-trip, which also increments currentStepIndex.
				// A step-0 record carrying either is therefore tampered or
				// corrupted; trusting it would let a stale token survive into
				// handleBack at a later step (progressTokens entries for
				// indices > 0 are preserved across the unconditional assign).
				if (parsed.progressToken !== null && parsed.progressToken !== undefined) {
					discard();
					return;
				}
				if (restoredTokens.size > 0) {
					discard();
					return;
				}
			}

			// Build a lookup for current step + interaction ids, plus a stepId
			// → index map so we can reject completions for steps beyond the
			// restored position.
			const stepIdToInteractionIds = new Map<string, Set<string>>();
			const stepIdToIndex = new Map<string, number>();
			for (let i = 0; i < wizard.steps.length; i++) {
				const step = wizard.steps[i];
				if (!step) continue;
				stepIdToInteractionIds.set(
					step.id,
					new Set(step.interactions.map((i) => i.id)),
				);
				stepIdToIndex.set(step.id, i);
			}

			let restoredCompletions = new Map<
				string,
				Map<string, InteractionCompletionData>
			>();
			if (parsed.completions) {
				const entries = parsed.completions as [
					string,
					[string, InteractionCompletionData][],
				][];
				for (const [stepId, completionEntries] of entries) {
					const interactionIds = stepIdToInteractionIds.get(stepId);
					if (!interactionIds) {
						// Saved completion references a step that no longer exists.
						discard();
						return;
					}
					// The persist $effect only writes completion data for steps
					// the user has actually reached, so any entry at an index
					// beyond savedIndex is tampered or corrupted; trusting it
					// would pre-arm the "already completed" path at a future
					// step and let the user bypass that step's interaction UX.
					const stepIndex = stepIdToIndex.get(stepId);
					if (stepIndex === undefined || stepIndex > savedIndex) {
						discard();
						return;
					}
					for (const [interactionId] of completionEntries) {
						if (!interactionIds.has(interactionId)) {
							// Saved completion references an interaction that no longer
							// exists on this step.
							discard();
							return;
						}
					}
					restoredCompletions.set(stepId, new Map(completionEntries));
				}
			}

			currentStepIndex = savedIndex;
			progressToken = parsed.progressToken ?? null;
			interactionCompletions = restoredCompletions;
			progressTokens = restoredTokens;
		} catch {
			discard();
		}
	}
});

// Scroll to top of wizard shell when step changes
let shellElement = $state<HTMLElement | null>(null);
$effect(() => {
	// Track currentStepIndex to trigger on step changes
	void currentStepIndex;
	if (browser && shellElement) {
		const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
		shellElement.scrollIntoView({ behavior: prefersReducedMotion ? "instant" : "smooth", block: "start" });
	}
});

// Persist progress to sessionStorage (skip in preview mode)
$effect(() => {
	if (browser && wizard.id && mode !== "preview") {
		// Serialize nested map
		const completions = Array.from(interactionCompletions.entries()).map(
			([stepId, completionMap]) => [
				stepId,
				Array.from(completionMap.entries()),
			],
		);
		safeSetItem(
			`wizard-${wizard.id}-progress`,
			JSON.stringify({
				stepIndex: currentStepIndex,
				completions,
				progressToken,
				progressTokens: Array.from(progressTokens.entries()),
			}),
		);
	}
});

async function handleNext() {
	const step = currentStep;
	if (!step) {
		// Should not happen after restore hardening, but defend anyway:
		// if the index ever falls outside wizard.steps, `canProceed` would be
		// vacuously true and the user would see a dead Next button.
		// Fully reset in-memory state too — otherwise the persist $effect
		// (which re-runs as soon as currentStepIndex changes) would
		// immediately re-write sessionStorage with stale completions/tokens
		// alongside stepIndex: 0, producing an inconsistent saved record.
		if (browser && mode !== "preview") {
			safeRemoveItem(`wizard-${wizard.id}-progress`);
			safeRemoveItem(`wizard-${wizard.id}-language`);
		}
		interactionCompletions = new Map();
		progressToken = null;
		progressTokens = new Map();
		selectedLanguage = null;
		currentStepIndex = 0;
		validationError = "Your progress was reset. Please start again.";
		return;
	}
	if (!canProceed || isValidating) return;

	isValidating = true;
	validationError = null;

	try {
		// Build interaction responses array
		const interactions = currentInteractions.map((interaction) => {
			const completion = currentCompletions.get(interaction.id);
			return {
				interaction_id: interaction.id,
				response: completion?.data ?? {},
				started_at: completion?.startedAt ?? null,
			};
		});

		const result = await validateStep({
			step_id: step.id,
			interactions: interactions.length > 0 ? interactions : [],
			progress_token: progressToken,
		});

		if (!result.data?.valid) {
			validationError = result.data?.error ?? "Validation failed";
			// Clear completion data for this step so interactions are re-enabled
			const newMap = new Map(interactionCompletions);
			newMap.delete(step.id);
			interactionCompletions = newMap;
			return;
		}

		if (isLastStep) {
			if (browser && mode !== "preview") {
				safeRemoveItem(`wizard-${wizard.id}-progress`);
				safeRemoveItem(`wizard-${wizard.id}-language`);
			}
			onComplete(result.data?.completion_token);
		} else {
			// Store progress token for next step validation
			const newToken = result.data?.completion_token ?? null;
			progressToken = newToken;
			// Save this token keyed by the step we just validated, so we can
			// restore it when navigating back to the *next* step
			const newTokens = new Map(progressTokens);
			newTokens.set(currentStepIndex, newToken);
			progressTokens = newTokens;
			currentStepIndex++;
		}
	} finally {
		isValidating = false;
	}
}

function handleBack() {
	if (!isFirstStep) {
		const targetIndex = currentStepIndex - 1;
		// Restore the progress token that was valid *before* the target step.
		// For step 0, no token is needed (null). For step N, we need the token
		// returned after validating step N-1, stored at progressTokens[N-1].
		progressToken = targetIndex === 0 ? null : (progressTokens.get(targetIndex - 1) ?? null);
		// Clear interaction completions for the step we're going back to
		// and all subsequent steps, since those will need to be re-completed
		const newCompletions = new Map(interactionCompletions);
		for (let i = targetIndex; i < wizard.steps.length; i++) {
			const stepId = wizard.steps[i]?.id;
			if (stepId) newCompletions.delete(stepId);
		}
		interactionCompletions = newCompletions;
		// Clear stored tokens for the target step onward (they'll be regenerated)
		const newTokens = new Map(progressTokens);
		for (let i = targetIndex; i < wizard.steps.length; i++) {
			newTokens.delete(i);
		}
		progressTokens = newTokens;
		currentStepIndex = targetIndex;
		validationError = null;
	}
}

function handleInteractionComplete(data: InteractionCompletionData) {
	validationError = null;
	const stepId = currentStep?.id;
	if (!stepId) return;

	const stepCompletions = new Map(
		interactionCompletions.get(stepId) ?? new Map(),
	);
	stepCompletions.set(data.interactionId, data);

	const newMap = new Map(interactionCompletions);
	newMap.set(stepId, stepCompletions);
	interactionCompletions = newMap;
}

async function handleInteractionValidate(
	data: InteractionCompletionData,
): Promise<{ valid: boolean; pending?: boolean; error?: string | null }> {
	const step = currentStep;
	if (!step) return { valid: false, error: "No current step" };
	validationError = null;

	// Build a temporary completions map including this pending response
	const tempCompletions = new Map(
		interactionCompletions.get(step.id) ?? new Map(),
	);
	tempCompletions.set(data.interactionId, data);

	// Check if all other interactions on the step are completed
	const allReady = currentInteractions.every((i) =>
		tempCompletions.has(i.id),
	);

	if (!allReady) {
		// Not all interactions ready — store completion locally, skip backend validation
		// Return pending: true so the interaction knows this is not a backend-validated result
		handleInteractionComplete(data);
		return { valid: true, pending: true };
	}

	// All interactions ready — validate with backend
	try {
		const interactions = currentInteractions.map((interaction) => {
			const completion = tempCompletions.get(interaction.id);
			return {
				interaction_id: interaction.id,
				response: completion?.data ?? {},
				started_at: completion?.startedAt ?? null,
			};
		});

		const result = await validateStep({
			step_id: step.id,
			interactions,
			progress_token: progressToken,
		});

		if (result.data?.valid) {
			handleInteractionComplete(data);
			return { valid: true };
		}
		// Backend rejected — clear all completions for this step so interactions can retry
		const newMap = new Map(interactionCompletions);
		newMap.delete(step.id);
		interactionCompletions = newMap;
		if (data.interactionType !== "quiz") {
			validationError = result.data?.error ?? "Incorrect answer";
		}
		return { valid: false, error: result.data?.error ?? "Incorrect answer" };
	} catch {
		return { valid: false, error: "Validation failed. Please try again." };
	}
}
</script>

<div class="wizard-shell" bind:this={shellElement}>
	<div class="wizard-container">
		<!-- Progress indicator -->
		<WizardProgress current={currentStepIndex + 1} total={wizard.steps.length} {progress} stepTitle={currentStep?.title} />

		<!-- Step content card -->
		{#key currentStep?.id}
		<div class="wizard-card">
			<!-- Step title with language switcher -->
			<div class="wizard-title-row">
				{#if displayTitle}
					{#key effectiveLanguage}
						<h2 class="wizard-title">{displayTitle}</h2>
					{/key}
				{/if}
				<LanguageSwitcher
					languages={availableLanguages}
					selected={effectiveLanguage ?? "en"}
					onSelect={handleLanguageSelect}
				/>
			</div>

			<!-- Markdown content -->
			{#key effectiveLanguage}
				<div class="wizard-content prose prose-invert lang-fade">
					{@html renderedMarkdown}
				</div>
			{/key}

			<!-- Interactions area -->
			<div class="wizard-interaction" class:has-interactions={hasInteractions}>
				{#if hasInteractions}
					{#if isMultiInteraction}
						<div class="interaction-progress">
							<span class="progress-text">{completedCount}/{totalCount} completed</span>
							<div class="progress-track">
								<div
									class="progress-fill"
									style="width: {totalCount > 0 ? (completedCount / totalCount) * 100 : 0}%"
								></div>
							</div>
						</div>
					{/if}

					{#each currentInteractions as interaction, idx (interaction.id)}
						{@const interactionDef = getInteractionType(interaction.interaction_type)}
						{@const isCompleted = currentCompletions.has(interaction.id)}

						{#if isMultiInteraction && idx > 0}
							<div class="interaction-divider"></div>
						{/if}

						{#if interactionDef}
							{@const InteractionComponent = interactionDef.interactionComponent}
							<div
								class="interaction-block"
								class:completed={isCompleted && isMultiInteraction}
								style="animation-delay: {0.3 + idx * 0.1}s"
							>
								{#if isMultiInteraction}
									<div class="interaction-header">
										<div class="completion-ring" class:done={isCompleted}>
											{#if isCompleted}
												<svg viewBox="0 0 20 20" class="check-icon" aria-hidden="true">
													<path d="M6 10l3 3 5-6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
												</svg>
											{/if}
										</div>
										<span class="interaction-label">{interactionDef.label}</span>
									</div>
								{/if}

								<InteractionComponent
									interactionId={interaction.id}
									config={interaction.config}
									onComplete={handleInteractionComplete}
									onValidate={handleInteractionValidate}
									disabled={isValidating || isCompleted}
									completionData={currentCompletions.get(interaction.id)}
									storageScope={interactionStorageScope}
								/>
							</div>
						{/if}
					{/each}
				{/if}
			</div>

			<!-- Validation error -->
			{#if validationError}
				<p class="wizard-error">{validationError}</p>
			{/if}
		</div>
		{/key}

		<!-- Navigation -->
		<WizardNavigation
			{isFirstStep}
			{isLastStep}
			{canProceed}
			loading={isValidating}
			onBack={handleBack}
			onNext={handleNext}
			{onCancel}
		/>
	</div>
</div>

<style>
	/*
	 * Wizard shell CSS variables — intentionally a fixed dark-mode-only design.
	 * The wizard is a standalone cinematic experience that doesn't follow the
	 * admin theme. Colors are hardcoded here rather than in app.css :root.
	 */
	.wizard-shell {
		--wizard-bg: hsl(220 20% 4%);
		--wizard-surface: hsl(220 15% 8%);
		--wizard-surface-elevated: hsl(220 20% 8%);
		--wizard-border: hsl(220 10% 18%);
		--wizard-text: hsl(220 10% 92%);
		--wizard-text-muted: hsl(220 10% 60%);
		--wizard-accent: var(--cr-module-active-accent);
		--wizard-accent-dim: var(--cr-module-active-accent-dim);
		--wizard-accent-glow: hsl(45 90% 55% / 0.15);
		--wizard-success: var(--cr-success);
		--wizard-error: var(--cr-error);
		--wizard-error-bg: hsl(0 70% 55% / 0.1);
		--wizard-error-border: hsl(0 70% 55% / 0.3);
		--wizard-code-bg: hsl(220 15% 12%);
		--wizard-track-bg: hsl(220 10% 16%);
		--wizard-divider: hsl(220 10% 20%);
		--wizard-ring-border: hsl(220 10% 30%);

		/* Glow/shadow colors (used by interaction components for box-shadow) */
		--wizard-accent-glow-sm: hsl(45 90% 55% / 0.15);
		--wizard-accent-glow-md: hsl(45 90% 55% / 0.2);
		--wizard-accent-glow-lg: hsl(45 90% 55% / 0.25);
		--wizard-accent-glow-xl: hsl(45 90% 55% / 0.3);
		--wizard-accent-glow-2xl: hsl(45 90% 55% / 0.35);
		--wizard-accent-glow-hover: hsl(45 90% 55% / 0.4);
		--wizard-accent-glow-active: hsl(45 90% 55% / 0.5);
		--wizard-accent-border-hover: hsl(45 90% 55% / 0.5);
		--wizard-accent-bg-subtle: hsl(45 90% 55% / 0.08);
		--wizard-shadow-sm: hsl(0 0% 0% / 0.2);
		--wizard-shadow-md: hsl(0 0% 0% / 0.25);
		--wizard-shadow-lg: hsl(0 0% 0% / 0.3);
		--wizard-success-glow-lg: hsl(150 60% 45% / 0.4);
		--wizard-success-glow-sm: hsl(150 60% 45% / 0.2);
		--wizard-error-glow-sm: hsl(0 70% 55% / 0.15);
		--wizard-card-inset: hsl(0 0% 100% / 0.05);
		--wizard-focus-ring: hsl(45 90% 55% / 0.5);

		/* SVG gradient stop colors */
		--wizard-accent-gradient-start: hsl(45 90% 45%);
		--wizard-accent-gradient-end: hsl(45 90% 60%);

		/* Form element colors (used by interaction components) */
		--wizard-text-secondary: hsl(220 10% 80%);
		--wizard-text-dim: hsl(220 10% 50%);
		--wizard-input-bg: hsl(220 15% 10%);
		--wizard-input-border: hsl(220 10% 22%);
		--wizard-input-hover-bg: hsl(220 15% 12%);
		--wizard-indicator-bg: hsl(220 15% 15%);
		--wizard-placeholder: hsl(220 10% 45%);
		--wizard-btn-disabled-bg: hsl(220 10% 25%);

		position: relative;
		display: flex;
		flex-direction: column;
		align-items: center;
		background: var(--wizard-bg);
		border-radius: 0.75rem;
		padding: 1.5rem;
		color: var(--wizard-text);
		font-family: 'Satoshi', 'DM Sans', system-ui, sans-serif;
	}

	.wizard-container {
		position: relative;
		width: 100%;
		max-width: 720px;
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
	}

	/* Step card with glass effect */
	.wizard-card {
		background: var(--wizard-surface);
		border: 1px solid var(--wizard-border);
		border-radius: 1.25rem;
		padding: 2.5rem;
		backdrop-filter: blur(8px);
		box-shadow:
			0 4px 24px var(--wizard-shadow-lg),
			0 0 0 1px var(--wizard-card-inset) inset,
			0 0 0 1px hsl(45 90% 55% / 0.06) inset;
		animation: step-enter 0.5s ease-out both;
		overflow-y: auto;
		overflow-x: hidden;
		min-height: 0;
		scrollbar-color: hsl(220 10% 30%) transparent;
		scrollbar-width: thin;
	}

	.wizard-card::-webkit-scrollbar {
		width: 8px;
	}

	.wizard-card::-webkit-scrollbar-track {
		background: transparent;
	}

	.wizard-card::-webkit-scrollbar-thumb {
		background: hsl(220 10% 30%);
		border-radius: 4px;
	}

	.wizard-card::-webkit-scrollbar-thumb:hover {
		background: hsl(220 10% 40%);
	}

	/* Title row: title + language switcher */
	.wizard-title-row {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 1rem;
		margin-bottom: 1.5rem;
	}

	/* Cinematic title */
	.wizard-title {
		font-family: 'Instrument Serif', 'Playfair Display', Georgia, serif;
		font-size: 2rem;
		font-weight: 500;
		letter-spacing: -0.02em;
		margin-bottom: 0;
		color: var(--wizard-text);
		animation: wizard-reveal 0.6s ease-out 0.15s both;
	}

	/* Fade animation for language-switched content */
	.lang-fade {
		animation: lang-fade-in 0.25s ease-out both;
	}

	/* Content area */
	.wizard-content {
		font-size: 1.125rem;
		line-height: 1.7;
		color: var(--wizard-text-muted);
		margin-bottom: 2rem;
		animation: wizard-reveal 0.6s ease-out 0.2s both;
	}

	.wizard-content :global(a) {
		color: var(--wizard-accent);
		text-decoration: underline;
		text-underline-offset: 2px;
		transition: opacity 0.15s ease;
	}

	.wizard-content :global(a:hover) {
		opacity: 0.8;
	}

	.wizard-content :global(strong) {
		color: var(--wizard-text);
		font-weight: 600;
	}

	.wizard-content :global(code) {
		font-family: 'JetBrains Mono', 'Fira Code', monospace;
		background: var(--wizard-code-bg);
		padding: 0.125rem 0.375rem;
		border-radius: 0.25rem;
		font-size: 0.9em;
		color: var(--wizard-accent);
		white-space: nowrap;
	}

	/* Headings */
	.wizard-content :global(h1) {
		font-family: 'Instrument Serif', 'Playfair Display', Georgia, serif;
		font-size: 1.875rem;
		font-weight: 500;
		letter-spacing: -0.02em;
		margin-top: 2rem;
		margin-bottom: 0.75rem;
		color: var(--wizard-text);
		line-height: 1.2;
	}

	.wizard-content :global(h2) {
		font-family: 'Instrument Serif', 'Playfair Display', Georgia, serif;
		font-size: 1.5rem;
		font-weight: 500;
		letter-spacing: -0.01em;
		margin-top: 1.75rem;
		margin-bottom: 0.625rem;
		color: var(--wizard-text);
		line-height: 1.3;
	}

	.wizard-content :global(h3) {
		font-family: 'Satoshi', 'DM Sans', system-ui, sans-serif;
		font-size: 1.25rem;
		font-weight: 600;
		margin-top: 1.5rem;
		margin-bottom: 0.5rem;
		color: var(--wizard-text);
		line-height: 1.4;
	}

	.wizard-content :global(h4) {
		font-family: 'Satoshi', 'DM Sans', system-ui, sans-serif;
		font-size: 1.125rem;
		font-weight: 600;
		margin-top: 1.25rem;
		margin-bottom: 0.375rem;
		color: var(--wizard-text);
		line-height: 1.4;
	}

	.wizard-content :global(h5),
	.wizard-content :global(h6) {
		font-family: 'Satoshi', 'DM Sans', system-ui, sans-serif;
		font-size: 1rem;
		font-weight: 600;
		margin-top: 1.125rem;
		margin-bottom: 0.375rem;
		color: var(--wizard-text-muted);
		line-height: 1.4;
	}

	/* Paragraph */
	.wizard-content :global(p) {
		max-width: 65ch;
		margin-bottom: 1.25rem;
		color: var(--wizard-text-muted);
		line-height: 1.7;
	}

	/* Horizontal rule */
	.wizard-content :global(hr) {
		height: 1px;
		background: linear-gradient(
			to right,
			transparent,
			hsl(220 10% 22%),
			transparent
		);
		border: none;
		margin-top: 1.5rem;
		margin-bottom: 1.5rem;
		border-radius: 1px;
	}

	/* Blockquote */
	.wizard-content :global(blockquote) {
		border-left: 3px solid var(--wizard-accent);
		padding-left: 1rem;
		padding-top: 0.5rem;
		padding-bottom: 0.5rem;
		margin-left: 0;
		margin-right: 0;
		margin-top: 1rem;
		margin-bottom: 1rem;
		background: hsl(220 15% 10% / 0.5);
		color: var(--wizard-text-muted);
		font-style: italic;
		line-height: 1.6;
	}

	/* Code blocks */
	.wizard-content :global(pre) {
		background: var(--wizard-code-bg);
		padding: 1rem;
		border-radius: 0.5rem;
		border: 1px solid hsl(220 10% 22%);
		margin-top: 1rem;
		margin-bottom: 1rem;
		overflow-x: auto;
		line-height: 1.5;
	}

	.wizard-content :global(pre code) {
		background: transparent;
		padding: 0;
		border-radius: 0;
		font-size: 0.875rem;
		color: hsl(220 10% 92%);
		white-space: pre;
		display: block;
	}

	/* Images */
	.wizard-content :global(img) {
		max-width: 100%;
		height: auto;
		border-radius: 0.5rem;
		margin-top: 1rem;
		margin-bottom: 1rem;
		display: block;
		box-shadow: 0 4px 16px hsl(0 0% 0% / 0.3);
		transition: box-shadow 0.2s ease;
	}

	.wizard-content :global(img:hover) {
		box-shadow: 0 8px 32px hsl(0 0% 0% / 0.4);
	}

	.wizard-content :global(img:focus-visible) {
		outline: 2px solid var(--wizard-accent);
		outline-offset: 2px;
	}

	/* Lists */
	.wizard-content :global(ul) {
		padding-left: 1.5rem;
		margin-top: 1rem;
		margin-bottom: 1rem;
		list-style-type: disc;
		list-style-position: outside;
	}

	.wizard-content :global(ol) {
		padding-left: 1.5rem;
		margin-top: 1rem;
		margin-bottom: 1rem;
		list-style-type: decimal;
		list-style-position: outside;
	}

	.wizard-content :global(li) {
		margin-bottom: 0.5rem;
		color: var(--wizard-text-muted);
		line-height: 1.7;
	}

	.wizard-content :global(li > p) {
		margin-bottom: 0;
	}

	.wizard-content :global(li strong) {
		color: var(--wizard-text);
	}

	/* Nested lists */
	.wizard-content :global(ul ul),
	.wizard-content :global(ol ol),
	.wizard-content :global(ul ol),
	.wizard-content :global(ol ul) {
		margin-top: 0.5rem;
		margin-bottom: 0;
		padding-left: 1.5rem;
	}

	/* Link enhancements */
	.wizard-content :global(a:focus-visible) {
		outline: 2px solid var(--wizard-accent);
		outline-offset: 2px;
		border-radius: 2px;
	}

	.wizard-content :global(a:active) {
		opacity: 0.7;
	}

	/* Text formatting */
	.wizard-content :global(em) {
		font-style: italic;
		color: var(--wizard-text-muted);
	}

	.wizard-content :global(u) {
		text-decoration: underline;
		text-underline-offset: 2px;
	}

	/* Interaction area */
	.wizard-interaction {
		animation: wizard-reveal 0.6s ease-out 0.3s both;
	}

	.wizard-interaction.has-interactions {
		padding-top: 2rem;
		border-top: 1px solid var(--wizard-divider);
	}

	/* Multi-interaction progress bar */
	.interaction-progress {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		margin-bottom: 1.25rem;
	}

	.progress-text {
		font-size: 0.6875rem;
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--wizard-text-muted);
	}

	.progress-track {
		height: 2px;
		background: var(--wizard-track-bg);
		border-radius: 1px;
		overflow: hidden;
	}

	.progress-fill {
		height: 100%;
		background: linear-gradient(to right, var(--wizard-accent), var(--wizard-accent-dim));
		border-radius: 1px;
		transition: width 0.4s ease;
	}

	/* Gradient divider between interactions */
	.interaction-divider {
		height: 1px;
		margin: 1.25rem 0;
		background: linear-gradient(to right, transparent, var(--wizard-divider), transparent);
	}

	/* Interaction block */
	.interaction-block {
		animation: wizard-reveal 0.5s ease-out both;
	}

	.interaction-block.completed {
		opacity: 0.7;
		transition: opacity 0.3s ease;
	}

	/* Interaction header (multi-interaction only) */
	.interaction-header {
		display: flex;
		align-items: center;
		gap: 0.625rem;
		margin-bottom: 0.75rem;
	}

	.completion-ring {
		width: 1.25rem;
		height: 1.25rem;
		border-radius: 50%;
		border: 1.5px solid var(--wizard-ring-border);
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all 0.3s ease;
		flex-shrink: 0;
	}

	.completion-ring.done {
		border-color: var(--wizard-accent);
		background: var(--wizard-accent);
		animation: check-pop 0.3s ease;
	}

	.check-icon {
		width: 0.75rem;
		height: 0.75rem;
		color: var(--wizard-bg);
	}

	.interaction-label {
		font-size: 0.6875rem;
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--wizard-text-muted);
	}

	/* Error message */
	.wizard-error {
		color: var(--wizard-error);
		font-size: 0.875rem;
		margin-top: 1rem;
		padding: 0.75rem 1rem;
		background: var(--wizard-error-bg);
		border: 1px solid var(--wizard-error-border);
		border-radius: 0.5rem;
	}

	/* Step transition animation */
	@keyframes step-enter {
		from {
			opacity: 0;
			transform: translateY(12px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}

	/* Reveal animation */
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

	@keyframes lang-fade-in {
		from {
			opacity: 0;
		}
		to {
			opacity: 1;
		}
	}

	@keyframes check-pop {
		0% {
			transform: scale(0.8);
		}
		50% {
			transform: scale(1.15);
		}
		100% {
			transform: scale(1);
		}
	}

	/* Responsive: tighter padding on mobile */
	@media (max-width: 639px) {
		.wizard-shell {
			padding: 1rem;
		}

		.wizard-card {
			padding: 1.5rem;
			border-radius: 1rem;
		}

		.wizard-title {
			font-size: 1.625rem;
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.wizard-card,
		.wizard-title,
		.wizard-content,
		.wizard-interaction,
		.interaction-block,
		.lang-fade {
			animation: none;
		}

		.wizard-content :global(a),
		.wizard-content :global(img) {
			transition: none;
		}

		.progress-fill {
			transition: none;
		}

		.wizard-card {
			scroll-behavior: auto;
		}
	}
</style>
