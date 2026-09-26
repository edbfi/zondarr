<script lang="ts">
/**
 * Invitation table row component.
 *
 * Displays a single invitation with:
 * - Code in monospace font
 * - Status badge based on is_active and enabled
 * - Use count with remaining uses if applicable
 * - Expiration date formatted
 * - Created date formatted
 * - Action menu
 *
 * @module $lib/components/invitations/invitation-row
 */

import { Check, Copy, Eye, MoreHorizontal, Pencil, Trash2 } from '@lucide/svelte';
import { onDestroy } from 'svelte';
import { goto } from '$app/navigation';
import type { InvitationResponse } from '$lib/api/client';
import StatusBadge, { type StatusBadgeStatus } from '$lib/components/status-badge.svelte';
import { Button } from '$lib/components/ui/button';
import * as Table from '$lib/components/ui/table';
import { showError, showSuccess } from '$lib/utils/toast';

interface Props {
	invitation: InvitationResponse;
	onEdit?: (id: string) => void;
	onDelete?: (id: string) => void;
}

const { invitation, onEdit, onDelete }: Props = $props();

/**
 * True when the invitation has a max_uses cap that's been fully consumed.
 * "Used up" beats the generic "Expired" so admins can tell why redemption
 * is blocked.
 */
const isUsedUp = $derived(
	invitation.max_uses != null && invitation.remaining_uses != null && invitation.remaining_uses <= 0
);

/**
 * Derive the status for the badge based on invitation state.
 * "Used up" is distinguished from the generic inactive state so admins can
 * see the specific reason redemption is blocked. Date-expiry is delegated to
 * the server via `is_active` to avoid client-clock-skew false positives.
 */
const status = $derived.by((): StatusBadgeStatus => {
	if (!invitation.enabled) return 'disabled';
	if (isUsedUp) return 'expired';
	if (!invitation.is_active) return 'expired';
	if (
		invitation.remaining_uses !== null &&
		invitation.remaining_uses !== undefined &&
		invitation.remaining_uses <= 3
	) {
		return 'limited';
	}
	return 'active';
});

/**
 * Derive the status label.
 */
const statusLabel = $derived.by(() => {
	if (!invitation.enabled) return 'Disabled';
	if (isUsedUp) return 'Used up';
	if (!invitation.is_active) return 'Expired';
	if (
		invitation.remaining_uses !== null &&
		invitation.remaining_uses !== undefined &&
		invitation.remaining_uses <= 3
	) {
		return 'Limited';
	}
	return 'Active';
});

/**
 * Format use count display.
 */
const useCountDisplay = $derived.by(() => {
	if (invitation.max_uses !== null && invitation.max_uses !== undefined) {
		return `${invitation.use_count} / ${invitation.max_uses}`;
	}
	return `${invitation.use_count}`;
});

/**
 * Format remaining uses display.
 */
const remainingDisplay = $derived.by(() => {
	if (invitation.remaining_uses !== null && invitation.remaining_uses !== undefined) {
		return `(${invitation.remaining_uses} left)`;
	}
	return '';
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
	if (!invitation.expires_at) return 'Never';
	const date = new Date(invitation.expires_at);
	const now = new Date();
	const isExpired = date < now;
	const formatted = formatDate(invitation.expires_at);
	return isExpired ? `${formatted} (expired)` : formatted;
});

/**
 * Navigate to invitation detail page.
 */
function viewInvitation() {
	goto(`/invitations/${invitation.id}`);
}

/**
 * Handle edit action.
 */
function handleEdit() {
	if (onEdit) {
		onEdit(invitation.id);
	} else {
		goto(`/invitations/${invitation.id}`);
	}
}

let copied = $state(false);
let copiedTimeoutId: ReturnType<typeof setTimeout> | null = null;

onDestroy(() => {
	if (copiedTimeoutId) clearTimeout(copiedTimeoutId);
});

/**
 * Copy the invite link to clipboard.
 */
async function copyInviteLink() {
	const url = `${window.location.origin}/join/${invitation.code}`;
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

/**
 * Handle delete action.
 */
function handleDelete() {
	if (onDelete) {
		onDelete(invitation.id);
	}
}
</script>

<Table.Row
	class="border-cr-border hover:bg-cr-border/30 cursor-pointer"
	data-invitation-row
	data-invitation-id={invitation.id}
	onclick={viewInvitation}
>
	<!-- Code (monospace) -->
	<Table.Cell>
		<code
			class="font-mono text-sm text-cr-accent bg-cr-accent/10 px-2 py-0.5 rounded"
			data-invitation-code
		>
			{invitation.code}
		</code>
	</Table.Cell>

	<!-- Status -->
	<Table.Cell>
		<StatusBadge {status} label={statusLabel} />
	</Table.Cell>

	<!-- Uses -->
	<Table.Cell>
		<span class="font-data text-cr-text" data-invitation-uses>
			{useCountDisplay}
		</span>
		{#if remainingDisplay}
			<span class="text-xs text-cr-text-muted ml-1" data-invitation-remaining>
				{remainingDisplay}
			</span>
		{/if}
	</Table.Cell>

	<!-- Expires -->
	<Table.Cell class="hidden sm:table-cell">
		<span class="font-data text-sm text-cr-text-muted" data-invitation-expires>
			{expiresDisplay}
		</span>
	</Table.Cell>

	<!-- Created -->
	<Table.Cell class="hidden md:table-cell">
		<span class="font-data text-sm text-cr-text-muted" data-invitation-created>
			{formatDate(invitation.created_at)}
		</span>
	</Table.Cell>

	<!-- Actions -->
	<Table.Cell class="text-right">
		<div class="flex items-center justify-end gap-1" role="toolbar" aria-label="Invitation actions">
			<Button
				variant="ghost"
				size="icon-sm"
				onclick={(e: MouseEvent) => {
	e.stopPropagation();
	copyInviteLink();
}}
				aria-label="Copy invite link"
				class="text-cr-text-muted hover:text-cr-accent hover:bg-cr-accent/10"
			>
				{#if copied}
					<Check class="size-4" />
				{:else}
					<Copy class="size-4" />
				{/if}
			</Button>
			<Button
				variant="ghost"
				size="icon-sm"
				onclick={(e: MouseEvent) => {
	e.stopPropagation();
	viewInvitation();
}}
				aria-label="View invitation"
				class="text-cr-text-muted hover:text-cr-accent hover:bg-cr-accent/10"
			>
				<Eye class="size-4" />
			</Button>
			<Button
				variant="ghost"
				size="icon-sm"
				onclick={(e: MouseEvent) => {
	e.stopPropagation();
	handleEdit();
}}
				aria-label="Edit invitation"
				class="text-cr-text-muted hover:text-cr-accent hover:bg-cr-accent/10"
			>
				<Pencil class="size-4" />
			</Button>
			<Button
				variant="ghost"
				size="icon-sm"
				onclick={(e: MouseEvent) => {
	e.stopPropagation();
	handleDelete();
}}
				aria-label="Delete invitation"
				class="text-cr-text-muted hover:text-rose-400 hover:bg-rose-400/10"
			>
				<Trash2 class="size-4" />
			</Button>
		</div>
	</Table.Cell>
</Table.Row>
