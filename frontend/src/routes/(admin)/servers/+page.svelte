<script lang="ts">
/**
 * Server list page.
 *
 * Displays all media servers as cards with:
 * - Loading skeleton state during data fetch
 * - Error state with retry functionality
 * - Empty state when no servers exist
 * - Card view with server details
 *
 * @module routes/(admin)/servers/+page
 */

import { goto, invalidateAll } from '$app/navigation';
import { getErrorMessage, isNetworkError } from '$lib/api/errors';
import EmptyState from '$lib/components/empty-state.svelte';
import ErrorState from '$lib/components/error-state.svelte';
import CreateServerDialog from '$lib/components/servers/create-server-dialog.svelte';
import ServerCard from '$lib/components/servers/server-card.svelte';
import ServerListSkeleton from '$lib/components/servers/server-list-skeleton.svelte';
import type { PageData } from './$types';

const { data }: { data: PageData } = $props();

// Loading state for refresh operations
let isRefreshing = $state(false);

/**
 * Handle retry after error.
 */
async function handleRetry() {
	isRefreshing = true;
	try {
		await invalidateAll();
	} finally {
		isRefreshing = false;
	}
}

/**
 * Navigate to server detail page.
 */
function handleViewDetails(serverId: string) {
	goto(`/servers/${serverId}`);
}
</script>

<div class="space-y-6">
	<!-- Header with description -->
	<div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
		<p class="text-cr-text-muted">View and manage connected media servers.</p>
		<CreateServerDialog onSuccess={handleRetry} />
	</div>

	<!-- Content area with loading/error/empty/data states -->
	{#if isRefreshing}
		<ServerListSkeleton />
	{:else if data.error}
		<ErrorState
			message={getErrorMessage(data.error)}
			title={isNetworkError(data.error) ? 'Connection Error' : 'Failed to load servers'}
			onRetry={handleRetry}
		/>
	{:else if !data.servers || data.servers.length === 0}
		<EmptyState
			title="No servers configured"
			description="Media servers will appear here once they are configured in the backend."
		/>
	{:else}
		<!-- Server cards grid -->
		<div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
			{#each data.servers as server (server.id)}
				<ServerCard {server} onViewDetails={handleViewDetails} />
			{/each}
		</div>
	{/if}
</div>
