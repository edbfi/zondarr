<script lang="ts">
/**
 * Server detail page.
 *
 * Displays server details with:
 * - Server information (name, type, url, enabled)
 * - Library list
 * - Sync status indicators
 * - Sync actions with results dialogs
 *
 * @module routes/(admin)/servers/[id]/+page
 */

import {
	ArrowLeft,
	Calendar,
	Clock3,
	Database,
	ExternalLink,
	KeyRound,
	Lock,
	RefreshCw,
	Server,
	ShieldAlert,
	Trash2
} from '@lucide/svelte';
import { onMount } from 'svelte';
import { goto, invalidateAll } from '$app/navigation';
import {
	deleteServer,
	type LibrarySyncResult,
	resetCircuitBreaker,
	type SyncChannelStatus,
	type SyncResult,
	syncServer,
	syncServerLibraries,
	withErrorHandling
} from '$lib/api/client';
import { asErrorResponse, getErrorMessage } from '$lib/api/errors';
import ConfirmDialog from '$lib/components/confirm-dialog.svelte';
import ErrorState from '$lib/components/error-state.svelte';
import LibrarySyncResultsDialog from '$lib/components/servers/library-sync-results-dialog.svelte';
import SyncResultsDialog from '$lib/components/servers/sync-results-dialog.svelte';
import StatusBadge from '$lib/components/status-badge.svelte';
import { Badge } from '$lib/components/ui/badge';
import { Button } from '$lib/components/ui/button';
import * as Card from '$lib/components/ui/card';
import { Label } from '$lib/components/ui/label';
import { getProviderBadgeStyle, getProviderLabel } from '$lib/stores/providers.svelte';
import { showError, showSuccess } from '$lib/utils/toast';
import type { PageData } from './$types';

const { data }: { data: PageData } = $props();

// Sync state
let syncingUsers = $state(false);
let syncingLibraries = $state(false);
let userSyncResult = $state<SyncResult | null>(null);
let librarySyncResult = $state<LibrarySyncResult | null>(null);
let showUserSyncDialog = $state(false);
let showLibrarySyncDialog = $state(false);

// Status refresh state
let nowMs = $state(Date.now());

// Circuit breaker state
let resettingCircuit = $state(false);

// Delete state
let deleting = $state(false);
let showDeleteDialog = $state(false);

const badgeStyle = $derived(data.server ? getProviderBadgeStyle(data.server.server_type) : '');
const serverTypeLabel = $derived(data.server ? getProviderLabel(data.server.server_type) : '');
const librariesStatus = $derived<SyncChannelStatus | null>(
	data.server?.sync_status?.libraries ?? null
);
const usersStatus = $derived<SyncChannelStatus | null>(data.server?.sync_status?.users ?? null);
const actionBusy = $derived(syncingUsers || syncingLibraries || deleting || resettingCircuit);
const anyCircuitOpen = $derived(
	librariesStatus?.circuit_state === 'open' || usersStatus?.circuit_state === 'open'
);
const urlLocked = $derived(data.credentialLocks?.url_locked ?? false);
const apiKeyLocked = $derived(data.credentialLocks?.api_key_locked ?? false);

onMount(() => {
	const countdownTimer = setInterval(() => {
		nowMs = Date.now();
	}, 1000);
	const pollTimer = setInterval(() => {
		void invalidateAll();
	}, 15000);

	return () => {
		clearInterval(countdownTimer);
		clearInterval(pollTimer);
	};
});

/**
 * Format date for display.
 */
