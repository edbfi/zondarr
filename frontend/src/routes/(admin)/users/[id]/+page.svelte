<script lang="ts">
/**
 * User detail page.
 *
 * Displays user details with:
 * - User information (username, external_user_id, enabled, expires_at)
 * - Identity information with all linked users
 * - Media server information
 * - Source invitation if available
 * - Action buttons (Enable/Disable/Delete)
 *
 * @module routes/(admin)/users/[id]/+page
 */

import {
	ArrowLeft,
	Calendar,
	Key,
	Link2,
	Power,
	PowerOff,
	Server,
	Settings,
	Trash2,
	User,
	Users
} from '@lucide/svelte';
import { goto, invalidateAll } from '$app/navigation';
import {
	deleteUser,
	disableUser,
	enableUser,
	removeSharedAccess,
	withErrorHandling
} from '$lib/api/client';
import { asErrorResponse, getErrorMessage } from '$lib/api/errors';
import ErrorState from '$lib/components/error-state.svelte';
import StatusBadge, { type StatusBadgeStatus } from '$lib/components/status-badge.svelte';
import SteppedDeleteDialog from '$lib/components/stepped-delete-dialog.svelte';
import { Button } from '$lib/components/ui/button';
import * as Card from '$lib/components/ui/card';
import { Label } from '$lib/components/ui/label';
import UserPermissionsEditor from '$lib/components/users/user-permissions-editor.svelte';
import { getProviderBadgeStyle, hasProviderCapability } from '$lib/stores/providers.svelte';
import { showError, showSuccess } from '$lib/utils/toast';
import type { PageData } from './$types';

const { data }: { data: PageData } = $props();

// Loading states
let enabling = $state(false);
let disabling = $state(false);
let deleting = $state(false);

// Delete confirmation dialog
let showDeleteDialog = $state(false);

/**
 * Check if user is expired based on expires_at.
 */
const isExpired = $derived.by(() => {
	if (!data.user?.expires_at) return false;
	return new Date(data.user.expires_at) < new Date();
});

/**
 * Check if user is expiring soon (within 7 days).
 */
const isExpiringSoon = $derived.by(() => {
	if (!data.user?.expires_at) return false;
	const expiresAt = new Date(data.user.expires_at);
	const now = new Date();
	const sevenDaysFromNow = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
	return expiresAt > now && expiresAt <= sevenDaysFromNow;
});

/**
 * Derive the status for the badge based on user state.
 */
const status = $derived.by((): StatusBadgeStatus => {
	if (!data.user) return 'disabled';
	if (!data.user.enabled) return 'disabled';
	if (isExpired) return 'expired';
	if (isExpiringSoon) return 'pending';
	return 'active';
});

/**
 * Derive the status label.
 */
const statusLabel = $derived.by(() => {
	if (!data.user) return 'Unknown';
	if (!data.user.enabled) return 'Disabled';
	if (isExpired) return 'Expired';
	if (isExpiringSoon) return 'Expiring Soon';
	return 'Active';
});

const badgeStyle = $derived(
	data.user ? getProviderBadgeStyle(data.user.media_server.server_type) : ''
);
const supportsEnableDisable = $derived(
	data.user
		? hasProviderCapability(data.user.media_server.server_type, 'enable_disable_user')
		: false
);

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
 * Format expiration date with relative indicator.
 */
const expiresDisplay = $derived.by(() => {
	if (!data.user?.expires_at) return 'Never';
	const formatted = formatDate(data.user.expires_at);
	if (isExpired) return `${formatted} (expired)`;
	if (isExpiringSoon) return `${formatted} (soon)`;
	return formatted;
});

/**
 * Handle enable user action.
 */
async function handleEnable() {
	if (!data.user) return;
	const userId = data.user.id;

	enabling = true;
	try {
		const result = await withErrorHandling(() => enableUser(userId), {
			showErrorToast: false
		});

		if (result.error) {
			const errorBody = asErrorResponse(result.error);
			showError('Failed to enable user', errorBody?.detail ?? 'An error occurred');
			return;
		}

		showSuccess('User enabled successfully');
		await invalidateAll();
	} finally {
		enabling = false;
	}
}

/**
 * Handle disable user action.
 */
