<script lang="ts">
/**
 * Simple invitation form component.
 *
 * Provides a form for creating or editing invitations with:
 * - Server multi-select for target servers
 * - Library multi-select (filtered by selected servers)
 * - Wizard selection for pre/post registration flows
 * - Optional fields: code, expires_at, max_uses, duration_days
 * - Inline validation errors
 *
 * Uses direct state binding instead of Superforms for simpler SPA usage.
 *
 * @module $lib/components/invitations/invitation-form-simple
 */

import { Calendar, Hash, Server, Timer, Users, Wand2 } from '@lucide/svelte';
import type {
	LibraryResponse,
	MediaServerWithLibrariesResponse,
	WizardResponse
} from '$lib/api/client';
import { Button } from '$lib/components/ui/button';
import { Input } from '$lib/components/ui/input';
import { Label } from '$lib/components/ui/label';
import type { CreateInvitationInput, UpdateInvitationInput } from '$lib/schemas/invitation';

type FormData = CreateInvitationInput | UpdateInvitationInput;

interface Props {
	formData: FormData;
	errors: Record<string, string[]>;
	servers: MediaServerWithLibrariesResponse[];
	wizards?: WizardResponse[];
	loadingWizards?: boolean;
	mode: 'create' | 'edit';
	submitting?: boolean;
	onSubmit: () => void;
	onCancel?: () => void;
}

let {
	formData = $bindable(),
	errors,
	servers,
	wizards = [],
	loadingWizards = false,
	mode,
	submitting = false,
	onSubmit,
	onCancel
}: Props = $props();

// Derive available libraries based on selected servers
const availableLibraries = $derived.by(() => {
	const selectedServerIds = formData.server_ids ?? [];
	if (selectedServerIds.length === 0) return [];

	const libraries: LibraryResponse[] = [];
	for (const server of servers) {
		if (selectedServerIds.includes(server.id)) {
			libraries.push(...server.libraries);
		}
	}
	return libraries;
});

/**
 * Toggle server selection.
 */
