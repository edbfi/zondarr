<script lang="ts">
/**
 * Wizard Builder Component
 *
 * Admin interface for creating and editing wizards.
 * Provides wizard metadata form, step list with reorder capability,
 * and simplified step creation (no type selection).
 *
 * @module $lib/components/wizard/wizard-builder
 */

import { GripVertical, Plus, Trash2, Wand2 } from '@lucide/svelte';
import { toast } from 'svelte-sonner';
import type {
	StepInteractionResponse,
	WizardDetailResponse,
	WizardStepResponse
} from '$lib/api/client';
import {
	createStep,
	createWizard,
	deleteStep,
	reorderStep,
	updateStep,
	updateWizard
} from '$lib/api/client';
import ConfirmDialog from '$lib/components/confirm-dialog.svelte';
import { Button } from '$lib/components/ui/button';
import * as Card from '$lib/components/ui/card';
import { Input } from '$lib/components/ui/input';
import { Label } from '$lib/components/ui/label';
import { Switch } from '$lib/components/ui/switch';
import { wizardSchema } from '$lib/schemas/wizard';
import { getInteractionType } from './interactions';
import StepEditor from './step-editor.svelte';

interface Props {
	wizard?: WizardDetailResponse;
	onSave?: (wizard: WizardDetailResponse) => void;
	onCancel?: () => void;
	onPreview?: (currentSteps: WizardStepResponse[]) => void;
}

const { wizard, onSave, onCancel, onPreview }: Props = $props();

// Form state (local copies for editing — intentionally captures initial prop values)
// svelte-ignore state_referenced_locally
let name = $state(wizard?.name ?? '');
// svelte-ignore state_referenced_locally
let description = $state(wizard?.description ?? '');
// svelte-ignore state_referenced_locally
let enabled = $state(wizard?.enabled ?? true);
// svelte-ignore state_referenced_locally
let steps = $state<WizardStepResponse[]>(wizard?.steps ?? []);
let isSaving = $state(false);
let errors = $state<Record<string, string[]>>({});

// Step editing state
let editingStepId = $state<string | null>(null);

// Delete step confirmation state
let showDeleteStepDialog = $state(false);
let deleteTargetStepId = $state<string | null>(null);
let deletingStep = $state(false);

// Drag state for reordering
let draggedStepId = $state<string | null>(null);
let dragOverStepId = $state<string | null>(null);

// Derived values
const isEditing = $derived(!!wizard?.id);
const editingStep = $derived(steps.find((s) => s.id === editingStepId));
const hasChanges = $derived(
	name !== (wizard?.name ?? '') ||
		description !== (wizard?.description ?? '') ||
		enabled !== (wizard?.enabled ?? true)
);

/**
 * Validate wizard form data.
 */
function validateForm(): boolean {
	const result = wizardSchema.safeParse({ name, description, enabled });
	if (!result.success) {
		const fieldErrors: Record<string, string[]> = {};
		for (const issue of result.error.issues) {
			const path = issue.path.join('.');
			if (!fieldErrors[path]) {
				fieldErrors[path] = [];
			}
			fieldErrors[path].push(issue.message);
		}
		errors = fieldErrors;
		return false;
	}
	errors = {};
	return true;
}

/**
 * Save wizard (create or update).
 */
async function handleSave() {
	if (!validateForm()) {
		return;
	}

	isSaving = true;
	try {
		if (isEditing && wizard) {
			// Update existing wizard
			const result = await updateWizard(wizard.id, {
				name: name !== wizard.name ? name : null,
				description: description !== wizard.description ? description : null,
				enabled: enabled !== wizard.enabled ? enabled : null
			});

			if (result.error) {
				throw new Error(result.error.detail ?? 'Failed to update wizard');
			}

			toast.success('Wizard updated successfully');

			// Notify parent with updated wizard
			if (result.data) {
				onSave?.({ ...result.data, steps } as WizardDetailResponse);
			}
		} else {
			// Create new wizard
			const result = await createWizard({ name, description, enabled });

			if (result.error) {
				throw new Error(result.error.detail ?? 'Failed to create wizard');
			}

			toast.success('Wizard created successfully');

			// Notify parent with new wizard
			if (result.data) {
				onSave?.({ ...result.data, steps: [] } as WizardDetailResponse);
			}
		}
	} catch (error) {
		toast.error(error instanceof Error ? error.message : 'Failed to save wizard');
	} finally {
		isSaving = false;
	}
}

/**
 * Add a new step to the wizard — bare step with default title + content.
 */
async function handleAddStep() {
	if (!wizard?.id) {
		toast.error('Please save the wizard first before adding steps');
		return;
	}

	try {
		const result = await createStep(wizard.id, {
			title: 'New Step',
			content_markdown: 'Enter your content here...'
		});

		if (result.error) {
			throw new Error(result.error.detail ?? 'Failed to create step');
		}

		if (result.data) {
			steps = [...steps, result.data];
			editingStepId = result.data.id;
			toast.success('Step added successfully');
		}
	} catch (error) {
		toast.error(error instanceof Error ? error.message : 'Failed to add step');
	}
}