async function handleDisable() {
	if (!data.user) return;
	const userId = data.user.id;

	disabling = true;
	try {
		const result = await withErrorHandling(() => disableUser(userId), {
			showErrorToast: false
		});

		if (result.error) {
			const errorBody = asErrorResponse(result.error);
			showError('Failed to disable user', errorBody?.detail ?? 'An error occurred');
			return;
		}

		showSuccess('User disabled successfully');
		await invalidateAll();
	} finally {
		disabling = false;
	}
}

/**
 * Handle removing shared access (step 1 for shared users).
 */
async function handleRemoveShares() {
	if (!data.user) return;
	const userId = data.user.id;

	const result = await withErrorHandling(() => removeSharedAccess(userId), {
		showErrorToast: false
	});

	if (result.error) {
		const errorBody = asErrorResponse(result.error);
		throw new Error(errorBody?.detail ?? 'Failed to remove shared access');
	}

	showSuccess('Shared access removed');
	await invalidateAll();
}

/**
 * Handle delete user confirmation (final step).
 */
async function handleDelete() {
	if (!data.user) return;
	const userId = data.user.id;

	const result = await withErrorHandling(() => deleteUser(userId), {
		showErrorToast: false
	});

	if (result.error) {
		const errorBody = asErrorResponse(result.error);
		throw new Error(errorBody?.detail ?? 'Failed to delete user');
	}

	showSuccess('User deleted successfully');
	goto('/users');
}

/**
 * Handle retry after error.
 */
async function handleRetry() {
	await invalidateAll();
}

/**
 * Navigate to linked user detail page.
 */
function viewLinkedUser(userId: string) {
	goto(`/users/${userId}`);
}
</script>

