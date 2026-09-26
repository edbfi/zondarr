<script lang="ts">
/**
 * Invitation detail page.
 *
 * Displays invitation details with:
 * - Immutable fields as read-only (code, use_count, created_at, created_by)
 * - Edit form for mutable fields
 * - Delete button with confirmation dialog
 * - Target servers and allowed libraries display
 * - Associated wizards display and selection
 *
 * @module routes/(admin)/invitations/[id]/+page
 */

import {
	ArrowLeft,
	Calendar,
	Check,
	Copy,
	ExternalLink,
	Hash,
	Save,
	Server,
	Timer,
	Trash2,
	Users,
	Wand2
} from '@lucide/svelte';
import { onDestroy } from 'svelte';
import { goto, invalidateAll } from '$app/navigation';
import {
	deleteInvitation,
	type InvitationDetailResponse,
	type MediaServerWithLibrariesResponse,
	updateInvitation,
	type WizardResponse,
	withErrorHandling
} from '$lib/api/client';
import { ApiError, asErrorResponse, getErrorMessage } from '$lib/api/errors';
import ConfirmDialog from '$lib/components/confirm-dialog.svelte';
import ErrorState from '$lib/components/error-state.svelte';
import StatusBadge, { type StatusBadgeStatus } from '$lib/components/status-badge.svelte';
import { Button } from '$lib/components/ui/button';
import * as Card from '$lib/components/ui/card';
import { Input } from '$lib/components/ui/input';
import { Label } from '$lib/components/ui/label';
import {
	transformUpdateFormData,
	type UpdateInvitationInput,
	updateInvitationSchema
} from '$lib/schemas/invitation';
import { showError, showSuccess } from '$lib/utils/toast';
import type { PageData } from './$types';

const { data }: { data: PageData } = $props();

// Derive initial form values from data (reactive to data changes)
const initialFormData = $derived<UpdateInvitationInput>({
	expires_at: data.invitation?.expires_at ?? '',
	max_uses: data.invitation?.max_uses ?? undefined,
	duration_days: data.invitation?.duration_days ?? undefined,
	enabled: data.invitation?.enabled ?? true,
	server_ids: data.invitation?.target_servers.map((s) => s.id) ?? [],
	library_ids: data.invitation?.allowed_libraries.map((l) => l.id) ?? [],
	pre_wizard_id: data.invitation?.pre_wizard?.id ?? '',
	post_wizard_id: data.invitation?.post_wizard?.id ?? ''
});

// Form state for mutable fields (user-editable copy)
const formData = $state<UpdateInvitationInput>({
	expires_at: '',
	max_uses: undefined,
	duration_days: undefined,
	enabled: true,
	server_ids: [],
	library_ids: [],
	pre_wizard_id: '',
	post_wizard_id: ''
});

// Cannot use $derived — formData must be independently mutable for user edits.
// This $effect resets the form when server data changes (e.g., after save + invalidateAll).
$effect(() => {
	formData.expires_at = initialFormData.expires_at
		? toISOString(initialFormData.expires_at)
		: initialFormData.expires_at;
	formData.max_uses = initialFormData.max_uses;
	formData.duration_days = initialFormData.duration_days;
	formData.enabled = initialFormData.enabled;
	formData.server_ids = [...(initialFormData.server_ids ?? [])];
	formData.library_ids = [...(initialFormData.library_ids ?? [])];
	formData.pre_wizard_id = initialFormData.pre_wizard_id;
	formData.post_wizard_id = initialFormData.post_wizard_id;
});

// Validation errors
let errors = $state<Record<string, string[]>>({});

// Loading states
let saving = $state(false);
let deleting = $state(false);

// Delete confirmation dialog
let showDeleteDialog = $state(false);

// Copy link state
let copied = $state(false);
let copiedTimeoutId: ReturnType<typeof setTimeout> | null = null;

onDestroy(() => {
	if (copiedTimeoutId) clearTimeout(copiedTimeoutId);
});

/**
 * Copy the invite link to clipboard.
 */
async function copyInviteLink() {
	if (!data.invitation) return;
	const url = `${window.location.origin}/join/${data.invitation.code}`;
	try {
		await navigator.clipboard.writeText(url);
		copied = true;
		showSuccess('Invite link copied');
		if (copiedTimeoutId) clearTimeout(copiedTimeoutId);
		copiedTimeoutId = setTimeout(() => {
			copied = false;
		}, 2000);
	} catch {
		showError('Failed to copy invite link');
	}
}