function toggleServer(serverId: string) {
	const current = formData.server_ids ?? [];
	if (current.includes(serverId)) {
		formData.server_ids = current.filter((id: string) => id !== serverId);
		// Also remove libraries from this server
		const serverLibraryIds =
			servers.find((s) => s.id === serverId)?.libraries.map((l) => l.id) ?? [];
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

function toLocalDateTimeString(date: Date): string {
	const year = date.getFullYear();
	const month = String(date.getMonth() + 1).padStart(2, '0');
	const day = String(date.getDate()).padStart(2, '0');
	const hours = String(date.getHours()).padStart(2, '0');
	const minutes = String(date.getMinutes()).padStart(2, '0');
	return `${year}-${month}-${day}T${hours}:${minutes}`;
}

function normalizeExpiration(value = expiresAtLocal) {
	expiresAtLocal = value;
	formData.expires_at = value ? toISOString(value) : '';
}

// Compute minimum datetime for expiration input (current time, local timezone)
const minDateTime = $derived(toLocalDateTimeString(new Date()));

// Local state for datetime-local input
let expiresAtLocal = $state(formatDateTimeLocal(formData.expires_at as string | undefined));

/**
 * Handle form submission.
 */
function handleSubmit(e: Event) {
	e.preventDefault();
	normalizeExpiration();
	onSubmit();
}

/**
 * Get error messages for a field.
 */
function getFieldErrors(field: string): string[] {
	return errors[field] ?? [];
}
</script>

<form onsubmit={handleSubmit} class="space-y-6" data-invitation-form>
	<!-- Target Servers (Required) -->
	<div class="space-y-2">
		<Label class="text-cr-text flex items-center gap-2">
			<Server class="size-4 text-cr-accent" />
			Target Servers
			<span class="text-rose-400">*</span>
		</Label>
		<!-- biome-ignore lint/a11y/useSemanticElements: This ARIA group labels existing controls without introducing native fieldset layout. -->
		<div
			class="mt-2 grid gap-2 sm:grid-cols-2 rounded-lg transition-shadow {getFieldErrors('server_ids').length > 0 ? 'ring-2 ring-rose-500/50 p-1' : ''}"
			role="group"
			aria-label="Select target servers"
		>
			{#each servers as server (server.id)}
				<button
					type="button"
					onclick={() => toggleServer(server.id)}
					class="flex items-center gap-3 rounded-lg border p-3 text-left transition-colors {isServerSelected(server.id)
	? 'border-cr-accent bg-cr-accent/10 text-cr-text'
	: 'border-cr-border bg-cr-surface text-cr-text-muted hover:border-cr-accent/50'}"
					aria-pressed={isServerSelected(server.id)}
					data-server-option={server.id}
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
						<div class="text-xs text-cr-text-muted">
							{server.server_type}
							· {server.libraries.length} libraries
						</div>
					</div>
				</button>
			{/each}
		</div>
		{#if servers.length === 0}
			<p class="mt-2 text-sm text-cr-text-muted">No servers available. Configure servers first.</p>
		{/if}
		{#if getFieldErrors('server_ids').length > 0}
			<div class="text-rose-400 text-sm" data-field-error="server_ids">
				{#each getFieldErrors('server_ids') as error}
					<p>{error}</p>
				{/each}
			</div>
		{/if}
	</div>

	<!-- Allowed Libraries (Optional, filtered by selected servers) -->
	{#if availableLibraries.length > 0}
		<div class="space-y-2">
			<Label class="text-cr-text flex items-center gap-2">
				<svg
					class="size-4 text-cr-accent"
					fill="none"
					viewBox="0 0 24 24"
					stroke="currentColor"
					aria-hidden="true"
				>
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
					/>
				</svg>
				Allowed Libraries
				<span class="text-cr-text-muted text-xs">(optional - all if none selected)</span>
			</Label>
			<!-- biome-ignore lint/a11y/useSemanticElements: This ARIA group labels existing controls without introducing native fieldset layout. -->
			<div class="mt-2 flex flex-wrap gap-2" role="group" aria-label="Select allowed libraries">
				{#each availableLibraries as library (library.id)}
					<button
						type="button"
						onclick={() => toggleLibrary(library.id)}
						class="rounded-full border px-3 py-1 text-sm transition-colors {isLibrarySelected(library.id)
	? 'border-cr-accent bg-cr-accent/10 text-cr-text'
	: 'border-cr-border bg-cr-surface text-cr-text-muted hover:border-cr-accent/50'}"
						aria-pressed={isLibrarySelected(library.id)}
						data-library-option={library.id}
					>
						{library.name}
					</button>
				{/each}
			</div>
		</div>
	{/if}

	<!-- Code (Optional, create mode only) -->
	{#if mode === 'create'}
		<div class="space-y-2">
			<Label class="text-cr-text flex items-center gap-2">
				<Hash class="size-4 text-cr-accent" />
				Custom Code
				<span class="text-cr-text-muted text-xs">(optional - auto-generated if empty)</span>
			</Label>
			<Input
				type="text"
				bind:value={(formData as CreateInvitationInput).code}
				placeholder="e.g., WELCOME2024"
				class="border-cr-border bg-cr-surface text-cr-text placeholder:text-cr-text-muted font-mono"
				maxlength={20}
				data-field-code
			/>
			<p class="text-cr-text-muted text-xs">Alphanumeric only, 1-20 characters</p>
			{#if getFieldErrors('code').length > 0}
				<div class="text-rose-400 text-sm" data-field-error="code">
					{#each getFieldErrors('code') as error}
						<p>{error}</p>
					{/each}
				</div>
			{/if}
		</div>
	{/if}

	<!-- Expiration Date (Optional) -->
	<div class="space-y-2">
		<Label class="text-cr-text flex items-center gap-2">
			<Calendar class="size-4 text-cr-accent" />
			Expiration Date
			<span class="text-cr-text-muted text-xs">(optional - never expires if empty)</span>
		</Label>
		<Input
			type="datetime-local"
			bind:value={expiresAtLocal}
			oninput={(e) => {
	normalizeExpiration(e.currentTarget.value);
}}
			onchange={(e) => {
	normalizeExpiration(e.currentTarget.value);
}}
			min={minDateTime}
			class="border-cr-border bg-cr-surface text-cr-text"
			data-field-expires-at
		/>
		{#if getFieldErrors('expires_at').length > 0}
			<div class="text-rose-400 text-sm" data-field-error="expires_at">
				{#each getFieldErrors('expires_at') as error}
					<p>{error}</p>
				{/each}
			</div>
		{/if}
	</div>

	<!-- Max Uses (Optional) -->
	<div class="space-y-2">
		<Label class="text-cr-text flex items-center gap-2">
			<Users class="size-4 text-cr-accent" />
			Maximum Uses
			<span class="text-cr-text-muted text-xs">(optional - unlimited if empty)</span>
		</Label>
		<Input
			type="number"
			bind:value={formData.max_uses}
			placeholder="e.g., 10"
			class="border-cr-border bg-cr-surface text-cr-text placeholder:text-cr-text-muted"
			min={1}
			data-field-max-uses
		/>
		{#if getFieldErrors('max_uses').length > 0}
			<div class="text-rose-400 text-sm" data-field-error="max_uses">
				{#each getFieldErrors('max_uses') as error}
					<p>{error}</p>
				{/each}
			</div>
		{/if}
	</div>

	<!-- Duration Days (Optional) -->
	<div class="space-y-2">
		<Label class="text-cr-text flex items-center gap-2">
			<Timer class="size-4 text-cr-accent" />
			Access Duration (days)
			<span class="text-cr-text-muted text-xs">(optional - permanent if empty)</span>
		</Label>
		<Input
			type="number"
			bind:value={formData.duration_days}
			placeholder="e.g., 30"
			class="border-cr-border bg-cr-surface text-cr-text placeholder:text-cr-text-muted"
			min={1}
			data-field-duration-days
		/>
		<p class="text-cr-text-muted text-xs">How long users will have access after redeeming</p>
		{#if getFieldErrors('duration_days').length > 0}
			<div class="text-rose-400 text-sm" data-field-error="duration_days">
				{#each getFieldErrors('duration_days') as error}
					<p>{error}</p>
				{/each}
			</div>
		{/if}
	</div>

	<!-- Wizard Selection Section -->
	{#if wizards.length > 0 || loadingWizards}
		<div class="space-y-4 pt-4 border-t border-cr-border">
			<div class="flex items-center gap-2">
				<Wand2 class="size-4 text-cr-accent" />
				<span class="text-cr-text font-medium">Onboarding Wizards</span>
				<span class="text-cr-text-muted text-xs">(optional)</span>
			</div>

			{#if loadingWizards}
				<div class="flex items-center gap-2 text-cr-text-muted text-sm">
					<span
						class="size-4 animate-spin rounded-full border-2 border-current border-t-transparent"
					></span>
					Loading wizards...
				</div>
			{:else}
				<!-- Pre-Registration Wizard -->
				<div class="space-y-2">
					<Label class="text-cr-text text-sm">
						Pre-Registration Wizard
						<span class="text-cr-text-muted text-xs ml-1">(runs before account creation)</span>
					</Label>
					<select
						bind:value={(formData as CreateInvitationInput).pre_wizard_id}
						class="w-full rounded-md border border-cr-border bg-cr-surface px-3 py-2 text-cr-text text-sm focus:outline-none focus:ring-2 focus:ring-cr-accent focus:ring-offset-2 focus:ring-offset-cr-bg"
						data-field-pre-wizard
					>
						<option value="">None</option>
						{#each wizards as wizard (wizard.id)}
							<option value={wizard.id}>{wizard.name}</option>
						{/each}
					</select>
					{#if getFieldErrors('pre_wizard_id').length > 0}
						<div class="text-rose-400 text-sm" data-field-error="pre_wizard_id">
							{#each getFieldErrors('pre_wizard_id') as error}
								<p>{error}</p>
							{/each}
						</div>
					{/if}
				</div>

				<!-- Post-Registration Wizard -->
				<div class="space-y-2">
					<Label class="text-cr-text text-sm">
						Post-Registration Wizard
						<span class="text-cr-text-muted text-xs ml-1">(runs after account creation)</span>
					</Label>
					<select
						bind:value={(formData as CreateInvitationInput).post_wizard_id}
						class="w-full rounded-md border border-cr-border bg-cr-surface px-3 py-2 text-cr-text text-sm focus:outline-none focus:ring-2 focus:ring-cr-accent focus:ring-offset-2 focus:ring-offset-cr-bg"
						data-field-post-wizard
					>
						<option value="">None</option>
						{#each wizards as wizard (wizard.id)}
							<option value={wizard.id}>{wizard.name}</option>
						{/each}
					</select>
					{#if getFieldErrors('post_wizard_id').length > 0}
						<div class="text-rose-400 text-sm" data-field-error="post_wizard_id">
							{#each getFieldErrors('post_wizard_id') as error}
								<p>{error}</p>
							{/each}
						</div>
					{/if}
				</div>
			{/if}
		</div>
	{/if}

	<!-- Enabled Toggle (Edit mode only) -->
	{#if mode === 'edit'}
		<div class="space-y-2">
			<div class="flex items-center gap-3">
				<button
					type="button"
					role="switch"
					aria-checked={(formData as UpdateInvitationInput).enabled ?? true}
					aria-label="Toggle invitation enabled status"
					onclick={() => {
	const current = (formData as UpdateInvitationInput).enabled ?? true;
	(formData as UpdateInvitationInput).enabled = !current;
}}
					class="relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cr-accent focus-visible:ring-offset-2 {((formData as UpdateInvitationInput).enabled ?? true) ? 'bg-cr-accent' : 'bg-cr-border'}"
					data-field-enabled
				>
					<span
						class="pointer-events-none inline-block size-5 transform rounded-full bg-white shadow-lg ring-0 transition-transform {((formData as UpdateInvitationInput).enabled ?? true) ? 'translate-x-5' : 'translate-x-0'}"
					></span>
				</button>
				<Label class="text-cr-text cursor-pointer">
					{((formData as UpdateInvitationInput).enabled ?? true) ? 'Enabled' : 'Disabled'}
				</Label>
			</div>
			<p class="text-cr-text-muted text-xs">Disabled invitations cannot be redeemed</p>
		</div>
	{/if}

	<!-- Form Actions -->
	<div class="flex items-center justify-end gap-3 pt-4 border-t border-cr-border">
		{#if onCancel}
			<Button
				type="button"
				variant="outline"
				onclick={onCancel}
				disabled={submitting}
				class="border-cr-border bg-cr-surface hover:bg-cr-border text-cr-text"
			>
				Cancel
			</Button>
		{/if}
		<Button
			type="submit"
			disabled={submitting || loadingWizards}
			class="bg-cr-accent text-cr-bg hover:bg-cr-accent-hover"
		>
			{#if submitting}
				<span
					class="size-4 animate-spin rounded-full border-2 border-current border-t-transparent"
				></span>
			{/if}
			{mode === 'create' ? 'Create Invitation' : 'Save Changes'}
		</Button>
	</div>
</form>
