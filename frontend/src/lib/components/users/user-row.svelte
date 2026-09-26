<script lang="ts">
/**
 * User table row component.
 *
 * Displays a single user with:
 * - Username
 * - Media server name and type
 * - Status badge based on enabled and expires_at
 * - Expiration date formatted
 * - Created date formatted
 * - Source invitation code (if available)
 * - Action menu
 *
 * @module $lib/components/users/user-row
 */

import { Eye, MoreHorizontal, Power, PowerOff, Trash2 } from '@lucide/svelte';
import { goto } from '$app/navigation';
import type { UserDetailResponse } from '$lib/api/client';
import StatusBadge, { type StatusBadgeStatus } from '$lib/components/status-badge.svelte';
import { Button } from '$lib/components/ui/button';
import * as Table from '$lib/components/ui/table';
import { getProviderBadgeStyle, hasProviderCapability } from '$lib/stores/providers.svelte';

interface Props {
	user: UserDetailResponse;
	onEnable?: (id: string) => void;
	onDisable?: (id: string) => void;
	onDelete?: (id: string) => void;
}

const { user, onEnable, onDisable, onDelete }: Props = $props();

/**
 * Check if user is expired based on expires_at.
 */
const isExpired = $derived.by(() => {
	if (!user.expires_at) return false;
	return new Date(user.expires_at) < new Date();
});

/**
 * Check if user is expiring soon (within 7 days).
 */
const isExpiringSoon = $derived.by(() => {
	if (!user.expires_at) return false;
	const expiresAt = new Date(user.expires_at);
	const now = new Date();
	const sevenDaysFromNow = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
	return expiresAt > now && expiresAt <= sevenDaysFromNow;
});

/**
 * Derive the status for the badge based on user state.
 */
const status = $derived.by((): StatusBadgeStatus => {
	if (!user.enabled) return 'disabled';
	if (isExpired) return 'expired';
	if (isExpiringSoon) return 'pending';
	return 'active';
});

/**
 * Derive the status label.
 */
const statusLabel = $derived.by(() => {
	if (!user.enabled) return 'Disabled';
	if (isExpired) return 'Expired';
	if (isExpiringSoon) return 'Expiring Soon';
	return 'Active';
});

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
			year: 'numeric'
		});
	} catch {
		return '—';
	}
}

/**
 * Format expiration date with relative indicator.
 */
const expiresDisplay = $derived.by(() => {
	if (!user.expires_at) return 'Never';
	const formatted = formatDate(user.expires_at);
	if (isExpired) return `${formatted} (expired)`;
	if (isExpiringSoon) return `${formatted} (soon)`;
	return formatted;
});

const badgeStyle = $derived(getProviderBadgeStyle(user.media_server.server_type));
const userEmail = $derived(user.email ?? user.identity.email);
const supportsEnableDisable = $derived(
	hasProviderCapability(user.media_server.server_type, 'enable_disable_user')
);

/**
 * Navigate to user detail page.
 */
function viewUser() {
	goto(`/users/${user.id}`);
}

/**
 * Handle enable action.
 */
function handleEnable() {
	if (onEnable) {
		onEnable(user.id);
	}
}

/**
 * Handle disable action.
 */
function handleDisable() {
	if (onDisable) {
		onDisable(user.id);
	}
}

/**
 * Handle delete action.
 */
function handleDelete() {
	if (onDelete) {
		onDelete(user.id);
	}
}
</script>

<Table.Row
	class="border-cr-border hover:bg-cr-border/30 cursor-pointer"
	data-user-row
	data-user-id={user.id}
	onclick={viewUser}
>
	<!-- Username -->
	<Table.Cell>
		<div class="min-w-0">
			<span class="block truncate font-medium text-cr-text" data-user-username>
				{user.username}
			</span>
			{#if userEmail}
				<span class="block truncate text-xs text-cr-text-muted" data-user-email>
					{userEmail}
				</span>
			{/if}
		</div>
	</Table.Cell>

	<!-- Server -->
	<Table.Cell>
		<div class="flex items-center gap-2">
			<span
				class="inline-flex items-center rounded border px-1.5 py-0.5 text-xs font-medium"
				style={badgeStyle}
			>
				{user.media_server.server_type}
			</span>
			{#if user.external_user_type === 'friend'}
				<span
					class="inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium bg-indigo-500/15 text-indigo-400 border border-indigo-500/30"
				>
					Friend
				</span>
			{:else if user.external_user_type === 'shared'}
				<span
					class="inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium bg-purple-500/15 text-purple-400 border border-purple-500/30"
				>
					Shared
				</span>
			{:else if user.external_user_type === 'home'}
				<span
					class="inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium bg-teal-500/15 text-teal-400 border border-teal-500/30"
				>
					Home
				</span>
			{/if}
			<span class="text-sm text-cr-text-muted" data-user-server>
				{user.media_server.name}
			</span>
		</div>
	</Table.Cell>

	<!-- Status -->
	<Table.Cell>
		<StatusBadge {status} label={statusLabel} />
	</Table.Cell>

	<!-- Expires -->
	<Table.Cell class="hidden sm:table-cell">
		<span class="font-data text-sm text-cr-text-muted" data-user-expires>
			{expiresDisplay}
		</span>
	</Table.Cell>

	<!-- Created -->
	<Table.Cell class="hidden md:table-cell">
		<span class="font-data text-sm text-cr-text-muted" data-user-created>
			{formatDate(user.created_at)}
		</span>
	</Table.Cell>

	<!-- Invitation -->
	<Table.Cell class="hidden lg:table-cell">
		{#if user.invitation}
			<code
				class="font-mono text-xs text-cr-accent bg-cr-accent/10 px-1.5 py-0.5 rounded"
				data-user-invitation
			>
				{user.invitation.code}
			</code>
		{:else}
			<span class="text-sm text-cr-text-muted">—</span>
		{/if}
	</Table.Cell>

	<!-- Actions -->
	<Table.Cell class="text-right">
		<div class="flex items-center justify-end gap-1" role="toolbar" aria-label="User actions">
			<Button
				variant="ghost"
				size="icon-sm"
				onclick={(e: MouseEvent) => {
	e.stopPropagation();
	viewUser();
}}
				aria-label="View user"
				class="text-cr-text-muted hover:text-cr-accent hover:bg-cr-accent/10"
			>
				<Eye class="size-4" />
			</Button>
			{#if supportsEnableDisable && user.enabled}
				<Button
					variant="ghost"
					size="icon-sm"
					onclick={(e: MouseEvent) => {
	e.stopPropagation();
	handleDisable();
}}
					aria-label="Disable user"
					class="text-cr-text-muted hover:text-amber-400 hover:bg-amber-400/10"
				>
					<PowerOff class="size-4" />
				</Button>
			{:else if supportsEnableDisable}
				<Button
					variant="ghost"
					size="icon-sm"
					onclick={(e: MouseEvent) => {
	e.stopPropagation();
	handleEnable();
}}
					aria-label="Enable user"
					class="text-cr-text-muted hover:text-emerald-400 hover:bg-emerald-400/10"
				>
					<Power class="size-4" />
				</Button>
			{/if}
			<Button
				variant="ghost"
				size="icon-sm"
				onclick={(e: MouseEvent) => {
	e.stopPropagation();
	handleDelete();
}}
				aria-label="Delete user"
				class="text-cr-text-muted hover:text-rose-400 hover:bg-rose-400/10"
			>
				<Trash2 class="size-4" />
			</Button>
		</div>
	</Table.Cell>
</Table.Row>