function toLocalDateTimeString(date: Date): string {
	const year = date.getFullYear();
	const month = String(date.getMonth() + 1).padStart(2, '0');
	const day = String(date.getDate()).padStart(2, '0');
	const hours = String(date.getHours()).padStart(2, '0');
	const minutes = String(date.getMinutes()).padStart(2, '0');
	return `${year}-${month}-${day}T${hours}:${minutes}`;
}

// Compute minimum datetime for expiration input (current time, local timezone)
const minDateTime = $derived(toLocalDateTimeString(new Date()));

// Derive local datetime value from initial data
const initialExpiresAtLocal = $derived(formatDateTimeLocal(data.invitation?.expires_at));

// Local state for datetime-local input
let expiresAtLocal = $state('');

// Cannot use $derived — expiresAtLocal is user-editable via the datetime-local input.
// This $effect resets it when server data changes (e.g., after save + invalidateAll).
$effect(() => {
	expiresAtLocal = initialExpiresAtLocal;
});

// "Used up" beats the generic "Expired" so admins see the specific reason
// redemption is blocked.
const isUsedUp = $derived(
	data.invitation != null &&
		data.invitation.max_uses != null &&
		data.invitation.remaining_uses != null &&
		data.invitation.remaining_uses <= 0
);

// Derive status for badge.
// Date-expiry is delegated to the server via `is_active` to avoid
// client-clock-skew false positives.
const status = $derived.by((): StatusBadgeStatus => {
	const inv = data.invitation;
	if (!inv) return 'disabled';
	if (!inv.enabled) return 'disabled';
	if (isUsedUp) return 'expired';
	if (!inv.is_active) return 'expired';
	if (inv.remaining_uses !== null && inv.remaining_uses !== undefined && inv.remaining_uses <= 3) {
		return 'limited';
	}
	return 'active';
});

// Derive status label
const statusLabel = $derived.by(() => {
	const inv = data.invitation;
	if (!inv) return 'Unknown';
	if (!inv.enabled) return 'Disabled';
	if (isUsedUp) return 'Used up';
	if (!inv.is_active) return 'Expired';
	if (inv.remaining_uses !== null && inv.remaining_uses !== undefined && inv.remaining_uses <= 3) {
		return 'Limited';
	}
	return 'Active';
});

// Derive available libraries based on selected servers
const availableLibraries = $derived.by(() => {
	const selectedServerIds = formData.server_ids ?? [];
	if (selectedServerIds.length === 0) return [];

	const libraries: { id: string; name: string }[] = [];
	for (const server of data.servers) {
		if (selectedServerIds.includes(server.id)) {
			libraries.push(...server.libraries);
		}
	}
	return libraries;
});

/**
 * Format datetime-local input value from ISO string.
 */
function formatDateTimeLocal(isoString: string | undefined | null): string {
	if (!isoString) return '';
	try {
		const date = new Date(isoString);
		return toLocalDateTimeString(date);
	} catch {
		return '';
	}
}

/**
 * Convert datetime-local value to ISO string.
 */
function toISOString(dateTimeLocal: string): string {
	if (!dateTimeLocal) return '';
	try {
		return new Date(dateTimeLocal).toISOString();
	} catch {
		return '';
	}
}

/**
 * Format date for display.
 */
function formatDate(dateString: string | null | undefined): string {
	if (!dateString) return '—';
	try {
		const date = new Date(dateString);
		return date.toLocaleDateString('en-US', {
			month: 'short',
			day: 'numeric',
			year: 'numeric',
			hour: '2-digit',
			minute: '2-digit'
		});
	} catch {
		return '—';
	}
}

/**
 * Toggle server selection.
 */
function toggleServer(serverId: string) {
	const current = formData.server_ids ?? [];
	if (current.includes(serverId)) {
		formData.server_ids = current.filter((id: string) => id !== serverId);
		// Also remove libraries from this server
		const serverLibraryIds =
			data.servers.find((s) => s.id === serverId)?.libraries.map((l) => l.id) ?? [];
		formData.library_ids = (formData.library_ids ?? []).filter(
			(id: string) => !serverLibraryIds.includes(id)
		);
	} else {
		formData.server_ids = [...current, serverId];
	}
}

