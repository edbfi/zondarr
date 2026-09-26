<script lang="ts">
/**
 * Wizard editor page.
 *
 * Displays the wizard builder for editing an existing wizard.
 * Includes preview mode for testing the wizard flow.
 *
 * @module routes/(admin)/wizards/[id]/+page
 */

import { goto, invalidateAll } from '$app/navigation';
import type { WizardDetailResponse, WizardStepResponse } from '$lib/api/client';
import { getErrorMessage, isNetworkError } from '$lib/api/errors';
import ErrorState from '$lib/components/error-state.svelte';
import { WizardBuilder, WizardShell } from '$lib/components/wizard';
import type { PageData } from './$types';

const { data }: { data: PageData } = $props();

// Preview mode state
let isPreviewMode = $state(false);
let previewSteps = $state<WizardStepResponse[]>([]);

/**
 * Handle save - refresh data and stay on page.
 */
async function handleSave(_wizard: WizardDetailResponse) {
	await invalidateAll();
}

/**
 * Handle cancel - go back to wizard list.
 */
function handleCancel() {
	goto('/wizards');
}

/**
 * Toggle preview mode with current steps from the builder.
 */
function handlePreview(currentSteps: WizardStepResponse[]) {
	previewSteps = currentSteps;
	isPreviewMode = true;
}

/**
 * Exit preview mode.
 */
async function handleExitPreview() {
	await invalidateAll();
	isPreviewMode = false;
}

/**
 * Handle wizard completion in preview mode.
 */
async function handlePreviewComplete() {
	await invalidateAll();
	isPreviewMode = false;
}

/**
 * Handle retry after error.
 */
async function handleRetry() {
	await invalidateAll();
}
</script>

{#if data.error}
	<ErrorState
		message={getErrorMessage(data.error)}
		title={isNetworkError(data.error) ? 'Connection Error' : 'Failed to load wizard'}
		onRetry={handleRetry}
	/>
{:else if data.wizard}
	{#if isPreviewMode}
		<!-- Preview mode - render the wizard shell -->
		<div class="preview-overlay">
			<div class="preview-toolbar">
				<span class="preview-badge">Preview Mode</span>
				<button type="button" class="exit-preview" onclick={handleExitPreview}>Exit Preview</button>
			</div>
			<div class="preview-viewport">
				<div class="preview-frame">
					<WizardShell
						wizard={{ ...data.wizard, steps: previewSteps }}
						onComplete={handlePreviewComplete}
						onCancel={handleExitPreview}
						mode="preview"
					/>
				</div>
			</div>
		</div>
	{:else}
		<!-- Edit mode - render the wizard builder -->
		<WizardBuilder
			wizard={data.wizard}
			onSave={handleSave}
			onCancel={handleCancel}
			onPreview={handlePreview}
		/>
	{/if}
{/if}

<style>
.preview-overlay {
	position: fixed;
	inset: 0;
	z-index: 100;
	display: flex;
	flex-direction: column;
	background: hsl(220 20% 4%);
}

/* Floating pill toolbar at top center */
.preview-toolbar {
	position: relative;
	z-index: 110;
	display: flex;
	align-items: center;
	gap: 0.75rem;
	align-self: center;
	margin-top: 1rem;
	padding: 0.375rem 0.5rem 0.375rem 0.75rem;
	background: hsl(220 15% 10% / 0.9);
	border: 1px solid hsl(220 10% 20%);
	border-radius: 9999px;
	backdrop-filter: blur(12px);
	box-shadow:
		0 4px 16px hsl(0 0% 0% / 0.3),
		0 0 0 1px hsl(220 10% 25% / 0.3) inset;
	flex-shrink: 0;
}

.preview-badge {
	padding: 0.25rem 0.625rem;
	font-size: 0.6875rem;
	font-weight: 600;
	text-transform: uppercase;
	letter-spacing: 0.06em;
	color: hsl(220 20% 4%);
	background: hsl(45 90% 55%);
	border-radius: 9999px;
}

.exit-preview {
	padding: 0.375rem 0.875rem;
	font-size: 0.8125rem;
	font-weight: 500;
	color: hsl(220 10% 70%);
	background: transparent;
	border: 1px solid hsl(220 10% 22%);
	border-radius: 9999px;
	cursor: pointer;
	transition: all 0.15s ease;
}

.exit-preview:hover {
	color: hsl(220 10% 92%);
	background: hsl(220 15% 15%);
	border-color: hsl(220 10% 35%);
}

/* Scrollable viewport that centers the wizard */
.preview-viewport {
	flex: 1;
	overflow-y: auto;
	display: flex;
	justify-content: center;
	align-items: flex-start;
	padding: 2rem 1.5rem 3rem;
}

/* Frame with animated glow border */
.preview-frame {
	position: relative;
	width: 100%;
	max-width: 960px;
	border-radius: 1rem;
	padding: 2px;
	background: linear-gradient(
		135deg,
		hsl(45 90% 55% / 0.15),
		hsl(220 60% 50% / 0.1),
		hsl(45 90% 55% / 0.15)
	);
	background-size: 200% 200%;
	animation: preview-glow 6s ease-in-out infinite;
	box-shadow:
		0 0 40px hsl(45 90% 55% / 0.06),
		0 0 80px hsl(45 90% 55% / 0.03);
}

.preview-frame::before {
	content: "";
	position: absolute;
	inset: 0;
	border-radius: 1rem;
	padding: 2px;
	background: linear-gradient(
		135deg,
		hsl(45 90% 55% / 0.25),
		transparent 40%,
		transparent 60%,
		hsl(45 90% 55% / 0.25)
	);
	background-size: 200% 200%;
	animation: preview-glow 6s ease-in-out infinite reverse;
	mask:
		linear-gradient(#fff 0 0) content-box,
		linear-gradient(#fff 0 0);
	mask-composite: exclude;
	pointer-events: none;
}

@keyframes preview-glow {
	0%,
	100% {
		background-position: 0% 50%;
	}
	50% {
		background-position: 100% 50%;
	}
}

@media (prefers-reduced-motion: reduce) {
	.preview-frame,
	.preview-frame::before {
		animation: none !important;
	}
}
</style>