<div class="space-y-6">
	<!-- Back button and header -->
	<div class="flex items-center gap-4">
		<Button
			variant="ghost"
			size="icon"
			onclick={() => goto('/users')}
			class="text-cr-text-muted hover:text-cr-text"
			aria-label="Back to users"
		>
			<ArrowLeft class="size-5" />
		</Button>
		<div class="flex-1">
			<h1 class="text-xl font-semibold text-cr-text">User Details</h1>
			{#if data.user}
				<p class="text-cr-text-muted">
					Username: <span class="font-medium text-cr-text">{data.user.username}</span>
				</p>
			{/if}
		</div>
		{#if data.user}
			<StatusBadge {status} label={statusLabel} />
			{#if data.user.external_user_type === 'friend'}
				<span
					class="inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium bg-indigo-500/15 text-indigo-400 border border-indigo-500/30"
				>
					Friend
				</span>
			{:else if data.user.external_user_type === 'shared'}
				<span
					class="inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium bg-purple-500/15 text-purple-400 border border-purple-500/30"
				>
					Shared
				</span>
			{:else if data.user.external_user_type === 'home'}
				<span
					class="inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium bg-teal-500/15 text-teal-400 border border-teal-500/30"
				>
					Home
				</span>
			{/if}
		{/if}
	</div>

	{#if data.error}
		<ErrorState
			message={getErrorMessage(data.error)}
			title="Failed to load user"
			onRetry={handleRetry}
		/>
	{:else if data.user}
		<div class="grid gap-6 lg:grid-cols-2">
			<!-- User Information Card -->
			<Card.Root class="border-cr-border bg-cr-surface" data-user-info>
				<Card.Header>
					<Card.Title class="text-cr-text flex items-center gap-2">
						<User class="size-5 text-cr-accent" />
						User Information
					</Card.Title>
					<Card.Description class="text-cr-text-muted">
						Account details for this user.
					</Card.Description>
				</Card.Header>
				<Card.Content class="space-y-4">
					<!-- Username -->
					<div class="space-y-1" data-field="username">
						<Label class="text-cr-text-muted text-xs uppercase tracking-wide">Username</Label>
						<div class="font-medium text-lg text-cr-text">{data.user.username}</div>
					</div>

					<!-- User Type -->
					<div class="space-y-1" data-field="user_type">
						<Label class="text-cr-text-muted text-xs uppercase tracking-wide">User Type</Label>
						<div class="flex flex-col gap-1">
							{#if data.user.external_user_type === 'friend'}
								<span
									class="inline-flex w-fit items-center rounded px-1.5 py-0.5 text-xs font-medium bg-indigo-500/15 text-indigo-400 border border-indigo-500/30"
								>
									Friend
								</span>
								<span class="text-xs text-cr-text-muted">No shared libraries on this server</span>
							{:else if data.user.external_user_type === 'shared'}
								<span
									class="inline-flex w-fit items-center rounded px-1.5 py-0.5 text-xs font-medium bg-purple-500/15 text-purple-400 border border-purple-500/30"
								>
									Shared
								</span>
								<span class="text-xs text-cr-text-muted">Has shared library access</span>
							{:else if data.user.external_user_type === 'home'}
								<span
									class="inline-flex w-fit items-center rounded px-1.5 py-0.5 text-xs font-medium bg-teal-500/15 text-teal-400 border border-teal-500/30"
								>
									Home
								</span>
								<span class="text-xs text-cr-text-muted">Plex Home member</span>
							{:else}
								<span
									class="inline-flex w-fit items-center rounded px-1.5 py-0.5 text-xs font-medium bg-zinc-500/15 text-zinc-500 border border-zinc-500/30"
								>
									Unknown
								</span>
								<span class="text-xs text-cr-text-dim"
									>Type not yet determined — run a sync to detect</span
								>
							{/if}
						</div>
					</div>

					<!-- External User ID -->
					<div class="space-y-1" data-field="external_user_id">
						<Label class="text-cr-text-muted text-xs uppercase tracking-wide"
							>External User ID</Label
						>
						<div
							class="font-mono text-sm text-cr-text bg-cr-bg px-3 py-2 rounded border border-cr-border"
						>
							{data.user.external_user_id}
						</div>
					</div>

					<!-- Enabled Status -->
					<div class="space-y-1" data-field="enabled">
						<Label class="text-cr-text-muted text-xs uppercase tracking-wide">Status</Label>
						<div class="flex items-center gap-2">
							<StatusBadge {status} label={statusLabel} />
						</div>
					</div>

					<!-- Expires At -->
					<div class="space-y-1" data-field="expires_at">
						<Label
							class="text-cr-text-muted text-xs uppercase tracking-wide flex items-center gap-1"
						>
							<Calendar class="size-3" />
							Expires
						</Label>
						<div class="text-cr-text font-data">{expiresDisplay}</div>
					</div>

					<!-- Created At -->
					<div class="space-y-1" data-field="created_at">
						<Label class="text-cr-text-muted text-xs uppercase tracking-wide">Created</Label>
						<div class="text-cr-text font-data">{formatDate(data.user.created_at)}</div>
					</div>

					<!-- Updated At -->
					{#if data.user.updated_at}
						<div class="space-y-1">
							<Label class="text-cr-text-muted text-xs uppercase tracking-wide">Last Updated</Label>
							<div class="text-cr-text font-data">{formatDate(data.user.updated_at)}</div>
						</div>
					{/if}
				</Card.Content>
			</Card.Root>

			<!-- Permissions Card -->
			<Card.Root class="border-cr-border bg-cr-surface" data-permissions>
				<Card.Header>
					<Card.Title class="text-cr-text flex items-center gap-2">
						<Settings class="size-5 text-cr-accent" />
						Permissions
					</Card.Title>
					<Card.Description class="text-cr-text-muted">
						Control what this user can do on the media server.
					</Card.Description>
				</Card.Header>
				<Card.Content>
					<UserPermissionsEditor
						userId={data.user.id}
						disabled={!data.user.enabled || enabling || disabling || deleting}
						supportedPermissions={data.user.media_server.supported_permissions ?? undefined}
					/>
				</Card.Content>
			</Card.Root>

			<!-- Media Server Card -->
			<Card.Root class="border-cr-border bg-cr-surface" data-media-server>
				<Card.Header>
					<Card.Title class="text-cr-text flex items-center gap-2">
						<Server class="size-5 text-cr-accent" />
						Media Server
					</Card.Title>
					<Card.Description class="text-cr-text-muted">
						The server this user account belongs to.
					</Card.Description>
				</Card.Header>
				<Card.Content>
					<div class="flex items-center gap-4 rounded-lg border border-cr-border bg-cr-bg p-4">
						<div class="flex-1 min-w-0">
							<div class="flex items-center gap-2 mb-1">
								<span class="font-medium text-cr-text">{data.user.media_server.name}</span>
								<span
									class="inline-flex items-center rounded border px-1.5 py-0.5 text-xs font-medium"
									style={badgeStyle}
								>
									{data.user.media_server.server_type}
								</span>
							</div>
							<div class="text-sm text-cr-text-muted font-mono break-all">
								{data.user.media_server.url}
							</div>
							<div class="mt-2">
								<StatusBadge
									status={data.user.media_server.enabled ? 'active' : 'disabled'}
									label={data.user.media_server.enabled ? 'Enabled' : 'Disabled'}
								/>
							</div>
						</div>
					</div>
				</Card.Content>
			</Card.Root>

			<!-- Identity Card -->
			<Card.Root class="border-cr-border bg-cr-surface" data-identity>
				<Card.Header>
					<Card.Title class="text-cr-text flex items-center gap-2">
						<Key class="size-5 text-cr-accent" />
						Identity
					</Card.Title>
					<Card.Description class="text-cr-text-muted">
						The unified identity this user belongs to.
					</Card.Description>
				</Card.Header>
				<Card.Content class="space-y-4">
					<!-- Display Name -->
					<div class="space-y-1" data-field="identity_display_name">
						<Label class="text-cr-text-muted text-xs uppercase tracking-wide">Display Name</Label>
						<div class="font-medium text-cr-text">{data.user.identity.display_name}</div>
					</div>

					<!-- Identity ID -->
					<div class="space-y-1" data-field="identity_id">
						<Label class="text-cr-text-muted text-xs uppercase tracking-wide">Identity ID</Label>
						<div
							class="font-mono text-xs text-cr-text-muted bg-cr-bg px-2 py-1 rounded border border-cr-border"
						>
							{data.user.identity.id}
						</div>
					</div>

					<!-- Email -->
					{#if data.user.identity.email}
						<div class="space-y-1" data-field="identity_email">
							<Label class="text-cr-text-muted text-xs uppercase tracking-wide">Email</Label>
							<div class="text-cr-text">{data.user.identity.email}</div>
						</div>
					{/if}

					<!-- Identity Status -->
					<div class="space-y-1">
						<Label class="text-cr-text-muted text-xs uppercase tracking-wide"
							>Identity Status</Label
						>
						<StatusBadge
							status={data.user.identity.enabled ? 'active' : 'disabled'}
							label={data.user.identity.enabled ? 'Enabled' : 'Disabled'}
						/>
					</div>

					<!-- Identity Created -->
					<div class="space-y-1">
						<Label class="text-cr-text-muted text-xs uppercase tracking-wide"
							>Identity Created</Label
						>
						<div class="text-cr-text font-data">{formatDate(data.user.identity.created_at)}</div>
					</div>
				</Card.Content>
			</Card.Root>

			<!-- Source Invitation Card -->
			{#if data.user.invitation}
				<Card.Root class="border-cr-border bg-cr-surface" data-invitation>
					<Card.Header>
						<Card.Title class="text-cr-text flex items-center gap-2">
							<Link2 class="size-5 text-cr-accent" />
							Source Invitation
						</Card.Title>
						<Card.Description class="text-cr-text-muted">
							The invitation used to create this account.
						</Card.Description>
					</Card.Header>
					<Card.Content class="space-y-4">
						<!-- Invitation Code -->
						<div class="space-y-1" data-field="invitation_code">
							<Label class="text-cr-text-muted text-xs uppercase tracking-wide">Code</Label>
							<div class="font-mono text-lg text-cr-accent bg-cr-accent/10 px-3 py-2 rounded">
								{data.user.invitation.code}
							</div>
						</div>

						<!-- Invitation Status -->
						<div class="space-y-1">
							<Label class="text-cr-text-muted text-xs uppercase tracking-wide">Status</Label>
							<StatusBadge
								status={data.user.invitation.is_active ? 'active' : 'expired'}
								label={data.user.invitation.is_active ? 'Active' : 'Inactive'}
							/>
						</div>

						<!-- Use Count -->
						<div class="space-y-1">
							<Label class="text-cr-text-muted text-xs uppercase tracking-wide">Use Count</Label>
							<div class="text-cr-text font-data">
								{data.user.invitation.use_count}
								{#if data.user.invitation.max_uses}
									<span class="text-cr-text-muted">/ {data.user.invitation.max_uses}</span>
								{/if}
							</div>
						</div>

						<!-- View Invitation Link -->
						<Button
							variant="outline"
							size="sm"
							onclick={() => goto(`/invitations/${data.user?.invitation?.id}`)}
							class="border-cr-border text-cr-text hover:bg-cr-border"
						>
							View Invitation Details
						</Button>
					</Card.Content>
				</Card.Root>
			{/if}

			<!-- Linked Users Card -->
			{#if data.linkedUsers.length > 0}
				<Card.Root class="border-cr-border bg-cr-surface lg:col-span-2" data-linked-users>
					<Card.Header>
						<Card.Title class="text-cr-text flex items-center gap-2">
							<Users class="size-5 text-cr-accent" />
							Linked Users
						</Card.Title>
						<Card.Description class="text-cr-text-muted">
							Other user accounts belonging to the same identity across different servers.
						</Card.Description>
					</Card.Header>
					<Card.Content>
						<div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
							{#each data.linkedUsers as linkedUser (linkedUser.id)}
								<button
									type="button"
									onclick={() => viewLinkedUser(linkedUser.id)}
									class="flex items-center gap-3 rounded-lg border border-cr-border bg-cr-bg p-3 text-left transition-colors hover:border-cr-accent/50 hover:bg-cr-border/30"
									data-linked-user={linkedUser.id}
								>
									<div class="flex-1 min-w-0">
										<div class="font-medium text-cr-text truncate">{linkedUser.username}</div>
										<div class="flex items-center gap-2 mt-1">
											<span
												class="inline-flex items-center rounded border px-1.5 py-0.5 text-xs font-medium"
												style={getProviderBadgeStyle(linkedUser.media_server.server_type)}
											>
												{linkedUser.media_server.server_type}
											</span>
											<span class="text-xs text-cr-text-muted truncate"
												>{linkedUser.media_server.name}</span
											>
										</div>
									</div>
									<StatusBadge
										status={linkedUser.enabled ? 'active' : 'disabled'}
										label={linkedUser.enabled ? 'Active' : 'Disabled'}
									/>
								</button>
							{/each}
						</div>
					</Card.Content>
				</Card.Root>
			{/if}

			<!-- Actions Card -->
			<Card.Root class="border-cr-border bg-cr-surface lg:col-span-2" data-actions>
				<Card.Header>
					<Card.Title class="text-cr-text">Actions</Card.Title>
					<Card.Description class="text-cr-text-muted">
						Manage this user account.
					</Card.Description>
				</Card.Header>
				<Card.Content>
					<div class="flex flex-wrap items-center gap-3">
						<!-- Enable Button (visible when disabled) -->
						{#if supportsEnableDisable && !data.user.enabled}
							<Button
								onclick={handleEnable}
								disabled={enabling || disabling || deleting}
								class="bg-emerald-500 hover:bg-emerald-600 text-white"
								data-action-enable
							>
								{#if enabling}
									<span
										class="size-4 animate-spin rounded-full border-2 border-current border-t-transparent"
									></span>
								{:else}
									<Power class="size-4" />
								{/if}
								Enable User
							</Button>
						{/if}

						<!-- Disable Button (visible when enabled) -->
						{#if supportsEnableDisable && data.user.enabled}
							<Button
								onclick={handleDisable}
								disabled={enabling || disabling || deleting}
								class="bg-amber-500 hover:bg-amber-600 text-white"
								data-action-disable
							>
								{#if disabling}
									<span
										class="size-4 animate-spin rounded-full border-2 border-current border-t-transparent"
									></span>
								{:else}
									<PowerOff class="size-4" />
								{/if}
								Disable User
							</Button>
						{/if}

						<!-- Delete Button -->
						<Button
							variant="outline"
							onclick={() => (showDeleteDialog = true)}
							disabled={enabling || disabling || deleting}
							class="border-rose-500/50 text-rose-400 hover:bg-rose-500/10 hover:border-rose-500"
							data-action-delete
						>
							<Trash2 class="size-4" />
							Delete User
						</Button>
					</div>
				</Card.Content>
			</Card.Root>
		</div>
	{/if}
</div>

<!-- Stepped Delete Dialog -->
<SteppedDeleteDialog
	bind:open={showDeleteDialog}
	userType={data.user?.external_user_type as 'friend' | 'shared' | 'home' | null | undefined}
	onRemoveShares={handleRemoveShares}
	onDelete={handleDelete}
	onCancel={() => (showDeleteDialog = false)}
/>