/**
 * Toggle library selection.
 */
function toggleLibrary(libraryId: string) {
	const current = formData.library_ids ?? [];
	if (current.includes(libraryId)) {
		formData.library_ids = current.filter((id: string) => id !== libraryId);
	} else {
		formData.library_ids = [...current, libraryId];
	}
}

/**
 * Check if a server is selected.
 */
function isServerSelected(serverId: string): boolean {
	return (formData.server_ids ?? []).includes(serverId);
}

/**
 * Check if a library is selected.
 */
function isLibrarySelected(libraryId: string): boolean {
	return (formData.library_ids ?? []).includes(libraryId);
}

/**
 * Validate form data.
 */
function validateForm(): boolean {
	const result = updateInvitationSchema.safeParse(formData);
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
 * Handle save changes.
 */
async function handleSave() {
	if (!data.invitation || !validateForm()) return;
	const invitationId = data.invitation.id;

	saving = true;
	try {
		const updateData = transformUpdateFormData(formData);
		const result = await withErrorHandling(() => updateInvitation(invitationId, updateData), {
			showErrorToast: false
		});

		if (result.error) {
			const errorBody = asErrorResponse(result.error);
			showError('Failed to update invitation', errorBody?.detail ?? 'An error occurred');
			return;
		}

		// Update data.invitation immediately from API response so $derived
		// status/statusLabel react before invalidateAll() resolves.
		if (result.data) {
			data.invitation = result.data as InvitationDetailResponse;
		}

		showSuccess('Invitation updated successfully');
		await invalidateAll();
	} finally {
		saving = false;
	}
}

/**
 * Handle delete confirmation.
 */
async function handleDelete() {
	if (!data.invitation) return;
	const invitationId = data.invitation.id;

	deleting = true;
	try {
		const result = await withErrorHandling(() => deleteInvitation(invitationId), {
			showErrorToast: false
		});

		if (result.error) {
			const errorBody = asErrorResponse(result.error);
			showError('Failed to delete invitation', errorBody?.detail ?? 'An error occurred');
			return;
		}

		showSuccess('Invitation deleted successfully');
		goto('/invitations');
	} finally {
		deleting = false;
		showDeleteDialog = false;
	}
}

/**
 * Handle retry after error.
 */
async function handleRetry() {
	await invalidateAll();
}

/**
 * Get error messages for a field.
 */
function getFieldErrors(field: string): string[] {
	return errors[field] ?? [];
}
</script>

<div class="space-y-6">
	<!-- Back button and header -->
	<div class="flex items-center gap-4">
		<Button
			variant="ghost"
			size="icon"
			onclick={() => goto('/invitations')}
			class="text-cr-text-muted hover:text-cr-text"
			aria-label="Back to invitations"
		>
			<ArrowLeft class="size-5" />
		</Button>
		<div class="flex-1">
			<h1 class="text-xl font-semibold text-cr-text">Invitation Details</h1>
			{#if data.invitation}
				<p class="text-cr-text-muted">
					Code: <code class="font-mono text-cr-accent">{data.invitation.code}</code>
				</p>
			{/if}
		</div>
		{#if data.invitation}
			<Button
				variant="outline"
				size="sm"
				onclick={copyInviteLink}
				class="border-cr-border text-cr-text-muted hover:text-cr-accent hover:border-cr-accent/50"
			>
				{#if copied}
					<Check class="size-4" />
					Copied!
				{:else}
					<Copy class="size-4" />
					Copy Invite Link
				{/if}
			</Button>
			<StatusBadge {status} label={statusLabel} />
		{/if}
	</div>

	{#if data.error}
		<ErrorState
			message={getErrorMessage(data.error)}
			title="Failed to load invitation"
			onRetry={handleRetry}
		/>
	{:else if data.invitation}
		<div class="grid gap-6 lg:grid-cols-2">
			<!-- Immutable Fields Card -->
			<Card.Root class="border-cr-border bg-cr-surface">
				<Card.Header>
					<Card.Title class="text-cr-text">Invitation Information</Card.Title>
					<Card.Description class="text-cr-text-muted">
						These fields cannot be modified after creation.
					</Card.Description>
				</Card.Header>
				<Card.Content class="space-y-4">
					<!-- Code (Immutable) -->
					<div class="space-y-1" data-field-readonly="code">
						<Label class="text-cr-text-muted text-xs uppercase tracking-wide">Code</Label>
						<div class="font-mono text-lg text-cr-accent bg-cr-accent/10 px-3 py-2 rounded">
							{data.invitation.code}
						</div>
					</div>

					<!-- Use Count (Immutable) -->
					<div class="space-y-1" data-field-readonly="use_count">
						<Label class="text-cr-text-muted text-xs uppercase tracking-wide">Use Count</Label>
						<div class="text-cr-text font-data">
							{data.invitation.use_count}
							{#if data.invitation.max_uses}
								<span class="text-cr-text-muted">/ {data.invitation.max_uses}</span>
							{/if}
							{#if data.invitation.remaining_uses !== null && data.invitation.remaining_uses !== undefined}
								<span class="text-cr-text-muted text-sm ml-2"
									>({data.invitation.remaining_uses}
									remaining)</span
								>
							{/if}
						</div>
					</div>

					<!-- Created At (Immutable) -->
					<div class="space-y-1" data-field-readonly="created_at">
						<Label class="text-cr-text-muted text-xs uppercase tracking-wide">Created</Label>
						<div class="text-cr-text font-data">{formatDate(data.invitation.created_at)}</div>
					</div>

					<!-- Created By (Immutable) -->
					{#if data.invitation.created_by}
						<div class="space-y-1" data-field-readonly="created_by">
							<Label class="text-cr-text-muted text-xs uppercase tracking-wide">Created By</Label>
							<div class="text-cr-text font-mono text-sm">{data.invitation.created_by}</div>
						</div>
					{/if}

					<!-- Updated At -->
					{#if data.invitation.updated_at}
						<div class="space-y-1">
							<Label class="text-cr-text-muted text-xs uppercase tracking-wide">Last Updated</Label>
							<div class="text-cr-text font-data">{formatDate(data.invitation.updated_at)}</div>
						</div>
					{/if}
				</Card.Content>
			</Card.Root>

			<!-- Target Servers Card -->
			<Card.Root class="border-cr-border bg-cr-surface">
				<Card.Header>
					<Card.Title class="text-cr-text">Target Servers</Card.Title>
					<Card.Description class="text-cr-text-muted">
						Servers this invitation grants access to.
					</Card.Description>
				</Card.Header>
				<Card.Content>
					<div class="space-y-2">
						{#each data.invitation.target_servers as server (server.id)}
							<div class="flex items-center gap-3 rounded-lg border border-cr-border bg-cr-bg p-3">
								<Server class="size-5 text-cr-accent" />
								<div class="flex-1">
									<div class="font-medium text-cr-text">{server.name}</div>
									<div class="text-xs text-cr-text-muted">{server.server_type} · {server.url}</div>
								</div>
							</div>
						{/each}
						{#if data.invitation.target_servers.length === 0}
							<p class="text-cr-text-muted text-sm">No target servers configured.</p>
						{/if}
					</div>
				</Card.Content>
			</Card.Root>

			<!-- Allowed Libraries Card -->
			{#if data.invitation.allowed_libraries.length > 0}
				<Card.Root class="border-cr-border bg-cr-surface">
					<Card.Header>
						<Card.Title class="text-cr-text">Allowed Libraries</Card.Title>
						<Card.Description class="text-cr-text-muted">
							Specific libraries users will have access to.
						</Card.Description>
					</Card.Header>
					<Card.Content>
						<div class="flex flex-wrap gap-2">
							{#each data.invitation.allowed_libraries as library (library.id)}
								<span
									class="rounded-full border border-cr-border bg-cr-bg px-3 py-1 text-sm text-cr-text"
								>
									{library.name}
								</span>
							{/each}
						</div>
					</Card.Content>
				</Card.Root>
			{/if}

			<!-- Onboarding Wizards Card -->
			{#if data.invitation.pre_wizard || data.invitation.post_wizard}
				<Card.Root class="border-cr-border bg-cr-surface">
					<Card.Header>
						<Card.Title class="text-cr-text flex items-center gap-2">
							<Wand2 class="size-5 text-cr-accent" />
							Onboarding Wizards
						</Card.Title>
						<Card.Description class="text-cr-text-muted">
							Wizard flows users must complete during invitation redemption.
						</Card.Description>
					</Card.Header>
					<Card.Content class="space-y-4">
						{#if data.invitation.pre_wizard}
							<div class="space-y-1">
								<Label class="text-cr-text-muted text-xs uppercase tracking-wide"
									>Pre-Registration</Label
								>
								<div
									class="flex items-center justify-between rounded-lg border border-cr-border bg-cr-bg p-3"
								>
									<div>
										<div class="font-medium text-cr-text">{data.invitation.pre_wizard.name}</div>
										{#if data.invitation.pre_wizard.description}
											<div class="text-xs text-cr-text-muted">
												{data.invitation.pre_wizard.description}
											</div>
										{/if}
									</div>
									<Button
										variant="ghost"
										size="sm"
										onclick={() => goto(`/wizards/${data.invitation?.pre_wizard?.id}`)}
										class="text-cr-text-muted hover:text-cr-accent"
									>
										<ExternalLink class="size-4" />
									</Button>
								</div>
							</div>
						{/if}
						{#if data.invitation.post_wizard}
							<div class="space-y-1">
								<Label class="text-cr-text-muted text-xs uppercase tracking-wide"
									>Post-Registration</Label
								>
								<div
									class="flex items-center justify-between rounded-lg border border-cr-border bg-cr-bg p-3"
								>
									<div>
										<div class="font-medium text-cr-text">{data.invitation.post_wizard.name}</div>
										{#if data.invitation.post_wizard.description}
											<div class="text-xs text-cr-text-muted">
												{data.invitation.post_wizard.description}
											</div>
										{/if}
									</div>
									<Button
										variant="ghost"
										size="sm"
										onclick={() => goto(`/wizards/${data.invitation?.post_wizard?.id}`)}
										class="text-cr-text-muted hover:text-cr-accent"
									>
										<ExternalLink class="size-4" />
									</Button>
								</div>
							</div>
						{/if}
					</Card.Content>
				</Card.Root>
			{/if}

			<!-- Edit Form Card -->
			<Card.Root class="border-cr-border bg-cr-surface lg:col-span-2">
				<Card.Header>
					<Card.Title class="text-cr-text">Edit Settings</Card.Title>
					<Card.Description class="text-cr-text-muted">
						Modify invitation settings. Changes take effect immediately.
					</Card.Description>
				</Card.Header>
				<Card.Content>
					<form
						onsubmit={(e) => {
	e.preventDefault();
	handleSave();
}}
						class="space-y-6"
					>
						<!-- Enabled Toggle -->
						<div class="space-y-2">
							<div class="flex items-center gap-3">
								<button
									type="button"
									role="switch"
									aria-checked={formData.enabled ?? true}
									aria-label="Toggle invitation enabled status"
									onclick={() => {
	formData.enabled = !(formData.enabled ?? true);
}}
									class="relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cr-accent focus-visible:ring-offset-2 {(formData.enabled ?? true) ? 'bg-cr-accent' : 'bg-cr-border'}"
									data-field-enabled
								>
									<span
										class="pointer-events-none inline-block size-5 transform rounded-full bg-white shadow-lg ring-0 transition-transform {(formData.enabled ?? true) ? 'translate-x-5' : 'translate-x-0'}"
									></span>
								</button>
								<Label class="text-cr-text cursor-pointer">
									{(formData.enabled ?? true) ? 'Enabled' : 'Disabled'}
								</Label>
							</div>
							<p class="text-cr-text-muted text-xs">Disabled invitations cannot be redeemed</p>
						</div>

						<div class="grid gap-6 sm:grid-cols-2">
							<!-- Expiration Date -->
							<div class="space-y-2">
								<Label class="text-cr-text flex items-center gap-2">
									<Calendar class="size-4 text-cr-accent" />
									Expiration Date
								</Label>
								<Input
									type="datetime-local"
									bind:value={expiresAtLocal}
									oninput={(e) => {
	const value = e.currentTarget.value;
	formData.expires_at = value ? toISOString(value) : '';
}}
									min={minDateTime}
									class="border-cr-border bg-cr-bg text-cr-text"
									data-field-expires-at
								/>
								{#if getFieldErrors('expires_at').length > 0}
									<div class="text-rose-400 text-sm">
										{#each getFieldErrors('expires_at') as error}
											<p>{error}</p>
										{/each}
									</div>
								{/if}
							</div>

							<!-- Max Uses -->
							<div class="space-y-2">
								<Label class="text-cr-text flex items-center gap-2">
									<Users class="size-4 text-cr-accent" />
									Maximum Uses
								</Label>
								<Input
									type="number"
									bind:value={formData.max_uses}
									oninput={(e) => {
	if (e.currentTarget.value === '') formData.max_uses = '';
}}
									placeholder="Unlimited"
									class="border-cr-border bg-cr-bg text-cr-text placeholder:text-cr-text-muted"
									min={1}
									data-field-max-uses
								/>
								{#if getFieldErrors('max_uses').length > 0}
									<div class="text-rose-400 text-sm">
										{#each getFieldErrors('max_uses') as error}
											<p>{error}</p>
										{/each}
									</div>
								{/if}
							</div>

							<!-- Duration Days -->
							<div class="space-y-2">
								<Label class="text-cr-text flex items-center gap-2">
									<Timer class="size-4 text-cr-accent" />
									Access Duration (days)
								</Label>
								<Input
									type="number"
									bind:value={formData.duration_days}
									oninput={(e) => {
	if (e.currentTarget.value === '') formData.duration_days = '';
}}
									placeholder="Permanent"
									class="border-cr-border bg-cr-bg text-cr-text placeholder:text-cr-text-muted"
									min={1}
									data-field-duration-days
								/>
								<p class="text-cr-text-muted text-xs">
									How long users will have access after redeeming
								</p>
								{#if getFieldErrors('duration_days').length > 0}
									<div class="text-rose-400 text-sm">
										{#each getFieldErrors('duration_days') as error}
											<p>{error}</p>
										{/each}
									</div>
								{/if}
							</div>
						</div>

						<!-- Target Servers Selection -->
						<div class="space-y-2">
							<Label class="text-cr-text flex items-center gap-2">
								<Server class="size-4 text-cr-accent" />
								Target Servers
							</Label>
							<!-- biome-ignore lint/a11y/useSemanticElements: This ARIA group labels existing controls without introducing native fieldset layout. -->
							<div
								class="grid gap-2 sm:grid-cols-2 rounded-lg transition-shadow {getFieldErrors('server_ids').length > 0 ? 'ring-2 ring-rose-500/50 p-1' : ''}"
								role="group"
								aria-label="Select target servers"
							>
								{#each data.servers as server (server.id)}
									<button
										type="button"
										onclick={() => toggleServer(server.id)}
										class="flex items-center gap-3 rounded-lg border p-3 text-left transition-colors {isServerSelected(server.id)
	? 'border-cr-accent bg-cr-accent/10 text-cr-text'
	: 'border-cr-border bg-cr-bg text-cr-text-muted hover:border-cr-accent/50'}"
										aria-pressed={isServerSelected(server.id)}
									>
										<div
											class="flex size-5 items-center justify-center rounded border {isServerSelected(server.id) ? 'border-cr-accent bg-cr-accent' : 'border-cr-border'}"
										>
											{#if isServerSelected(server.id)}
												<svg
													class="size-3 text-cr-bg"
													fill="none"
													viewBox="0 0 24 24"
													stroke="currentColor"
													aria-hidden="true"
												>
													<path
														stroke-linecap="round"
														stroke-linejoin="round"
														stroke-width="3"
														d="M5 13l4 4L19 7"
													/>
												</svg>
											{/if}
										</div>
										<div class="flex-1">
											<div class="font-medium">{server.name}</div>
											<div class="text-xs text-cr-text-muted">{server.server_type}</div>
										</div>
									</button>
								{/each}
							</div>
							{#if getFieldErrors('server_ids').length > 0}
								<div class="text-rose-400 text-sm">
									{#each getFieldErrors('server_ids') as error}
										<p>{error}</p>
									{/each}
								</div>
							{/if}
						</div>

						<!-- Allowed Libraries Selection -->
						{#if availableLibraries.length > 0}
							<div class="space-y-2">
								<Label class="text-cr-text">
									Allowed Libraries
									<span class="text-cr-text-muted text-xs ml-2"
										>(optional - all if none selected)</span
									>
								</Label>
								<div class="flex flex-wrap gap-2">
									{#each availableLibraries as library (library.id)}
										<button
											type="button"
											onclick={() => toggleLibrary(library.id)}
											class="rounded-full border px-3 py-1 text-sm transition-colors {isLibrarySelected(library.id)
	? 'border-cr-accent bg-cr-accent/10 text-cr-text'
	: 'border-cr-border bg-cr-bg text-cr-text-muted hover:border-cr-accent/50'}"
											aria-pressed={isLibrarySelected(library.id)}
										>
											{library.name}
										</button>
									{/each}
								</div>
							</div>
						{/if}

						<!-- Wizard Selection Section -->
						{#if data.wizards.length > 0}
							<div class="space-y-4 pt-4 border-t border-cr-border">
								<div class="flex items-center gap-2">
									<Wand2 class="size-4 text-cr-accent" />
									<span class="text-cr-text font-medium">Onboarding Wizards</span>
									<span class="text-cr-text-muted text-xs">(optional)</span>
								</div>

								<div class="grid gap-4 sm:grid-cols-2">
									<!-- Pre-Registration Wizard -->
									<div class="space-y-2">
										<Label class="text-cr-text text-sm"> Pre-Registration Wizard </Label>
										<select
											bind:value={formData.pre_wizard_id}
											class="w-full rounded-md border border-cr-border bg-cr-bg px-3 py-2 text-cr-text text-sm focus:outline-none focus:ring-2 focus:ring-cr-accent focus:ring-offset-2 focus:ring-offset-cr-bg"
											data-field-pre-wizard
										>
											<option value="">None</option>
											{#each data.wizards as wizard (wizard.id)}
												<option value={wizard.id}>{wizard.name}</option>
											{/each}
										</select>
										<p class="text-cr-text-muted text-xs">Runs before account creation</p>
										{#if getFieldErrors('pre_wizard_id').length > 0}
											<div class="text-rose-400 text-sm">
												{#each getFieldErrors('pre_wizard_id') as error}
													<p>{error}</p>
												{/each}
											</div>
										{/if}
									</div>

									<!-- Post-Registration Wizard -->
									<div class="space-y-2">
										<Label class="text-cr-text text-sm"> Post-Registration Wizard </Label>
										<select
											bind:value={formData.post_wizard_id}
											class="w-full rounded-md border border-cr-border bg-cr-bg px-3 py-2 text-cr-text text-sm focus:outline-none focus:ring-2 focus:ring-cr-accent focus:ring-offset-2 focus:ring-offset-cr-bg"
											data-field-post-wizard
										>
											<option value="">None</option>
											{#each data.wizards as wizard (wizard.id)}
												<option value={wizard.id}>{wizard.name}</option>
											{/each}
										</select>
										<p class="text-cr-text-muted text-xs">Runs after account creation</p>
										{#if getFieldErrors('post_wizard_id').length > 0}
											<div class="text-rose-400 text-sm">
												{#each getFieldErrors('post_wizard_id') as error}
													<p>{error}</p>
												{/each}
											</div>
										{/if}
									</div>
								</div>
							</div>
						{/if}

						<!-- Form Actions -->
						<div class="flex items-center justify-between pt-4 border-t border-cr-border">
							<Button
								type="button"
								variant="outline"
								onclick={() => (showDeleteDialog = true)}
								disabled={saving || deleting}
								class="border-rose-500/50 text-rose-400 hover:bg-rose-500/10 hover:border-rose-500"
							>
								<Trash2 class="size-4" />
								Delete Invitation
							</Button>
							<Button
								type="submit"
								disabled={saving || deleting}
								class="bg-cr-accent text-cr-bg hover:bg-cr-accent-hover"
							>
								{#if saving}
									<span
										class="size-4 animate-spin rounded-full border-2 border-current border-t-transparent"
									></span>
								{:else}
									<Save class="size-4" />
								{/if}
								Save Changes
							</Button>
						</div>
					</form>
				</Card.Content>
			</Card.Root>
		</div>
	{/if}
</div>

<!-- Delete Confirmation Dialog -->
<ConfirmDialog
	bind:open={showDeleteDialog}
	title="Delete Invitation"
	description="Are you sure you want to delete this invitation? This action cannot be undone. Users who have already redeemed this invitation will not be affected."
	confirmLabel="Delete"
	variant="destructive"
	loading={deleting}
	onConfirm={handleDelete}
	onCancel={() => (showDeleteDialog = false)}
/>