/**
 * Request step deletion (shows confirmation dialog).
 */
function handleDeleteStepRequest(stepId: string) {
	deleteTargetStepId = stepId;
	showDeleteStepDialog = true;
}

/**
 * Delete a step from the wizard after confirmation.
 */
async function handleDeleteStepConfirm() {
	if (!wizard?.id || !deleteTargetStepId) return;

	deletingStep = true;
	try {
		const result = await deleteStep(wizard.id, deleteTargetStepId);

		if (result.error) {
			throw new Error(result.error.detail ?? 'Failed to delete step');
		}

		steps = steps.filter((s) => s.id !== deleteTargetStepId);
		if (editingStepId === deleteTargetStepId) {
			editingStepId = null;
		}
		toast.success('Step deleted successfully');
	} catch (error) {
		toast.error(error instanceof Error ? error.message : 'Failed to delete step');
	} finally {
		deletingStep = false;
		showDeleteStepDialog = false;
		deleteTargetStepId = null;
	}
}

/**
 * Update a step (title + content + translations).
 */
async function handleUpdateStep(stepId: string, updates: Partial<WizardStepResponse>) {
	if (!wizard?.id) return;

	try {
		const result = await updateStep(wizard.id, stepId, {
			title: updates.title ?? null,
			content_markdown: updates.content_markdown ?? null,
			primary_language: updates.primary_language ?? null,
			translations:
				updates.translations?.map((t) => ({
					language_code: t.language_code,
					title: t.title,
					content_markdown: t.content_markdown
				})) ?? null
		});

		if (result.error) {
			throw new Error(result.error.detail ?? 'Failed to update step');
		}

		if (result.data) {
			const updatedStep = result.data;
			steps = steps.map((s) => (s.id === stepId ? updatedStep : s));
			toast.success('Step updated successfully');
		}
	} catch (error) {
		toast.error(error instanceof Error ? error.message : 'Failed to update step');
	}
}

/**
 * Handle interaction changes from step editor.
 */
function handleInteractionsChange(stepId: string, interactions: StepInteractionResponse[]) {
	steps = steps.map((s) => (s.id === stepId ? { ...s, interactions } : s));
}

/**
 * Handle drag start for step reordering.
 */
function handleDragStart(event: DragEvent, stepId: string) {
	draggedStepId = stepId;
	if (event.dataTransfer) {
		event.dataTransfer.effectAllowed = 'move';
		event.dataTransfer.setData('text/plain', stepId);
	}
}

/**
 * Handle drag over for step reordering.
 */
function handleDragOver(event: DragEvent, stepId: string) {
	event.preventDefault();
	if (draggedStepId && draggedStepId !== stepId) {
		dragOverStepId = stepId;
	}
}

/**
 * Handle drag leave.
 */
function handleDragLeave() {
	dragOverStepId = null;
}

/**
 * Handle drop for step reordering.
 */
async function handleDrop(event: DragEvent, targetStepId: string) {
	event.preventDefault();
	dragOverStepId = null;

	if (!wizard?.id || !draggedStepId || draggedStepId === targetStepId) {
		draggedStepId = null;
		return;
	}

	const draggedIndex = steps.findIndex((s) => s.id === draggedStepId);
	const targetIndex = steps.findIndex((s) => s.id === targetStepId);

	if (draggedIndex === -1 || targetIndex === -1) {
		draggedStepId = null;
		return;
	}

	try {
		const result = await reorderStep(wizard.id, draggedStepId, targetIndex);

		if (result.error) {
			throw new Error(result.error.detail ?? 'Failed to reorder step');
		}

		// Reorder locally
		const newSteps = [...steps];
		const [removed] = newSteps.splice(draggedIndex, 1);
		if (removed) {
			newSteps.splice(targetIndex, 0, removed);
		}

		// Update step_order values
		steps = newSteps.map((s, i) => ({ ...s, step_order: i }));
		toast.success('Step reordered successfully');
	} catch (error) {
		toast.error(error instanceof Error ? error.message : 'Failed to reorder step');
	} finally {
		draggedStepId = null;
	}
}

/**
 * Handle drag end.
 */
function handleDragEnd() {
	draggedStepId = null;
	dragOverStepId = null;
}
</script>

