<script lang="ts">
/**
 * Library sync results dialog.
 *
 * Displays manual library sync summary metrics:
 * - Total libraries after sync
 * - Added, updated, and removed counts
 */

import { BookCopy, CheckCircle, PlusCircle, RefreshCw, Trash2 } from '@lucide/svelte';
import type { LibrarySyncResult } from '$lib/api/client';
import { Button } from '$lib/components/ui/button';
import * as Dialog from '$lib/components/ui/dialog';

interface Props {
	open: boolean;
	result: LibrarySyncResult | null;
	onClose: () => void;
}

let { open = $bindable(), result, onClose }: Props = $props();

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
				<CheckCircle class="size-5 text-emerald-400" />
				Library Sync Complete
			</Dialog.Title>
			<Dialog.Description class="text-cr-text-muted">
				{#if result}
					{result.server_name}
					updated at {syncedAtFormatted}
				{/if}
			</Dialog.Description>
		</Dialog.Header>

		{#if result}
			<div class="grid gap-3 py-4 sm:grid-cols-2">
				<div class="rounded-lg border border-cr-border bg-cr-bg p-3" data-library-sync-total>
					<div class="flex items-center gap-2 text-cr-text-muted text-sm">
						<BookCopy class="size-4 text-cr-accent" />
						Total Libraries
					</div>
					<div class="mt-2 text-2xl font-semibold text-cr-text">{result.total_libraries}</div>
				</div>

				<div
					class="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3"
					data-library-sync-added
				>
					<div class="flex items-center gap-2 text-emerald-300 text-sm">
						<PlusCircle class="size-4" />
						Added
					</div>
					<div class="mt-2 text-2xl font-semibold text-emerald-400">{result.added_count}</div>
				</div>

				<div
					class="rounded-lg border border-blue-500/30 bg-blue-500/5 p-3"
					data-library-sync-updated
				>
					<div class="flex items-center gap-2 text-blue-300 text-sm">
						<RefreshCw class="size-4" />
						Updated
					</div>
					<div class="mt-2 text-2xl font-semibold text-blue-400">{result.updated_count}</div>
				</div>

				<div
					class="rounded-lg border border-rose-500/30 bg-rose-500/5 p-3"
					data-library-sync-removed
				>
					<div class="flex items-center gap-2 text-rose-300 text-sm">
						<Trash2 class="size-4" />
						Removed
					</div>
					<div class="mt-2 text-2xl font-semibold text-rose-400">{result.removed_count}</div>
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
