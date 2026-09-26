<script lang="ts">
/**
 * Sync results dialog component.
 *
 * Displays the results of a server sync operation including:
 * - Imported users (orphaned users imported from server)
 * - Stale users (local but not on server)
 * - Matched users count
 *
 * @module $lib/components/servers/sync-results-dialog
 */

import { AlertTriangle, CheckCircle, UserMinus, UserPlus, Users } from '@lucide/svelte';
import type { SyncResult } from '$lib/api/client';
import { Button } from '$lib/components/ui/button';
import * as Dialog from '$lib/components/ui/dialog';

interface Props {
	open: boolean;
	result: SyncResult | null;
	onClose: () => void;
}

let { open = $bindable(), result, onClose }: Props = $props();

/**
 * Check if there are any discrepancies (only stale users count as discrepancies).
 */
const hasDiscrepancies = $derived.by(() => {
	if (!result) return false;
	return result.stale_users.length > 0;
});

/**
 * Format the sync timestamp.
 */
const syncedAtFormatted = $derived.by(() => {
	if (!result?.synced_at) return '';
	try {
		const date = new Date(result.synced_at);
		return date.toLocaleString('en-US', {
			month: 'short',
			day: 'numeric',
			year: 'numeric',
			hour: '2-digit',
			minute: '2-digit'
		});
	} catch {
		return result.synced_at;
	}
});
</script>

<Dialog.Root bind:open>
	<Dialog.Content class="border-cr-border bg-cr-surface sm:max-w-lg">
		<Dialog.Header>
			<Dialog.Title class="text-cr-text flex items-center gap-2">
				{#if hasDiscrepancies}
					<AlertTriangle class="size-5 text-amber-400" />
					Sync Results - Discrepancies Found
				{:else}
					<CheckCircle class="size-5 text-emerald-400" />
					Sync Results - All Matched
				{/if}
			</Dialog.Title>
			<Dialog.Description class="text-cr-text-muted">
				{#if result}
					Sync completed for {result.server_name} at {syncedAtFormatted}
				{/if}
			</Dialog.Description>
		</Dialog.Header>

		{#if result}
			<div class="space-y-4 py-4">
				<!-- Matched Users -->
				<div
					class="flex items-center gap-3 rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3"
					data-sync-matched
				>
					<div class="rounded-full bg-emerald-500/15 p-2">
						<Users class="size-4 text-emerald-400" />
					</div>
					<div class="flex-1">
						<div class="font-medium text-cr-text">Matched Users</div>
						<div class="text-sm text-cr-text-muted">
							Users found on both server and local database
						</div>
					</div>
					<div class="text-2xl font-bold text-emerald-400" data-field="matched_users">
						{result.matched_users}
					</div>
				</div>

				<!-- Imported Users -->
				<div
					class="flex items-start gap-3 rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3"
					data-sync-orphaned
				>
					<div class="rounded-full bg-emerald-500/15 p-2">
						<UserPlus class="size-4 text-emerald-400" />
					</div>
					<div class="flex-1">
						<div class="font-medium text-cr-text">Imported Users</div>
						<div class="text-sm text-cr-text-muted">
							Users imported from server into local database
						</div>
						{#if result.orphaned_users.length > 0}
							<div class="mt-2 space-y-1" data-field="orphaned_users">
								{#each result.orphaned_users as username, index (index)}
									<div
										class="inline-flex items-center rounded bg-emerald-500/10 px-2 py-0.5 text-xs font-mono text-emerald-400 mr-1"
									>
										{username}
									</div>
								{/each}
							</div>
						{/if}
					</div>
					<div class="text-2xl font-bold text-emerald-400">
						{result.orphaned_users.length}
					</div>
				</div>

				<!-- Stale Users -->
				<div
					class="flex items-start gap-3 rounded-lg border border-rose-500/30 bg-rose-500/5 p-3"
					data-sync-stale
				>
					<div class="rounded-full bg-rose-500/15 p-2">
						<UserMinus class="size-4 text-rose-400" />
					</div>
					<div class="flex-1">
						<div class="font-medium text-cr-text">Stale Users</div>
						<div class="text-sm text-cr-text-muted">Users in local database but not on server</div>
						{#if result.stale_users.length > 0}
							<div class="mt-2 space-y-1" data-field="stale_users">
								{#each result.stale_users as username, index (index)}
									<div
										class="inline-flex items-center rounded bg-rose-500/10 px-2 py-0.5 text-xs font-mono text-rose-400 mr-1"
									>
										{username}
									</div>
								{/each}
							</div>
						{/if}
					</div>
					<div class="text-2xl font-bold text-rose-400">
						{result.stale_users.length}
					</div>
				</div>
			</div>
		{/if}

		<Dialog.Footer>
			<Button onclick={onClose} class="bg-cr-accent text-cr-bg hover:bg-cr-accent-hover">
				Close
			</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