<div class="wizard-builder">
	<!-- Header -->
	<div class="builder-header">
		<div class="header-title">
			<Wand2 class="size-6 text-cr-accent" />
			<h2>{isEditing ? 'Edit Wizard' : 'Create Wizard'}</h2>
		</div>
		<div class="header-actions">
			{#if isEditing && steps.length > 0}
				<Button
					variant="outline"
					onclick={() => onPreview?.(steps)}
					class="border-cr-border text-cr-text-muted"
				>
					Preview
				</Button>
			{/if}
			<Button variant="ghost" onclick={onCancel} class="text-cr-text-muted"> Cancel </Button>
			<Button
				onclick={handleSave}
				disabled={isSaving || (!hasChanges && isEditing)}
				class="bg-cr-accent text-cr-bg hover:bg-cr-accent-hover"
			>
				{isSaving ? 'Saving...' : isEditing ? 'Save Changes' : 'Create Wizard'}
			</Button>
		</div>
	</div>

	<div class="builder-content">
		<!-- Wizard Metadata Form -->
		<Card.Root class="border-cr-border bg-cr-surface">
			<Card.Header>
				<Card.Title class="text-cr-text">Wizard Details</Card.Title>
				<Card.Description class="text-cr-text-muted">
					Configure the basic information for this wizard.
				</Card.Description>
			</Card.Header>
			<Card.Content class="space-y-4">
				<!-- Name field -->
				<div class="space-y-2">
					<Label for="wizard-name" class="text-cr-text">Name</Label>
					<Input
						id="wizard-name"
						bind:value={name}
						placeholder="Enter wizard name"
						class="border-cr-border bg-cr-bg text-cr-text"
						aria-invalid={!!errors.name}
					/>
					{#if errors.name}
						<p class="text-sm text-destructive">{errors.name[0]}</p>
					{/if}
				</div>

				<!-- Description field -->
				<div class="space-y-2">
					<Label for="wizard-description" class="text-cr-text">Description</Label>
					<textarea
						id="wizard-description"
						bind:value={description}
						placeholder="Enter wizard description (optional)"
						rows="3"
						class="w-full rounded-md border border-cr-border bg-cr-bg px-3 py-2 text-sm text-cr-text placeholder:text-cr-text-muted focus:border-cr-accent focus:outline-none focus:ring-1 focus:ring-cr-accent"
					></textarea>
					{#if errors.description}
						<p class="text-sm text-destructive">{errors.description[0]}</p>
					{/if}
				</div>

				<!-- Enabled toggle -->
				<div class="flex items-center gap-3">
					<Switch
						id="wizard-enabled"
						checked={enabled}
						onCheckedChange={(checked: boolean) => (enabled = checked)}
					/>
					<Label for="wizard-enabled" class="text-cr-text cursor-pointer">
						Wizard is enabled
					</Label>
				</div>
			</Card.Content>
		</Card.Root>

		<!-- Steps Section -->
		{#if isEditing}
			<Card.Root class="border-cr-border bg-cr-surface">
				<Card.Header>
					<div class="flex items-center justify-between">
						<div>
							<Card.Title class="text-cr-text">Steps</Card.Title>
							<Card.Description class="text-cr-text-muted">
								Drag to reorder steps. Click to edit.
							</Card.Description>
						</div>
						<Button
							variant="outline"
							size="sm"
							onclick={handleAddStep}
							class="border-cr-border text-cr-text-muted hover:text-cr-accent"
						>
							<Plus class="size-4" />
							Add Step
						</Button>
					</div>
				</Card.Header>
				<Card.Content>
					<!-- Step list -->
					{#if steps.length === 0}
						<div class="py-8 text-center text-cr-text-muted">
							<p>No steps yet. Add your first step to get started.</p>
						</div>
					{:else}
						<div class="space-y-2">
							{#each steps as step, index (step.id)}
								<!-- biome-ignore lint/a11y/useSemanticElements: The drag-sort container keeps list semantics and its existing grid layout. -->
								<div
									class="step-item"
									class:dragging={draggedStepId === step.id}
									class:drag-over={dragOverStepId === step.id}
									class:editing={editingStepId === step.id}
									draggable="true"
									ondragstart={(e) => handleDragStart(e, step.id)}
									ondragover={(e) => handleDragOver(e, step.id)}
									ondragleave={handleDragLeave}
									ondrop={(e) => handleDrop(e, step.id)}
									ondragend={handleDragEnd}
									role="listitem"
								>
									<div class="step-drag-handle">
										<GripVertical class="size-4 text-cr-text-muted" />
									</div>
									<div class="step-info">
										<span class="step-order">{index + 1}</span>
										<div class="step-badges">
											{#if step.interactions.length > 0}
												{#each step.interactions as interaction}
													{@const reg = getInteractionType(interaction.interaction_type)}
													{#if reg}
														<span class="interaction-badge">{reg.label}</span>
													{/if}
												{/each}
											{:else}
												<span class="interaction-badge empty">Content only</span>
											{/if}
										</div>
										<span class="step-title">{step.title}</span>
									</div>
									<div class="step-actions">
										<Button
											variant="ghost"
											size="sm"
											onclick={() => (editingStepId = editingStepId === step.id ? null : step.id)}
											class="text-cr-text-muted hover:text-cr-accent"
										>
											{editingStepId === step.id ? 'Close' : 'Edit'}
										</Button>
										<Button
											variant="ghost"
											size="sm"
											onclick={() => handleDeleteStepRequest(step.id)}
											class="text-cr-text-muted hover:text-destructive"
										>
											<Trash2 class="size-4" />
										</Button>
									</div>
								</div>

								<!-- Step editor (expanded) -->
								{#if editingStepId === step.id && wizard}
									<div class="step-editor-container">
										<StepEditor
											{step}
											wizardId={wizard.id}
											onSave={(updates) => handleUpdateStep(step.id, updates)}
											onCancel={() => (editingStepId = null)}
											onInteractionsChange={(interactions) =>
												handleInteractionsChange(step.id, interactions)}
										/>
									</div>
								{/if}
							{/each}
						</div>
					{/if}
				</Card.Content>
			</Card.Root>
		{:else}
			<Card.Root class="border-cr-border bg-cr-surface">
				<Card.Content class="py-8 text-center text-cr-text-muted">
					<p>Save the wizard first to add steps.</p>
				</Card.Content>
			</Card.Root>
		{/if}
	</div>
</div>

<ConfirmDialog
	open={showDeleteStepDialog}
	title="Delete Step"
	description="Are you sure you want to delete this step? The step and all its interactions will be permanently removed."
	confirmLabel={deletingStep ? 'Deleting...' : 'Delete'}
	variant="destructive"
	loading={deletingStep}
	onConfirm={handleDeleteStepConfirm}
	onCancel={() => {
		showDeleteStepDialog = false;
		deleteTargetStepId = null;
	}}
/>

<style>
.wizard-builder {
	display: flex;
	flex-direction: column;
	gap: 1.5rem;
}

.builder-header {
	display: flex;
	flex-wrap: wrap;
	align-items: center;
	justify-content: space-between;
	gap: 1rem;
}

.header-title {
	display: flex;
	align-items: center;
	gap: 0.75rem;
}

.header-title h2 {
	font-size: 1.5rem;
	font-weight: 600;
	color: var(--cr-text);
	margin: 0;
}

.header-actions {
	display: flex;
	align-items: center;
	gap: 0.5rem;
}

.builder-content {
	display: flex;
	flex-direction: column;
	gap: 1.5rem;
}

/* Step item styles */
.step-item {
	display: flex;
	align-items: center;
	gap: 0.75rem;
	padding: 0.75rem 1rem;
	background: var(--cr-bg);
	border: 1px solid var(--cr-border);
	border-radius: 0.5rem;
	cursor: grab;
	transition: all 0.2s ease;
}

.step-item:hover {
	border-color: var(--cr-accent);
}

.step-item.dragging {
	opacity: 0.5;
	cursor: grabbing;
}

.step-item.drag-over {
	border-color: var(--cr-accent);
	background: var(--cr-accent-highlight);
}

.step-item.editing {
	border-color: var(--cr-accent);
	background: var(--cr-accent-highlight);
}

.step-drag-handle {
	cursor: grab;
	padding: 0.25rem;
}

.step-info {
	flex: 1;
	display: flex;
	align-items: center;
	gap: 0.75rem;
	min-width: 0;
}

.step-order {
	flex-shrink: 0;
	width: 1.5rem;
	height: 1.5rem;
	display: flex;
	align-items: center;
	justify-content: center;
	font-size: 0.75rem;
	font-weight: 600;
	color: var(--cr-bg);
	background: var(--cr-accent);
	border-radius: 50%;
}

.step-badges {
	display: flex;
	flex-wrap: wrap;
	gap: 0.25rem;
	flex-shrink: 0;
}

.interaction-badge {
	font-size: 0.6875rem;
	font-weight: 500;
	padding: 0.125rem 0.5rem;
	border-radius: 9999px;
	color: var(--cr-badge-text);
	background: var(--cr-badge-bg);
	border: 1px solid var(--cr-badge-border);
	white-space: nowrap;
}

.interaction-badge.empty {
	font-style: italic;
	color: var(--cr-badge-muted-text);
	background: var(--cr-badge-muted-bg);
	border-color: var(--cr-badge-muted-border);
}

.step-title {
	flex: 1;
	font-size: 0.875rem;
	color: var(--cr-text);
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}

.step-actions {
	display: flex;
	align-items: center;
	gap: 0.25rem;
}

.step-editor-container {
	margin-top: 0.5rem;
	margin-bottom: 0.5rem;
	padding: 1rem;
	background: var(--cr-bg);
	border: 1px solid var(--cr-border);
	border-radius: 0.5rem;
}
</style>