function formatDate(dateInput: string | Date | null | undefined): string {
	if (!dateInput) return '—';
	try {
		const date = dateInput instanceof Date ? dateInput : new Date(dateInput);
		if (Number.isNaN(date.getTime())) return '—';
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
 * Parse ISO date string safely.
 */
function parseDate(dateString: string | null | undefined): Date | null {
	if (!dateString) return null;
	const parsed = new Date(dateString);
	return Number.isNaN(parsed.getTime()) ? null : parsed;
}

/**
 * Format time-until countdown label.
 */
function formatCountdown(nextScheduledAt: string | null | undefined, inProgress: boolean): string {
	if (inProgress) return 'Syncing now...';
	const target = parseDate(nextScheduledAt);
	if (!target) return 'Not scheduled';

	const diffMs = target.getTime() - nowMs;
	if (diffMs <= 0) return 'Due now';

	const totalSeconds = Math.floor(diffMs / 1000);
	const days = Math.floor(totalSeconds / 86400);
	const hours = Math.floor((totalSeconds % 86400) / 3600);
	const minutes = Math.floor((totalSeconds % 3600) / 60);
	const seconds = totalSeconds % 60;

	if (days > 0) return `in ${days}d ${hours}h`;
	if (hours > 0) return `in ${hours}h ${minutes}m`;
	if (minutes > 0) return `in ${minutes}m ${seconds}s`;
	return `in ${seconds}s`;
}

/**
 * Handle user sync button click.
 */
async function handleUserSync() {
	if (!data.server) return;
	const serverId = data.server.id;

	syncingUsers = true;
	try {
		const result = await withErrorHandling(() => syncServer(serverId, false), {
			showErrorToast: false
		});

		if (result.error) {
			const errorBody = asErrorResponse(result.error);
			showError('Sync failed', errorBody?.detail ?? 'An error occurred');
			return;
		}

		if (result.data) {
			userSyncResult = result.data;
			showUserSyncDialog = true;
			showSuccess('User sync completed successfully');
			await invalidateAll();
		}
	} finally {
		syncingUsers = false;
	}
}

/**
 * Handle library sync button click.
 */
async function handleLibrarySync() {
	if (!data.server) return;
	const serverId = data.server.id;

	syncingLibraries = true;
	try {
		const result = await withErrorHandling(() => syncServerLibraries(serverId), {
			showErrorToast: false
		});

		if (result.error) {
			const errorBody = asErrorResponse(result.error);
			showError('Library sync failed', errorBody?.detail ?? 'An error occurred');
			return;
		}

		if (result.data) {
			librarySyncResult = result.data as LibrarySyncResult;
			showLibrarySyncDialog = true;
			showSuccess('Library sync completed successfully');
			await invalidateAll();
		}
	} finally {
		syncingLibraries = false;
	}
}

/**
 * Handle circuit breaker reset.
 */
async function handleResetCircuit() {
	if (!data.server) return;
	const serverId = data.server.id;

	resettingCircuit = true;
	try {
		const result = await withErrorHandling(() => resetCircuitBreaker(serverId), {
			showErrorToast: false
		});

		if (result.error) {
			showError('Failed to reset circuit breaker');
			return;
		}

		showSuccess('Circuit breaker reset successfully');
		await invalidateAll();
	} finally {
		resettingCircuit = false;
	}
}

/**
 * Handle retry after error.
 */
async function handleRetry() {
	await invalidateAll();
}

/**
 * Close user sync results dialog.
 */
function closeUserSyncDialog() {
	showUserSyncDialog = false;
}

/**
 * Close library sync results dialog.
 */
function closeLibrarySyncDialog() {
	showLibrarySyncDialog = false;
}

/**
 * Handle delete server action.
 */
async function handleDelete() {
	if (!data.server) return;
	const serverId = data.server.id;

	deleting = true;
	try {
		const result = await withErrorHandling(() => deleteServer(serverId), { showErrorToast: false });

		if (result.error) {
			const errorBody = asErrorResponse(result.error);
			showError('Failed to delete server', errorBody?.detail ?? 'An error occurred');
			return;
		}

		showSuccess('Server deleted successfully');
		goto('/servers');
	} finally {
		deleting = false;
		showDeleteDialog = false;
	}
}
</script>

<div class="space-y-6">
	<!-- Back button and header -->
	<div class="flex items-center gap-4">
		<a
			href="/servers"
			class="inline-flex items-center justify-center size-9 rounded-md text-cr-text-muted hover:text-cr-text hover:bg-accent"
			aria-label="Back to servers"
		>
			<ArrowLeft class="size-5" />
		</a>
		<div class="flex-1">
			<h1 class="text-xl font-semibold text-cr-text">Server Details</h1>
			{#if data.server}
				<p class="text-cr-text-muted">
					<span class="font-medium text-cr-text">{data.server.name}</span>
				</p>
			{/if}
		</div>
		{#if data.server}
			<StatusBadge
				status={data.server.enabled ? 'active' : 'disabled'}
				label={data.server.enabled ? 'Enabled' : 'Disabled'}
			/>
		{/if}
	</div>

	{#if data.error}
		<ErrorState
			message={getErrorMessage(data.error)}
			title="Failed to load server"
			onRetry={handleRetry}
		/>
	{:else if data.server}
		<div class="grid gap-6 lg:grid-cols-2">
			<!-- Server Information Card -->
			<Card.Root class="border-cr-border bg-cr-surface" data-server-info>
				<Card.Header>
					<Card.Title class="text-cr-text flex items-center gap-2">
						<Server class="size-5 text-cr-accent" />
						Server Information
					</Card.Title>
					<Card.Description class="text-cr-text-muted">
						Details about this media server.
					</Card.Description>
				</Card.Header>
				<Card.Content class="space-y-4">
					<!-- Name -->
					<div class="space-y-1" data-field="name">
						<Label class="text-cr-text-muted text-xs uppercase tracking-wide">Name</Label>
						<div class="font-medium text-lg text-cr-text">{data.server.name}</div>
					</div>

					<!-- Server Type -->
					<div class="space-y-1" data-field="server_type">
						<Label class="text-cr-text-muted text-xs uppercase tracking-wide">Type</Label>
						<div>
							<span
								class="inline-flex items-center rounded border px-2 py-1 text-sm font-medium"
								style={badgeStyle}
							>
								{serverTypeLabel}
							</span>
						</div>
					</div>

					<!-- URL -->
					<div class="space-y-1" data-field="url">
						<div class="flex items-center gap-2">
							<Label
								class="text-cr-text-muted text-xs uppercase tracking-wide flex items-center gap-1"
							>
								<ExternalLink class="size-3" />
								URL
							</Label>
							{#if urlLocked}
								<Badge variant="secondary" class="gap-1">
									<Lock class="size-3" />
									Environment Variable
								</Badge>
							{/if}
						</div>
						<div
							class="font-mono text-sm text-cr-text bg-cr-bg px-3 py-2 rounded border border-cr-border break-all"
						>
							{data.server.url}
						</div>
					</div>

					<!-- API Key -->
					<div class="space-y-1" data-field="api_key">
						<div class="flex items-center gap-2">
							<Label
								class="text-cr-text-muted text-xs uppercase tracking-wide flex items-center gap-1"
							>
								<KeyRound class="size-3" />
								API Key
							</Label>
							{#if apiKeyLocked}
								<Badge variant="secondary" class="gap-1">
									<Lock class="size-3" />
									Environment Variable
								</Badge>
							{/if}
						</div>
						<div
							class="font-mono text-sm text-cr-text bg-cr-bg px-3 py-2 rounded border border-cr-border break-all"
						>
							{#if apiKeyLocked}
								<span class="text-cr-text-muted">Set via environment variable</span>
							{:else}
								<span class="text-cr-text-muted">••••••••</span>
							{/if}
						</div>
					</div>

					<!-- Enabled Status -->
					<div class="space-y-1" data-field="enabled">
						<Label class="text-cr-text-muted text-xs uppercase tracking-wide">Status</Label>
						<div class="flex items-center gap-2">
							<StatusBadge
								status={data.server.enabled ? 'active' : 'disabled'}
								label={data.server.enabled ? 'Enabled' : 'Disabled'}
							/>
						</div>
					</div>

					<!-- Created At -->
					<div class="space-y-1">
						<Label
							class="text-cr-text-muted text-xs uppercase tracking-wide flex items-center gap-1"
						>
							<Calendar class="size-3" />
							Created
						</Label>
						<div class="text-cr-text font-data">{formatDate(data.server.created_at)}</div>
					</div>

					<!-- Updated At -->
					{#if data.server.updated_at}
						<div class="space-y-1">
							<Label class="text-cr-text-muted text-xs uppercase tracking-wide">Last Updated</Label>
							<div class="text-cr-text font-data">{formatDate(data.server.updated_at)}</div>
						</div>
					{/if}
				</Card.Content>
			</Card.Root>

			<!-- Libraries Card -->
			<Card.Root class="border-cr-border bg-cr-surface" data-libraries>
				<Card.Header>
					<Card.Title class="text-cr-text flex items-center gap-2">
						<Database class="size-5 text-cr-accent" />
						Libraries
						<span class="text-sm font-normal text-cr-text-muted">
							({data.server.libraries.length})
						</span>
					</Card.Title>
					<Card.Description class="text-cr-text-muted">
						Content libraries available on this server.
					</Card.Description>
				</Card.Header>
				<Card.Content>
					{#if data.server.libraries.length === 0}
						<div class="text-center py-6 text-cr-text-muted">
							No libraries found on this server.
						</div>
					{:else}
						<div class="space-y-2">
							{#each data.server.libraries as library (library.id)}
								<div
									class="flex items-center justify-between rounded-lg border border-cr-border bg-cr-bg p-3"
									data-library={library.id}
								>
									<div class="flex-1 min-w-0">
										<div class="font-medium text-cr-text truncate">{library.name}</div>
										<div class="flex items-center gap-2 mt-1">
											<span class="text-xs text-cr-text-muted capitalize">
												{library.library_type}
											</span>
											<span class="text-xs text-cr-text-muted">•</span>
											<span class="text-xs font-mono text-cr-text-muted truncate">
												{library.external_id}
											</span>
										</div>
									</div>
								</div>
							{/each}
						</div>
					{/if}
				</Card.Content>
			</Card.Root>

			<!-- Sync Status Card -->
			<Card.Root class="border-cr-border bg-cr-surface lg:col-span-2" data-sync-status>
				<Card.Header>
					<Card.Title class="text-cr-text flex items-center gap-2">
						<Clock3 class="size-5 text-cr-accent" />
						Sync Status
					</Card.Title>
					<Card.Description class="text-cr-text-muted">
						Automatic synchronization schedule and current activity.
					</Card.Description>
				</Card.Header>
				<Card.Content>
					<div class="grid gap-3 md:grid-cols-2">
						<div
							class="rounded-lg border p-4 space-y-2 {librariesStatus?.circuit_state === 'open'
	? 'border-rose-500/50 bg-rose-500/5'
	: 'border-cr-border bg-cr-bg'}"
							data-sync-channel="libraries"
						>
							<div class="flex items-center justify-between gap-3">
								<div>
									<div class="font-medium text-cr-text flex items-center gap-2">
										Libraries
										{#if librariesStatus?.circuit_state === 'open'}
											<span
												class="inline-flex items-center gap-1 rounded-full bg-rose-500/15 px-2 py-0.5 text-xs font-medium text-rose-400"
											>
												<ShieldAlert class="size-3" />
												Circuit Open
											</span>
										{:else if librariesStatus?.circuit_state === 'half_open'}
											<span
												class="inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-2 py-0.5 text-xs font-medium text-amber-400"
											>
												Recovering
											</span>
										{/if}
									</div>
									<div class="text-xs text-cr-text-muted">Media library sync</div>
								</div>
								<div class="text-right">
									{#if syncingLibraries || librariesStatus?.in_progress}
										<div class="inline-flex items-center gap-2 text-amber-300 text-sm">
											<span
												class="size-3 animate-spin rounded-full border-2 border-current border-t-transparent"
											></span>
											Syncing now...
										</div>
									{:else}
										<div class="text-sm text-cr-text">
											Next: {formatDate(librariesStatus?.next_scheduled_at)}
										</div>
										<div class="text-xs text-cr-text-muted">
											{formatCountdown(librariesStatus?.next_scheduled_at, false)}
										</div>
									{/if}
								</div>
							</div>
							<div class="text-xs text-cr-text-muted">
								Last completed: {formatDate(librariesStatus?.last_completed_at)}
							</div>
							{#if librariesStatus?.circuit_state === 'open' && librariesStatus.consecutive_failures}
								<div class="text-xs text-rose-400">
									{librariesStatus.consecutive_failures}
									consecutive failure{librariesStatus.consecutive_failures === 1 ? '' : 's'}
								</div>
							{:else if (librariesStatus?.consecutive_failures ?? 0) > 0 && librariesStatus?.circuit_state !== 'open'}
								<div class="text-xs text-cr-text-muted">
									{librariesStatus?.consecutive_failures}
									recent failure{librariesStatus?.consecutive_failures === 1 ? '' : 's'}
								</div>
							{/if}
						</div>

						<div
							class="rounded-lg border p-4 space-y-2 {usersStatus?.circuit_state === 'open'
	? 'border-rose-500/50 bg-rose-500/5'
	: 'border-cr-border bg-cr-bg'}"
							data-sync-channel="users"
						>
							<div class="flex items-center justify-between gap-3">
								<div>
									<div class="font-medium text-cr-text flex items-center gap-2">
										Users
										{#if usersStatus?.circuit_state === 'open'}
											<span
												class="inline-flex items-center gap-1 rounded-full bg-rose-500/15 px-2 py-0.5 text-xs font-medium text-rose-400"
											>
												<ShieldAlert class="size-3" />
												Circuit Open
											</span>
										{:else if usersStatus?.circuit_state === 'half_open'}
											<span
												class="inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-2 py-0.5 text-xs font-medium text-amber-400"
											>
												Recovering
											</span>
										{/if}
									</div>
									<div class="text-xs text-cr-text-muted">Account state sync</div>
								</div>
								<div class="text-right">
									{#if syncingUsers || usersStatus?.in_progress}
										<div class="inline-flex items-center gap-2 text-amber-300 text-sm">
											<span
												class="size-3 animate-spin rounded-full border-2 border-current border-t-transparent"
											></span>
											Syncing now...
										</div>
									{:else}
										<div class="text-sm text-cr-text">
											Next: {formatDate(usersStatus?.next_scheduled_at)}
										</div>
										<div class="text-xs text-cr-text-muted">
											{formatCountdown(usersStatus?.next_scheduled_at, false)}
										</div>
									{/if}
								</div>
							</div>
							<div class="text-xs text-cr-text-muted">
								Last completed: {formatDate(usersStatus?.last_completed_at)}
							</div>
							{#if usersStatus?.circuit_state === 'open' && usersStatus.consecutive_failures}
								<div class="text-xs text-rose-400">
									{usersStatus.consecutive_failures}
									consecutive failure{usersStatus.consecutive_failures === 1 ? '' : 's'}
								</div>
							{:else if (usersStatus?.consecutive_failures ?? 0) > 0 && usersStatus?.circuit_state !== 'open'}
								<div class="text-xs text-cr-text-muted">
									{usersStatus?.consecutive_failures}
									recent failure{usersStatus?.consecutive_failures === 1 ? '' : 's'}
								</div>
							{/if}
						</div>
					</div>
				</Card.Content>
			</Card.Root>

			<!-- Actions Card -->
			<Card.Root class="border-cr-border bg-cr-surface lg:col-span-2" data-actions>
				<Card.Header>
					<Card.Title class="text-cr-text">Actions</Card.Title>
					<Card.Description class="text-cr-text-muted">
						Manage this media server.
					</Card.Description>
				</Card.Header>
				<Card.Content>
					<div class="flex flex-wrap items-center gap-3">
						<!-- Sync Users Button -->
						<Button
							onclick={handleUserSync}
							disabled={actionBusy}
							class="bg-cr-accent text-cr-bg hover:bg-cr-accent-hover"
							data-action-sync
							data-action-sync-users
						>
							{#if syncingUsers}
								<span
									class="size-4 animate-spin rounded-full border-2 border-current border-t-transparent"
								></span>
								Syncing Users...
							{:else}
								<RefreshCw class="size-4" />
								Sync Users
							{/if}
						</Button>

						<!-- Sync Libraries Button -->
						<Button
							variant="outline"
							onclick={handleLibrarySync}
							disabled={actionBusy}
							class="border-cr-accent/60 text-cr-accent hover:bg-cr-accent/10 hover:border-cr-accent"
							data-action-sync-libraries
						>
							{#if syncingLibraries}
								<span
									class="size-4 animate-spin rounded-full border-2 border-current border-t-transparent"
								></span>
								Syncing Libraries...
							{:else}
								<Database class="size-4" />
								Sync Libraries
							{/if}
						</Button>

						<!-- Reset Circuit Breaker Button -->
						{#if anyCircuitOpen}
							<Button
								variant="outline"
								onclick={handleResetCircuit}
								disabled={actionBusy}
								class="border-amber-500/50 text-amber-400 hover:bg-amber-500/10 hover:border-amber-500"
								data-action-reset-circuit
							>
								{#if resettingCircuit}
									<span
										class="size-4 animate-spin rounded-full border-2 border-current border-t-transparent"
									></span>
									Resetting...
								{:else}
									<ShieldAlert class="size-4" />
									Reset Circuit Breaker
								{/if}
							</Button>
						{/if}

						<!-- Delete Button -->
						<Button
							variant="outline"
							onclick={() => (showDeleteDialog = true)}
							disabled={actionBusy}
							class="border-rose-500/50 text-rose-400 hover:bg-rose-500/10 hover:border-rose-500"
							data-action-delete
						>
							<Trash2 class="size-4" />
							Delete Server
						</Button>
					</div>
				</Card.Content>
			</Card.Root>
		</div>
	{/if}
</div>

<!-- Sync Results Dialog -->
<SyncResultsDialog
	bind:open={showUserSyncDialog}
	result={userSyncResult}
	onClose={closeUserSyncDialog}
/>

<!-- Library Sync Results Dialog -->
<LibrarySyncResultsDialog
	bind:open={showLibrarySyncDialog}
	result={librarySyncResult}
	onClose={closeLibrarySyncDialog}
/>

<!-- Delete Confirmation Dialog -->
<ConfirmDialog
	bind:open={showDeleteDialog}
	title="Delete Server"
	description="Are you sure you want to delete this server? This will remove all associated libraries and user records. Users will NOT be deleted from the media server itself, but their local tracking records will be lost. This action cannot be undone."
	confirmLabel="Delete"
	variant="destructive"
	loading={deleting}
	onConfirm={handleDelete}
	onCancel={() => (showDeleteDialog = false)}
/>
